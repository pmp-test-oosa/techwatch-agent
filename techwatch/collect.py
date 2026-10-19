"""Step 2 - COLLECT raw items per watch field from every source. A failing source never stops the run."""
from __future__ import annotations

import logging
from datetime import date

from .sources import Source
from .windows import Window

log = logging.getLogger("techwatch.collect")


def collect(profile: dict, window: Window, sources: list[Source]) -> tuple[list[dict], dict, list[str]]:
    items: list[dict] = []
    per_source: dict[str, int] = {}
    errors: list[str] = []
    for src in sources:
        got = 0
        for field in profile["watch_fields"]:
            try:
                raw = src.collect(profile, field, window)
            except Exception as exc:
                msg = f"{src.name}/{field['id']}: {type(exc).__name__}: {str(exc)[:200]}"
                log.warning("source failed, continuing: %s", msg)
                errors.append(msg)
                continue
            inside = [r for r in raw if isinstance(r.get("date"), date) and window.contains(r["date"])]
            dropped = len(raw) - len(inside)
            log.info("source=%s field=%s fetched=%d in_window=%d dropped_outside=%d",
                     src.name, field["id"], len(raw), len(inside), dropped)
            items.extend(inside)
            got += len(inside)
        per_source[src.name] = got
    log.info("collected=%d per_source=%s errors=%d", len(items), per_source, len(errors))
    return items, per_source, errors
