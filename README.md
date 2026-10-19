# TechWatch Agent

A weekly technology-watch agent for small and mid-sized German manufacturers (Mittelstand).
Every Monday it collects research and news for the client's technology fields, has an LLM read
and score them, lets deterministic code decide what is published, and updates a static website.

> **The AI reads and scores. Code decides what gets published, and every item links to its original source.**

Demo client: **Lindner Präzisionsguss GmbH** (fictional), an aluminium die caster for e-mobility
structural parts, with four watch fields: gigacasting, recycled/low-carbon alloys, AI-based casting
defect detection, and digital twins/simulation. The company is invented; the news is real.

Zero cost: free sources without API keys, free GitHub Actions, free Netlify hosting, and the LLM runs
on an existing Claude subscription through Claude Code in headless mode.

## How it works

```
GitHub Actions (cron Mon 06:00 UTC, or manual)
  └─ python -m techwatch run
       1 LOAD       profiles/<id>.yaml
       2 COLLECT    arXiv API + Google News RSS, per watch field, date window in the query
       3 NORMALIZE  one schema, spam filter, dedupe (also against earlier weeks)       [code]
       4 SCORE      Claude Haiku: relevance 0-10, signal, news type, reason, story    [AI]
       5 FILTER     relevance >= 7, max 20, >= 1 per field, max 6 per type, 1/story   [code]
       6 DIGEST     Claude Sonnet: headline, summary, actions, top signal (ids only)  [AI]
       7 VALIDATE   ids exist, links came from collectors, dates inside the window     [code]
       8 PUBLISH    site/data/digests/<id>/<YYYY>-W<WW>.json, index.json, run-log.json, commit, push
  └─ Netlify redeploys /site (static HTML/CSS/JS, no build step, no server code)
```

* The LLM never uses tools. It gets the items on stdin and must return JSON that matches a schema
  (`claude -p ... --output-format json --json-schema ... --tools "" --permission-mode dontAsk`).
  Responses are validated again in Python; 2 retries with backoff (each retry tells the model why
  its previous answer was rejected), then the run fails cleanly.
* One item per story: the scoring model labels the underlying event of each item; code keeps the
  best item per story and lists the other outlets ("+3 more outlets"). Across weeks, re-reports of
  an announcement that was already published are dropped, while follow-ups with new facts stay.
* Budget per weekly run: at most 100 items, batches of 15, so at most 7 scoring calls + 1 digest call.
* Any validation error fails the run. Nothing is published for that week.
* A failing source is logged in the run log and never stops the run.
* Each item has two independent labels: **news type** (Research, Competitor moves, Industry & market,
  Funding & M&A, Regulation & standards, Events) and **signal** (threat, opportunity, watch), plus
  the **watch field**. The site filters by all three.

## Repository layout

```
profiles/lindner.yaml          client profile (add more YAML files for more clients)
techwatch/                     the pipeline, one module per step
  sources/                     source plugins: arxiv, google_news, fixtures (dry runs only)
  llm/                         providers: claude_subscription (default), mock
site/                          the static website (Netlify publish directory)
  data/                        published JSON, written only by the pipeline
tests/                         offline tests + fixtures (fixtures never reach site/data)
tools/screenshots.py           Playwright design QA (390 px / 1440 px, light / dark)
.github/workflows/techwatch.yml
netlify.toml
```

## Local setup

