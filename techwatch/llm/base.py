from __future__ import annotations

import logging
import time
from typing import Any, Callable

from ..config import LLM_RETRIES
from .schemas import check_digest, check_scores

log = logging.getLogger("techwatch.llm")


class LLMError(Exception):
    pass


class Provider:
    """Both methods return schema-validated JSON or raise LLMError after retries."""

    name = "base"
    score_model = "-"
    digest_model = "-"
    backoff_s = (5, 20)

    def __init__(self, max_calls: int):
        self.max_calls = max_calls
        self.calls = 0
        self.models_used: set[str] = set()

    # --- public API ---------------------------------------------------------
    def score_batch(self, items: list[dict], profile: dict) -> list[dict]:
        return self._with_retries("score", lambda fb: self._score(items, profile, fb),
                                  lambda r: check_scores(r, items))

    def write_digest(self, items: list[dict], profile: dict) -> dict:
        return self._with_retries("digest", lambda fb: self._digest(items, profile, fb),
                                  lambda r: check_digest(r, items))

    # --- implemented by providers ------------------------------------------
    # `feedback` is None on the first attempt, else the reason the previous answer was rejected.
    def _score(self, items: list[dict], profile: dict, feedback: str | None = None) -> dict:
        raise NotImplementedError

    def _digest(self, items: list[dict], profile: dict, feedback: str | None = None) -> dict:
        raise NotImplementedError

    # --- shared ---------------------------------------------------------------
    def _with_retries(self, kind: str, call: Callable[[str | None], dict], check: Callable[[dict], Any]):
        last: Exception | None = None
        for attempt in range(LLM_RETRIES + 1):
            if attempt:
                wait = self.backoff_s[min(attempt - 1, len(self.backoff_s) - 1)]
                log.warning("%s call failed (%s), retry %d/%d in %ss", kind, last, attempt, LLM_RETRIES, wait)
                time.sleep(wait)
            self.calls += 1
            try:
                return check(call(str(last)[:400] if last else None))
            except Exception as exc:  # invalid JSON, schema violation, CLI failure, timeout
                last = exc
        raise LLMError(f"{kind} failed after {LLM_RETRIES + 1} attempts: {last}")
