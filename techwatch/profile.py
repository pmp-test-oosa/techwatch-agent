"""Step 1 - LOAD the profile."""
from __future__ import annotations

import functools
import logging
import re

import yaml

from .config import PROFILES_DIR

log = logging.getLogger("techwatch.load")

REQUIRED = ("id", "name", "description", "watch_fields")
REQUIRED_FIELD = ("id", "name", "keywords_en", "keywords_de")
MAX_KEYWORDS_PER_LANGUAGE = 8


class ProfileError(Exception):
    pass


def list_profiles() -> list[str]:
    return sorted(p.stem for p in PROFILES_DIR.glob("*.yaml"))


def load_profile(profile_id: str) -> dict:
    path = PROFILES_DIR / f"{profile_id}.yaml"
    if not path.exists():
        raise ProfileError(f"profile not found: {path.name} (available: {', '.join(list_profiles())})")
    with path.open(encoding="utf-8") as f:
        profile = yaml.safe_load(f)
    missing = [k for k in REQUIRED if not profile.get(k)]
    if missing:
        raise ProfileError(f"{path.name}: missing keys {missing}")
    if profile["id"] != profile_id:
        raise ProfileError(f"{path.name}: id '{profile['id']}' does not match file name")
    ids = set()
    for field in profile["watch_fields"]:
        miss = [k for k in REQUIRED_FIELD if not field.get(k)]
        if miss:
            raise ProfileError(f"{path.name}: watch field {field.get('id')} missing {miss}")
        if field["id"] in ids:
            raise ProfileError(f"{path.name}: duplicate watch field id {field['id']}")
        for lang in ("keywords_en", "keywords_de"):
            if len(field[lang]) > MAX_KEYWORDS_PER_LANGUAGE:
                raise ProfileError(f"{path.name}: {field['id']}.{lang} has more than "
                                   f"{MAX_KEYWORDS_PER_LANGUAGE} keywords")
        ids.add(field["id"])
        field.setdefault("news_queries", [])
    profile["companies_to_watch"] = profile.get("companies_to_watch") or profile.get("competitors") or []
    log.info("profile=%s watch_fields=%d companies_to_watch=%d", profile_id,
             len(profile["watch_fields"]), len(profile["companies_to_watch"]))
    return profile


def field_keywords(field: dict) -> list[str]:
    return [k.lower() for k in field["keywords_en"] + field["keywords_de"]]


@functools.lru_cache(maxsize=512)
def _pattern(keyword: str) -> re.Pattern:
    kw = re.escape(keyword.lower())
    # short keywords (IIoT, CBAM, Cobot) must stand alone; longer ones may be part of a compound word
    return re.compile(rf"(?<!\w){kw}(?!\w)" if len(keyword) <= 6 else kw)


def keyword_hits(text: str, field: dict) -> int:
    low = (text or "").lower()
    return sum(1 for k in field_keywords(field) if _pattern(k).search(low))


def company_hits(text: str, profile: dict) -> list[str]:
    low = (text or "").lower()
    return [c for c in profile.get("companies_to_watch", []) if _pattern(c.lower()).search(low)]
