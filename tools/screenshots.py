"""Design QA: full-page screenshots of every page at 390 px and 1440 px, light and dark.

Usage: python tools/screenshots.py [base_url] [out_dir] [pages...]
Start the preview first:  python -m techwatch serve --dry-run --port 8765
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "screenshots")
PAGES = sys.argv[3:] or ["index", "archive", "profile", "how", "runs"]
WIDTHS = {"390": (390, 844), "1440": (1440, 900)}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    problems = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in ("light", "dark"):
            for wname, (w, h) in WIDTHS.items():
                ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=theme,
                                          device_scale_factor=1 if w > 800 else 2)
                page = ctx.new_page()
                errors = []
                page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: errors.append(str(e)))
                for name in PAGES:
                    page.goto(f"{BASE}/{name}.html", wait_until="networkidle")
                    page.wait_for_timeout(600)
                    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                    if overflow > 0:
                        problems.append(f"{name} {wname} {theme}: horizontal overflow {overflow}px")
                    page.screenshot(path=str(OUT / f"{name}-{wname}-{theme}.png"), full_page=True)
                for e in errors:
                    problems.append(f"{wname} {theme}: console error: {e}")
                ctx.close()
        browser.close()
    for pr in problems:
        print("PROBLEM:", pr)
    print(f"saved {len(PAGES) * 4} screenshots to {OUT}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
