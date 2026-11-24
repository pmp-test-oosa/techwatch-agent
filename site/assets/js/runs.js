/* Run log: every pipeline run with real counts, including skipped and failed runs. */
(async function () {
  "use strict";
  const { esc, icon, fmtRange, fmtDateTime, kw, NEWS_TYPES, state } = TW;
  await TW.init("runs");
  const main = document.getElementById("main");
  const runs = state.runs.filter((r) => !state.profileId || r.profile === state.profileId);
  const status = TW.computeStatus(new Date());

  const SOURCE_LABELS = { arxiv: "arXiv", google_news: "Google News", fixture: "Fixtures", idw: "idw",
    maschinenmarkt: "MaschinenMarkt", industry_of_things: "Industry of Things" };
  const published = runs.filter((r) => r.status === "published" || !r.status);
  const sources = Array.from(new Set(published.flatMap((r) => Object.keys(r.items_per_source || {}))));
  const sum = (list, f) => list.reduce((a, r) => a + (Number(f(r)) || 0), 0);
  const fmtDur = (s) => (s >= 60 ? `${Math.floor(s / 60)}m ${Math.round(s % 60)}s` : `${(+s).toFixed(1)}s`);
  const NCOLS = 10;

  function head(r) {
    const models = r.models ? (r.provider === "mock" ? "mock" : `${esc(r.models.score)} / ${esc(r.models.digest)}`) : "";
    const st = r.status || "published";
    const flags = [
      st === "failed" ? '<span class="flag flag--failed">failed</span>' : "",
      st === "skipped" ? '<span class="flag flag--skipped">skipped</span>' : "",
      st === "superseded" ? '<span class="flag">superseded</span>' : "",
      st === "published" ? (r.backfilled ? '<span class="flag flag--yes">backfilled</span>' : '<span class="flag">weekly</span>') : "",
      r.dry_run ? '<span class="flag">dry run</span>' : "",
    ].join("");
    const trigger = r.trigger ? (r.run_url ? `<a href="${esc(r.run_url)}" target="_blank" rel="noopener noreferrer">${esc(r.trigger)}</a>` : esc(r.trigger)) : "";
    return `<td><span class="strong">KW ${kw(r.week).n}</span> <span class="muted">${kw(r.week).year}</span><span class="sub">${fmtRange(r.window.start, r.window.end)}</span></td>
      <td>${fmtDateTime(r.generated_at)}<span class="sub">${[trigger, models].filter(Boolean).join(" · ")}</span>
        <span class="flags">${flags}</span></td>`;
  }

  const rows = runs.map((r) => {
    const st = r.status || "published";
    if (st === "skipped" || st === "failed") {
      const msg = st === "failed"
        ? `<span class="err">Failed in step <b>${esc(r.stage || "?")}</b>: ${esc(r.error || "")}</span>`
        : esc(r.note || "Digest already existed; nothing to do.");
      return `<tr class="is-${st}">${head(r)}<td colspan="${NCOLS - 4}"><span class="note-cell">${msg}</span></td>
        <td class="num">${r.llm_calls ?? 0}</td><td class="num">${fmtDur(r.duration_s || 0)}</td></tr>`;
    }
    const types = Object.keys(NEWS_TYPES).map((t) => {
      const n = (r.per_news_type || {})[t] || 0;
      return `<span class="${n ? "" : "zero"}" title="${esc(NEWS_TYPES[t])}: ${n}">${icon(t)}${n}</span>`;
    }).join("");
    const sig = r.per_signal || {};
    const errs = r.errors || [];
    const trimmed = (r.trimmed || []).length ? `<span class="sub" title="${esc(r.trimmed.join("\n"))}">trimmed: ${r.trimmed.length}</span>` : "";
    return `<tr>${head(r)}
      <td>${sources.map((s) => `<span class="srcline">${esc(SOURCE_LABELS[s] || s)} <b>${(r.items_per_source || {})[s] ?? "–"}</b></span>`).join("")}</td>
      <td class="num">${r.collected}<span class="sub">${r.after_dedupe} unique</span></td>
      <td class="num">${r.scored}</td>
      <td class="num"><span class="strong">${r.kept}</span>${trimmed}</td>
      <td><span class="typecounts">${types}</span></td>
      <td class="num"><span style="color:var(--threat-ink)">${sig.threat || 0}</span> · <span style="color:var(--opportunity-ink)">${sig.opportunity || 0}</span> · <span style="color:var(--watch-ink)">${sig.watch || 0}</span>
        ${errs.length ? `<span class="sub err" title="${esc(errs.join("\n"))}">${errs.length} source error${errs.length === 1 ? "" : "s"}</span>` : ""}</td>
      <td class="num">${r.llm_calls}</td>
      <td class="num">${fmtDur(r.duration_s || 0)}</td>
    </tr>`;
  }).join("");

  const next = status.next[0];
  main.innerHTML = `
    <section class="wrap page-head">
      <p class="kicker">Run log</p>
      <h1>Every run, with real counts</h1>
      <p class="lede">The pipeline runs on its own every Monday at 05:17 UTC, with a Tuesday fallback if the week is still missing. Every run leaves a row here: published (with what each source returned, what the AI scored and what code kept), skipped (the week already existed) or failed (nothing published, with the step and the error).</p>
      <dl class="stats">
        <div class="stat"><dt>Status</dt><dd class="stat__status">${TW.statusChip(status.level)}<span class="sub">${esc(status.text)}</span></dd></div>
        <div class="stat"><dt>Last successful run</dt><dd class="stat__small">${status.lastSuccess ? esc(fmtDateTime(status.lastSuccess.generated_at)) : "none yet"}</dd></div>
        <div class="stat"><dt>Next scheduled run</dt><dd class="stat__small">${next ? esc(fmtDateTime(next.at.toISOString())) : "–"}${next && next.fallback ? '<span class="sub">fallback run</span>' : ""}</dd></div>
        <div class="stat"><dt>Published · LLM calls</dt><dd>${published.length} · ${sum(runs, (r) => r.llm_calls)}</dd></div>
      </dl>
    </section>
    <section class="wrap">
      ${runs.length ? `<div class="table-wrap" tabindex="0" role="region" aria-label="Run log table, scrolls horizontally">
        <table>
          <caption>Signals: threats · opportunities · watch. Scheduled runs start at 05:17 UTC; GitHub may start them up to about two hours later.</caption>
          <thead><tr>
            <th scope="col">Week / window</th><th scope="col">Run</th>
            <th scope="col">Items per source</th>
            <th scope="col" class="num">Scanned</th><th scope="col" class="num">Scored</th><th scope="col" class="num">Kept</th>
            <th scope="col">Kept per news type</th><th scope="col" class="num">Signals</th><th scope="col" class="num">LLM calls</th><th scope="col" class="num">Duration</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table></div>` : `<div class="empty"><h3>No runs yet</h3><p>The first run appears here after the pipeline has run once.</p></div>`}
    </section>`;
})();
