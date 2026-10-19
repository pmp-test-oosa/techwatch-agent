"""Step 6 - DIGEST via the LLM. The model may only reference kept items by their id."""
from __future__ import annotations

import logging

from .llm.base import Provider

log = logging.getLogger("techwatch.digest")


def write(kept: list[dict], profile: dict, provider: Provider) -> dict:
    if not kept:
        log.info("no items kept, writing quiet-week digest without LLM")
        return {
            "headline": "Quiet week: nothing crossed the relevance threshold",
            "summary": [{"text": "No collected item scored 7 or higher for this client this week.",
                         "item_ids": []}],
            "actions": [],
            "top_signal": None,
        }
    digest = provider.write_digest(kept, profile)
    log.info("digest headline=%r bullets=%d actions=%d top=%s", digest["headline"],
             len(digest["summary"]), len(digest["actions"]), digest["top_signal"])
    return digest
