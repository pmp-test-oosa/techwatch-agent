"""Orchestrates the 8 steps for one profile and one date window."""
from __future__ import annotations

import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import collect as collect_step
from . import digest as digest_step
from . import filter as filter_step
from . import normalize as normalize_step
from . import publish as publish_step
from . import score as score_step
from . import validate as validate_step
from .config import (BATCH_SIZE, MAX_SCORED_ITEMS, NEWS_TYPES, QUIET_WEEK_THRESHOLD, SIGNALS,
                     SITE_DATA_DIR)
from .llm import get_provider
from .profile import load_profile
from .sources import build_sources
from .windows import Window

log = logging.getLogger("techwatch.pipeline")


@dataclass
class RunOptions:
    provider: str
    sources: list[str]
    data_dir: Path
    max_llm_calls: int
    dry_run: bool = False
    commit: bool = False
    extra_errors: list[str] = field(default_factory=list)

    @property
    def publish_to_site(self) -> bool:
        return self.data_dir.resolve() == SITE_DATA_DIR.resolve()


class PipelineError(Exception):
    pass


def check_safe(opts: RunOptions) -> None:
    if opts.publish_to_site and ("fixture" in opts.sources or opts.provider == "mock"):
        raise PipelineError("refusing to write fixture or mock output into site/data; use --dry-run")
    if opts.max_llm_calls < 2:
        raise PipelineError("--max-llm-calls must be at least 2 (one scoring batch + the digest)")


def publisher_group(item: dict) -> str:
    return "arXiv" if item["source"] == "arxiv" else (item.get("publisher") or item["source"])


def run_window(profile_id: str, window: Window, opts: RunOptions, backfilled: bool) -> dict:
    check_safe(opts)
    t0 = time.monotonic()
    log.info("=== run profile=%s window=%s provider=%s dry_run=%s backfilled=%s ===",
             profile_id, window, opts.provider, opts.dry_run, backfilled)

    profile = load_profile(profile_id)                                         # 1 LOAD
    field_ids = [f["id"] for f in profile["watch_fields"]]

    sources = build_sources(opts.sources)                                      # 2 COLLECT
    raw, per_source, errors = collect_step.collect(profile, window, sources)
    collected = {}
    for r in raw:
        n = normalize_step.normalize(r)
        collected[n["id"]] = n["url"]

    published = normalize_step.load_published(opts.data_dir, profile_id, window.label)
    items, dedupe_stats = normalize_step.normalize_and_dedupe(                 # 3 NORMALIZE + DEDUPE
        raw, normalize_step.published_keys(published))

    provider = get_provider(opts.provider, opts.max_llm_calls)                 # 4 SCORE
    max_batches = min(opts.max_llm_calls - 1, -(-MAX_SCORED_ITEMS // BATCH_SIZE))
    scored, score_stats = score_step.score(items, profile, provider, max_batches)

    kept = filter_step.select(scored, field_ids, published)                    # 5 FILTER

    digest = digest_step.write(kept, profile, provider)                        # 6 DIGEST

    validate_step.validate(digest, kept, window, collected, field_ids,        # 7 VALIDATE
                           opts.publish_to_site)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()        # 8 PUBLISH
    sig = Counter(it["signal"] for it in kept)
    per_type = Counter(it["news_type"] for it in kept)
    per_field = Counter(it["watch_field"] for it in kept)
    quiet = len(kept) < QUIET_WEEK_THRESHOLD
    models = {"score": provider.score_model, "digest": provider.digest_model}
    duration = round(time.monotonic() - t0, 1)
    all_errors = errors + opts.extra_errors
    stats = {
        "scanned": len(raw),
        "after_dedupe": len(items),
        "scored": len(scored),
        "kept": len(kept),
        "threats": sig.get("threat", 0),
        "opportunities": sig.get("opportunity", 0),
        "watch": sig.get("watch", 0),
        "sources": len({publisher_group(it) for it in items}),
        "per_source": per_source,
        "per_news_type": {t: per_type.get(t, 0) for t in NEWS_TYPES},
        "per_signal": {s: sig.get(s, 0) for s in SIGNALS},
        "per_watch_field": {f: per_field.get(f, 0) for f in field_ids},
    }
    doc = {
        "schema_version": 1,
        "profile": profile_id,
        "week": window.label,
        "week_number": window.week_number,
        "window": window.as_dict(),
        "generated_at": now,
        "backfilled": backfilled,
        "quiet_week": quiet,
        "dry_run": opts.dry_run,
        "provider": provider.name,
        "models": models,
        "headline": digest["headline"],
        "summary": digest["summary"],
        "actions": digest["actions"],
        "top_signal": digest["top_signal"],
        "stats": stats,
        "items": [{k: it.get(k) for k in normalize_step.ITEM_KEYS + ("publisher", "story", "also_reported_by")}
                  for it in kept],
    }
    run_record = {
        "profile": profile_id,
        "week": window.label,
        "window": window.as_dict(),
        "generated_at": now,
        "backfilled": backfilled,
        "dry_run": opts.dry_run,
        "status": "published",
        "provider": provider.name,
        "models": models,
        "models_used": sorted(provider.models_used),
        "items_per_source": per_source,
        "collected": len(raw),
        "dedupe": dedupe_stats,
        "after_dedupe": len(items),
        "scored": len(scored),
        "kept": len(kept),
        "per_news_type": stats["per_news_type"],
        "per_signal": stats["per_signal"],
        "llm_calls": provider.calls,
        "duration_s": duration,
        "errors": all_errors,
        "quiet_week": quiet,
    }
    path = publish_step.publish(opts.data_dir, profile, doc, run_record)
    if opts.commit:
        publish_step.commit(opts.data_dir, profile_id, window.label)
    log.info("=== done %s: scanned=%d after_dedupe=%d scored=%d kept=%d llm_calls=%d duration=%.1fs ===",
             window.label, len(raw), len(items), len(scored), len(kept), provider.calls, duration)
    return {"path": str(path), **run_record}
