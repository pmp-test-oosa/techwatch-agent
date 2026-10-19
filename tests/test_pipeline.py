"""Offline tests: mock LLM + fixtures only. Run with `python -m pytest -q`."""
from __future__ import annotations

import json
from datetime import date

import pytest

from techwatch import filter as flt
from techwatch.__main__ import main
from techwatch.config import SITE_DATA_DIR
from techwatch.normalize import normalize_and_dedupe
from techwatch.pipeline import PipelineError, RunOptions, check_safe
from techwatch.validate import ValidationError, validate
from techwatch.windows import Window, backfill_windows, weekly_window

FIELDS = ["gigacasting", "low-carbon-alloys", "defect-detection", "digital-twins"]


def item(i, field="gigacasting", rel=8, ntype="industry", signal="watch", day=15, story=None):
    return {"id": f"gn-{i:04d}", "source": "google_news", "title": f"Headline {i} " + " ".join(f"w{i}x{k}" for k in range(5)),
            "url": f"https://example.org/{i}", "date": f"2026-10-{day:02d}", "snippet": "", "watch_field": field,
            "news_type": ntype, "signal": signal, "relevance": rel, "reason": "because", "publisher": f"P{i}",
            "story": story or f"story {i} unique{i}"}


def test_windows_monday_is_previous_iso_week():
    w = weekly_window(date(2026, 10, 19))
    assert (w.start, w.end, w.label) == (date(2026, 10, 12), date(2026, 10, 18), "2026-W42")
    labels = [x.label for x in backfill_windows(2, date(2026, 10, 19))]
    assert labels == ["2026-W40", "2026-W41", "2026-W42"]


def test_filter_rules():
    items = [item(i, ntype="industry", rel=9) for i in range(10)]           # 10 industry, only 6 allowed
    items += [item(100 + i, ntype="research", rel=8) for i in range(10)]
    items += [item(200 + i, ntype="funding", rel=7) for i in range(10)]
    items += [item(300, field="digital-twins", ntype="industry", rel=7)]    # field coverage beats rank
    items += [item(400 + i, rel=6) for i in range(5)]                       # below threshold
    kept = flt.select(items, FIELDS)
    assert len(kept) <= 20
    assert all(k["relevance"] >= 7 for k in kept)
    types = [k["news_type"] for k in kept]
    assert max(types.count(t) for t in set(types)) <= 6
    assert any(k["watch_field"] == "digital-twins" for k in kept)


def test_story_collapse_keeps_best_and_notes_outlets():
    a = item(1, rel=9, story="Toyota Lexus China gigacasting plant")
    b = item(2, rel=8, story="Toyota China gigacasting plant")
    c = item(3, rel=8, story="Nemak battery housing order")
    kept = flt.select([b, a, c], FIELDS)
    assert [k["id"] for k in kept] == ["gn-0001", "gn-0003"]
    assert kept[0]["also_reported_by"] == ["P2"]


def test_story_labels_from_different_batches_still_match():
    a = item(1, rel=9, story="Toyota China gigacasting technology debut")
    b = item(2, rel=8, story="Toyota Lexus China gigacasting plant")
    c = item(3, rel=8, story="Europe aluminium scrap curbs analysis")
    d = item(4, rel=7, story="Aluminium scrap strategic raw material")
    kept = flt.select([a, b, c, d], FIELDS)
    assert [k["id"] for k in kept] == ["gn-0001", "gn-0003", "gn-0004"]


def test_story_already_published_in_earlier_week_is_dropped():
    # real cases from W40-W42: Speira re-report is dropped, the Volvo follow-up with new facts stays
    prev = [{**item(1, story="Speira €40 million recycling furnace"),
             "title": "Speira inaugurates €40 million aluminium recycling furnace"},
            {**item(2, story="Volvo EX60 Bühler megacasting launch"),
             "title": "Bühler-Megacasting kommt im neuen Volvo EX60 auf die Strasse"}]
    again = {**item(3, rel=7, story="Speira EUR 40M circular aluminium investment"),
             "title": "Speira: €40 Million Investment Strengthens Aluminium Circular Economy"}
    follow_up = {**item(4, rel=8, story="Volvo EX60 megacasting launch hurdles"),
                 "title": "Assembly Line Hiccups Hobble Volvo EX60 North American Launch Manufacturing"}
    kept = flt.select([again, follow_up], FIELDS, published=prev)
    assert [k["id"] for k in kept] == ["gn-0004"]


