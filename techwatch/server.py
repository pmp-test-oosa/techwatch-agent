"""Local preview: serves /site, optionally with /data mapped to another folder (dry runs)."""
from __future__ import annotations

import functools
import http.server
import logging
from pathlib import Path

from .config import SITE_DIR

log = logging.getLogger("techwatch.serve")


class Handler(http.server.SimpleHTTPRequestHandler):
    data_dir: Path | None = None

    def translate_path(self, path: str) -> str:
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if self.data_dir is not None and clean.startswith("/data/"):
            rel = clean[len("/data/"):]
            target = (self.data_dir / rel).resolve()
            if self.data_dir.resolve() in target.parents or target == self.data_dir.resolve():
                return str(target)
        return super().translate_path(path)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args) -> None:
        pass


def serve(port: int, data_dir: Path | None) -> None:
    Handler.data_dir = data_dir
    handler = functools.partial(Handler, directory=str(SITE_DIR))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        log.info("serving %s at http://localhost:%d (data: %s)", SITE_DIR, port, data_dir or "site/data")
        httpd.serve_forever()
