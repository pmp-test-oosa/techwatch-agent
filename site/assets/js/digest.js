/* Weekly briefing page. */
(async function () {
  "use strict";
  const { esc, icon, safeUrl, fmtDate, fmtRange, kw, json, params, link, NEWS_TYPES, SIGNALS, relBar, badge, typeLabel, fieldName } = TW;
  const main = document.getElementById("main");
  main.innerHTML = `<div class="wrap loading"><div class="skeleton" style="width:40%"></div><div class="skeleton" style="width:70%;height:42px;margin-top:18px"></div></div>`;

  const st = await TW.init("digest");
  const entry = st.profileEntry;
  if (!entry || !entry.weeks || !entry.weeks.length) {
    TW.fatal(main, "No briefing published yet", "The first weekly digest appears here after the pipeline has run once.");
    return;
  }
  const weeks = entry.weeks; // newest first
  const wanted = params.get("week");
  const idx = Math.max(0, weeks.findIndex((w) => w.week === wanted));
  const wk = weeks[idx];
  let doc;
  try {
    doc = await json(`data/${wk.file}`);
  } catch (e) {
    TW.fatal(main, "This briefing could not be loaded", String(e.message || e));
    return;
  }
  const issueNo = weeks.length - idx;
  const k = kw(doc.week);
  document.title = `KW ${k.n} · ${doc.headline} · TechWatch`;

  // ----- week switcher -----
  const older = weeks[idx + 1], newer = weeks[idx - 1];
  const navBtn = (w, dir, label) => w
    ? `<a href="${esc(link("index.html", { week: w.week }))}" aria-label="${label}: KW ${kw(w.week).n}" title="${label}">${icon(dir)}</a>`
    : `<span class="disabled" aria-hidden="true">${icon(dir)}</span>`;
  document.getElementById("week-switch-slot").innerHTML =
    `<nav class="week-switch" aria-label="Week">${navBtn(older, "left", "Previous week")}
      <span class="week-switch__label" aria-current="page">KW ${k.n}<small>${fmtRange(doc.window.start, doc.window.end)}</small></span>
      ${navBtn(newer, "right", "Next week")}</nav>`;

  const items = doc.items || [];
  const byId = Object.fromEntries(items.map((it, i) => [it.id, { ...it, no: i + 1 }]));
  const s = doc.stats || {};
  const num = (n) => String(n).padStart(2, "0");
  const more = (it) => {
    const o = it.also_reported_by || [];
    return o.length ? ` <span class="more" title="Also reported by: ${esc(o.join(", "))}">+${o.length} more outlet${o.length === 1 ? "" : "s"}</span>` : "";
  };
  const refs = (ids) => (ids || []).filter((id) => byId[id]).map((id) =>
    `<a class="ref" href="#item-${esc(id)}" data-ref="${esc(id)}" title="${esc(byId[id].title)}">#${num(byId[id].no)}</a>`).join("");

  // ----- notices -----
  const notices = [];
  if (doc.dry_run) notices.push(`<p class="notice notice--warn">${icon("info")}<span><strong>Dry run.</strong> This page shows invented fixture items and mock scores, not real news.</span></p>`);
  if (doc.backfilled) notices.push(`<p class="notice">${icon("clock")}<span>Generated retroactively on ${fmtDate(doc.generated_at)} from items published in this week.</span></p>`);
  if (doc.quiet_week) notices.push(`<p class="notice">${icon("info")}<span><strong>Quiet week.</strong> Only ${items.length} item${items.length === 1 ? "" : "s"} met the relevance threshold of 7/10. We publish what we found rather than pad the briefing.</span></p>`);

  // ----- hero -----
  const hero = `
    <section class="wrap hero" aria-labelledby="headline">
      <p class="eyebrow"><span>Issue ${issueNo}</span><span class="dot"></span><strong>KW ${k.n} · ${k.year}</strong><span class="dot"></span><span>${fmtRange(doc.window.start, doc.window.end)}</span></p>
      <h1 id="headline" class="hero__title">${esc(doc.headline)}</h1>
      ${notices.join("")}
      <dl class="kpis">
        <div class="kpi"><dt>Items scanned</dt><dd class="tnum">${s.scanned ?? "–"}</dd></div>
        <div class="kpi"><dt>Items kept</dt><dd class="tnum">${s.kept ?? items.length}</dd></div>
        <div class="kpi kpi--threat"><dt><span class="swatch sigdot--threat"></span>Threats</dt><dd class="tnum">${s.threats ?? 0}</dd></div>
        <div class="kpi kpi--opportunity"><dt><span class="swatch sigdot--opportunity"></span>Opportunities</dt><dd class="tnum">${s.opportunities ?? 0}</dd></div>
        <div class="kpi"><dt>Sources</dt><dd class="tnum">${s.sources ?? "–"}<small>publishers</small></dd></div>
      </dl>
    </section>`;

  // ----- top signal -----
  const top = byId[doc.top_signal];
  const topHtml = top ? `
    <section class="wrap section" aria-labelledby="top-h">
      <div class="section-head"><h2 id="top-h" class="kicker">Top signal of the week</h2></div>
      <a class="feature" href="${esc(safeUrl(top.url))}" target="_blank" rel="noopener noreferrer">
        <div>
          <div class="feature__meta">${badge(top.signal)}${typeLabel(top.news_type)}</div>
          <h3 class="feature__title">${esc(top.title)}</h3>
          <p class="feature__reason">${esc(top.reason)}</p>
          <div class="feature__foot">
            <span class="feature__src"><strong>${esc(top.publisher || top.source)}</strong> · ${fmtDate(top.date)}${more(top)}</span>
            <span class="cta">Read original source ${icon("external")}<span class="visually-hidden">(opens in a new tab)</span></span>
          </div>
        </div>
        <div class="feature__aside">
          <p class="aside-label">Relevance for this client</p>
          <div class="score" aria-hidden="true"><span class="score__n">${esc(top.relevance)}</span><span class="score__of">/10</span></div>
          ${relBar(top.relevance)}
          <dl><div><dt>Watch field</dt><dd>${esc(fieldName(top.watch_field))}</dd></div>
              <div><dt>Published</dt><dd>${fmtDate(top.date)}</dd></div></dl>
        </div>
      </a>
    </section>` : "";

  // ----- summary + actions -----
  const summary = (doc.summary || []).map((b) => `<li><p>${esc(b.text)}${b.item_ids && b.item_ids.length ? `<span class="refs">${refs(b.item_ids)}</span>` : ""}</p></li>`).join("");
  const actions = (doc.actions || []).map((a) => `<li><p>${esc(a.text)}${a.item_ids && a.item_ids.length ? `<span class="refs">${refs(a.item_ids)}</span>` : ""}</p></li>`).join("");
  const briefHtml = `
    <section class="wrap section" aria-label="Briefing">
      <div class="brief">
        <div class="panel"><p class="kicker">Executive summary</p><h2>What happened this week</h2>
          <ol class="summary-list">${summary || '<li><p class="empty-inline">No summary this week.</p></li>'}</ol></div>
        <div class="panel actions-panel"><p class="kicker">Action list</p><h2>What to do this week</h2>
          <ol class="actions-list">${actions || '<li><p class="empty-inline">No actions this week.</p></li>'}</ol></div>
      </div>
    </section>`;

  // ----- filters + grid -----
  const DIMS = [
    { key: "news_type", label: "Type", values: Object.keys(NEWS_TYPES), name: (v) => NEWS_TYPES[v], pre: (v) => icon(v) },
    { key: "signal", label: "Signal", values: Object.keys(SIGNALS), name: (v) => SIGNALS[v], pre: (v) => `<span class="sigdot sigdot--${v}"></span>` },
    { key: "watch_field", label: "Field", values: ((st.profile && st.profile.watch_fields) || []).map((f) => f.id), name: (v) => fieldName(v, true), pre: () => "" },
  ];
  // include any unexpected values present in the data
  DIMS.forEach((d) => items.forEach((it) => { if (!d.values.includes(it[d.key])) d.values.push(it[d.key]); }));

  const cards = Object.values(byId).map((it) => `
    <a class="card card--${esc(it.signal)}" id="item-${esc(it.id)}" href="${esc(safeUrl(it.url))}" target="_blank" rel="noopener noreferrer"
       data-news_type="${esc(it.news_type)}" data-signal="${esc(it.signal)}" data-watch_field="${esc(it.watch_field)}">
      <div class="card__top">${typeLabel(it.news_type)}<span class="card__no">#${num(it.no)}</span>${badge(it.signal)}</div>
      ${icon("external", "card__ext")}
      <h3 class="card__title">${esc(it.title)}</h3>
      <p class="card__reason">${esc(it.reason)}</p>
      <div class="card__foot">
        <span class="card__src"><strong>${esc(it.publisher || it.source)}</strong>${fmtDate(it.date)} · ${esc(fieldName(it.watch_field, true))}${more(it)}</span>
        ${relBar(it.relevance)}
      </div>
      <span class="visually-hidden">(opens original source in a new tab)</span>
    </a>`).join("");

  const gridHtml = items.length ? `
    <section class="wrap section" aria-labelledby="items-h">
      <div class="section-head">
        <div><p class="kicker">This week's items</p><h2 id="items-h" class="section-title">Everything we kept</h2></div>
        <p class="muted small">Relevance ≥ 7/10 · max 20 · each card opens the original source</p>
      </div>
      <div class="filters" id="filters">
        ${DIMS.map((d) => `<div class="filter-group" role="group" aria-labelledby="fl-${d.key}">
            <span class="filter-label" id="fl-${d.key}">${d.label}</span>
            <div class="chips">${d.values.map((v) => `<button type="button" class="chip" aria-pressed="false" data-dim="${d.key}" data-val="${esc(v)}">${d.pre(v)}<span>${esc(d.name(v) || v)}</span><span class="chip__n"></span></button>`).join("")}</div>
          </div>`).join("")}
        <div class="filter-foot"><p class="result-line" id="result-line" aria-live="polite"></p><button type="button" class="link-btn" id="reset" hidden>Reset filters</button></div>
      </div>
      <div class="grid" id="grid">${cards}</div>
      <div class="empty" id="empty" hidden>
        ${icon("search")}<h3>No items match these filters</h3>
        <p>Try removing a filter. Every combination is computed from this week's ${items.length} kept items.</p>
        <button type="button" class="btn" id="reset-2">Reset filters</button>
      </div>
    </section>` : "";

  main.innerHTML = hero + topHtml + briefHtml + gridHtml;
  if (!items.length) return;

  // ----- filtering logic (client-side, instant) -----
  const active = { news_type: new Set(), signal: new Set(), watch_field: new Set() };
  const grid = document.getElementById("grid");
  const cardEls = Array.from(grid.querySelectorAll(".card"));
  const chipEls = Array.from(document.querySelectorAll(".chip"));
  const matches = (it, skip) => Object.keys(active).every((k2) => k2 === skip || !active[k2].size || active[k2].has(it[k2]));

  function counts() {
    chipEls.forEach((c) => {
      const dim = c.dataset.dim, val = c.dataset.val;
      const n = items.filter((it) => it[dim] === val && matches(it, dim)).length;
      c.querySelector(".chip__n").textContent = n;
      const pressed = active[dim].has(val);
      c.setAttribute("aria-pressed", String(pressed));
      c.disabled = n === 0 && !pressed;
      c.setAttribute("aria-label", `${c.textContent.replace(/\d+$/, "").trim()}, ${n} item${n === 1 ? "" : "s"}`);
    });
  }
  function apply(animate) {
    const any = Object.values(active).some((x) => x.size);
    const run = () => {
      let shown = 0;
      cardEls.forEach((el) => {
        const it = { news_type: el.dataset.news_type, signal: el.dataset.signal, watch_field: el.dataset.watch_field };
        const ok = matches(it);
        el.hidden = !ok;
        if (ok) shown++;
      });
      document.getElementById("empty").hidden = shown !== 0;
      grid.hidden = shown === 0;
      document.getElementById("result-line").innerHTML = `Showing <strong>${shown}</strong> of ${items.length} items`;
      document.getElementById("reset").hidden = !any;
      counts();
      grid.classList.remove("is-updating");
    };
    if (animate) { grid.classList.add("is-updating"); setTimeout(run, 170); } else run();
  }
  chipEls.forEach((c) => c.addEventListener("click", () => {
    const set = active[c.dataset.dim];
    set.has(c.dataset.val) ? set.delete(c.dataset.val) : set.add(c.dataset.val);
    apply(true);
  }));
  const reset = () => { Object.values(active).forEach((x) => x.clear()); apply(true); };
  document.getElementById("reset").addEventListener("click", reset);
  document.getElementById("reset-2").addEventListener("click", reset);

  // reference chips jump to the card (clearing filters if it is hidden)
  document.querySelectorAll("[data-ref]").forEach((a) => a.addEventListener("click", (ev) => {
    ev.preventDefault();
    const el = document.getElementById(`item-${a.dataset.ref}`);
    if (!el) return;
    const go = () => {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash");
      el.focus({ preventScroll: true });
    };
    if (el.hidden) { Object.values(active).forEach((x) => x.clear()); apply(false); }
    go();
  }));
  apply(false);
})();
