"""Source plugins. To add a source, subclass Source and register it in SOURCES."""
from __future__ import annotations

from datetime import date

from .arxiv import ArxivSource
from .base import Source
from .fixtures import FixtureSource
from .google_news import GoogleNewsSource

SOURCES: dict[str, type[Source]] = {
    ArxivSource.name: ArxivSource,
    GoogleNewsSource.name: GoogleNewsSource,
    FixtureSource.name: FixtureSource,
}

LIVE_SOURCES = [ArxivSource.name, GoogleNewsSource.name]
FIXTURE_SOURCES = [FixtureSource.name]


def build_sources(names: list[str], today: date | None = None) -> list[Source]:
    return [SOURCES[n](today) if SOURCES[n].is_fixture else SOURCES[n]() for n in names]
