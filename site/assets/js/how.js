/* How it works: 8-step pipeline diagram (inline SVG) and the core design rule. */
(async function () {
  "use strict";
  const { esc, icon } = TW;
  await TW.init("how");
  const main = document.getElementById("main");

  const STEPS = [
    { t: "Load", ai: false, d: ["Profile: watch fields,", "keywords EN + DE, competitors"],
      long: "Reads the client profile: four watch fields with English and German keywords, the competitors to watch and a short business description." },
    { t: "Collect", ai: false, d: ["arXiv + Google News RSS,", "date window in the query"],
      long: "Queries the arXiv API (by submission date) and Google News RSS (with after:/before: operators) for every watch field. Items outside the week are dropped. A failing source is logged and never stops the run." },
    { t: "Normalize + dedupe", ai: false, d: ["One schema, spam filter,", "dedupe vs. earlier weeks"],
      long: "Turns every item into one schema, removes press-release spam, duplicates and anything already published in an earlier week. Plain code, no AI." },
    { t: "Score", ai: true, d: ["Relevance 0–10, signal, type,", "reason · batches of 15"],
      long: "Claude Haiku rates each item for this client: relevance 0–10, threat / opportunity / watch, news type from a fixed list, and one client-specific sentence. No tools, JSON schema only." },
    { t: "Filter", ai: false, d: ["≥ 7/10 · max 20 · 1 per field", "max 6 per news type"],
      long: "Code decides what is kept: relevance 7 or higher, at most 20 items, at least one per watch field if available, at most 6 of the same news type." },
    { t: "Digest", ai: true, d: ["Headline, summary, actions,", "cites kept items by id only"],
      long: "Claude Sonnet writes the headline (max 12 words), up to 5 summary bullets, up to 3 actions and picks the top signal. It may only reference kept items by their id." },
    { t: "Validate", ai: false, d: ["ids, links, dates checked:", "any violation = no publish"],
      long: "A script checks that every referenced id exists, every link came from a collector and every date lies inside the week. One violation fails the run and nothing is published." },
    { t: "Publish", ai: false, d: ["JSON → /site/data, commit,", "push → Netlify redeploys"],
      long: "Writes the week's JSON, the archive index and the run log, commits and pushes. Netlify redeploys the static site from the repository." },
  ];

  const who = (s) => (s.ai ? "AI" : "CODE");

  function box(s, i, x, y, w, h, tall) {
    const cls = s.ai ? "d-ai" : "d-code";
    const ty = tall ? y + 36 : y + 70;
    const tx = tall ? x + 50 : x + 18;
    const dy = tall ? y + 62 : y + 96;
    return `<g class="${cls}">
      <rect class="d-box" x="${x}" y="${y}" width="${w}" height="${h}" rx="12"/>
      <circle class="d-num" cx="${x + 28}" cy="${y + (tall ? 31 : 30)}" r="14"/>
      <text class="d-numtxt" x="${x + 28}" y="${y + (tall ? 36 : 35)}" text-anchor="middle">${i + 1}</text>
      <text class="d-who" x="${x + w - 16}" y="${y + (tall ? 28 : 34)}" text-anchor="end">${who(s)}</text>
      <text class="d-title" x="${tx}" y="${ty}">${esc(s.t)}</text>
      ${s.d.map((line, j) => `<text class="d-desc" x="${tx}" y="${dy + j * 18}">${esc(line)}</text>`).join("")}
    </g>`;
  }
  const defs = `<defs><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 10 5 0 10z" class="d-arrowhead"/></marker></defs>`;

  // Wide: 2 rows x 4
  const W = 214, H = 132, xs = [3, 263, 523, 783], ys = [14, 244];
  let wide = defs;
  STEPS.forEach((s, i) => { wide += box(s, i, xs[i % 4], ys[Math.floor(i / 4)], W, H, false); });
  for (let r = 0; r < 2; r++) for (let c = 0; c < 3; c++) {
    const y = ys[r] + H / 2;
    wide += `<line class="d-line" x1="${xs[c] + W + 4}" y1="${y}" x2="${xs[c + 1] - 6}" y2="${y}" marker-end="url(#arr)"/>`;
  }
  wide += `<path class="d-line" d="M${xs[3] + W / 2} ${ys[0] + H + 4} V${ys[0] + H + 36} Q${xs[3] + W / 2} ${ys[0] + H + 48} ${xs[3] + W / 2 - 12} ${ys[0] + H + 48} H${xs[0] + W / 2 + 12} Q${xs[0] + W / 2} ${ys[0] + H + 48} ${xs[0] + W / 2} ${ys[0] + H + 60} V${ys[1] - 6}" marker-end="url(#arr)"/>`;
  wide += `<text class="d-note" x="500" y="${ys[0] + H + 42}" text-anchor="middle">only items with relevance ≥ 7 continue</text>`;

  // Tall: 1 column
  const TW_ = 336, TH = 96, GAP = 26;
  let tall = defs;
  STEPS.forEach((s, i) => {
    const y = 2 + i * (TH + GAP);
    tall += box(s, i, 2, y, TW_, TH, true);
    if (i < STEPS.length - 1) tall += `<line class="d-line" x1="170" y1="${y + TH + 3}" x2="170" y2="${y + TH + GAP - 5}" marker-end="url(#arr)"/>`;
  });
  const tallH = 2 + STEPS.length * TH + (STEPS.length - 1) * GAP + 2;

  main.innerHTML = `
    <section class="wrap page-head">
      <p class="kicker">How it works</p>
      <h1>A weekly agent with a strict division of labour</h1>
      <p class="lede">Every Monday at 06:00 UTC a GitHub Actions job runs eight steps for the past week. Two of them use an LLM; six are plain, deterministic code. The result is a static JSON file that this website reads.</p>
      <div class="rule"><p class="rule__label">Core design rule</p>
        <blockquote>The AI reads and scores. Code decides what gets published, and every item links to its original source.</blockquote></div>
    </section>

    <section class="wrap section" aria-labelledby="pipe-h">
      <div class="section-head"><div><p class="kicker">The pipeline</p><h2 id="pipe-h" class="section-title">Eight steps, every week</h2></div></div>
      <figure class="diagram" style="margin-left:0;margin-right:0">
        <div class="legend"><span><i class="l-code"></i>Deterministic code</span><span><i class="l-ai"></i>LLM step (Claude, no tools, JSON schema)</span></div>
        <svg class="d-wide" viewBox="0 0 1000 ${ys[1] + H + 4}" role="img" aria-labelledby="dw-t"><title id="dw-t">Pipeline: ${STEPS.map((s, i) => `${i + 1} ${s.t}`).join(", ")}</title>${wide}</svg>
        <svg class="d-tall" viewBox="0 0 340 ${tallH}" role="img" aria-labelledby="dt-t"><title id="dt-t">Pipeline: ${STEPS.map((s, i) => `${i + 1} ${s.t}`).join(", ")}</title>${tall}</svg>
        <figcaption class="visually-hidden">The eight steps are described in detail below.</figcaption>
      </figure>
      <ol class="steps">${STEPS.map((s, i) => `<li class="step"><div class="step__n">Step ${i + 1}<span class="step__who${s.ai ? " step__who--ai" : ""}">${s.ai ? "AI" : "Code"}</span></div><h3>${esc(s.t)}</h3><p>${esc(s.long)}</p></li>`).join("")}</ol>
    </section>

    <section class="wrap section" aria-labelledby="infra-h">
      <div class="section-head"><div><p class="kicker">Infrastructure</p><h2 id="infra-h" class="section-title">Zero cost, no servers, no secrets in the site</h2></div></div>
      <div class="flow" aria-label="Infrastructure flow">
        <div class="flow__node"><b>GitHub Actions</b><span>weekly cron + manual run</span></div><span class="flow__arrow">${icon("right")}</span>
        <div class="flow__node"><b>Python pipeline</b><span>8 steps, Python 3.12</span></div><span class="flow__arrow">${icon("right")}</span>
        <div class="flow__node"><b>Claude Code CLI</b><span>subscription token, headless</span></div><span class="flow__arrow">${icon("right")}</span>
        <div class="flow__node"><b>/site/data/*.json</b><span>commit + push</span></div><span class="flow__arrow">${icon("right")}</span>
        <div class="flow__node"><b>Netlify</b><span>static site, free plan</span></div>
      </div>
      <ul class="guard">
        <li>${icon("coin")}<div><b>Zero cost</b><span>Free sources without API keys, free GitHub Actions minutes, free Netlify hosting, and the LLM runs on an existing Claude subscription.</span></div></li>
        <li>${icon("lock")}<div><b>One secret, never in the site</b><span>The only secret is the Claude OAuth token in GitHub Actions secrets. The website is static HTML and JSON with no server code.</span></div></li>
        <li>${icon("shield")}<div><b>Fail closed</b><span>If scoring, the digest or validation fails after retries, the run stops and nothing is published.</span></div></li>
        <li>${icon("link")}<div><b>Traceable</b><span>Every item links to its original source, and the run log shows the real counts of every run.</span></div></li>
        <li>${icon("plug")}<div><b>Pluggable</b><span>Sources and the LLM provider are plugins. A deterministic mock provider runs dry runs and tests.</span></div></li>
        <li>${icon("clock")}<div><b>Budgeted</b><span>At most 100 items per week, batches of 15, about 8 LLM calls per run, 2 retries with backoff.</span></div></li>
      </ul>
    </section>`;
})();
