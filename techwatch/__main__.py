"""CLI.

  python -m techwatch run      --profile tmg-radar [--provider mock] [--dry-run] [--catch-up 1] [--force]
  python -m techwatch backfill --profile tmg-radar --weeks 2
  python -m techwatch serve    [--dry-run | --data DIR] [--port 8000]
  python -m techwatch record-failure --reason TEXT [--push]      (used by the workflow)
  python -m techwatch watchdog --out DIR                         (used by the watchdog workflow)
  python -m techwatch failure-report --log FILE --out FILE        (used by the workflow)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from . import ops
from .config import DEFAULT_PROVIDER, DRY_RUN_DIR, MAX_LLM_CALLS, SITE_DATA_DIR
from .pipeline import PipelineError, RunFailed, RunOptions, run_window
from .profile import ProfileError, list_profiles
from .publish import commit, digest_path, push
from .sources import FIXTURE_SOURCES, LIVE_SOURCES
from .windows import backfill_windows, today_utc, weekly_window

log = logging.getLogger("techwatch")
DEFAULT_PROFILE = "tmg-radar"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="techwatch", description="Weekly technology-watch agent")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("--profile", default=DEFAULT_PROFILE, help="profile id, or 'all'")
        sp.add_argument("--provider", default=DEFAULT_PROVIDER, choices=["claude_subscription", "mock"])
        sp.add_argument("--dry-run", action="store_true", help=f"write to a temp folder ({DRY_RUN_DIR}), never site/data")
        sp.add_argument("--sources", choices=["fixtures", "live"],
                        help="default: fixtures for --dry-run, live otherwise")
        sp.add_argument("--out", type=Path, help="override the data folder")
        sp.add_argument("--max-llm-calls", type=int, default=MAX_LLM_CALLS,
                        help="planned LLM calls per window (scoring batches + 1 digest)")
        sp.add_argument("--today", type=date.fromisoformat, help="pretend today is this date (YYYY-MM-DD)")
        sp.add_argument("--force", action="store_true", help="regenerate weeks that already have a digest")
        sp.add_argument("--commit", action="store_true", help="git commit after every window (also skips/failures)")
        sp.add_argument("--push", action="store_true", help="git push at the end, also after a failure (implies --commit)")

    run = sub.add_parser("run", help="run the pipeline for the last completed ISO week")
    common(run)
    run.add_argument("--catch-up", type=int, default=0, metavar="N",
                     help="also generate up to N previous weeks if their digest is missing")
    bf = sub.add_parser("backfill", help="run the previous N weeks (oldest first), then the current week")
    common(bf)
    bf.add_argument("--weeks", type=int, default=2)

    sv = sub.add_parser("serve", help="local preview of the website")
    sv.add_argument("--port", type=int, default=8000)
    g = sv.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="serve dry-run data instead of site/data")
    g.add_argument("--data", type=Path, help="serve this folder as /data")

    rf = sub.add_parser("record-failure", help="record a workflow failure in run-log.json")
    rf.add_argument("--reason", required=True)
    rf.add_argument("--profile", default="all")
    rf.add_argument("--push", action="store_true")

    wd = sub.add_parser("watchdog", help="check digest age and token expiry, write issue texts")
    wd.add_argument("--out", type=Path, required=True)

    fr = sub.add_parser("failure-report", help="write the failure issue text with a redacted log excerpt")
    fr.add_argument("--log", type=Path)
    fr.add_argument("--out", type=Path, required=True)
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
    if args.command == "record-failure":
        profiles = list_profiles() if args.profile == "all" else [args.profile]
        if ops.record_failure(SITE_DATA_DIR, profiles, args.reason) and args.push:
            commit(SITE_DATA_DIR, "chore: run-log (failed workflow step)")
            push()
        return 0
    if args.command == "watchdog":
        ops.watchdog(SITE_DATA_DIR, args.out, os.environ.get("TOKEN_CREATED_AT"))
        return 0
    if args.command == "failure-report":
        ops.failure_report(args.log, args.out)
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
        force=args.force,
        today=today,
    )
    try:
        profiles = list_profiles() if args.profile == "all" else [args.profile]
        if not profiles:
            raise ProfileError("no profiles found in profiles/")
    except ProfileError as exc:
        log.error("%s", exc)
        return 1

    failed = False
    for pid in profiles:
        # (window, backfilled, silent_if_present)
        if args.command == "backfill":
            ws = backfill_windows(args.weeks, today)
            plan = [(w, i < len(ws) - 1, False) for i, w in enumerate(ws)]
        else:
            current = weekly_window(today)
            plan = [(weekly_window(today - timedelta(days=7 * k)), True, True)
                    for k in range(args.catch_up, 0, -1)] + [(current, False, False)]
        for window, backfilled, silent in plan:
            if silent and not args.force and digest_path(data_dir, pid, window.label).exists():
                continue  # catch-up: an earlier week that already exists needs no run-log entry
            try:
                run_window(pid, window, opts, backfilled)
            except RunFailed as exc:
                log.error("%s", exc)
                failed = True  # recorded in the run log; the other weeks are independent
            except PipelineError as exc:
                log.error("RUN FAILED: %s", exc)
                return 2
    if args.push:
        push()
    if failed:
        log.error("at least one window failed; see run-log.json")
        return 1
    log.info("all done. data folder: %s", data_dir)
    if args.dry_run:
        log.info("preview: python -m techwatch serve --dry-run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
