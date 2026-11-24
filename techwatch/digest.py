"""Step 6 - DIGEST via the LLM. The model may only reference kept items by their id."""
from __future__ import annotations

import logging

from .config import ACTIONS_MAX, SUMMARY_MAX_BULLETS
from .llm.base import Provider

log = logging.getLogger("techwatch.digest")
MAX_REFS_PER_ENTRY = 4


def write(kept: list[dict], profile: dict, provider: Provider) -> dict:
    if not kept:
        log.info("no items kept, writing quiet-week digest without LLM")
        return {
            "headline": "Quiet week: nothing crossed the relevance threshold",
            "summary": [{"text": "No collected item scored 7 or higher for this profile this week.",
                         "item_ids": []}],
            "actions": [],
            "top_signal": None,
        }
    digest = provider.write_digest(kept, profile)
    log.info("digest headline=%r bullets=%d actions=%d top=%s", digest["headline"],
             len(digest["summary"]), len(digest["actions"]), digest["top_signal"])
    return digest


def trim(digest: dict) -> tuple[dict, list[str]]:
    """Code enforces the list limits: overlong lists are cut (first entries win) and logged."""
    notes: list[str] = []
    out = dict(digest)
    for part, limit in (("summary", SUMMARY_MAX_BULLETS), ("actions", ACTIONS_MAX)):
        entries = list(out.get(part) or [])
        if len(entries) > limit:
            notes.append(f"{part}: {len(entries)} entries trimmed to {limit}")
            entries = entries[:limit]
        fixed = []
        for i, entry in enumerate(entries):
            refs = list(entry.get("item_ids") or [])
            if len(refs) > MAX_REFS_PER_ENTRY:
                notes.append(f"{part}[{i}].item_ids: {len(refs)} trimmed to {MAX_REFS_PER_ENTRY}")
                refs = refs[:MAX_REFS_PER_ENTRY]
            fixed.append({**entry, "item_ids": refs})
        out[part] = fixed
    for n in notes:
        log.warning("trimmed: %s", n)
    return out, notes
