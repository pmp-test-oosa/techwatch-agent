"""Date windows. A weekly run covers the last completed ISO week (Mon-Sun, UTC).

Run by the Monday cron, that is exactly the last 7 days. A manual run on any other
day covers the same calendar week, so windows never overlap or leave gaps, and the
label (e.g. 2026-W42) always matches the window.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone


@dataclass(frozen=True)
class Window:
    start: date  # inclusive
    end: date    # inclusive

    @property
    def label(self) -> str:
        year, week, _ = self.end.isocalendar()
        return f"{year}-W{week:02d}"

    @property
    def week_number(self) -> int:
        return self.end.isocalendar()[1]

    def contains(self, d: date) -> bool:
        return self.start <= d <= self.end

    def as_dict(self) -> dict:
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}

    def __str__(self) -> str:
        return f"{self.label} ({self.start} .. {self.end})"


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def weekly_window(today: date | None = None) -> Window:
    today = today or today_utc()
    this_monday = today - timedelta(days=today.weekday())
    start = this_monday - timedelta(days=7)
    return Window(start=start, end=start + timedelta(days=6))


def backfill_windows(weeks: int, today: date | None = None) -> list[Window]:
    """The `weeks` previous weeks, oldest first, followed by the current weekly window."""
    today = today or today_utc()
    return [weekly_window(today - timedelta(days=7 * k)) for k in range(weeks, -1, -1)]
