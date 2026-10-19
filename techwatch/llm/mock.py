"""Deterministic fake LLM for dry runs and tests. Same input -> same output, no network."""
from __future__ import annotations

import hashlib
import re

from ..profile import field_keywords
from .base import Provider

RULES = [
    ("funding", re.compile(r"fund|invest|acqui|merger|startup|raises|series [a-c]|stake|übernahme|finanzierung", re.I)),
    ("regulation", re.compile(r"cbam|regulation|directive|\beu\b|standard|norm\b|din |iso |reporting|verordnung|richtlinie", re.I)),
    ("events", re.compile(r"conference|fair|euroguss|gifa|call for papers|webinar|summit|messe|tagung|kongress", re.I)),
    ("research", re.compile(r"paper|study|researchers|preprint|universit|fraunhofer|institute", re.I)),
]
THREAT = re.compile(r"in-house|insourc|replace|cheaper|price|tariff|shortage|cuts|closes|loses|wins order|undercut|eigenfertigung", re.I)
OPPORTUNITY = re.compile(r"grant|fund|partner|open|new alloy|low-cost|saves|reduces scrap|demand|tender|förder|call for", re.I)


def _h(text: str) -> int:
    return int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16)


class MockProvider(Provider):
    name = "mock"
    score_model = "mock"
    digest_model = "mock"
    backoff_s = (0, 0)

    def _score(self, items: list[dict], profile: dict, feedback: str | None = None) -> dict:
        self.models_used.add("mock")
        fields = {f["id"]: f for f in profile["watch_fields"]}
        out = []
        for it in items:
            field = fields[it["watch_field"]]
            text = f"{it['title']} {it['snippet']}"
            low = text.lower()
            hits = sum(1 for k in field_keywords(field) if k in low)
            comp = [c for c in profile["competitors"] if c.lower() in low]
            relevance = max(0, min(10, 2 + hits + 2 * len(comp) + _h(it["id"]) % 4))
            news_type = "competitor" if comp else next((t for t, rx in RULES if rx.search(text)), "industry")
            if THREAT.search(text) or comp:
                signal = "threat"
            elif OPPORTUNITY.search(text):
                signal = "opportunity"
            else:
                signal = "watch"
            who = f" ({comp[0]})" if comp else ""
            out.append({
                "id": it["id"],
                "relevance": relevance,
                "signal": signal,
                "news_type": news_type,
                "story": " ".join(it["title"].split()[:5]),
                "reason": f"Mock score: {hits} keyword match(es) for {field['name']}{who}, "
                          f"relevant to Lindner's structural-casting business.",
            })
        return {"scores": out}

    def _digest(self, items: list[dict], profile: dict, feedback: str | None = None) -> dict:
        self.models_used.add("mock")
        top = items[0]
        threats = sum(1 for i in items if i["signal"] == "threat")
        opps = sum(1 for i in items if i["signal"] == "opportunity")
        fields = {f["id"]: f.get("short") or f["name"] for f in profile["watch_fields"]}
        return {
            "headline": f"{fields[top['watch_field']]} leads a week of {len(items)} signals",
            "summary": [
                {"text": f"{it['title']}: {it['reason']}", "item_ids": [it["id"]]} for it in items[:5]
            ],
            "actions": [
                {"text": f"Review the {threats} threat item(s) with the sales lead.",
                 "item_ids": [i["id"] for i in items if i["signal"] == "threat"][:2]},
                {"text": f"Check the {opps} opportunity item(s) for funding or partner fit.",
                 "item_ids": [i["id"] for i in items if i["signal"] == "opportunity"][:2]},
                {"text": "Share the top signal with the managing director.", "item_ids": [top["id"]]},
            ],
            "top_signal": top["id"],
        }
