# TechWatch Agent

An autonomous weekly technology-watch agent for the producing Mittelstand (DACH). Every week it
collects research and news on the profile's technology fields, has an LLM read and score them, lets
deterministic code decide what is published, and updates a static website. It runs on a schedule
with no human in the loop: nobody starts, approves or feeds it.

> **The AI reads and scores. Code decides what gets published, and every item links to its original source.**

Profile: **TMG Technologie-Radar: Produzierender Mittelstand** (`profiles/tmg-radar.yaml`), weekly
technology monitoring for clients of TMG Technologie Management Gruppe, with four watch fields:
AI in production, Industrial IoT / edge / Industrie 4.0, robotics and cobots, and regulation and
sustainability for manufacturers (CBAM, CSRD, EU AI Act, Machinery Regulation).

Website: GitHub Pages, deployed by the workflow after every run. Cost: zero (free sources without
API keys, free GitHub Actions and Pages, LLM on an existing Claude subscription).

## How it works

```
GitHub Actions (Mon 05:17 UTC main run, Tue 05:17 UTC fallback)
  └─ python -m techwatch run --profile all --catch-up 1 --push
       1 LOAD       profiles/*.yaml
       2 COLLECT    arXiv API, Google News RSS (per field, date window in the query),
                    idw-online, MM MaschinenMarkt, Industry of Things (German RSS, field by keyword)
       3 NORMALIZE  one schema, spam filter, dedupe (also against earlier weeks)          [code]
       4 SCORE      Claude Haiku: relevance 0-10, signal, news type, reason, story label [AI]
       5 FILTER     relevance >= 7, max 20, >= 1 per field, max 6 per type, 1 per story   [code]
       6 DIGEST     Claude Sonnet: headline, summary, actions, top signal (ids only)     [AI]
                    code trims lists that are too long and logs it                       [code]
       7 VALIDATE   strict schema on the whole document, ids exist, links came from      [code]
                    collectors, dates inside the week; any violation = nothing published
       8 PUBLISH    site/data/digests/<id>/<YYYY>-W<WW>.json, index.json, run-log.json, commit, push
  └─ GitHub Pages deploy of /site
```

* A run covers the **last completed ISO week** (KW, Monday to Sunday, UTC).
* **Idempotent:** if the week already has a digest, the run is recorded as `skipped` and makes no
  LLM call. `--force` (or the `force` input of the manual run) regenerates it.
* **Fallback and catch-up:** the Tuesday run only does work if Monday did not publish. Every
  scheduled run also regenerates the previous week if it is still missing (marked as backfilled).
* **LLM:** no tools, JSON schema output, 3 attempts per call with backoff (each retry tells the model
  why the previous answer was rejected), then the run fails cleanly. Nothing invented or placeholder
  is ever published.
* **Sources:** a failing source is logged and never stops the run.
* **Every run writes run-log.json and commits**, also when it is skipped or fails.

## Self-monitoring (informs, never needs action at runtime)

| What | Where | Behaviour |
|---|---|---|
| Run failed | `techwatch.yml` | Failed record in `run-log.json`, issue **"TechWatch run failed"** created or commented with a redacted log excerpt; closed automatically after the next successful run |
| Digest stale (> 8 days) | `watchdog.yml`, daily 06:47 UTC | Issue **"TechWatch digest is stale"**, closed automatically when fresh |
| Claude token expiry | `watchdog.yml` | Reads repo variable `TOKEN_CREATED_AT`; issue **"TechWatch: Claude token needs attention"** 30 days before the 1-year expiry (or if the variable is missing) |
| Schedule keepalive | `watchdog.yml` | Re-enables both scheduled workflows daily. GitHub disables schedules in public repos after 60 days without activity; the weekly commits already count, this is a second guard |
| Status on the website | every page | Badge **OK / Delayed / Error**, last successful run, next scheduled run, from `run-log.json` |

## Repository layout

```
profiles/tmg-radar.yaml        the profile (add more YAML files for more profiles)
techwatch/                     the pipeline, one module per step, ops.py for self-monitoring
  sources/                     arxiv, google_news, rss (idw, maschinenmarkt, industry_of_things), fixtures
  llm/                         providers: claude_subscription (default), mock
site/                          the static website (GitHub Pages)
  data/                        published JSON, written only by the pipeline
archive/lindner/               retired fictional demo profile and its data (not shown on the site)
tests/                         offline tests + invented fixtures (fixtures never reach site/data)
tools/screenshots.py           Playwright design QA (390 px / 1440 px, light / dark)
.github/workflows/             techwatch.yml (digest), pages.yml (deploy), watchdog.yml
.github/scripts/               issue helpers (create-or-comment, close)
```

## Local use

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
python -m pytest -q               # offline tests, mock LLM
```

Dry run (invented fixtures + mock LLM, written to a temp folder, never to site/data):

```bash
python -m techwatch backfill --provider mock --dry-run --weeks 2
python -m techwatch serve --dry-run          # http://localhost:8000
```

Real sources with the mock LLM, still in a temp folder: add `--sources live`.
Real run with your own Claude login: `--provider claude_subscription` (without `--dry-run` it writes
to `site/data`). Useful flags: `--profile all`, `--today YYYY-MM-DD`, `--max-llm-calls N`, `--force`,
`--catch-up N`, `--commit`, `--push`.

## Setup (one time)

1. **Secret** `CLAUDE_CODE_OAUTH_TOKEN`: run `claude setup-token` and store the token under
   Settings → Secrets and variables → Actions → Secrets. It is the only secret.
2. **Variable** `TOKEN_CREATED_AT`: the ISO date the token was created (e.g. `2026-10-19`), under
   Settings → Secrets and variables → Actions → Variables.
3. **GitHub Pages**: Settings → Pages → Source: **GitHub Actions**.
4. Optional test: Actions → *TechWatch weekly digest* → Run workflow (`backfill_weeks`, `force`).

After that nothing is needed at runtime.

## When the token expires (after one year)

The watchdog opens an issue 30 days before. Run `claude setup-token`, update the secret
`CLAUDE_CODE_OAUTH_TOKEN`, set `TOKEN_CREATED_AT` to today. If a week was missed in the meantime, the
next scheduled run catches up the previous week automatically; older gaps can be filled with a manual
run using `backfill_weeks`.

## Extending

* **New profile:** add `profiles/<id>.yaml` (`id` = file name, up to 8 keywords per language and
  field). The workflow runs every profile; the site shows a selector when there is more than one.
* **New source:** subclass `techwatch.sources.base.Source` (or `RssFeedSource` for a feed) and register
  it in `techwatch/sources/__init__.py`. Check the feed live first: it must deliver dates.

## Known limitations

* RSS feeds only carry their latest items (about 5 to 20 days), so backfilled weeks get fewer feed items.
* arXiv has few papers on some fields (e.g. regulation); the pipeline reports this honestly.
* Google News links are Google redirect URLs; they open the publisher's original article.
* GitHub starts scheduled runs late under load (typically 30 minutes to 2 hours).
* Cross-week dedupe compares titles, so a re-report in another language can appear twice.
