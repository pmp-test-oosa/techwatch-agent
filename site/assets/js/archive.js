/* Archive: timeline of weekly briefings. */
(async function () {
  "use strict";
  const { esc, fmtRange, fmtDate, kw, link } = TW;
  const st = await TW.init("archive");
  const main = document.getElementById("main");
  const weeks = (st.profileEntry && st.profileEntry.weeks) || [];

  const items = weeks.map((w) => {
    const k = kw(w.week);
    const sig = w.signals || {};
    const total = (sig.threat || 0) + (sig.opportunity || 0) + (sig.watch || 0);
    const pct = (n) => (total ? (100 * n) / total : 0).toFixed(1);
    const tags = [
      w.backfilled ? `<span class="tag tag--copper" title="Generated on ${esc(fmtDate(w.generated_at))}">Backfilled</span>` : "",
      w.quiet_week ? `<span class="tag">Quiet week</span>` : "",
    ].join("");
    return `<li class="tl">
      <a class="tl__card" href="${esc(link("index.html", { week: w.week }))}">
        <div><div class="tl__kw">KW ${k.n}</div><div class="tl__date">${fmtRange(w.window.start, w.window.end)}</div></div>
        <div><h2 class="tl__head">${esc(w.headline)}</h2>${tags ? `<div class="tl__tags">${tags}</div>` : ""}</div>
        <div>
          <div class="stack" role="img" aria-label="${sig.threat || 0} threats, ${sig.opportunity || 0} opportunities, ${sig.watch || 0} to watch">
            <span class="s-threat" style="width:${pct(sig.threat || 0)}%"></span><span class="s-opportunity" style="width:${pct(sig.opportunity || 0)}%"></span><span class="s-watch" style="width:${pct(sig.watch || 0)}%"></span>
          </div>
          <div class="sigcounts">
            <span class="sc"><span class="sigdot sigdot--threat" style="width:8px;height:8px;border-radius:50%"></span><b>${sig.threat || 0}</b> threats</span>
            <span class="sc"><span class="sigdot sigdot--opportunity" style="width:8px;height:8px;border-radius:50%"></span><b>${sig.opportunity || 0}</b> opportunities</span>
            <span class="sc"><span class="sigdot sigdot--watch" style="width:8px;height:8px;border-radius:50%"></span><b>${sig.watch || 0}</b> watch</span>
            <span class="sc"><b>${w.kept}</b> kept of ${w.scanned ?? "–"} scanned</span>
          </div>
        </div>
      </a></li>`;
  }).join("");

  main.innerHTML = `
    <section class="wrap page-head">
      <p class="kicker">Archive</p>
      <h1>Every weekly briefing</h1>
      <p class="lede">${weeks.length} week${weeks.length === 1 ? "" : "s"} published so far. Each digest covers one calendar week (KW) and links every item to its original source.</p>
    </section>
    <section class="wrap">
      ${weeks.length ? `<ol class="timeline">${items}</ol>` : `<div class="empty"><h3>No weeks published yet</h3><p>The archive fills up after the first weekly run.</p></div>`}
    </section>`;
})();
