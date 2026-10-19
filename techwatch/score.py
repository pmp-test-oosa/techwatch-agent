"""Step 4 - SCORE via the LLM, in batches. Code picks which items get scored (cap) and merges results."""
from __future__ import annotations

import logging

from .config import BATCH_SIZE, MAX_SCORED_ITEMS
from .llm.base import Provider
from .profile import field_keywords

log = logging.getLogger("techwatch.score")


def keyword_hits(item: dict, field: dict, competitors: list[str]) -> int:
    text = f"{item['title']} {item['snippet']}".lower()
    hits = sum(1 for k in field_keywords(field) if k in text)
    hits += sum(2 for c in competitors if c.lower() in text)
    return hits


def preselect(items: list[dict], profile: dict, cap: int) -> list[dict]:
    """Deterministic cap: rank each watch field by keyword hits and recency, then round-robin."""
    if len(items) <= cap:
        return items
    fields = {f["id"]: f for f in profile["watch_fields"]}
    queues = []
    for fid, field in fields.items():
        q = [it for it in items if it["watch_field"] == fid]
        q.sort(key=lambda it: (-keyword_hits(it, field, profile["competitors"]), _neg_date(it["date"]), it["id"]))
        queues.append(q)
    picked: list[dict] = []
    while len(picked) < cap and any(queues):
        for q in queues:
            if q and len(picked) < cap:
                picked.append(q.pop(0))
    return picked


def _neg_date(iso: str) -> int:
    return -int(iso.replace("-", ""))


def score(items: list[dict], profile: dict, provider: Provider, max_batches: int) -> tuple[list[dict], dict]:
    cap = min(MAX_SCORED_ITEMS, max_batches * BATCH_SIZE)
    selected = preselect(items, profile, cap)
    log.info("to_score=%d of %d (cap=%d, batches<=%d)", len(selected), len(items), cap, max_batches)
    scored: list[dict] = []
    for start in range(0, len(selected), BATCH_SIZE):
        batch = selected[start:start + BATCH_SIZE]
        results = {r["id"]: r for r in provider.score_batch(batch, profile)}
        for it in batch:
            r = results[it["id"]]
            merged = dict(it)
            merged["relevance"] = int(r["relevance"])
            merged["signal"] = r["signal"]
            merged["reason"] = r["reason"].strip()
            merged["story"] = r["story"].strip()
            if not merged["news_type"]:          # source-set types (arXiv = research) win
                merged["news_type"] = r["news_type"]
            scored.append(merged)
        log.info("batch %d: scored=%d", start // BATCH_SIZE + 1, len(batch))
    return scored, {"candidates": len(items), "scored": len(scored), "capped": len(items) - len(selected)}
