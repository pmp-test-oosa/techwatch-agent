"""arXiv API (free, no key). Filtered by submission date inside the query."""
from __future__ import annotations

import logging
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

from ..windows import Window
from .base import Source

log = logging.getLogger("techwatch.collect.arxiv")

API = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}


class ArxivSource(Source):
    name = "arxiv"
    label = "arXiv"
    min_interval_s = 3.5  # arXiv asks for at most one request every 3 seconds
    max_results = 50

    def build_query(self, field: dict, window: Window) -> str:
        base = field.get("arxiv_query") or " OR ".join(f'abs:"{k}"' for k in field["keywords_en"][:6])
        date_from = window.start.strftime("%Y%m%d") + "0000"
        date_to = window.end.strftime("%Y%m%d") + "2359"
        return f"({base}) AND submittedDate:[{date_from} TO {date_to}]"

    def collect(self, profile: dict, field: dict, window: Window) -> list[dict]:
        params = urllib.parse.urlencode({
            "search_query": self.build_query(field, window),
            "start": 0,
            "max_results": self.max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        })
        root = ET.fromstring(self.http_get(f"{API}?{params}"))
        items = []
        for entry in root.findall("a:entry", NS):
            url = (entry.findtext("a:id", default="", namespaces=NS) or "").strip()
            title = " ".join((entry.findtext("a:title", default="", namespaces=NS) or "").split())
            published = entry.findtext("a:published", default="", namespaces=NS)
            if not url or not title or not published:
                continue
            authors = [a.findtext("a:name", default="", namespaces=NS) for a in entry.findall("a:author", NS)]
            publisher = "arXiv"
            if authors:
                publisher = f"arXiv · {authors[0]}{' et al.' if len(authors) > 1 else ''}"
            items.append({
                "source": self.name,
                "title": title,
                "url": url.replace("http://", "https://"),
                "date": datetime.fromisoformat(published.replace("Z", "+00:00")).date(),
                "snippet": entry.findtext("a:summary", default="", namespaces=NS),
                "publisher": publisher,
                "watch_field": field["id"],
                "news_type": "research",
            })
        return items
