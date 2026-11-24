"""Offline tests: mock LLM + fixtures only. Run with `python -m pytest -q`."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from techwatch import digest as digest_step
from techwatch import filter as flt
from techwatch import ops
from techwatch import pipeline
from techwatch.__main__ import main
from techwatch.config import SITE_DATA_DIR
from techwatch.llm.mock import MockProvider
from techwatch.normalize import normalize_and_dedupe
from techwatch.pipeline import PipelineError, RunOptions, check_safe
from techwatch.profile import load_profile
from techwatch.sources.rss import RssFeedSource
from techwatch.validate import ValidationError, validate
from techwatch.windows import Window, backfill_windows, weekly_window

PROFILE = "tmg-radar"
FIELDS = ["ai-production", "iiot-edge", "robotics", "regulation"]


def item(i, field="ai-production", rel=8, ntype="industry", signal="watch", day=15, story=None):
    return {"id": f"gn-{i:010x}", "source": "google_news", "title": f"Headline {i} " + " ".join(f"w{i}x{k}" for k in range(5)),
            "url": f"https://example.org/{i}", "date": f"2026-10-{day:02d}", "snippet": "", "watch_field": field,
            "news_type": ntype, "signal": signal, "relevance": rel, "reason": "because it matters", "publisher": f"P{i}",
            "story": story or f"story {i} unique{i}", "also_reported_by": []}


def doc_for(items, window, **over):
    doc = {"schema_version": 1, "profile": PROFILE, "week": window.label, "window": window.as_dict(),
           "generated_at": "2026-10-19T06:00:00+00:00", "backfilled": False, "quiet_week": len(items) < 5,
           "headline": "Short headline here", "summary": [{"text": "A summary line", "item_ids": [items[0]["id"]]}],
           "actions": [], "top_signal": items[0]["id"], "stats": {}, "items": items}
    doc.update(over)
    return doc


def runs_of(out):
    return json.loads((out / "run-log.json").read_text(encoding="utf-8"))["runs"]


def dry(out, *extra, today="2026-10-19", cmd="run"):
    return main([cmd, "--profile", PROFILE, "--provider", "mock", "--dry-run", "--out", str(out),
                 "--today", today, *extra])


# ---------------------------------------------------------------- windows

def test_windows_monday_is_previous_iso_week():
    w = weekly_window(date(2026, 10, 19))
    assert (w.start, w.end, w.label) == (date(2026, 10, 12), date(2026, 10, 18), "2026-W42")
    assert [x.label for x in backfill_windows(2, date(2026, 10, 19))] == ["2026-W40", "2026-W41", "2026-W42"]


def test_windows_other_weekdays_cover_the_last_completed_iso_week():
    for day in range(27, 32):  # Tue 27 .. Sat 31 Oct
        w = weekly_window(date(2026, 10, day))
        assert (w.start, w.end, w.label) == (date(2026, 10, 19), date(2026, 10, 25), "2026-W43")
    assert weekly_window(date(2026, 11, 1)).label == "2026-W43"
    assert all(w.start.weekday() == 0 and w.end.weekday() == 6 for w in backfill_windows(4, date(2026, 10, 29)))


def test_next_scheduled_runs_monday_and_tuesday_0517():
    now = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)  # Tuesday noon
    nxt = ops.next_scheduled_runs(now, 2)
    assert [t.isoformat() for t in nxt] == ["2026-11-30T05:17:00+00:00", "2026-12-01T05:17:00+00:00"]


# ---------------------------------------------------------------- profile, sources, dedupe

def test_tmg_profile_loads_with_keyword_limits():
    p = load_profile(PROFILE)
    assert [f["id"] for f in p["watch_fields"]] == FIELDS
    assert all(len(f["keywords_en"]) <= 8 and len(f["keywords_de"]) <= 8 for f in p["watch_fields"])
    assert not p.get("fictional")


def test_rss_items_are_assigned_by_keywords_and_unmatched_dropped():
    p = load_profile(PROFILE)
    src = RssFeedSource()
    src._entries = [
        {"title": "Neuer Cobot für die Montage", "url": "https://x.de/1", "date": date(2026, 10, 14), "snippet": "Robotik"},
        {"title": "CBAM-Pflichten steigen", "url": "https://x.de/2", "date": date(2026, 10, 14), "snippet": "CSRD auch"},
        {"title": "Fußball: Ergebnisse vom Wochenende", "url": "https://x.de/3", "date": date(2026, 10, 14), "snippet": ""},
    ]
    w = Window(date(2026, 10, 12), date(2026, 10, 18))
    got = {f["id"]: [i["url"] for i in src.collect(p, f, w)] for f in p["watch_fields"]}
    assert got == {"ai-production": [], "iiot-edge": [], "robotics": ["https://x.de/1"], "regulation": ["https://x.de/2"]}


def test_dedupe_and_spam():
    raw = [
        {"source": "google_news", "title": "Big news", "url": "https://x.org/a?utm_source=y", "date": date(2026, 10, 14),
         "snippet": "", "publisher": "X", "watch_field": "robotics"},
        {"source": "google_news", "title": "Big news!", "url": "https://x.org/b", "date": date(2026, 10, 14),
         "snippet": "", "publisher": "Y", "watch_field": "robotics"},
        {"source": "google_news", "title": "Cobot Market Size to reach USD 5 billion by 2032", "url": "https://x.org/c",
         "date": date(2026, 10, 14), "snippet": "", "publisher": "Z", "watch_field": "robotics"},
        {"source": "google_news", "title": "Old story", "url": "https://x.org/old", "date": date(2026, 10, 14),
         "snippet": "", "publisher": "Z", "watch_field": "robotics"},
    ]
    out, stats = normalize_and_dedupe(raw, ({"https://x.org/old"}, set()))
    assert [o["title"] for o in out] == ["Big news"] and out[0]["url"] == "https://x.org/a"
    assert (stats["duplicate"], stats["spam"], stats["already_published"]) == (1, 1, 1)


# ---------------------------------------------------------------- filter

def test_filter_rules():
    items = [item(i, ntype="industry", rel=9) for i in range(10)]
    items += [item(100 + i, ntype="research", rel=8) for i in range(10)]
    items += [item(200 + i, ntype="funding", rel=7) for i in range(10)]
    items += [item(300, field="regulation", ntype="industry", rel=7)]  # field coverage beats rank
    items += [item(400 + i, rel=6) for i in range(5)]
    kept = flt.select(items, FIELDS)
    assert len(kept) <= 20 and all(k["relevance"] >= 7 for k in kept)
    types = [k["news_type"] for k in kept]
    assert max(types.count(t) for t in set(types)) <= 6
    assert any(k["watch_field"] == "regulation" for k in kept)


def test_story_collapse_keeps_best_and_notes_outlets():
    a = item(1, rel=9, story="Siemens Industrial Copilot shop floor launch")
    b = item(2, rel=8, story="Siemens Industrial Copilot launch")
    c = item(3, rel=8, story="KUKA mobile robot stake")
    kept = flt.select([b, a, c], FIELDS)
    assert [k["id"] for k in kept] == [a["id"], c["id"]] and kept[0]["also_reported_by"] == ["P2"]


def test_story_already_published_in_earlier_week_is_dropped():
    prev = [{**item(1), "title": "Speira inaugurates €40 million aluminium recycling furnace"},
            {**item(2), "title": "Bühler-Megacasting kommt im neuen Volvo EX60 auf die Strasse"}]
    again = {**item(3, rel=7), "title": "Speira: €40 Million Investment Strengthens Aluminium Circular Economy"}
    follow_up = {**item(4, rel=8), "title": "Assembly Line Hiccups Hobble Volvo EX60 North American Launch Manufacturing"}
    assert [k["id"] for k in flt.select([again, follow_up], FIELDS, published=prev)] == [follow_up["id"]]


# ---------------------------------------------------------------- digest trimming and validation

def test_trim_cuts_overlong_lists_and_reports_it():
    d = {"headline": "h", "summary": [{"text": f"s{i}", "item_ids": ["a", "b", "c", "d", "e"]} for i in range(7)],
         "actions": [{"text": f"a{i}", "item_ids": []} for i in range(4)], "top_signal": "a"}
    out, notes = digest_step.trim(d)
    assert len(out["summary"]) == 5 and len(out["actions"]) == 3
    assert all(len(e["item_ids"]) == 4 for e in out["summary"])
    assert any("actions: 4 entries trimmed to 3" in n for n in notes)


def test_validate_catches_violations():
    w = Window(date(2026, 10, 12), date(2026, 10, 18))
    good = item(1)
    collected = {good["id"]: good["url"]}
    validate(doc_for([good], w), w, collected, FIELDS, publish_to_site=True)
    bad = [
        doc_for([{**good, "date": "2026-10-20"}], w),                                   # outside window
        doc_for([{**good, "url": "https://evil.example/x"}], w),                        # link not from collector
        doc_for([good], w, top_signal="gn-9999999999"),                                  # unknown id
        doc_for([{**good, "source": "fixture"}], w),                                     # fixture to site/data
        doc_for([good], w, headline=" ".join(["word"] * 13)),                            # headline words
        doc_for([good], w, actions=[{"text": "act now", "item_ids": []}] * 4),           # schema maxItems
        doc_for([{**good, "relevance": 6}], w),                                          # below threshold
        doc_for([{**good, "reason": "x" * 301}], w),                                     # string limit
        doc_for([{**good, "signal": "panic"}], w),                                       # enum
        doc_for([{**good, "extra": 1}], w),                                              # unknown field
        doc_for([good], w, quiet_week=False),                                            # flag mismatch
    ]
    for d in bad:
        with pytest.raises(ValidationError):
            validate(d, w, collected, FIELDS, True)


def test_mock_or_fixtures_never_target_site_data():
    with pytest.raises(PipelineError):
        check_safe(RunOptions(provider="mock", sources=["google_news"], data_dir=SITE_DATA_DIR, max_llm_calls=10))
    with pytest.raises(PipelineError):
        check_safe(RunOptions(provider="claude_subscription", sources=["fixture"], data_dir=SITE_DATA_DIR,
                              max_llm_calls=10))


def test_retry_feeds_validator_error_back_to_the_model():
    from techwatch.llm.base import Provider

    class Flaky(Provider):
        backoff_s = (0, 0)
        seen: list = []

        def _digest(self, items, profile, feedback=None):
            self.seen.append(feedback)
            words = 13 if feedback is None else 8
            return {"headline": " ".join(["word"] * words), "summary": [{"text": "a summary", "item_ids": []}],
                    "actions": [{"text": "an action", "item_ids": []}], "top_signal": items[0]["id"]}

    p = Flaky(max_calls=10)
    out = p.write_digest([item(1)], {})
    assert len(out["headline"].split()) == 8 and p.calls == 2
    assert p.seen[0] is None and "13 words" in p.seen[1]


# ---------------------------------------------------------------- end to end (dry run)

def test_dry_run_backfill_end_to_end(tmp_path):
    out = tmp_path / "data"
    assert dry(out, "--weeks", "2", cmd="backfill") == 0
    weeks = json.loads((out / "index.json").read_text(encoding="utf-8"))["profiles"][0]["weeks"]
    assert [w["week"] for w in weeks] == ["2026-W42", "2026-W41", "2026-W40"]
    assert [w["backfilled"] for w in weeks] == [False, True, True]
    runs = runs_of(out)
    assert [r["status"] for r in runs] == ["published"] * 3 and all(r["llm_calls"] >= 2 for r in runs)
    doc = json.loads((out / "digests" / PROFILE / "2026-W42.json").read_text(encoding="utf-8"))
    assert doc["top_signal"] in {i["id"] for i in doc["items"]} and doc["dry_run"] is True
    assert all(i["url"].startswith("https://example.com/fixture/") for i in doc["items"])
    assert (out / "profiles" / f"{PROFILE}.json").exists()


def test_dry_run_is_reproducible_for_any_reference_date(tmp_path):
    out = tmp_path / "data"
    assert dry(out, "--weeks", "2", today="2025-03-03", cmd="backfill") == 0
    runs = runs_of(out)
    assert [r["week"] for r in runs] == ["2025-W09", "2025-W08", "2025-W07"]
    assert all(r["collected"] > 0 and r["kept"] > 0 for r in runs)


def test_second_run_for_the_same_week_is_skipped_without_llm(tmp_path):
    out = tmp_path / "data"
    assert dry(out) == 0
    first = (out / "digests" / PROFILE / "2026-W42.json").read_text(encoding="utf-8")
    assert dry(out, today="2026-10-20") == 0  # Tuesday fallback, same week
    assert (out / "digests" / PROFILE / "2026-W42.json").read_text(encoding="utf-8") == first
    runs = runs_of(out)
    assert [r["status"] for r in runs] == ["skipped", "published"] and runs[0]["llm_calls"] == 0
    assert dry(out, "--force") == 0
    assert runs_of(out)[0]["status"] == "published"


def test_catch_up_fills_a_missing_previous_week_once(tmp_path):
    out = tmp_path / "data"
    assert dry(out, "--catch-up", "1") == 0
    runs = runs_of(out)
    assert [(r["week"], r["status"], r["backfilled"]) for r in runs] == [
        ("2026-W42", "published", False), ("2026-W41", "published", True)]
    assert dry(out, "--catch-up", "1", today="2026-10-20") == 0  # existing previous week: silent
    assert [(r["week"], r["status"]) for r in runs_of(out)][:1] == [("2026-W42", "skipped")]
    assert len(runs_of(out)) == 3


def test_failure_is_recorded_and_nothing_is_published(tmp_path, monkeypatch):
    class Broken(MockProvider):
        def _digest(self, items, profile, feedback=None):
            raise RuntimeError("model unavailable")
    monkeypatch.setattr(pipeline, "get_provider", lambda name, calls: Broken(calls))
    out = tmp_path / "data"
    assert dry(out) == 1
    assert not (out / "digests" / PROFILE / "2026-W42.json").exists()
    rec = runs_of(out)[0]
    assert rec["status"] == "failed" and rec["stage"] == "digest" and "model unavailable" in rec["error"]
    assert rec["llm_calls"] >= 3 + 1  # three digest attempts after scoring


def test_overlong_digest_lists_are_trimmed_and_logged(tmp_path, monkeypatch):
    class Wordy(MockProvider):
        def _digest(self, items, profile, feedback=None):
            d = super()._digest(items, profile, feedback)
            d["actions"] = d["actions"] + [{"text": "A fourth action", "item_ids": []}]
            return d
    monkeypatch.setattr(pipeline, "get_provider", lambda name, calls: Wordy(calls))
    out = tmp_path / "data"
    assert dry(out) == 0
    doc = json.loads((out / "digests" / PROFILE / "2026-W42.json").read_text(encoding="utf-8"))
    assert len(doc["actions"]) == 3
    assert runs_of(out)[0]["trimmed"] == ["actions: 4 entries trimmed to 3"]


# ---------------------------------------------------------------- self-monitoring

def test_watchdog_flags_stale_digest_and_token_expiry(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "index.json").write_text(json.dumps({"profiles": [{"id": PROFILE, "weeks": [
        {"week": "2026-W46", "generated_at": "2026-11-16T07:00:00+00:00"}]}]}), encoding="utf-8")
    now = datetime(2026, 11, 25, 7, 0, tzinfo=timezone.utc)
    f = ops.watchdog(data, tmp_path / "w", "2025-12-01", now=now)
    assert set(f) == {"stale", "token"} and (tmp_path / "w" / "stale.md").exists()
    f = ops.watchdog(data, tmp_path / "w", "2026-10-19", now=datetime(2026, 11, 20, tzinfo=timezone.utc))
    assert f == {} and not (tmp_path / "w" / "stale.md").exists() and not (tmp_path / "w" / "token.md").exists()
    assert "token" in ops.watchdog(data, tmp_path / "w", "", now=now)


def test_record_failure_once_per_github_run(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setenv("TW_SCHEDULE", "17 5 * * 2")
    assert ops.record_failure(tmp_path, [PROFILE], "Install Claude Code failed", date(2026, 11, 24)) == 1
    assert ops.record_failure(tmp_path, [PROFILE], "again", date(2026, 11, 24)) == 0
    rec = runs_of(tmp_path)[0]
    assert (rec["status"], rec["week"], rec["trigger"], rec["run_id"]) == ("failed", "2026-W47", "schedule (fallback)", "123")


def test_failure_report_redacts_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat01-SECRETSECRETSECRET")
    log = tmp_path / "pipeline.log"
    log.write_text("start\nauth sk-ant-oat01-SECRETSECRETSECRET failed\n", encoding="utf-8")
    ops.failure_report(log, tmp_path / "issue.md")
    text = (tmp_path / "issue.md").read_text(encoding="utf-8")
    assert "SECRET" not in text and "auth *** failed" in text


def test_german_digest_text_is_rejected_so_the_model_retries_in_english():
    from techwatch.llm.schemas import looks_german
    assert looks_german("Für Hersteller vernetzter Maschinen gelten laut Bericht Meldepflichten, daher braucht es jetzt einen Prozess.")
    assert looks_german("CRA-Meldepflichten gelten bereits; CBAM-Regeln für Drittlandspreise und Gratiszertifikate werden konkreter")
    assert not looks_german("Germany's Bundesrat cleared the Cyber Resilience Act law, so die casting makers face new duties.")
    assert not looks_german("Siemens extends its industrial AI copilot to shop floor maintenance teams")


def test_unreachable_feed_is_tried_only_once_per_run(monkeypatch):
    p = load_profile(PROFILE)
    src = RssFeedSource()
    calls = []

    def boom(url):
        calls.append(url)
        raise TimeoutError("timed out")
    monkeypatch.setattr(src, "http_get", boom)
    w = Window(date(2026, 10, 12), date(2026, 10, 18))
    for f in p["watch_fields"]:
        with pytest.raises(Exception):
            src.collect(p, f, w)
    assert len(calls) == 1
