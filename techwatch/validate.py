"""Step 7 - VALIDATE the complete digest document. Any violation fails the run; nothing is published.

Two layers: a strict JSON schema with every limit (lengths, counts, enums, formats), and the
checks a schema cannot express (ids, link provenance, date window, per-type cap, fixtures).
"""
from __future__ import annotations

import logging
from datetime import date

import jsonschema

from .config import (ACTIONS_MAX, HEADLINE_MAX_WORDS, MAX_KEPT, MAX_PER_NEWS_TYPE, MIN_RELEVANCE,
                     NEWS_TYPES, QUIET_WEEK_THRESHOLD, SIGNALS, SUMMARY_MAX_BULLETS)
from .windows import Window

log = logging.getLogger("techwatch.validate")

ISO_DAY = r"^\d{4}-\d{2}-\d{2}$"
_REF = {
    "type": "object",
    "required": ["text", "item_ids"],
    "additionalProperties": False,
    "properties": {
        "text": {"type": "string", "minLength": 5, "maxLength": 400},
        "item_ids": {"type": "array", "maxItems": 4, "items": {"type": "string"}},
    },
}


def published_schema(field_ids: list[str]) -> dict:
    item = {
        "type": "object",
        "required": ["id", "source", "title", "url", "date", "snippet", "watch_field", "news_type",
                     "signal", "relevance", "reason", "publisher"],
        "additionalProperties": False,
        "properties": {
            "id": {"type": "string", "pattern": r"^[a-z]{2}-[0-9a-f]{10}$"},
            "source": {"type": "string", "minLength": 1},
            "title": {"type": "string", "minLength": 1, "maxLength": 300},
            "url": {"type": "string", "pattern": r"^https?://\S+$", "maxLength": 2000},
            "date": {"type": "string", "pattern": ISO_DAY},
            "snippet": {"type": "string", "maxLength": 600},
            "watch_field": {"enum": field_ids},
            "news_type": {"enum": list(NEWS_TYPES)},
            "signal": {"enum": list(SIGNALS)},
            "relevance": {"type": "integer", "minimum": MIN_RELEVANCE, "maximum": 10},
            "reason": {"type": "string", "minLength": 10, "maxLength": 300},
            "publisher": {"type": "string", "maxLength": 80},
            "story": {"type": ["string", "null"], "maxLength": 80},
            "also_reported_by": {"type": ["array", "null"], "items": {"type": "string"}},
        },
    }
    return {
        "type": "object",
        "required": ["schema_version", "profile", "week", "window", "generated_at", "headline", "summary",
                     "actions", "top_signal", "stats", "items", "backfilled", "quiet_week"],
        "properties": {
            "week": {"type": "string", "pattern": r"^\d{4}-W\d{2}$"},
            "window": {"type": "object", "required": ["start", "end"],
                       "properties": {"start": {"type": "string", "pattern": ISO_DAY},
                                      "end": {"type": "string", "pattern": ISO_DAY}}},
            "headline": {"type": "string", "minLength": 5, "maxLength": 110},
            "summary": {"type": "array", "minItems": 1, "maxItems": SUMMARY_MAX_BULLETS, "items": _REF},
            "actions": {"type": "array", "maxItems": ACTIONS_MAX, "items": _REF},
            "top_signal": {"type": ["string", "null"]},
            "items": {"type": "array", "maxItems": MAX_KEPT, "items": item},
            "backfilled": {"type": "boolean"},
            "quiet_week": {"type": "boolean"},
        },
    }


class ValidationError(Exception):
    def __init__(self, violations: list[str]):
        super().__init__(f"{len(violations)} violation(s): " + "; ".join(violations[:10]))
        self.violations = violations


def validate(doc: dict, window: Window, collected: dict[str, str], field_ids: list[str],
             publish_to_site: bool) -> None:
    """`collected` maps item id -> url for every item the collectors returned this run."""
    v: list[str] = []
    schema_errors = sorted(jsonschema.Draft202012Validator(published_schema(field_ids)).iter_errors(doc),
                           key=lambda e: list(e.absolute_path))
    for err in schema_errors:
        where = "/".join(str(p) for p in err.absolute_path) or "(document)"
        v.append(f"schema: {where}: {err.message[:160]}")

    items = doc.get("items") or []
    ids = [it.get("id") for it in items]
    idset = set(ids)
    if len(ids) != len(idset):
        v.append("duplicate item ids")
    per_type: dict[str, int] = {}
    for it in items:
        iid = it.get("id")
        if iid not in collected:
            v.append(f"{iid}: id was not produced by a collector")
        elif collected[iid] != it.get("url"):
            v.append(f"{iid}: url does not match the collected url")
        try:
            if not window.contains(date.fromisoformat(it.get("date", ""))):
                v.append(f"{iid}: date {it['date']} outside window {window.start}..{window.end}")
        except (TypeError, ValueError):
            v.append(f"{iid}: invalid date {it.get('date')!r}")
        if publish_to_site and it.get("source") == "fixture":
            v.append(f"{iid}: fixture item must never be published to site/data")
        per_type[it.get("news_type")] = per_type.get(it.get("news_type"), 0) + 1
    for t, n in per_type.items():
        if n > MAX_PER_NEWS_TYPE:
            v.append(f"news type {t}: {n} items > max {MAX_PER_NEWS_TYPE}")

    headline = doc.get("headline") or ""
    if len(headline.split()) > HEADLINE_MAX_WORDS:
        v.append(f"headline has {len(headline.split())} words > {HEADLINE_MAX_WORDS}")
    for part in ("summary", "actions"):
        for entry in doc.get(part) or []:
            for ref in entry.get("item_ids", []):
                if ref not in idset:
                    v.append(f"{part} references unknown id {ref}")
    top = doc.get("top_signal")
    if items and top not in idset:
        v.append(f"top_signal {top!r} is not a kept item")
    if not items and top is not None:
        v.append("top_signal set although no items were kept")
    if doc.get("window") != window.as_dict() or doc.get("week") != window.label:
        v.append("week/window of the document does not match the run window")
    if doc.get("quiet_week") != (len(items) < QUIET_WEEK_THRESHOLD):
        v.append("quiet_week flag does not match the item count")

    if v:
        for msg in v:
            log.error("violation: %s", msg)
        raise ValidationError(v)
    log.info("validation passed: schema ok, items=%d, references ok, links from collectors, dates inside %s..%s",
             len(items), window.start, window.end)
