"""JSON schemas for LLM output, plus the semantic checks a schema cannot express."""
from __future__ import annotations

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


def check_scores(result: dict, items: list[dict]) -> list[dict]:
    jsonschema.validate(result, SCORE_SCHEMA)
    want = {it["id"] for it in items}
    got = [s for s in result["scores"] if s["id"] in want]
    got_ids = {s["id"] for s in got}
    missing = want - got_ids
    if missing:
        raise ValueError(f"scores missing for ids {sorted(missing)}")
    return got


def check_digest(result: dict, items: list[dict]) -> dict:
    jsonschema.validate(result, DIGEST_SCHEMA)
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
    return result
