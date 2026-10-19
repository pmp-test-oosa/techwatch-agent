"""Fixture source for dry runs and tests. Items are invented; they must never be published.

Dates are relative to the day of the run (days_ago), so every dry-run window has data.
"""
from __future__ import annotations

import json
from datetime import timedelta

from ..config import FIXTURES_DIR
from ..windows import Window, today_utc
from .base import Source


class FixtureSource(Source):
    name = "fixture"
    label = "Fixtures (dry run)"
    is_fixture = True

    def __init__(self) -> None:
        super().__init__()
        with (FIXTURES_DIR / "items.json").open(encoding="utf-8") as f:
            self._items = json.load(f)["items"]

    def collect(self, profile: dict, field: dict, window: Window) -> list[dict]:
        today = today_utc()
        out = []
        for it in self._items:
            if it["watch_field"] != field["id"]:
                continue
            out.append({
                "source": self.name,
                "title": it["title"],
                "url": f"https://example.com/fixture/{it['key']}",
                "date": today - timedelta(days=it["days_ago"] + 1),
                "snippet": it["snippet"],
                "publisher": it["publisher"],
                "watch_field": field["id"],
                "news_type": "research" if it["kind"] == "paper" else None,
            })
        return out
