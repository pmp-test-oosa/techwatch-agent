"""Step 8 - PUBLISH: digest JSON, index.json, profile JSON, run-log.json; git commit and push."""
from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

from .config import ROOT

log = logging.getLogger("techwatch.publish")
RUN_LOG_MAX = 300


def read_json(path: Path, default):
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def digest_path(data_dir: Path, profile_id: str, week: str) -> Path:
    return data_dir / "digests" / profile_id / f"{week}.json"


def run_context() -> dict:
    """Where a run came from (GitHub Actions or local). Never contains secrets."""
    event = os.environ.get("GITHUB_EVENT_NAME")
    schedule = os.environ.get("TW_SCHEDULE", "")
    if event == "schedule":
        trigger = "schedule (fallback)" if schedule.strip().endswith("* * 2") else "schedule"
    elif event == "workflow_dispatch":
        trigger = "manual"
    else:
        trigger = event or "local"
    ctx = {"trigger": trigger}
    if os.environ.get("GITHUB_RUN_ID"):
        ctx["run_id"] = os.environ["GITHUB_RUN_ID"]
        ctx["run_url"] = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
                          f"{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ['GITHUB_RUN_ID']}")
    return ctx


def public_profile(profile: dict) -> dict:
    keep = ("id", "name", "fictional", "audience", "industry", "description", "companies_to_watch")
    out = {k: profile.get(k) for k in keep}
    out["watch_fields"] = [{k: f.get(k) for k in ("id", "name", "short", "name_de", "description",
                                                   "keywords_en", "keywords_de")}
                           for f in profile["watch_fields"]]
    return out


def append_run(data_dir: Path, record: dict) -> None:
    path = data_dir / "run-log.json"
    runlog = read_json(path, {"runs": []})
    runlog["runs"] = ([record] + runlog["runs"])[:RUN_LOG_MAX]
    write_json(path, runlog)
    log.info("run-log.json: %s %s %s (%d runs)", record.get("profile"), record.get("week"),
             record.get("status"), len(runlog["runs"]))


def publish(data_dir: Path, profile: dict, digest_doc: dict, run_record: dict) -> Path:
    pid, week = profile["id"], digest_doc["week"]
    path = digest_path(data_dir, pid, week)
    write_json(path, digest_doc)
    write_json(data_dir / "profiles" / f"{pid}.json", public_profile(profile))

    index_path = data_dir / "index.json"
    index = read_json(index_path, {"profiles": []})
    entry = next((p for p in index["profiles"] if p["id"] == pid), None)
    if entry is None:
        entry = {"id": pid, "weeks": []}
        index["profiles"].append(entry)
    entry.update({"name": profile["name"], "fictional": bool(profile.get("fictional"))})
    s = digest_doc["stats"]
    week_entry = {
        "week": week,
        "file": f"digests/{pid}/{week}.json",
        "window": digest_doc["window"],
        "headline": digest_doc["headline"],
        "kept": s["kept"],
        "scanned": s["scanned"],
        "signals": {"threat": s["threats"], "opportunity": s["opportunities"], "watch": s["watch"]},
        "backfilled": digest_doc["backfilled"],
        "quiet_week": digest_doc["quiet_week"],
        "generated_at": digest_doc["generated_at"],
    }
    entry["weeks"] = sorted([w for w in entry["weeks"] if w["week"] != week] + [week_entry],
                            key=lambda w: w["week"], reverse=True)
    index["profiles"].sort(key=lambda p: p["id"])
    index["updated_at"] = digest_doc["generated_at"]
    write_json(index_path, index)
    append_run(data_dir, run_record)
    log.info("published %s (%d weeks in index)", path.name, len(entry["weeks"]))
    return path


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def commit(data_dir: Path, message: str) -> bool:
    git("add", str(data_dir))
    if git("diff", "--cached", "--quiet").returncode == 0:
        log.info("nothing to commit")
        return False
    res = git("commit", "-m", message)
    if res.returncode != 0:
        raise RuntimeError(f"git commit failed: {res.stderr.strip()[:300]}")
    log.info("committed: %s", message)
    return True


def push() -> None:
    for attempt in range(3):
        res = git("push")
        if res.returncode == 0:
            log.info("pushed")
            return
        log.warning("push rejected (attempt %d), rebasing: %s", attempt + 1, res.stderr.strip()[:200])
        git("pull", "--rebase")
    raise RuntimeError("git push failed after 3 attempts")
