"""CLI.

  python -m techwatch run      --profile lindner [--provider mock] [--dry-run]
  python -m techwatch backfill --profile lindner --weeks 2
  python -m techwatch serve    [--dry-run | --data DIR] [--port 8000]
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from .config import DEFAULT_PROVIDER, DRY_RUN_DIR, MAX_LLM_CALLS, SITE_DATA_DIR
from .llm import LLMError
from .pipeline import PipelineError, RunOptions, run_window
from .profile import ProfileError, list_profiles
from .publish import push
from .sources import FIXTURE_SOURCES, LIVE_SOURCES
from .validate import ValidationError
from .windows import backfill_windows, today_utc, weekly_window

log = logging.getLogger("techwatch")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="techwatch", description="Weekly technology-watch agent")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("--profile", default="lindner", help="profile id, or 'all'")
        sp.add_argument("--provider", default=DEFAULT_PROVIDER, choices=["claude_subscription", "mock"])
        sp.add_argument("--dry-run", action="store_true", help=f"write to a temp folder ({DRY_RUN_DIR}), never site/data")
        sp.add_argument("--sources", choices=["fixtures", "live"],
                        help="default: fixtures for --dry-run, live otherwise")
        sp.add_argument("--out", type=Path, help="override the data folder")
        sp.add_argument("--max-llm-calls", type=int, default=MAX_LLM_CALLS,
                        help="planned LLM calls per window (scoring batches + 1 digest)")
        sp.add_argument("--today", type=date.fromisoformat, help="pretend today is this date (YYYY-MM-DD)")
        sp.add_argument("--commit", action="store_true", help="git commit each published digest")
        sp.add_argument("--push", action="store_true", help="git push at the end (implies --commit)")

    run = sub.add_parser("run", help="run the weekly pipeline for the last 7 days")
    common(run)
    bf = sub.add_parser("backfill", help="run the previous N weeks (oldest first), then the current week")
    common(bf)
    bf.add_argument("--weeks", type=int, default=2)

    sv = sub.add_parser("serve", help="local preview of the website")
    sv.add_argument("--port", type=int, default=8000)
    g = sv.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="serve dry-run data instead of site/data")
    g.add_argument("--data", type=Path, help="serve this folder as /data")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                        datefmt="%H:%M:%S", stream=sys.stderr)
    args = build_parser().parse_args(argv)

    if args.command == "serve":
        from .server import serve
        serve(args.port, DRY_RUN_DIR if args.dry_run else args.data)
        return 0

    data_dir = args.out or (DRY_RUN_DIR if args.dry_run else SITE_DATA_DIR)
    if args.dry_run and data_dir.resolve() == SITE_DATA_DIR.resolve():
        log.error("--dry-run must never write to site/data")
        return 2
    sources_mode = args.sources or ("fixtures" if args.dry_run else "live")
    today = args.today or today_utc()
    opts = RunOptions(
        provider=args.provider,
        sources=FIXTURE_SOURCES if sources_mode == "fixtures" else LIVE_SOURCES,
        data_dir=data_dir,
        max_llm_calls=args.max_llm_calls,
        dry_run=args.dry_run,
        commit=args.commit or args.push,
        today=today,
    )
    windows = (backfill_windows(args.weeks, today) if args.command == "backfill" else [weekly_window(today)])
    profiles = list_profiles() if args.profile == "all" else [args.profile]

    try:
        for pid in profiles:
            for i, window in enumerate(windows):
                backfilled = args.command == "backfill" and i < len(windows) - 1
                run_window(pid, window, opts, backfilled)
        if args.push:
            push()
    except (ValidationError, LLMError, PipelineError, ProfileError) as exc:
        log.error("RUN FAILED, nothing was published for this window: %s", exc)
        return 1
    log.info("all done. data folder: %s", data_dir)
    if args.dry_run:
        log.info("preview: python -m techwatch serve --dry-run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
