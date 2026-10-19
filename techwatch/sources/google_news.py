"""Google News RSS search (free, no key), with after:/before: date operators in the query.

Links are Google News article links that redirect to the publisher's original article.
"""
from __future__ import annotations

import logging
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import timedelta, timezone
from email.utils import parsedate_to_datetime

from ..windows import Window
from .base import Source

log = logging.getLogger("techwatch.collect.google_news")

FEED = "https://news.google.com/rss/search"
LOCALES = {
    "en": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
    "de": {"hl": "de", "gl": "DE", "ceid": "DE:de"},
}


class GoogleNewsSource(Source):
    name = "google_news"
    label = "Google News"
    min_interval_s = 1.5

    def queries(self, field: dict) -> list[dict]:
        if field.get("news_queries"):
            return field["news_queries"]
        return [
            {"lang": "en", "q": " OR ".join(f'"{k}"' for k in field["keywords_en"][:5])},
            {"lang": "de", "q": " OR ".join(f'"{k}"' for k in field["keywords_de"][:5])},
        ]

    def build_url(self, query: dict, window: Window) -> str:
        # before: is exclusive, so use the day after the window end.
        q = f"{query['q']} after:{window.start.isoformat()} before:{(window.end + timedelta(days=1)).isoformat()}"
        params = {"q": q, **LOCALES.get(query.get("lang", "en"), LOCALES["en"])}
        return f"{FEED}?{urllib.parse.urlencode(params)}"

    def collect(self, profile: dict, field: dict, window: Window) -> list[dict]:
        items = []
        errors = []
        for query in self.queries(field):
            try:
                root = ET.fromstring(self.http_get(self.build_url(query, window)))
            except Exception as exc:  # one failing query must not drop the others
                errors.append(f"{query.get('lang')}: {exc}")
                continue
            for it in root.iter("item"):
                title = (it.findtext("title") or "").strip()
                url = (it.findtext("link") or "").strip()
                pub = it.findtext("pubDate")
                if not title or not url or not pub:
                    continue
                src = it.find("source")
                publisher = (src.text or "").strip() if src is not None else ""
                if publisher and title.endswith(f" - {publisher}"):
                    title = title[: -len(publisher) - 3].strip()
                items.append({
                    "source": self.name,
                    "title": title,
                    "url": url,
                    "date": parsedate_to_datetime(pub).astimezone(timezone.utc).date(),
                    "snippet": it.findtext("description") or "",
                    "publisher": publisher or "Google News",
                    "watch_field": field["id"],
                    "news_type": None,
                    "lang": query.get("lang", "en"),
                })
        if errors and not items:
            raise RuntimeError("; ".join(errors))
        for e in errors:
            log.warning("field=%s query failed: %s", field["id"], e)
        return items
