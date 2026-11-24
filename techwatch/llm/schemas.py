"""JSON schemas for LLM output, plus the semantic checks a schema cannot express."""
from __future__ import annotations

import re

import jsonschema

from ..config import ACTIONS_MAX, HEADLINE_MAX_WORDS, NEWS_TYPES, SIGNALS, SUMMARY_MAX_BULLETS

SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "relevance": {"type": "integer", "minimum": 0, "maximum": 10},
                    "signal": {"type": "string", "enum": list(SIGNALS)},
                    "news_type": {"type": "string", "enum": list(NEWS_TYPES)},
                    "reason": {"type": "string", "minLength": 10, "maxLength": 300},
                    "story": {"type": "string", "minLength": 3, "maxLength": 80},
                },
                "required": ["id", "relevance", "signal", "news_type", "reason", "story"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["scores"],
    "additionalProperties": False,
}

_REF_LIST = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "minLength": 5, "maxLength": 400},
            "item_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        },
        "required": ["text", "item_ids"],
        "additionalProperties": False,
    },
}

DIGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "minLength": 5, "maxLength": 110},
        "summary": {**_REF_LIST, "minItems": 1, "maxItems": SUMMARY_MAX_BULLETS},
        "actions": {**_REF_LIST, "minItems": 1, "maxItems": ACTIONS_MAX},
        "top_signal": {"type": "string"},
    },
    "required": ["headline", "summary", "actions", "top_signal"],
    "additionalProperties": False,
}


def _lenient(schema: dict) -> dict:
    """Copy of the schema without list-length limits: code trims overlong lists instead of
    spending an LLM retry on them (see digest.trim)."""
    out = {k: (_lenient(v) if isinstance(v, dict) else v) for k, v in schema.items() if k != "maxItems"}
    return out


DIGEST_SCHEMA_LENIENT = _lenient(DIGEST_SCHEMA)


# German function words that do not occur in normal English text ("die" is left out: die casting).
GERMAN_WORDS = {"und", "der", "das", "für", "werden", "wird", "nicht", "sind", "auf", "bereits", "eine",
                "einen", "einer", "bei", "durch", "sowie", "laut", "dass", "zum", "zur", "vom", "noch", "auch"}


def looks_german(text: str) -> bool:
    words = re.findall(r"\w+", text.lower())
    hits = sum(1 for w in words if w in GERMAN_WORDS)
    return hits >= 3 or (hits >= 2 and hits / max(len(words), 1) > 0.12)


def require_english(texts: list[str], what: str) -> None:
    german = [t for t in texts if looks_german(t)]
    if german:
        raise ValueError(f"{what} must be written in English, also for German items; "
                         f"German text found: {german[0][:80]!r}")


def check_scores(result: dict, items: list[dict]) -> list[dict]:
    jsonschema.validate(result, SCORE_SCHEMA)
    want = {it["id"] for it in items}
    got = [s for s in result["scores"] if s["id"] in want]
    got_ids = {s["id"] for s in got}
    missing = want - got_ids
    if missing:
        raise ValueError(f"scores missing for ids {sorted(missing)}")
    require_english([s["reason"] for s in got], "every reason")
    return got


def check_digest(result: dict, items: list[dict]) -> dict:
    jsonschema.validate(result, DIGEST_SCHEMA_LENIENT)
    ids = {it["id"] for it in items}
    words = len(result["headline"].split())
    if words > HEADLINE_MAX_WORDS:
        raise ValueError(f"headline has {words} words (max {HEADLINE_MAX_WORDS})")
    if result["top_signal"] not in ids:
        raise ValueError(f"top_signal {result['top_signal']!r} is not a kept item id")
    for part in ("summary", "actions"):
        for entry in result[part]:
            unknown = [r for r in entry["item_ids"] if r not in ids]
            if unknown:
                raise ValueError(f"{part} references unknown ids {unknown}")
    require_english([result["headline"]] + [e["text"] for e in result["summary"] + result["actions"]],
                    "the headline, summary and actions")
    return result
