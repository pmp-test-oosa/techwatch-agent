/* Run log: every pipeline run with real counts. */
(async function () {
  "use strict";
  const { esc, icon, fmtRange, fmtDateTime, kw, json, NEWS_TYPES, state } = TW;
  await TW.init("runs");
  const main = document.getElementById("main");
  let runs = [];
  try { runs = (await json("data/run-log.json")).runs || []; } catch (e) { runs = []; }
  if (state.profileId) runs = runs.filter((r) => r.profile === state.profileId);

  const SOURCE_LABELS = { arxiv: "arXiv", google_news: "Google News", fixture: "Fixtures" };
  const sources = Array.from(new Set(runs.flatMap((r) => Object.keys(r.items_per_source || {}))));
  const sum = (f) => runs.reduce((a, r) => a + (Number(f(r)) || 0), 0);
  const avgDur = runs.length ? sum((r) => r.duration_s) / runs.length : 0;
  const fmtDur = (s) => (s >= 60 ? `${Math.floor(s / 60)}m ${Math.round(s % 60)}s` : `${(+s).toFixed(1)}s`);

  const rows = runs.map((r) => {
    const types = Object.keys(NEWS_TYPES).map((t) => {
      const n = (r.per_news_type || {})[t] || 0;
      return `<span class="${n ? "" : "zero"}" title="${esc(NEWS_TYPES[t])}: ${n}">${icon(t)}${n}</span>`;
    }).join("");
    const sig = r.per_signal || {};
    const errs = (r.errors || []);
    const models = r.provider === "mock" ? "mock" : `${esc((r.models || {}).score)} / ${esc((r.models || {}).digest)}`;
    return `<tr>
      <td><span class="strong">KW ${kw(r.week).n}</span> <span class="muted">${kw(r.week).year}</span><span class="sub">${fmtRange(r.window.start, r.window.end)}</span></td>
      <td>${fmtDateTime(r.generated_at)}<span class="sub">${esc(r.provider)} · ${models}</span>
        <span class="flags">${r.backfilled ? '<span class="flag flag--yes">backfilled</span>' : '<span class="flag">weekly</span>'}${r.dry_run ? '<span class="flag">dry run</span>' : ""}</span></td>
      <td>${sources.map((s) => `<span class="srcline">${esc(SOURCE_LABELS[s] || s)} <b>${(r.items_per_source || {})[s] ?? "–"}</b></span>`).join("")}</td>
      <td class="num">${r.collected}<span class="sub">${r.after_dedupe} unique</span></td>
      <td class="num">${r.scored}</td>
      <td class="num"><span class="strong">${r.kept}</span></td>
      <td><span class="typecounts">${types}</span></td>
      <td class="num"><span style="color:var(--threat-ink)">${sig.threat || 0}</span> · <span style="color:var(--opportunity-ink)">${sig.opportunity || 0}</span> · <span style="color:var(--watch-ink)">${sig.watch || 0}</span></td>
      <td class="num">${r.llm_calls}</td>
      <td class="num">${fmtDur(r.duration_s || 0)}</td>
      <td>${errs.length ? `<span class="err" title="${esc(errs.join("\n"))}">${errs.length} source error${errs.length === 1 ? "" : "s"}</span>` : '<span class="muted">none</span>'}</td>
    </tr>`;
  }).join("");

  main.innerHTML = `
    <section class="wrap page-head">
      <p class="kicker">Run log</p>
      <h1>Every run, with real counts</h1>
      <p class="lede">One row per published weekly run: what each source returned, how many items survived deduplication, how many the AI scored, how many code kept, and what it cost in LLM calls and time. Failed runs publish nothing and appear in the GitHub Actions history instead.</p>
      <dl class="stats">
        <div class="stat"><dt>Runs</dt><dd>${runs.length}</dd></div>
        <div class="stat"><dt>Items scanned</dt><dd>${sum((r) => r.collected)}</dd></div>
        <div class="stat"><dt>LLM calls</dt><dd>${sum((r) => r.llm_calls)}</dd></div>
        <div class="stat"><dt>Avg. duration</dt><dd>${fmtDur(avgDur)}</dd></div>
      </dl>
    </section>
    <section class="wrap">
      ${runs.length ? `<div class="table-wrap" tabindex="0" role="region" aria-label="Run log table, scrolls horizontally">
        <table>
          <caption>Signals column: threats · opportunities · watch. Hover an error count for details.</caption>
          <thead><tr>
            <th scope="col">Week / window</th><th scope="col">Generated / LLM</th>
            <th scope="col">Items per source</th>
            <th scope="col" class="num">Scanned</th><th scope="col" class="num">Scored</th><th scope="col" class="num">Kept</th>
            <th scope="col">Kept per news type</th><th scope="col" class="num">Signals</th><th scope="col" class="num">LLM calls</th><th scope="col" class="num">Duration</th><th scope="col">Errors</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table></div>` : `<div class="empty"><h3>No runs yet</h3><p>The first run appears here after the pipeline publishes a digest.</p></div>`}
    </section>`;
})();
