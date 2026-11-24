"""German RSS feeds with an industry or research focus (free, no key).

A feed is not organised by watch field, so code assigns each item to the field whose
keywords it matches most often; items that match no field are dropped. Feeds only carry
their latest items, so past weeks (backfill) get fewer or no items from them.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from ..profile import keyword_hits
from ..windows import Window
from .base import Source

log = logging.getLogger("techwatch.collect.rss")


def parse_date(text: str | None):
    text = (text or "").strip()
    if not text:
        return None
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


class RssFeedSource(Source):
    """One feed = one source, so the run log shows items per feed."""

    name = "rss"
    label = "RSS"
    url = ""
    min_interval_s = 1.0
    https_upgrade = False  # feed links use http although the site serves https

    def __init__(self) -> None:
        super().__init__()
        self._entries: list[dict] | None = None
        self._assigned: dict[str, list[dict]] = {}
        self._error: Exception | None = None  # the feed is fetched at most once per run

    def entries(self) -> list[dict]:
        if self._error is not None:
            raise RuntimeError(f"feed unavailable in this run ({type(self._error).__name__})")
        if self._entries is None:
            try:
                root = ET.fromstring(self.http_get(self.url))
            except Exception as exc:
                self._error = exc
                raise
            out = []
            for node in root.iter():
                if _local(node.tag) not in ("item", "entry"):
                    continue
                fields: dict[str, str] = {}
                for child in node:
                    tag = _local(child.tag)
                    if tag == "link" and child.get("href"):
                        fields.setdefault("link", child.get("href"))
                    elif child.text and tag not in fields:
                        fields[tag] = child.text.strip()
                url = fields.get("link", "")
                if self.https_upgrade and url.startswith("http://"):
                    url = "https://" + url[len("http://"):]
                day = parse_date(fields.get("pubDate") or fields.get("published")
                                 or fields.get("updated") or fields.get("date"))
                if url and fields.get("title") and day:
                    out.append({"title": fields["title"], "url": url, "date": day,
                                "snippet": fields.get("description") or fields.get("summary") or ""})
            self._entries = out
            log.info("feed=%s entries=%d", self.name, len(out))
        return self._entries

    def assign(self, profile: dict) -> dict[str, list[dict]]:
        """Deterministic field assignment: most keyword hits wins, ties go to the earlier field."""
        if not self._assigned:
            fields = profile["watch_fields"]
            assigned: dict[str, list[dict]] = {f["id"]: [] for f in fields}
            unmatched = 0
            for e in self.entries():
                text = f"{e['title']} {e['snippet']}"
                hits = [(keyword_hits(text, f), -i, f["id"]) for i, f in enumerate(fields)]
                best = max(hits)
                if best[0] == 0:
                    unmatched += 1
                    continue
                assigned[best[2]].append(e)
            log.info("feed=%s matched=%s unmatched(dropped)=%d", self.name,
                     {k: len(v) for k, v in assigned.items()}, unmatched)
            self._assigned = assigned
        return self._assigned

    def collect(self, profile: dict, field: dict, window: Window) -> list[dict]:
        return [{
            "source": self.name,
            "title": e["title"],
            "url": e["url"],
            "date": e["date"],
            "snippet": e["snippet"],
            "publisher": self.label,
            "watch_field": field["id"],
            "news_type": None,
        } for e in self.assign(profile)[field["id"]]]


class IdwSource(RssFeedSource):
    name = "idw"
    label = "idw – Informationsdienst Wissenschaft"
    url = "https://idw-online.de/de/pressreleasesrss"
    https_upgrade = True


class MaschinenmarktSource(RssFeedSource):
    name = "maschinenmarkt"
    label = "MM MaschinenMarkt"
    url = "https://www.maschinenmarkt.vogel.de/rss/news.xml"


class IndustryOfThingsSource(RssFeedSource):
    name = "industry_of_things"
    label = "Industry of Things"
    url = "https://www.industry-of-things.de/rss/news.xml"
