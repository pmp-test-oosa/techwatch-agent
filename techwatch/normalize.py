"""Step 3 - NORMALIZE + DEDUPE. Deterministic code, no LLM."""
from __future__ import annotations

import hashlib
import html
import json
import logging
import re
import urllib.parse
from pathlib import Path

log = logging.getLogger("techwatch.normalize")

ITEM_KEYS = ("id", "source", "title", "url", "date", "snippet", "watch_field",
             "news_type", "signal", "relevance", "reason")
SOURCE_PREFIX = {"arxiv": "ax", "google_news": "gn", "fixture": "fx"}

# SEO press-release spam ("... Market Size to reach $X billion by 2032, CAGR ...").
SPAM = re.compile(
    r"market (size|share|report|research|forecast|analysis|outlook|trends?)\b|\bcagr\b|"
    r"to reach (usd|us\$|\$)|billion by 20\d\d|million by 20\d\d|market will (grow|witness)",
    re.IGNORECASE,
)
TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")


def clean_text(text: str, limit: int) -> str:
    text = WS.sub(" ", TAG.sub(" ", html.unescape(text or ""))).strip()
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def canonical_url(url: str, source: str) -> str:
    url = url.strip()
    if source == "arxiv":
        url = re.sub(r"v\d+$", "", url.replace("http://", "https://"))  # drop version suffix
        return url
    parts = urllib.parse.urlsplit(url)
    if parts.netloc.endswith("news.google.com"):
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    query = "&".join(p for p in parts.query.split("&") if p and not p.startswith("utm_"))
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), query, ""))


def title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9äöüß]+", "", title.lower())[:120]


def make_id(source: str, url: str) -> str:
    return f"{SOURCE_PREFIX.get(source, 'xx')}-{hashlib.sha1(url.encode('utf-8')).hexdigest()[:10]}"


def normalize(raw: dict) -> dict:
    url = canonical_url(raw["url"], raw["source"])
    title = clean_text(raw["title"], 300)
    snippet = clean_text(raw.get("snippet", ""), 600)
    publisher = clean_text(raw.get("publisher", ""), 80)
    if publisher.startswith(("http://", "https://")):  # some feeds give the site URL as the name
        publisher = urllib.parse.urlsplit(publisher).netloc.removeprefix("www.") or publisher
    # Google News descriptions usually repeat the title and the publisher; drop that echo.
    if snippet.startswith(title):
        snippet = snippet[len(title):].strip()
    if publisher and snippet.endswith(publisher):
        snippet = snippet[: -len(publisher)].strip()
    return {
        "id": make_id(raw["source"], url),
        "source": raw["source"],
        "title": title,
        "url": url,
        "date": raw["date"].isoformat(),
        "snippet": snippet,
        "watch_field": raw["watch_field"],
        "news_type": raw.get("news_type"),
        "signal": None,
        "relevance": None,
        "reason": None,
        "publisher": publisher,
    }


def load_published(data_dir: Path, profile_id: str, before_week: str) -> list[dict]:
    """Items already published in weeks before `before_week` (labels like 2026-W42 sort correctly)."""
    out: list[dict] = []
    for path in sorted((data_dir / "digests" / profile_id).glob("*.json")):
        if path.stem >= before_week:
            continue
        with path.open(encoding="utf-8") as f:
            out.extend(json.load(f).get("items", []))
    return out


def published_keys(published: list[dict]) -> tuple[set[str], set[str]]:
    return {it["url"] for it in published}, {title_key(it["title"]) for it in published}


def normalize_and_dedupe(raw_items: list[dict], published: tuple[set[str], set[str]]) -> tuple[list[dict], dict]:
    pub_urls, pub_titles = published
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    out = []
    stats = {"input": len(raw_items), "spam": 0, "duplicate": 0, "already_published": 0, "empty": 0}
    for raw in raw_items:
        item = normalize(raw)
        tkey = title_key(item["title"])
        if not item["title"] or not item["url"].startswith("http"):
            stats["empty"] += 1
            continue
        if SPAM.search(item["title"]):
            stats["spam"] += 1
            continue
        if item["url"] in pub_urls or tkey in pub_titles:
            stats["already_published"] += 1
            continue
        if item["url"] in seen_urls or tkey in seen_titles:
            stats["duplicate"] += 1
            continue
        seen_urls.add(item["url"])
        seen_titles.add(tkey)
        out.append(item)
    stats["output"] = len(out)
    log.info("normalized input=%d output=%d spam=%d duplicates=%d already_published=%d empty=%d",
             stats["input"], stats["output"], stats["spam"], stats["duplicate"],
             stats["already_published"], stats["empty"])
    return out, stats
