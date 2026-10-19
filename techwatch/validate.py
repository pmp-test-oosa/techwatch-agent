"""Step 7 - VALIDATE. Any violation fails the run and nothing is published."""
from __future__ import annotations

import logging
from datetime import date

from .config import (ACTIONS_MAX, HEADLINE_MAX_WORDS, MAX_KEPT, MAX_PER_NEWS_TYPE, MIN_RELEVANCE,
                     NEWS_TYPES, SIGNALS, SUMMARY_MAX_BULLETS)
from .windows import Window

log = logging.getLogger("techwatch.validate")


class ValidationError(Exception):
    def __init__(self, violations: list[str]):
        super().__init__(f"{len(violations)} violation(s): " + "; ".join(violations[:10]))
        self.violations = violations


def validate(digest: dict, items: list[dict], window: Window, collected: dict[str, str],
             field_ids: list[str], publish_to_site: bool) -> None:
    """`collected` maps item id -> url for every item the collectors returned this run."""
    v: list[str] = []
    ids = [it["id"] for it in items]
    idset = set(ids)
    if len(ids) != len(idset):
        v.append("duplicate item ids")
    if len(items) > MAX_KEPT:
        v.append(f"{len(items)} items > max {MAX_KEPT}")
    per_type: dict[str, int] = {}
    for it in items:
        iid = it["id"]
        if iid not in collected:
            v.append(f"{iid}: id was not produced by a collector")
        elif collected[iid] != it["url"]:
            v.append(f"{iid}: url does not match the collected url")
        try:
            d = date.fromisoformat(it["date"])
            if not window.contains(d):
                v.append(f"{iid}: date {it['date']} outside window {window.start}..{window.end}")
        except (TypeError, ValueError):
            v.append(f"{iid}: invalid date {it.get('date')!r}")
        if not str(it.get("url", "")).startswith("https://") and not str(it.get("url", "")).startswith("http://"):
            v.append(f"{iid}: url is not http(s)")
        if it.get("relevance") is None or it["relevance"] < MIN_RELEVANCE:
            v.append(f"{iid}: relevance below {MIN_RELEVANCE}")
        if it.get("signal") not in SIGNALS:
            v.append(f"{iid}: invalid signal {it.get('signal')!r}")
        if it.get("news_type") not in NEWS_TYPES:
            v.append(f"{iid}: invalid news_type {it.get('news_type')!r}")
        if it.get("watch_field") not in field_ids:
            v.append(f"{iid}: unknown watch_field {it.get('watch_field')!r}")
        if not it.get("reason"):
            v.append(f"{iid}: missing reason")
        if publish_to_site and it.get("source") == "fixture":
            v.append(f"{iid}: fixture item must never be published to site/data")
        per_type[it.get("news_type")] = per_type.get(it.get("news_type"), 0) + 1
    for t, n in per_type.items():
        if n > MAX_PER_NEWS_TYPE:
            v.append(f"news type {t}: {n} items > max {MAX_PER_NEWS_TYPE}")

    headline = digest.get("headline") or ""
    if not headline.strip():
        v.append("empty headline")
    if len(headline.split()) > HEADLINE_MAX_WORDS:
        v.append(f"headline has {len(headline.split())} words > {HEADLINE_MAX_WORDS}")
    if len(digest.get("summary", [])) > SUMMARY_MAX_BULLETS:
        v.append("too many summary bullets")
    if len(digest.get("actions", [])) > ACTIONS_MAX:
        v.append("too many actions")
    for part in ("summary", "actions"):
        for entry in digest.get(part, []):
            for ref in entry.get("item_ids", []):
                if ref not in idset:
                    v.append(f"{part} references unknown id {ref}")
    top = digest.get("top_signal")
    if items and top not in idset:
        v.append(f"top_signal {top!r} is not a kept item")
    if not items and top is not None:
        v.append("top_signal set although no items were kept")

    if v:
        for msg in v:
            log.error("violation: %s", msg)
        raise ValidationError(v)
    log.info("validation passed: items=%d references ok, links ok, dates inside %s..%s",
             len(items), window.start, window.end)
