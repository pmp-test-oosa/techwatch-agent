/* Profile: audience, watch fields with keywords, companies to watch, sources. */
(async function () {
  "use strict";
  const { esc } = TW;
  const st = await TW.init("profile");
  const main = document.getElementById("main");
  const p = st.profile;
  if (!p) {
    TW.fatal(main, "Profile not available", "The profile is published together with the first digest.");
    return;
  }
  const fields = (p.watch_fields || []).map((f, i) => `
    <article class="fieldcard">
      <span class="fieldcard__no">${String(i + 1).padStart(2, "0")}</span>
      <h3>${esc(f.name)}</h3>
      ${f.name_de ? `<p class="de" lang="de">${esc(f.name_de)}</p>` : ""}
      <p class="desc">${esc(f.description || "")}</p>
      <p class="kwlabel">Keywords · English</p>
      <div class="kws">${(f.keywords_en || []).map((k) => `<span class="kw">${esc(k)}</span>`).join("")}</div>
      <p class="kwlabel">Keywords · Deutsch</p>
      <div class="kws" lang="de">${(f.keywords_de || []).map((k) => `<span class="kw">${esc(k)}</span>`).join("")}</div>
    </article>`).join("");
  const SOURCES = [
    ["arXiv", "research preprints, searched per watch field by submission date"],
    ["Google News", "English and German news search per watch field, with date operators"],
    ["idw – Informationsdienst Wissenschaft", "press releases of German universities and institutes (RSS)"],
    ["MM MaschinenMarkt", "German machine-building and production news (RSS)"],
    ["Industry of Things", "German Industrial IoT and Industrie 4.0 news (RSS)"],
  ].map(([n, d]) => `<div><dt>${esc(n)}</dt><dd>${esc(d)}</dd></div>`).join("");

  main.innerHTML = `
    <section class="wrap page-head">
      <p class="kicker">Profile</p>
      <h1>${esc(p.name)}</h1>
      <p class="lede">${esc(p.description)}</p>
      <dl class="facts">
        ${p.industry ? `<div class="fact"><dt>Scope</dt><dd>${esc(p.industry)}</dd></div>` : ""}
        ${p.audience ? `<div class="fact"><dt>Audience</dt><dd>${esc(p.audience)}</dd></div>` : ""}
      </dl>
    </section>
    <section class="wrap section" aria-labelledby="wf-h">
      <div class="section-head"><div><p class="kicker">What we monitor</p><h2 id="wf-h" class="section-title">${(p.watch_fields || []).length} watch fields</h2></div>
        <p class="muted small">Searched every week in English and German</p></div>
      <div class="fields">${fields}</div>
    </section>
    <section class="wrap section">
      <div class="two-col">
        <div class="panel"><p class="kicker">Companies to watch</p><h2>Vendors and technology leaders</h2>
          <p class="muted small">Moves by these companies are typed as "Company moves" and ranked higher before scoring.</p>
          <div class="namelist">${(p.companies_to_watch || []).map((c) => `<span>${esc(c)}</span>`).join("")}</div></div>
        <div class="panel"><p class="kicker">Sources</p><h2>Where the items come from</h2>
          <p class="muted small">Free sources without API keys. Every item links to its original.</p>
          <dl class="eco">${SOURCES}</dl></div>
      </div>
    </section>`;
})();
