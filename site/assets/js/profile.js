/* Client profile: description, competitors, watch fields with keywords. */
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
  const eco = Object.entries(p.ecosystem || {}).map(([k, v]) =>
    `<div><dt>${esc(k.replace(/_/g, " "))}</dt><dd>${esc((v || []).join(", "))}</dd></div>`).join("");

  main.innerHTML = `
    <section class="wrap page-head">
      <p class="kicker">Client profile</p>
      <h1>${esc(p.name)}</h1>
      ${p.fictional ? `<p class="notice">${TW.icon("info")}<span><strong>Fictional demo client.</strong> This company does not exist. The profile shows how TechWatch is configured for one Mittelstand manufacturer; the news it collects is real.</span></p>` : ""}
      <p class="lede">${esc(p.description)}</p>
      <dl class="facts">
        ${p.employees ? `<div class="fact"><dt>Employees</dt><dd>${esc(p.employees)}</dd></div>` : ""}
        ${p.industry ? `<div class="fact"><dt>Business</dt><dd>${esc(p.industry)}</dd></div>` : ""}
        ${p.location ? `<div class="fact"><dt>Location</dt><dd>${esc(p.location)}</dd></div>` : ""}
      </dl>
    </section>
    <section class="wrap section" aria-labelledby="wf-h">
      <div class="section-head"><div><p class="kicker">What we monitor</p><h2 id="wf-h" class="section-title">${(p.watch_fields || []).length} watch fields</h2></div>
        <p class="muted small">Searched every week in English and German</p></div>
      <div class="fields">${fields}</div>
    </section>
    <section class="wrap section">
      <div class="two-col">
        <div class="panel"><p class="kicker">Competitors to watch</p><h2>Named competitors</h2>
          <p class="muted small">Items about these companies are typed as "Competitor moves".</p>
          <div class="namelist">${(p.competitors || []).map((c) => `<span>${esc(c)}</span>`).join("")}</div></div>
        <div class="panel"><p class="kicker">Ecosystem</p><h2>Customers and suppliers</h2>
          <p class="muted small">Context for scoring. These are not treated as competitors.</p>
          <dl class="eco">${eco}</dl></div>
      </div>
    </section>`;
})();
