from __future__ import annotations

import time
import urllib.request

from ..config import HTTP_TIMEOUT_S, USER_AGENT
from ..windows import Window


class Source:
    """A source returns raw items for one watch field and one date window.

    Raw item keys: source, title, url, date (datetime.date), snippet, publisher,
    watch_field, and optionally news_type (if the source already knows it).
    """

    name = "base"
    label = "Base"
    min_interval_s = 0.0
    is_fixture = False

    def __init__(self) -> None:
        self._last_request = 0.0

    def collect(self, profile: dict, field: dict, window: Window) -> list[dict]:
        raise NotImplementedError

    def http_get(self, url: str) -> bytes:
        wait = self.min_interval_s - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
                return resp.read()
        finally:
            self._last_request = time.monotonic()