def test_dedupe_and_spam():
    raw = [
        {"source": "google_news", "title": "Big news", "url": "https://x.org/a?utm_source=y", "date": date(2026, 10, 14),
         "snippet": "", "publisher": "X", "watch_field": "gigacasting"},
        {"source": "google_news", "title": "Big news!", "url": "https://x.org/b", "date": date(2026, 10, 14),
         "snippet": "", "publisher": "Y", "watch_field": "gigacasting"},
        {"source": "google_news", "title": "Die Casting Market Size to reach USD 5 billion by 2032", "url": "https://x.org/c",
         "date": date(2026, 10, 14), "snippet": "", "publisher": "Z", "watch_field": "gigacasting"},
        {"source": "google_news", "title": "Old story", "url": "https://x.org/old", "date": date(2026, 10, 14),
         "snippet": "", "publisher": "Z", "watch_field": "gigacasting"},
    ]
    out, stats = normalize_and_dedupe(raw, ({"https://x.org/old"}, set()))
    assert [o["title"] for o in out] == ["Big news"]
    assert out[0]["url"] == "https://x.org/a"
    assert (stats["duplicate"], stats["spam"], stats["already_published"]) == (1, 1, 1)


def test_validate_catches_violations():
    w = Window(date(2026, 10, 12), date(2026, 10, 18))
    good = item(1)
    collected = {good["id"]: good["url"]}
    digest = {"headline": "Short headline", "summary": [{"text": "x", "item_ids": [good["id"]]}],
              "actions": [], "top_signal": good["id"]}
    validate(digest, [good], w, collected, FIELDS, publish_to_site=True)

    bad_date = {**good, "date": "2026-10-20"}
    with pytest.raises(ValidationError):
        validate(digest, [bad_date], w, collected, FIELDS, True)
    with pytest.raises(ValidationError):  # link not from the collector
        validate(digest, [{**good, "url": "https://evil.example/x"}], w, collected, FIELDS, True)
    with pytest.raises(ValidationError):  # unknown id referenced by the digest
        validate({**digest, "top_signal": "gn-9999"}, [good], w, collected, FIELDS, True)
    with pytest.raises(ValidationError):  # fixtures never go to site/data
        validate(digest, [{**good, "source": "fixture"}], w, collected, FIELDS, True)
    with pytest.raises(ValidationError):
        validate({**digest, "headline": " ".join(["word"] * 13)}, [good], w, collected, FIELDS, True)


def test_mock_or_fixtures_never_target_site_data():
    with pytest.raises(PipelineError):
        check_safe(RunOptions(provider="mock", sources=["google_news"], data_dir=SITE_DATA_DIR, max_llm_calls=10))
    with pytest.raises(PipelineError):
        check_safe(RunOptions(provider="claude_subscription", sources=["fixture"], data_dir=SITE_DATA_DIR,
                              max_llm_calls=10))


def test_dry_run_backfill_end_to_end(tmp_path):
    out = tmp_path / "data"
    assert main(["backfill", "--profile", "lindner", "--provider", "mock", "--dry-run", "--weeks", "2",
                 "--out", str(out), "--today", "2026-10-19"]) == 0
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    weeks = index["profiles"][0]["weeks"]
    assert [w["week"] for w in weeks] == ["2026-W42", "2026-W41", "2026-W40"]
    assert [w["backfilled"] for w in weeks] == [False, True, True]
    runs = json.loads((out / "run-log.json").read_text(encoding="utf-8"))["runs"]
    assert len(runs) == 3 and all(r["llm_calls"] >= 2 for r in runs)
    doc = json.loads((out / "digests" / "lindner" / "2026-W42.json").read_text(encoding="utf-8"))
    ids = {i["id"] for i in doc["items"]}
    assert doc["top_signal"] in ids and doc["dry_run"] is True
    assert all(i["url"].startswith("https://example.com/fixture/") for i in doc["items"])
    assert (out / "profiles" / "lindner.json").exists()


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