Requirements: Python 3.12, and for real runs Claude Code logged in with your Claude subscription.

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
python -m pytest -q               # offline tests, mock LLM
```

### Dry run (fixtures + mock LLM, writes to a temp folder, never to site/data)

```bash
python -m techwatch run --profile lindner --provider mock --dry-run
python -m techwatch backfill --profile lindner --provider mock --dry-run --weeks 2
python -m techwatch serve --dry-run          # http://localhost:8000
```

Real sources with the mock LLM, still in a temp folder:

```bash
python -m techwatch run --profile lindner --provider mock --dry-run --sources live
```

### Real run with your own Claude login

```bash
python -m techwatch run --profile lindner --provider claude_subscription --dry-run --sources live --max-llm-calls 2
```

Without `--dry-run`, output goes to `site/data` (the published data). Preview it with
`python -m techwatch serve`.

### Backfill (so the site is not empty at launch)

```bash
python -m techwatch backfill --profile lindner --weeks 2
```

This runs the full pipeline for the two previous weeks (oldest first) and then the current week, so
the site starts with three digests. Only real items with real publication dates are used. Past weeks
are marked on the site as "Generated retroactively on <date> from items published in this week".
A week with fewer than 5 kept items is published anyway as a "quiet week". It is never padded.

Week definition: a run covers the 7 full days that end yesterday (UTC). Run on a Monday, that is
exactly the previous ISO week (KW), which is how the weekly cron works.

Useful flags: `--profile all`, `--today YYYY-MM-DD` (pretend date), `--max-llm-calls N`,
`--commit` (commit each digest as `chore: digest <profile> <week>`), `--push`.

## Deploy

### 1. GitHub repository and secret

1. Push this repository to a **public** GitHub repository.
2. On your machine, create a long-lived subscription token (valid for one year):
   ```bash
   claude setup-token
   ```
3. In GitHub: **Settings → Secrets and variables → Actions → New repository secret**
   * Name: `CLAUDE_CODE_OAUTH_TOKEN`
   * Value: the token printed by `claude setup-token`

   This is the only secret. Never put it in a file, the site, or a commit.
4. **Settings → Actions → General → Workflow permissions** may stay read-only:
   the workflow requests `contents: write` itself.

### 2. Netlify (free plan)

1. Netlify → **Add new site → Import an existing project → GitHub**, pick the repository.
2. Branch: `main`. **Base directory:** empty. **Build command:** empty.
   **Publish directory:** `site`. (`netlify.toml` sets the same values.)
3. Deploy. Every push, including the weekly `chore: digest ...` commits, redeploys the site.

### 3. Manual run and backfill in CI

GitHub → **Actions → TechWatch weekly digest → Run workflow**.
`backfill_weeks` = `0` runs only the last 7 days; `2` regenerates the two previous weeks and then
the current week. The weekly schedule runs on its own every Monday at 06:00 UTC.

## When the token expires (after one year)

Symptoms: the weekly workflow fails in the step "Run pipeline" with an authentication error from
`claude`, and nothing is published (the site keeps showing the last good week).

Fix:
1. Run `claude setup-token` again on your machine (needs your Claude Pro/Max subscription).
2. GitHub → Settings → Secrets and variables → Actions → `CLAUDE_CODE_OAUTH_TOKEN` → **Update** and
   paste the new token.
3. Actions → Run workflow (optionally with `backfill_weeks` to fill missed weeks).

Put a calendar reminder about 11 months after creating the token.

## Extending

* **New client:** copy `profiles/lindner.yaml`, change `id` (must match the file name), watch
  fields, keywords, `arxiv_query` and `news_queries`. The workflow runs every profile (`--profile all`),
  and the site shows a client selector when there is more than one profile.
* **New source:** subclass `techwatch.sources.base.Source`, implement `collect(profile, field, window)`
  returning raw items with real dates and URLs, and register it in `techwatch/sources/__init__.py`.
* **Other LLM:** implement `_score` and `_digest` in a new `techwatch/llm/*.py` provider and select
  it with `LLM_PROVIDER`.

## Known limitations

* arXiv rarely has papers on die casting or aluminium recycling, so the Research share depends on
  the week. The pipeline reports this honestly instead of padding.
* Google News RSS links are Google redirect URLs. They open the publisher's original article.
* The relevance score is an LLM judgement. Code applies the publication rules on top of it, and the
  run log shows how many items each step kept.
* Cross-week story dedupe compares titles, so a re-report of last week's announcement in another
  language (e.g. an English story in KW 41 and its German version in KW 42) can appear twice.
