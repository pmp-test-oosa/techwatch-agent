/* TechWatch core: data loading, masthead, footer, theme, icons, formatting. No libraries. */
(function () {
  "use strict";

  const NEWS_TYPES = {
    research: "Research",
    competitor: "Company moves",
    industry: "Industry & market",
    funding: "Funding & M&A",
    regulation: "Regulation & standards",
    events: "Events",
  };
  const SIGNALS = { threat: "Threat", opportunity: "Opportunity", watch: "Watch" };

  const ICON_PATHS = {
    research: '<path d="M9 3h6M10 3v6.2l-5.6 9.3A1.7 1.7 0 0 0 5.9 21h12.2a1.7 1.7 0 0 0 1.5-2.5L14 9.2V3"/><path d="M7.2 15.5h9.6"/>',
    competitor: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.6"/><circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none"/>',
    industry: '<path d="M3 20.5V10l5 3v-3l5 3v-3l5 3V4h3v16.5z"/><path d="M7 17h2M12 17h2M17 17h1"/>',
    funding: '<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.8"/><path d="M6 9.5v5M18 9.5v5"/>',
    regulation: '<path d="M12 4v16M8 20h8M5 7h14"/><path d="M5 7l-2.6 6a2.6 2.6 0 0 0 5.2 0z"/><path d="M19 7l-2.6 6a2.6 2.6 0 0 0 5.2 0z"/>',
    events: '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/><rect x="7.5" y="13.2" width="3.4" height="3.4" rx=".6"/>',
    threat: '<path d="M12 4.2 2.9 19.5h18.2z"/><path d="M12 10v4.4M12 17.1v.01"/>',
    opportunity: '<path d="M7 17 17 7M9 7h8v8"/>',
    watch: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>',
    external: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M4.6 4.6 6 6M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4"/>',
    moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
    left: '<path d="m15 5-7 7 7 7"/>',
    right: '<path d="m9 5 7 7-7 7"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.6v.01"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
    shield: '<path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.2 7.5 9.5 4.3-1.3 7.5-4.9 7.5-9.5V6z"/><path d="m9 12 2.2 2.2L15.5 10"/>',
    lock: '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7.8a4 4 0 0 1 8 0v2.7"/>',
    link: '<path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3A4.5 4.5 0 0 0 13 4.6l-1.2 1.2"/><path d="M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1.2-1.2"/>',
    coin: '<circle cx="12" cy="12" r="8.5"/><path d="M14.8 9.2c-.6-.9-1.6-1.4-2.8-1.4-1.6 0-2.8.9-2.8 2.1 0 2.9 5.6 1.4 5.6 4.3 0 1.2-1.2 2.1-2.8 2.1-1.2 0-2.3-.6-2.8-1.4M12 6.3v1.5M12 16.9v1.5"/>',
    clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    plug: '<path d="M9 3v5M15 3v5M6.5 8h11v3.5a5.5 5.5 0 0 1-11 0zM12 17v4"/>',
  };

  function icon(name, cls) {
    return `<svg class="icon${cls ? " " + cls : ""}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${ICON_PATHS[name] || ""}</svg>`;
  }

  const LOGO = `<svg class="brand__mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <circle cx="16" cy="16" r="13.5" fill="none" stroke="currentColor" stroke-width="2"/>
      <circle cx="16" cy="16" r="8" fill="none" stroke="currentColor" stroke-width="1.4" opacity=".45"/>
      <path class="sweep" d="M16 16 16 2.5A13.5 13.5 0 0 1 29.1 12.8z"/>
      <circle cx="16" cy="16" r="2.4" fill="currentColor"/></svg>`;

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function safeUrl(url) {
    return /^https?:\/\//i.test(String(url || "")) ? String(url) : "#";
  }

  // ----- dates -----
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const utc = (iso) => new Date(String(iso).slice(0, 10) + "T00:00:00Z");
  function fmtDate(iso, opts) {
    const d = utc(iso);
    const noYear = opts && opts.year === undefined && "year" in opts;
    return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}${noYear ? "" : " " + d.getUTCFullYear()}`;
  }
  function fmtRange(start, end) {
    const s = utc(start), e = utc(end);
    const sameYear = s.getUTCFullYear() === e.getUTCFullYear();
    const sameMonth = sameYear && s.getUTCMonth() === e.getUTCMonth();
    if (sameMonth) return `${s.getUTCDate()}–${fmtDate(end)}`;
    if (sameYear) return `${fmtDate(start, { year: undefined })} – ${fmtDate(end)}`;
    return `${fmtDate(start)} – ${fmtDate(end)}`;
  }
  function fmtDateTime(iso) {
    const d = new Date(iso);
    const p = (n) => String(n).padStart(2, "0");
    return `${fmtDate(d.toISOString())}, ${p(d.getUTCHours())}:${p(d.getUTCMinutes())} UTC`;
  }
  function kw(week) { // "2026-W42" -> { n: 42, year: 2026 }
    const m = /^(\d{4})-W(\d{2})$/.exec(week || "");
    return m ? { year: +m[1], n: +m[2] } : { year: "", n: "?" };
  }

  // ----- storage (per-viewer convenience only) -----
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* ignore */ } },
  };

  // ----- theme -----
  function effectiveTheme() {
    const t = document.documentElement.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function bindThemeToggle(btn) {
    const sync = () => {
      const next = effectiveTheme() === "dark" ? "light" : "dark";
      btn.setAttribute("aria-label", `Switch to ${next} theme`);
      btn.title = `Switch to ${next} theme`;
    };
    btn.addEventListener("click", () => {
      const next = effectiveTheme() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      store.set("tw-theme", next);
      sync();
    });
    sync();
  }

  // ----- data -----
  async function json(path) {
    const res = await fetch(path, { cache: "no-cache" });
    if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
    return res.json();
  }
  const params = new URLSearchParams(location.search);

  function link(page, extra) {
    const p = new URLSearchParams();
    if (state.profileId && state.multiProfile) p.set("profile", state.profileId);
    Object.entries(extra || {}).forEach(([k, v]) => v != null && p.set(k, v));
    const q = p.toString();
    return page + (q ? "?" + q : "");
  }

  const state = { index: null, profileId: null, profileEntry: null, profile: null, multiProfile: false, runs: [] };

  // ----- schedule and status (mirrors .github/workflows/techwatch.yml and techwatch/windows.py) -----
  const SCHEDULE_UTC = [[1, 5, 17], [2, 5, 17]]; // [JS weekday (Mon=1), hour, minute]: main run, fallback
  const DAY = 86400000;
  function isoWeekLabel(d) { // d: Date (UTC)
    const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
    const dow = t.getUTCDay() || 7;
    t.setUTCDate(t.getUTCDate() + 4 - dow);
    const year = t.getUTCFullYear();
    const week = Math.ceil(((t - Date.UTC(year, 0, 1)) / DAY + 1) / 7);
    return `${year}-W${String(week).padStart(2, "0")}`;
  }
  function mondayOf(now) {
    const t = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
    return new Date(t - ((t.getUTCDay() + 6) % 7) * DAY);
  }
  function expectedWeek(now) { // last completed ISO week
    return isoWeekLabel(new Date(mondayOf(now) - DAY));
  }
  function nextRuns(now, weeks) {
    const out = [];
    for (let i = 0; i < 15 && out.length < 3; i++) {
      const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + i));
      for (const [wd, h, m] of SCHEDULE_UTC) {
        const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), h, m));
        if (d.getUTCDay() !== wd || t <= now) continue;
        const fallback = wd !== SCHEDULE_UTC[0][0];
        // the fallback only works when the week it covers is still missing
        if (fallback && weeks.some((w) => w.week === expectedWeek(t))) continue;
        out.push({ at: t, fallback });
      }
    }
    return out;
  }
  function computeStatus(now) {
    const weeks = (state.profileEntry && state.profileEntry.weeks) || [];
    const mine = state.runs.filter((r) => !state.profileId || r.profile === state.profileId);
    const real = mine.filter((r) => !r.dry_run);
    const runs = real.length ? real : mine; // a pure dry-run preview has no real runs
    const lastAttempt = runs.find((r) => r.status === "published" || r.status === "failed") || null;
    const lastSuccess = runs.find((r) => r.status === "published") || null;
    const expected = expectedWeek(now);
    const hasExpected = weeks.some((w) => w.week === expected);
    const newest = weeks.reduce((m, w) => (!m || w.generated_at > m ? w.generated_at : m), null);
    const graceEnd = new Date(+mondayOf(now) + DAY + 9 * 3600000); // Tuesday 09:00 UTC
    let level = "ok", text = "Up to date";
    if (lastAttempt && lastAttempt.status === "failed") {
      level = "error";
      text = `Last run failed (${fmtDateTime(lastAttempt.generated_at)})`;
    } else if ((!hasExpected && now > graceEnd) || (newest && now - new Date(newest) > 8 * DAY)) {
      level = "delayed";
      text = `Delayed: KW ${kw(expected).n} not published yet`;
    } else if (!hasExpected) {
      text = `KW ${kw(expected).n} due with the next run`;
    }
    return { level, text, lastSuccess, expected, next: nextRuns(now, weeks) };
  }
  const STATUS_LABEL = { ok: "OK", delayed: "Delayed", error: "Error" };
  function statusChip(level) {
    return `<span class="status status--${level}"><span class="status__dot" aria-hidden="true"></span>${STATUS_LABEL[level]}</span>`;
  }
  function renderStatus() {
    const el = document.getElementById("statusbar");
    if (!el) return;
    const s = computeStatus(new Date());
    const next = s.next[0];
    el.innerHTML = `
      <span class="statusbar__item" title="${esc(s.text)}">${statusChip(s.level)}<span class="statusbar__text">${esc(s.text)}</span></span>
      <span class="statusbar__item"><span class="muted">Last successful run</span>
        <strong>${s.lastSuccess ? esc(fmtDateTime(s.lastSuccess.generated_at)) : "none yet"}</strong></span>
      <span class="statusbar__item"><span class="muted">Next scheduled run</span>
        <strong>${next ? esc(fmtDateTime(next.at.toISOString())) : "–"}</strong>${next && next.fallback ? '<span class="muted"> (fallback)</span>' : ""}</span>`;
  }

  const PAGES = [
    ["digest", "index.html", "Briefing"],
    ["archive", "archive.html", "Archive"],
    ["profile", "profile.html", "Profile"],
    ["how", "how.html", "How it works"],
    ["runs", "runs.html", "Run log"],
  ];

  function renderMasthead(page) {
    const el = document.getElementById("masthead");
    const nav = PAGES.map(([id, href, label]) =>
      `<a href="${esc(link(href))}"${id === page ? ' aria-current="page"' : ""}>${label}</a>`).join("");
    const entry = state.profileEntry;
    let client = "";
    if (entry) {
      const name = state.multiProfile
        ? `<label class="visually-hidden" for="profile-select">Profile</label>
           <select id="profile-select">${state.index.profiles.map((p) =>
             `<option value="${esc(p.id)}"${p.id === entry.id ? " selected" : ""}>${esc(p.name)}</option>`).join("")}</select>`
        : `<span class="client__name">${esc(entry.name)}</span>`;
      client = `<div class="client"><span class="client__label">Profile</span>${name}</div>`;
    }
    el.innerHTML = `
      <div class="topbar"><div class="wrap topbar__inner">
        <a class="brand" href="${esc(link("index.html"))}" aria-label="TechWatch, current briefing">${LOGO}<span>TechWatch</span></a>
        <nav class="nav" aria-label="Main">${nav}</nav>
        <div class="topbar__end">
          <button class="icon-btn theme-toggle" type="button">${icon("sun", "sun")}${icon("moon", "moon")}</button>
        </div>
      </div></div>
      <div class="subbar"><div class="wrap subbar__inner">${client}<div id="week-switch-slot"></div></div></div>
      <div class="statusbar" aria-label="Pipeline status"><div class="wrap statusbar__inner" id="statusbar" aria-live="polite"></div></div>`;
    bindThemeToggle(el.querySelector(".theme-toggle"));
    const sel = el.querySelector("#profile-select");
    if (sel) sel.addEventListener("change", () => { location.href = `${location.pathname}?profile=${encodeURIComponent(sel.value)}`; });
  }

  function renderFooter() {
    const el = document.getElementById("footer");
    if (!el) return;
    el.innerHTML = `<div class="wrap footer__inner">
        <p class="footer__rule">The AI reads and scores. Code decides what gets published, and every item links to its original source.</p>
        <div class="footer__meta">
          <p>Built by Philip Maurice · agentic build for AI in Action · runs autonomously every week at zero cost</p>
          <p class="footer__links"><a href="${esc(link("how.html"))}">How it works</a><a href="${esc(link("runs.html"))}">Run log</a><a href="${esc(link("archive.html"))}">Archive</a></p>
        </div></div>`;
  }

  async function init(page) {
    renderFooter();
    try {
      state.index = await json("data/index.json");
    } catch (e) {
      state.index = { profiles: [] };
    }
    const profiles = state.index.profiles || [];
    state.multiProfile = profiles.length > 1;
    const wanted = params.get("profile");
    state.profileEntry = profiles.find((p) => p.id === wanted) || profiles[0] || null;
    state.profileId = state.profileEntry ? state.profileEntry.id : null;
    if (state.profileId) {
      try { state.profile = await json(`data/profiles/${encodeURIComponent(state.profileId)}.json`); } catch (e) { state.profile = null; }
    }
    renderMasthead(page);
    renderFooter();
    try { state.runs = (await json("data/run-log.json")).runs || []; } catch (e) { state.runs = []; }
    renderStatus();
    return state;
  }

  function fieldName(id, short) {
    const f = state.profile && (state.profile.watch_fields || []).find((x) => x.id === id);
    if (!f) return id;
    return short ? (f.short || f.name) : f.name;
  }

  function relBar(n) {
    const v = Math.max(0, Math.min(10, Number(n) || 0));
    let segs = "";
    for (let i = 1; i <= 10; i++) segs += `<i${i <= v ? ' class="on"' : ""}></i>`;
    return `<span class="rel" role="img" aria-label="Relevance ${v} of 10"><span class="rel__bar">${segs}</span><span class="rel__n">${v}<small>/10</small></span></span>`;
  }
  function badge(signal) {
    return `<span class="badge badge--${esc(signal)}">${icon(signal)}${esc(SIGNALS[signal] || signal)}</span>`;
  }
  function typeLabel(t) {
    return `<span class="type">${icon(t)}${esc(NEWS_TYPES[t] || t)}</span>`;
  }

  function fatal(container, title, text) {
    container.innerHTML = `<section class="wrap page-head"><p class="kicker">TechWatch</p><h1>${esc(title)}</h1><p class="lede">${esc(text)}</p></section>`;
  }

  window.TW = { NEWS_TYPES, SIGNALS, icon, esc, safeUrl, fmtDate, fmtRange, fmtDateTime, kw, json, params, link, init, state,
    computeStatus, statusChip,
    fieldName, relBar, badge, typeLabel, fatal, store };
})();
