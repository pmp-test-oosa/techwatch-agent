"""Step 8 - PUBLISH: digest JSON, index.json, run-log.json, profile JSON; optional git commit."""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from .config import ROOT

log = logging.getLogger("techwatch.publish")
RUN_LOG_MAX = 300


def _read(path: Path, default):
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    return default


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def public_profile(profile: dict) -> dict:
    keep = ("id", "name", "fictional", "employees", "location", "industry", "description",
            "competitors", "ecosystem")
    out = {k: profile.get(k) for k in keep}
    out["watch_fields"] = [{k: f.get(k) for k in ("id", "name", "short", "name_de", "description",
                                                   "keywords_en", "keywords_de")}
                           for f in profile["watch_fields"]]
    return out


def publish(data_dir: Path, profile: dict, digest_doc: dict, run_record: dict) -> Path:
    pid, week = profile["id"], digest_doc["week"]
    digest_path = data_dir / "digests" / pid / f"{week}.json"
    _write(digest_path, digest_doc)

    _write(data_dir / "profiles" / f"{pid}.json", public_profile(profile))

    index_path = data_dir / "index.json"
    index = _read(index_path, {"profiles": []})
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
    _write(index_path, index)

    runlog_path = data_dir / "run-log.json"
    runlog = _read(runlog_path, {"runs": []})
    runlog["runs"] = ([run_record] + runlog["runs"])[:RUN_LOG_MAX]
    _write(runlog_path, runlog)

    log.info("published %s, index.json (%d weeks), run-log.json (%d runs)",
             digest_path.relative_to(data_dir.parent) if data_dir.parent in digest_path.parents else digest_path,
             len(entry["weeks"]), len(runlog["runs"]))
    return digest_path


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def commit(data_dir: Path, profile_id: str, week: str) -> bool:
    git("add", str(data_dir))
    if git("diff", "--cached", "--quiet").returncode == 0:
        log.info("nothing to commit")
        return False
    res = git("commit", "-m", f"chore: digest {profile_id} {week}")
    if res.returncode != 0:
        raise RuntimeError(f"git commit failed: {res.stderr.strip()[:300]}")
    log.info("committed: chore: digest %s %s", profile_id, week)
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
