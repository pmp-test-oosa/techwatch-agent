"""Step 1 - LOAD the client profile."""
from __future__ import annotations

import logging

import yaml

from .config import PROFILES_DIR

log = logging.getLogger("techwatch.load")

REQUIRED = ("id", "name", "description", "competitors", "watch_fields")
REQUIRED_FIELD = ("id", "name", "keywords_en", "keywords_de")


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
        ids.add(field["id"])
        field.setdefault("news_queries", [])
    log.info("profile=%s watch_fields=%d competitors=%d", profile_id,
             len(profile["watch_fields"]), len(profile["competitors"]))
    return profile


def field_keywords(field: dict) -> list[str]:
    return [k.lower() for k in field["keywords_en"] + field["keywords_de"]]
