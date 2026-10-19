"""Step 5 - FILTER. Deterministic code decides what gets published, not the LLM."""
from __future__ import annotations

import logging
import re
from collections import Counter

from .config import MAX_KEPT, MAX_PER_NEWS_TYPE, MIN_RELEVANCE

log = logging.getLogger("techwatch.filter")

STOP = {"the", "and", "for", "with", "its", "new", "from", "into", "der", "die", "das", "und", "mit", "für", "von"}
SAME_STORY_SHARED = 3   # story labels sharing >= 3 content words ...
SAME_STORY_OVERLAP = 0.5  # ... covering at least half of the shorter label describe the same event
SAME_TITLE_SHARED = 4   # titles sharing >= 4 content words covering half of the shorter title


def rank_key(item: dict):
    return (-item["relevance"], -int(item["date"].replace("-", "")), item["id"])


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"\w+", (text or "").lower()) if (len(t) > 2 or t.isdigit()) and t not in STOP}


def overlaps(a: set[str], b: set[str], min_shared: int) -> bool:
    shared = len(a & b)
    return bool(a and b) and shared >= min_shared and shared / min(len(a), len(b)) >= SAME_STORY_OVERLAP


def same_title(a: dict, b: dict) -> bool:
    return overlaps(tokens(a["title"]), tokens(b["title"]), SAME_TITLE_SHARED)


def same_story(a: dict, b: dict) -> bool:
    """Within one week: same LLM story label or near-identical title."""
    return overlaps(tokens(a.get("story")), tokens(b.get("story")), SAME_STORY_SHARED) or same_title(a, b)


def collapse_stories(candidates: list[dict]) -> list[dict]:
    """One item per underlying story: keep the best-ranked one, note the other outlets."""
    reps: list[dict] = []
    for it in candidates:  # already sorted by rank
        rep = next((r for r in reps if same_story(r, it)), None)
        if rep is None:
            reps.append({**it, "also_reported_by": []})
        elif it.get("publisher") and it["publisher"] not in rep["also_reported_by"] + [rep.get("publisher")]:
            rep["also_reported_by"].append(it["publisher"])
    return reps


def select(items: list[dict], watch_field_ids: list[str], published: list[dict] | None = None) -> list[dict]:
    best = {f: max((it["relevance"] for it in items if it["watch_field"] == f), default=None) for f in watch_field_ids}
    log.info("best relevance per watch field: %s", best)
    qualifying = sorted((it for it in items if it["relevance"] >= MIN_RELEVANCE), key=rank_key)
    if published:  # a story already published in an earlier week is not news again
        # across weeks only the title rule: re-reports of the same announcement are dropped,
        # genuine follow-ups of a developing story (new facts, new title) stay
        fresh = [it for it in qualifying if not any(same_title(p, it) for p in published)]
        log.info("dropped %d item(s) covering stories published in earlier weeks", len(qualifying) - len(fresh))
        qualifying = fresh
    candidates = collapse_stories(qualifying)
    kept: list[dict] = []
    per_type: Counter = Counter()

    def take(it: dict) -> bool:
        if it in kept or len(kept) >= MAX_KEPT or per_type[it["news_type"]] >= MAX_PER_NEWS_TYPE:
            return False
        kept.append(it)
        per_type[it["news_type"]] += 1
        return True

    # 1) at least one item per watch field, if one qualifies
    for fid in watch_field_ids:
        for it in candidates:
            if it["watch_field"] == fid and take(it):
                break
    # 2) fill by rank
    for it in candidates:
        take(it)

    kept.sort(key=rank_key)
    log.info("qualifying(relevance>=%d)=%d stories=%d kept=%d per_type=%s", MIN_RELEVANCE, len(qualifying),
             len(candidates), len(kept), dict(per_type))
    return kept
