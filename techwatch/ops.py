"""Self-monitoring helpers used by the GitHub Actions workflows. None of them needs a human.

* record_failure: a workflow step failed before or outside the pipeline -> failed run-log record
* watchdog:       stale digest or Claude token close to expiry -> issue texts
* failure_report: issue text with a redacted log excerpt
"""
from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import publish as publish_step
from .config import SCHEDULE_UTC
from .windows import today_utc, weekly_window

log = logging.getLogger("techwatch.ops")

TOKEN_VALID_DAYS = 365
TOKEN_WARN_DAYS = 30
STALE_AFTER_DAYS = 8
SECRET_PATTERNS = [re.compile(r"sk-ant-[A-Za-z0-9_\-]+"), re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")]


def record_failure(data_dir: Path, profile_ids: list[str], reason: str, today: date | None = None) -> int:
    """Append one failed record per profile unless this GitHub run already recorded one."""
    ctx = publish_step.run_context()
    runs = publish_step.read_json(data_dir / "run-log.json", {"runs": []})["runs"]
    window = weekly_window(today or today_utc())
    added = 0
    for pid in profile_ids:
        if ctx.get("run_id") and any(r.get("run_id") == ctx["run_id"] and r.get("profile") == pid
                                     and r.get("status") == "failed" for r in runs):
            log.info("failure for run %s / %s already recorded", ctx["run_id"], pid)
            continue
        publish_step.append_run(data_dir, {
            "profile": pid,
            "week": window.label,
            "window": window.as_dict(),
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "status": "failed",
            "stage": "workflow",
            "error": reason[:500],
            "backfilled": False,
            "dry_run": False,
            "llm_calls": 0,
            "duration_s": 0.0,
            **ctx,
        })
        added += 1
    return added


def next_scheduled_runs(now: datetime, count: int = 2) -> list[datetime]:
    out = []
    day = now.date()
    for offset in range(0, 15):
        d = day + timedelta(days=offset)
        for weekday, hour, minute in SCHEDULE_UTC:
            if d.weekday() == weekday:
                t = datetime(d.year, d.month, d.day, hour, minute, tzinfo=timezone.utc)
                if t > now:
                    out.append(t)
    return sorted(out)[:count]


def watchdog(data_dir: Path, out_dir: Path, token_created_at: str | None, now: datetime | None = None) -> dict:
    """Write stale.md / token.md into out_dir when an issue is needed. Returns the findings."""
    now = now or datetime.now(timezone.utc)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ("stale.md", "token.md"):
        (out_dir / name).unlink(missing_ok=True)
    findings: dict = {}

    index = publish_step.read_json(data_dir / "index.json", {"profiles": []})
    newest = None
    for p in index.get("profiles", []):
        for w in p.get("weeks", []):
            ts = datetime.fromisoformat(w["generated_at"])
            if newest is None or ts > newest[0]:
                newest = (ts, p["id"], w["week"])
    if newest is None or now - newest[0] > timedelta(days=STALE_AFTER_DAYS):
        age = "no digest has been published yet" if newest is None else \
            f"the newest digest ({newest[1]} {newest[2]}) was generated on {newest[0]:%Y-%m-%d %H:%M} UTC, " \
            f"{(now - newest[0]).days} days ago"
        findings["stale"] = age
        (out_dir / "stale.md").write_text(
            f"The TechWatch watchdog found that {age} (limit: {STALE_AFTER_DAYS} days).\n\n"
            "The weekly run should have produced a newer digest. Check the latest runs of the "
            "\"TechWatch weekly digest\" workflow and any open \"TechWatch run failed\" issue. "
            "This issue closes itself after the next successful digest.\n", encoding="utf-8")

    token_created_at = (token_created_at or "").strip()
    if not token_created_at:
        findings["token"] = "TOKEN_CREATED_AT is not set"
        (out_dir / "token.md").write_text(
            "The repository variable `TOKEN_CREATED_AT` is not set, so the watchdog cannot warn before the "
            "Claude token (`CLAUDE_CODE_OAUTH_TOKEN`, valid for one year) expires.\n\n"
            "Set it once under Settings → Secrets and variables → Actions → Variables, as an ISO date "
            "(YYYY-MM-DD) of the day the token was created with `claude setup-token`.\n", encoding="utf-8")
    else:
        try:
            created = date.fromisoformat(token_created_at)
        except ValueError:
            created = None
        if created is None:
            findings["token"] = f"TOKEN_CREATED_AT is not an ISO date: {token_created_at!r}"
            (out_dir / "token.md").write_text(
                f"The repository variable `TOKEN_CREATED_AT` has the value `{token_created_at}`, "
                "which is not an ISO date (YYYY-MM-DD).\n", encoding="utf-8")
        else:
            expires = created + timedelta(days=TOKEN_VALID_DAYS)
            days_left = (expires - now.date()).days
            if days_left <= TOKEN_WARN_DAYS:
                findings["token"] = f"token expires on {expires} ({days_left} days left)"
                (out_dir / "token.md").write_text(
                    f"The Claude token (`CLAUDE_CODE_OAUTH_TOKEN`, created {created}) expires on **{expires}** "
                    f"({days_left} days left). After that every weekly run fails.\n\n"
                    "Renew it: run `claude setup-token`, update the repository secret "
                    "`CLAUDE_CODE_OAUTH_TOKEN`, and set the variable `TOKEN_CREATED_AT` to today's date. "
                    "This issue closes itself on the next watchdog run after that.\n", encoding="utf-8")
    log.info("watchdog findings: %s", findings or "none")
    return findings


def redact(text: str) -> str:
    for name in ("CLAUDE_CODE_OAUTH_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(name)
        if value and len(value) > 8:
            text = text.replace(value, "***")
    for pat in SECRET_PATTERNS:
        text = pat.sub("***", text)
    return text


def failure_report(log_file: Path | None, out: Path, lines: int = 80) -> None:
    ctx = publish_step.run_context()
    excerpt = "(no pipeline log was written; the job failed before the pipeline started)"
    if log_file and log_file.exists():
        tail = log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
        excerpt = redact("\n".join(tail))
    out.write_text(
        f"A TechWatch run failed on {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC "
        f"(trigger: {ctx.get('trigger')}). Nothing was published for the affected week; the failure is "
        f"recorded in the run log.\n\n"
        f"Run: {ctx.get('run_url', '(local)')}\n\n"
        f"Last {lines} log lines:\n\n```text\n{excerpt}\n```\n\n"
        "The Tuesday fallback run retries automatically if the week is still missing. "
        "This issue closes itself after the next successful run.\n", encoding="utf-8")
