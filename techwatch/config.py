"""Paths and fixed rules. Everything that decides what gets published lives here, in code."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"
SITE_DATA_DIR = SITE_DIR / "data"
PROFILES_DIR = ROOT / "profiles"
FIXTURES_DIR = ROOT / "tests" / "fixtures"
DRY_RUN_DIR = Path(tempfile.gettempdir()) / "techwatch-dryrun" / "data"

# Dimension A: what kind of information an item is (fixed list, the LLM may only pick from it).
NEWS_TYPES = {
    "research": "Research",
    "competitor": "Competitor moves",
    "industry": "Industry & market",
    "funding": "Funding & M&A",
    "regulation": "Regulation & standards",
    "events": "Events",
}
# Dimension B: what it means for the client.
SIGNALS = ("threat", "opportunity", "watch")

# Budget and filter rules.
MAX_SCORED_ITEMS = 100      # cap per window, before scoring
BATCH_SIZE = 15             # items per scoring call
MAX_LLM_CALLS = 10          # planned calls per weekly run (scoring batches + 1 digest)
LLM_RETRIES = 2             # retries per call, with backoff
LLM_TIMEOUT_S = 300
MIN_RELEVANCE = 7
MAX_KEPT = 20
MAX_PER_NEWS_TYPE = 6
QUIET_WEEK_THRESHOLD = 5
HEADLINE_MAX_WORDS = 12
SUMMARY_MAX_BULLETS = 5
ACTIONS_MAX = 3

DEFAULT_PROVIDER = os.environ.get("LLM_PROVIDER", "claude_subscription")
SCORE_MODEL = os.environ.get("TECHWATCH_SCORE_MODEL", "haiku")
DIGEST_MODEL = os.environ.get("TECHWATCH_DIGEST_MODEL", "sonnet")

USER_AGENT = "TechWatchAgent/1.0 (weekly technology watch; non-commercial university project)"
HTTP_TIMEOUT_S = 30
