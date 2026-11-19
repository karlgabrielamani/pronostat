// ---------- Accueil (web : match du jour, stat du jour, tableau ; téléphone : cartes par compétition), fiche de match, favoris ----------
(() => {
  const $ = id => document.getElementById(id);
  const APIS = () => [window.FootAPI, window.TennisAPI, window.NbaAPI, window.ElAPI, window.WnAPI].filter(Boolean);
  const pct = x => Math.round(x * 100) + " %";
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const SPN = { Foot: "Football", Tennis: "Tennis", NBA: "NBA" };
  // drapeaux dessinés (les drapeaux emoji ne s'affichent pas sous Windows ni sur certains Android)
  const fsv = (body, vb = "0 0 30 20") => `<svg class="flg" viewBox="${vb}" aria-hidden="true">${body}</svg>`;
  const v3 = (a, b, c) => fsv(`<rect width="10" height="20" fill="${a}"/><rect x="10" width="10" height="20" fill="${b}"/><rect x="20" width="10" height="20" fill="${c}"/>`);
  const h3 = (a, b, c, m = 1) => fsv(`<rect width="30" height="20" fill="${a}"/><rect y="${10 - 10 * m / 3}" width="30" height="${20 * m / 3}" fill="${b}"/><rect y="${10 + 10 * m / 3}" width="30" height="${10 - 10 * m / 3}" fill="${c}"/>`);
  const FLAG = {
    "France": v3("#002395", "#fff", "#ED2939"), "Italie": v3("#009246", "#fff", "#CE2B37"), "Belgique": v3("#000", "#FAE042", "#ED2939"),
    "Allemagne": h3("#000", "#DD0000", "#FFCE00"), "Pays-Bas": h3("#AE1C28", "#fff", "#21468B"),
    "Espagne": fsv('<rect width="30" height="20" fill="#AA151B"/><rect y="5" width="30" height="10" fill="#F1BF00"/>'),
    "Portugal": fsv('<rect width="30" height="20" fill="#FF0000"/><rect width="12" height="20" fill="#006600"/><circle cx="12" cy="10" r="3.6" fill="#FFCC00"/><circle cx="12" cy="10" r="2.2" fill="#FF0000"/>'),
    "Angleterre": fsv('<rect width="30" height="20" fill="#fff"/><rect x="12.5" width="5" height="20" fill="#CE1124"/><rect y="7.5" width="30" height="5" fill="#CE1124"/>'),
    "Écosse": fsv('<rect width="30" height="20" fill="#005EB8"/><path d="M0 0 30 20M30 0 0 20" stroke="#fff" stroke-width="3.2"/>'),
    "Turquie": fsv('<rect width="30" height="20" fill="#E30A17"/><circle cx="11" cy="10" r="5" fill="#fff"/><circle cx="12.3" cy="10" r="4" fill="#E30A17"/><circle cx="17.6" cy="10" r="1.7" fill="#fff"/>'),
    "Grèce": fsv('<rect width="30" height="20" fill="#0D5EAF"/>' + [2, 6, 10, 14, 18].map(y => `<rect y="${y - 1.1}" width="30" height="2.2" fill="#fff"/>`).join("") + '<rect width="12" height="11" fill="#0D5EAF"/><rect x="5" width="2.2" height="11" fill="#fff"/><rect y="4.4" width="12" height="2.2" fill="#fff"/>'),
    "Europe": fsv('<rect width="30" height="20" fill="#003399"/>' + Array.from({ length: 12 }, (_, i) => `<circle cx="${15 + 6 * Math.cos(i * Math.PI / 6)}" cy="${10 + 6 * Math.sin(i * Math.PI / 6)}" r="0.9" fill="#FFCC00"/>`).join("")),
    "États-Unis": fsv('<rect width="30" height="20" fill="#fff"/>' + [0, 2, 4, 6, 8, 10, 12].map(k => `<rect y="${k * 20 / 13 * 1}" width="30" height="${20 / 13}" fill="#B22234"/>`).join("").replace(/y="([\d.]+)"/g, (m, y) => `y="${(+y * 2).toFixed(2)}"`) + '<rect width="13" height="10.8" fill="#3C3B6E"/>')
  };
  // ordre d'affichage des compétitions de foot
  const PRIO = ["WC", "EURO", "UNL", "WCQ", "EUQ", "UCL", "F1", "E0", "SP1", "I1", "D1", "UEL", "N1", "B1", "P1", "UECL", "F2", "E1", "D2", "SP2", "I2", "SC0", "T1", "G1", "N2", "CDF", "FAC", "CDR", "CIT", "DFB", "KNVB", "TDP", "SCC"];
  const prio = x => { const i = PRIO.indexOf(x.lg); return i < 0 ? 99 : i; };
  // championnats : ordre alphabétique, la division inférieure juste en dessous
  const LORD = ["D1", "D2", "N1", "N2", "B1", "SP1", "SP2", "P1", "F1", "F2", "E0", "E1", "E2", "E3", "SC0", "SC1", "I1", "I2", "G1", "T1", "CDR", "CIT", "CDF", "DFB", "EFL", "FAC", "KNVB", "SCC", "SLC", "TDP"];
  const lord = x => { const i = LORD.indexOf(x.lg); return i < 0 ? 50 + prio(x) : i; };
  // notoriété d'une équipe : niveau de son championnat (1 = grand championnat)
  const LRANK = { "Premier League": 1, "La Liga": 1, "Serie A": 1, "Bundesliga": 1, "Ligue 1": 1, "Eredivisie": 2, "Liga Portugal": 2, "Jupiler Pro League": 2,
    "Championship": 3, "Eerste Divisie": 4, "Ligue 2": 3, "2. Bundesliga": 3, "Segunda": 3, "Serie B": 3, "Süper Lig": 3, "Scottish Prem": 3, "Super League Grèce": 3 };
  let TIER = null;
  const tier = n => { if (!TIER) { TIER = {}; try { (window.FootAPI ? FootAPI.teams() : []).forEach(t => { if (!(t.name in TIER)) TIER[t.name] = LRANK[t.sub] || 5; }); } catch (e) {} } return TIER[n] || 5; };
  const fame = x => x.nat ? (x.lg === "FRI" ? 7 : 3) : tier(x.a) + tier(x.b) + (x.cup && x.country === "Europe" ? -2 : x.cup ? 1 : 0);

  // ---- écussons : initiales sur une couleur tirée du nom (aucun logo officiel)
  const STOP = new Set(["fc", "cf", "ac", "as", "sc", "sv", "afc", "ssc", "rc", "cd", "ud", "sd", "rcd", "vfb", "vfl", "tsg", "fk", "sk", "bk", "if", "de", "of", "the", "real", "club", "1.", "1"]);
  function initials(n) {
    const w = String(n).replace(/[.'’]/g, " ").split(/[\s-]+/).filter(x => x && !STOP.has(x.toLowerCase()));
    if (!w.length) return String(n).slice(0, 3).toUpperCase();
    if (w.length === 1) return w[0].slice(0, 3).toUpperCase();
    return (w[0][0] + w[1][0]).toUpperCase();
  }
  function hue(n) { let h = 0; for (const c of String(n)) h = (h * 31 + c.charCodeAt(0)) % 360; return h; }
  let LOGOS = window.LOGOS || {};
  if (!window.LOGOS && window.fetch) fetch("data/logos.json").then(r => r.ok ? r.json() : {}).then(j => { LOGOS = j || {}; if (window.Home) Home.show(true); }).catch(() => {});
  const crest = (n, cls = "") => LOGOS[n]
    ? `<span class="crest logo ${cls}" aria-hidden="true"><img src="${LOGOS[n]}" alt="" loading="lazy" decoding="async"></span>`
    : `<span class="crest ${cls}" style="background:hsl(${hue(n)} 52% 40%)" aria-hidden="true">${esc(initials(n))}</span>`;
  const short = (x, n) => x.sport === "Tennis" ? String(n).replace(/\s+[A-Z][\w.\-]*\.$/u, "") : n;
  const bn = (x, n) => x.comp === "EuroLeague" ? n : nick(n);          // EuroLeague : nom complet (« Tel Aviv », « Istanbul » sont partagés)
  const nick = n => { const w = String(n).split(" "); return w.length > 1 ? w[w.length - 1] : n; };

  // ---- jours
  const dkey = d => { const x = new Date(d); return x.getFullYear() + "-" + String(x.getMonth() + 1).padStart(2, "0") + "-" + String(x.getDate()).padStart(2, "0"); };
  const todayKey = () => dkey(new Date());
  function dayLabel(k, long) {
    const t0 = new Date(); t0.setHours(0, 0, 0, 0);
    const [y, m, d] = k.split("-").map(Number), dd = new Date(y, m - 1, d);
    const n = Math.round((dd - t0) / 864e5);
    if (n === 0) return "Aujourd'hui"; if (n === 1) return "Demain";
    const s = dd.toLocaleDateString("fr-FR", long ? { weekday: "long", day: "numeric", month: "long" } : { weekday: "short", day: "numeric", month: "short" });
    return s.charAt(0).toUpperCase() + s.slice(1);
  }
  const hm = x => new Date(x.dt).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  const whenTxt = x => dayLabel(dkey(x.dt)) + ", " + hm(x);
  const keyOf = x => Fav.key(x.sport, x.dt, x.a, x.b);

  // ---- calculs par sport
  const pois = (k, l) => { let p = Math.exp(-l); for (let i = 1; i <= k; i++) p *= l / i; return p; };
  const MG = 10;
  function footM(x) {
    if (x._m) return x._m;
    const m = []; let tot = 0;
    for (let i = 0; i <= MG; i++) { m.push([]); for (let j = 0; j <= MG; j++) {
      let p = pois(i, x.lh) * pois(j, x.la);
      if (i === 0 && j === 0) p *= 1 - x.lh * x.la * x.rho; else if (i === 0 && j === 1) p *= 1 + x.lh * x.rho;
      else if (i === 1 && j === 0) p *= 1 + x.la * x.rho; else if (i === 1 && j === 1) p *= 1 - x.rho;
      m[i].push(p); tot += p; } }
    m.forEach(r => r.forEach((v, j) => r[j] = v / tot));
    const sum = fn => { let s = 0; for (let i = 0; i <= MG; i++) for (let j = 0; j <= MG; j++) if (fn(i, j)) s += m[i][j]; return s; };
    const sc = []; for (let i = 0; i <= 6; i++) for (let j = 0; j <= 6; j++) sc.push([i, j, m[i][j]]);
    sc.sort((p, q) => q[2] - p[2]);
    return x._m = { btts: sum((i, j) => i > 0 && j > 0), o: k => sum((i, j) => i + j >= k), ha: 1 - sum(i => i === 0), aa: 1 - sum((i, j) => j === 0), sc };
  }
  function tennisS(x) {          // chance de gagner une manche, retrouvée à partir de la chance de gagner le match
    if (x._s) return x._s;
    const bo = x.bo === 5 ? 5 : 3;
    const P = s => bo === 3 ? s * s * (3 - 2 * s) : s ** 3 * (1 + 3 * (1 - s) + 6 * (1 - s) ** 2);
    let lo = 0, hi = 1; for (let k = 0; k < 40; k++) { const mid = (lo + hi) / 2; P(mid) < x.pa ? lo = mid : hi = mid; }
    const s = (lo + hi) / 2, t = 1 - s, need = bo === 3 ? 2 : 3;
    const sc = bo === 3 ? [["2–0", s * s, 0], ["2–1", 2 * s * s * t, 0], ["0–2", t * t, 1], ["1–2", 2 * s * t * t, 1]]
                        : [["3–0", s ** 3, 0], ["3–1", 3 * s ** 3 * t, 0], ["3–2", 6 * s ** 3 * t * t, 0], ["0–3", t ** 3, 1], ["1–3", 3 * t ** 3 * s, 1], ["2–3", 6 * t ** 3 * s * s, 1]];
    return x._s = { s, bo, need, setA: 1 - t ** need, setB: 1 - s ** need, sc: sc.sort((p, q) => q[1] - p[1]) };
  }
  const erf = z => { const t = 1 / (1 + 0.3275911 * Math.abs(z)); const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-z * z); return z >= 0 ? y : -y; };
  const Phi = z => 0.5 * (1 + erf(z / Math.SQRT2));
  const nbaBy = (x, k) => [1 - Phi((k - x.mg) / x.sg), Phi((-k - x.mg) / x.sg)];

  // ---- données
  // Autres championnats de basket (window.BASKET : WNBA, EuroLeague…) : même calcul que la NBA, sans les absents
  const BK = window.BASKET || {}, W = BK.WNBA;
  function basketList() {
    return Object.entries(BK).flatMap(([comp, B]) => {
      if (!B || !B.games || (comp === "EuroLeague" && window.ElAPI) || (comp === "WNBA" && window.WnAPI)) return [];   // déjà fournis par leur outil
      const T = Object.fromEntries(B.teams.map(t => [t.name, t])), sg = B.sd_team * Math.sqrt(2 * (1 - B.corr));
      return B.games.filter(g => T[g.home] && T[g.away]).map(g => {
        const a = T[g.home], b = T[g.away], h = g.neutral ? 0 : B.hca, m = (B.mu + a.o - b.d + h / 2) - (B.mu + b.o - a.d - h / 2), p = Phi(m / sg);
        return { sport: "NBA", comp, lg: comp, dt: g.dt, a: g.home, b: g.away, pa: p, pb: 1 - p, mg: m, sg };
      });
    });
  }
  let ALL = [];
  function load() {
    ALL = APIS().flatMap(a => { try { return a.list(); } catch (e) { return []; } }).concat(basketList())
      .filter(x => x.dt && isFinite(new Date(x.dt)))
      .sort((p, q) => new Date(p.dt) - new Date(q.dt));
    const sod = new Date(); sod.setHours(0, 0, 0, 0);
    ALL = ALL.filter(x => new Date(x.dt) >= sod);
    ALL.forEach(x => x.k = keyOf(x));
  }
  const findKey = k => ALL.find(x => x.k === k);

  // ---- état de l'accueil
  const small = () => matchMedia("(max-width: 760px)").matches;
  let S = { sport: "", day: null, more: false, comp: {} };
  try { const o = JSON.parse(sessionStorage.getItem("ps-home") || "{}"); if (o && typeof o === "object") S = Object.assign(S, o, { more: false }); } catch (e) {}
  const saveS = () => { try { sessionStorage.setItem("ps-home", JSON.stringify(S)); } catch (e) {} };
  const curSport = () => small() ? (S.sport || firstSport()) : S.sport;
  function firstSport() { for (const s of ["Foot", "Tennis", "NBA"]) if (ALL.some(x => x.sport === s)) return s; return "Foot"; }
  // ---- compétitions : championnat (foot), circuit ou tournoi (tennis)
  const compKey = x => x.sport === "Foot" ? x.lg : x.sport === "Tennis" ? "ev:" + x.tour + "|" + (x.event || x.comp) : x.comp;
  const compOk = x => { const c = (S.comp || {})[x.sport]; if (!c) return true; if (c === "ATP" || c === "WTA") return x.tour === c; return compKey(x) === c; };
  const pool = sp => ALL.filter(x => !x.few && (!sp || (x.sport === sp && compOk(x))));
  const SHORT = { "Ligue des Champions": "Ligue des champions", "Jupiler Pro League": "Jupiler Pro League", "Super League Grèce": "Super League" };
  const FOOTGRP = x => x.nat ? "Sélections nationales" : x.cup && x.country === "Europe" ? "Coupes d'Europe" : x.cup ? "Coupes nationales" : "Championnats";
  function compOptions(sp) {                                   // [{k, label, flag, n, grp}]
    const base = ALL.filter(x => !x.few && x.sport === sp && upcoming(x));
    const by = {}; base.forEach(x => { const k = compKey(x); (by[k] = by[k] || { x, n: 0 }).n++; });
    let list = Object.entries(by).map(([k, { x, n }]) => ({ k, n, x }));
    const out = [{ k: "", label: sp === "Foot" ? "Tous les championnats" : sp === "Tennis" ? "Tous les tournois" : "Tout le basket", n: base.length, grp: "" }];
    if (sp === "Foot") {
      let lgs = []; try { lgs = window.FootAPI && FootAPI.leagues ? FootAPI.leagues() : []; } catch (e) {}
      lgs.filter(l => !l.cup && !by[l.k]).forEach(l => list.push({ k: l.k, n: 0, x: { lg: l.k, comp: l.name, country: l.country, cup: false } }));   // championnats sans match cette semaine : gardés
      const GO = ["Sélections nationales", "Coupes d'Europe", "Championnats", "Coupes nationales"];
      list.sort((a, b) => GO.indexOf(FOOTGRP(a.x)) - GO.indexOf(FOOTGRP(b.x)) || lord(a.x) - lord(b.x));
      list.forEach(o => out.push({ k: o.k, label: SHORT[o.x.comp] || o.x.comp, flag: FLAG[o.x.country] || "", n: o.n, sub: o.n ? "" : "classement", grp: FOOTGRP(o.x) }));
    } else if (sp === "Tennis") {
      for (const t of ["ATP", "WTA"]) { const n = base.filter(x => x.tour === t).length; if (n) out.push({ k: t, label: t === "ATP" ? "ATP · hommes" : "WTA · femmes", n, grp: "Circuits" }); }
      list.sort((a, b) => new Date(a.x.dt) - new Date(b.x.dt)).forEach(o => out.push({ k: o.k, label: o.x.event || o.x.comp, sub: o.x.tour, n: o.n, grp: "Tournois" }));
    } else {
      const n = k => base.filter(x => x.comp === k).length;
      out.push({ k: "NBA", label: "NBA", flag: FLAG["États-Unis"], n: n("NBA"), grp: "Championnats" });
      if (BK.EuroLeague) out.push({ k: "EuroLeague", label: "EuroLeague", flag: FLAG.Europe, n: n("EuroLeague"), grp: "Championnats" });
      if (W) out.push({ k: "WNBA", label: "WNBA", flag: FLAG["États-Unis"], n: n("WNBA"), sub: n("WNBA") ? "" : "reprise en mai", grp: "Championnats" });
    }
    return out;
  }
  function compsHtml(sp) {
    const opts = compOptions(sp); if (opts.length < 3 && sp !== "NBA") return "";
    const cur = (S.comp || {})[sp] || "", sel = opts.find(o => o.k === cur) || opts[0];
    const row = (o, i) => `<button type="button" role="option" class="copt" data-c="${esc(o.k)}" aria-selected="${o.k === sel.k}">
        <span class="cf">${o.flag || ""}</span><span class="cl"><b>${esc(o.label)}</b>${o.sub ? `<small>${esc(o.sub)}</small>` : ""}</span><span class="cn">${o.n || "–"}</span>
        <svg class="ck" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 5 5 9-10"/></svg></button>`;
    let html = "", g = null;
    opts.forEach((o, i) => { if (o.grp !== g) { g = o.grp; if (g) html += `<div class="cgrp">${esc(g)}</div>`; } html += row(o, i); });
    return `<button type="button" class="cbtn" aria-haspopup="listbox" aria-expanded="false"><span class="cf">${sel.flag || ""}</span><span class="cl"><b>${esc(sel.label)}</b></span><span class="cn">${sel.n ? sel.n + " match" + (sel.n > 1 ? "s" : "") : "aucun match"}</span>
      <svg class="cv" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></button>
      <div class="cpop" role="listbox" aria-label="Compétition" hidden><div class="chd"><b>${sp === "Foot" ? "Championnat" : sp === "Tennis" ? "Circuit ou tournoi" : "Championnat"}</b><button type="button" class="cx" aria-label="Fermer">×</button></div><div class="cls">${html}</div></div>`;
  }

  const addDays = (k, n) => { const [y, m, d] = k.split("-").map(Number); return dkey(new Date(y, m - 1, d + n, 12)); };
  const WEEK = "semaine";                                   // vue « les 7 prochains jours »
  function days(sp) {                                       // tous les jours d'aujourd'hui au dernier match connu (au moins 7, au plus 21)
    const t = todayKey(), last = pool(sp).reduce((m, x) => { const k = dkey(x.dt); return k > m ? k : m; }, t);
    const out = []; for (let k = t, n = 0; n < 21 && (k <= last || n < 7); k = addDays(k, 1), n++) out.push(k);
    return out;
  }
  const upcoming = x => new Date(x.dt).getTime() > Date.now() - 3 * 3600e3;
  const count = (sp, d) => pool(sp).filter(x => (d === WEEK ? inWeek(x) && upcoming(x) : dkey(x.dt) === d)).length;
  const inWeek = x => { const k = dkey(x.dt); return k >= todayKey() && k < addDays(todayKey(), 7); };
  function pickDay(sp) {
    if (S.day === WEEK || (S.day && days(sp).includes(S.day))) return S.day;
    if (pool(sp).some(x => dkey(x.dt) === todayKey() && upcoming(x))) return todayKey();
    const nx = pool(sp).filter(x => upcoming(x) && dkey(x.dt) > todayKey()).map(x => dkey(x.dt)).sort()[0];   // rien aujourd'hui : le prochain jour avec des matchs
    return nx && days(sp).includes(nx) ? nx : WEEK;
  }
  const dayName = d => d === WEEK ? "7 prochains jours" : dayLabel(d);
  function stripHtml(sp, day) {
    const chip = (d, top, bot, n) => `<button type="button" data-d="${d}" aria-pressed="${d === day}"${n ? "" : ' class="none"'}><span class="t">${top}</span><span class="b">${bot}</span><span class="n">${n ? n + " match" + (n > 1 ? "s" : "") : "–"}</span></button>`;
    return chip(WEEK, "7 jours", "à venir", count(sp, WEEK)) + days(sp).map(d => {
      const [y, m, dd] = d.split("-").map(Number), dt = new Date(y, m - 1, dd);
      const n = Math.round((dt - new Date(new Date().setHours(0, 0, 0, 0))) / 864e5);
      const top = n === 0 ? "Aujourd'hui" : n === 1 ? "Demain" : dt.toLocaleDateString("fr-FR", { weekday: "short" });
      return chip(d, top, dt.toLocaleDateString("fr-FR", { day: "numeric", month: "short" }), count(sp, d));
    }).join("");
  }

  // ---- morceaux communs
  const probsInline = (x, cls) => {
    const two = x.pd == null;
    const cells = two ? [[short(x, x.a), x.pa], [short(x, x.b), x.pb]] : [[x.a, x.pa], ["Match nul", x.pd], [x.b, x.pb]];
    return `<div class="${cls}${two ? " two" : ""}">${cells.map(([n, p]) => `<div><span class="nm">${esc(n)}</span><span class="pc">${pct(p)}</span></div>`).join("")}</div>`;
  };
  const bar = x => x.pd == null
    ? `<div class="pbar" aria-hidden="true"><span class="b1" style="flex:${x.pa}"></span><span class="b2" style="flex:${x.pb}"></span></div>`
    : `<div class="pbar" aria-hidden="true"><span class="b1" style="flex:${x.pa}"></span><span class="bd" style="flex:${x.pd}"></span><span class="b2" style="flex:${x.pb}"></span></div>`;
  const compLabel = x => x.sport === "Tennis" ? `${x.tour || ""} · ${x.event || x.comp}` : x.comp;
  const go = x => { location.hash = "#m/" + encodeURIComponent(x.k); };

  // ---- carte téléphone
  function mcard(x, showDay) {
    const past = new Date(x.dt).getTime() < Date.now();
    const cr = x.sport !== "Tennis";
    return `<div class="mcard${past ? " past" : ""}" data-k="${encodeURIComponent(x.k)}" role="link" tabindex="0">
      <div class="top"><span class="tm">${showDay ? `<small class="dd">${new Date(x.dt).toLocaleDateString("fr-FR", { weekday: "short", day: "numeric" })}</small>` : ""}${hm(x)}${past ? "<small>Commencé</small>" : ""}</span>
        <span class="mt">${cr ? crest(x.a, "sm") : ""}<span class="n">${esc(x.sport === "NBA" ? bn(x, x.a) : short(x, x.a))}</span><span class="dash">—</span><span class="n">${esc(x.sport === "NBA" ? bn(x, x.b) : short(x, x.b))}</span>${cr ? crest(x.b, "sm") : ""}</span>
        ${Fav.star(x.sport, x.dt, x.a, x.b, x.comp)}</div>
      ${probsInline(x, "pbox")}</div>`;
  }
  function groupKey(x) {
    if (x.sport === "Foot") return { id: "F|" + x.lg, order: ["Sélections nationales", "Coupes d'Europe", "Championnats", "Coupes nationales"].indexOf(FOOTGRP(x)) * 100 + lord(x), html: `<span class="fl">${FLAG[x.country] || ""}</span><span><b>${esc(x.comp)}</b></span>` };
    if (x.sport === "Tennis") return { id: "T|" + x.tour + x.event, order: x.tour === "ATP" ? 0 : 1, html: `<span><b>${esc(x.tour || "")}</b> · ${esc(x.event || x.comp)}${x.round ? " · " + esc(x.round) : ""}</span>` };
    return { id: "B|" + x.comp, order: x.comp === "NBA" ? 0 : 1, html: `<span class="fl">${x.comp === "EuroLeague" ? FLAG.Europe : FLAG["États-Unis"]}</span><span><b>${esc(x.comp || "NBA")}</b></span>` };
  }
  function groupedList(items, withDays) {
    if (withDays) {                                         // plusieurs jours : une seule fois chaque compétition, le jour dans la ligne
      const groups = {}; items.forEach(x => { const g = groupKey(x); (groups[g.id] = groups[g.id] || { g, xs: [] }).xs.push(x); });
      return Object.values(groups).sort((p, q) => p.g.order - q.g.order || new Date(p.xs[0].dt) - new Date(q.xs[0].dt)).map(({ g, xs }) => `<div class="grp">${g.html}</div>` + xs.map(x => mcard(x, true)).join("")).join("");
    }
    const out = []; let lastDay = "";
    const byDay = {}; items.forEach(x => (byDay[dkey(x.dt)] = byDay[dkey(x.dt)] || []).push(x));
    for (const d of Object.keys(byDay).sort()) {
      const groups = {};
      byDay[d].forEach(x => { const g = groupKey(x); (groups[g.id] = groups[g.id] || { g, xs: [] }).xs.push(x); });
      const gs = Object.values(groups).sort((p, q) => p.g.order - q.g.order || new Date(p.xs[0].dt) - new Date(q.xs[0].dt));
      if (withDays && d !== lastDay) { out.push(`<div class="jday" style="margin:16px 0 0">${dayLabel(d, true)}</div>`); lastDay = d; }
      gs.forEach(({ g, xs }) => out.push(`<div class="grp">${g.html}</div>` + xs.map(x => mcard(x)).join("")));
    }
    return out.join("");
  }

  // ---- match du jour et stats
  function matchOfDay(items) {
    const f = items.filter(x => x.sport === "Foot" && new Date(x.dt) > Date.now() - 2 * 3600e3);
    if (f.length) return [...f].sort((p, q) => fame(p) - fame(q) || prio(p) - prio(q) || (q.str || 0) - (p.str || 0))[0];
    const r = items.filter(x => new Date(x.dt) > Date.now() - 2 * 3600e3);
    const pool2 = r.length ? r : items;
    const fv = x => Math.abs(Math.max(x.pa, x.pb) - 0.62);            // un favori net, sans être joué d'avance
    return [...pool2].sort((p, q) => fv(p) - fv(q))[0];
  }
  const setScore = (x, [s, p, w]) => `${short(x, w ? x.b : x.a)} ${w ? s.split("–").reverse().join("–") : s}`;
  function motdRows(x) {
    if (x.sport === "Foot") { const m = footM(x), s = m.sc[0];
      return [["Les deux équipes marquent", pct(m.btts)], ["Plus de 2,5 buts", pct(m.o(3))], ["Score probable", `${s[0]}–${s[1]}`]]; }
    if (x.sport === "Tennis") { const t = tennisS(x);
      return [[`${short(x, x.a)} gagne au moins un set`, pct(t.setA)], [`${short(x, x.b)} gagne au moins un set`, pct(t.setB)], ["Score probable", setScore(x, t.sc[0])]]; }
    const fav = x.mg >= 0 ? x.a : x.b, [a10, b10] = nbaBy(x, 10);
    return [["Écart prévu", (Math.abs(x.mg) < 1 ? "Moins d'1 pt" : `${bn(x, fav)} +${Math.abs(x.mg).toFixed(0)} pts`)], [`${bn(x, x.a)} : victoire par plus de 10 pts`, pct(a10)], [`${bn(x, x.b)} : victoire par plus de 10 pts`, pct(b10)]];
  }
  function motdCard(x) {
    if (!x) return `<div class="pcard"><p class="empty">Aucun match ce jour-là.</p></div>`;
    const cr = x.sport !== "Tennis";
    return `<div class="pcard"><div class="motd-top"><span class="tag">${esc(compLabel(x))}</span><span class="when">· ${whenTxt(x)}</span></div>
      <div class="motd-teams"><span class="t"><span>${esc(short(x, x.a))}</span>${cr ? crest(x.a, "lg") : ""}</span><span class="dash">–</span><span class="t">${cr ? crest(x.b, "lg") : ""}<span>${esc(short(x, x.b))}</span></span></div>
      ${rbar(x, x.pd == null ? [[short(x, x.a), x.pa], [short(x, x.b), x.pb]] : [[x.a, x.pa], ["Match nul", x.pd], [x.b, x.pb]])}
      ${motdRows(x).map(([l, v]) => `<div class="prow"><span>${esc(l)}</span><b>${esc(v)}</b></div>`).join("")}
      <a class="more-link" href="#m/${encodeURIComponent(x.k)}">Voir l'analyse <span aria-hidden="true">→</span></a></div>`;
  }
  function statCands(x) {                                    // statistiques marquantes d'un match (pourcentages élevés de préférence)
    if (x.sport === "Tennis") { const t = tennisS(x), fa = x.pa >= x.pb, und = !fa;
      return [{ v: fa ? t.setB : t.setA, l: `${short(x, fa ? x.b : x.a)} gagne un set`, kind: "tset" },
              { v: Math.max(x.pa, x.pb), l: `${short(x, fa ? x.a : x.b)} gagne`, kind: "twin" }]; }
    if (x.sport === "NBA") { const fa = x.pa >= x.pb, [a5, b5] = nbaBy(x, 5);
      return [{ v: Math.max(x.pa, x.pb), l: `${bn(x, fa ? x.a : x.b)} gagne`, kind: "bwin" }, { v: fa ? a5 : b5, l: `${bn(x, fa ? x.a : x.b)} gagne de plus de 5 pts`, kind: "b5" }]; }
    const m = footM(x), fa = x.pa >= x.pb;
    return [{ v: m.o(2), l: "Plus de 1,5 buts", kind: "o15" }, { v: m.o(3), l: "Plus de 2,5 buts", kind: "o25" }, { v: m.btts, l: "Les deux équipes marquent", kind: "btts" },
            { v: fa ? m.ha : m.aa, l: `${fa ? x.a : x.b} marque au moins un but`, kind: "score" }, { v: Math.max(x.pa, x.pb), l: `${fa ? x.a : x.b} gagne`, kind: "win" }];
  }
  function statsOfDay(items, skip, max = 5) {
    const up = items.filter(x => x !== skip && new Date(x.dt) > Date.now() - 2 * 3600e3);
    const pick = (lo, hi) => {
      const by = {};
      up.forEach(x => {                                    // la meilleure stat de chaque match, entre lo et hi
        statCands(x).filter(c => c.v >= lo && c.v <= hi).forEach(c => (by[x.sport] = by[x.sport] || []).push({ ...c, x, sc: c.v * (x.sport === "Foot" ? 1.15 - fame(x) / 40 : 1) }));
      });
      Object.values(by).forEach(a => a.sort((p, q) => q.sc - p.sc));
      return by;
    };
    let by = pick(0.7, 0.95);
    if (Object.values(by).flat().length < max) { const more = pick(0.55, 0.95); by = more; }
    const out = [], used = new Set(), kinds = {}, order = ["Foot", "Tennis", "NBA"].filter(s => by[s]);
    const ok = c => !used.has(c.x.k) && (kinds[c.kind] || 0) < 2;                         // pas plus de 2 stats du même genre
    const take = c => { out.push(c); used.add(c.x.k); kinds[c.kind] = (kinds[c.kind] || 0) + 1; };
    order.forEach(s => { const c = by[s].find(ok); if (c) take(c); });                       // au moins une par sport
    Object.values(by).flat().sort((p, q) => q.sc - p.sc).forEach(c => { if (out.length < max && ok(c)) take(c); });
    Object.values(by).flat().sort((p, q) => q.sc - p.sc).forEach(c => { if (out.length < max && !used.has(c.x.k)) take(c); });   // compléter si besoin
    return out.sort((p, q) => q.v - p.v);
  }
  const statRow = c => `<a class="stat" href="#m/${encodeURIComponent(c.x.k)}"><span class="v">${pct(c.v)}</span><span class="l"><b>${esc(c.l)}</b>
      <span class="m"><span class="tag">${c.x.sport === "Foot" ? "Foot" : c.x.sport === "NBA" ? c.x.comp : SPN[c.x.sport]}</span><span>${esc(short(c.x, c.x.a))} – ${esc(short(c.x, c.x.b))}</span></span><span class="when">${whenTxt(c.x)}</span></span></a>`;

  // ---- tableau
  function tableRows(items) {
    const lim = S.more ? items.length : 12;
    const rows = items.slice(0, lim).map(x => {
      const cr = x.sport !== "Tennis", past = new Date(x.dt).getTime() < Date.now();
      return `<tr data-k="${encodeURIComponent(x.k)}"${past ? ' class="past"' : ""}><td class="h-sport"><span class="tag">${x.sport === "Foot" ? "Football" : x.sport === "NBA" ? x.comp : x.sport}</span></td>
        <td><span class="mt">${cr ? crest(x.a, "sm") : ""}<span>${esc(short(x, x.a))}</span><span class="dash">–</span><span>${esc(short(x, x.b))}</span>${cr ? crest(x.b, "sm") : ""}</span></td>
        <td class="dt">${whenTxt(x)}</td><td class="c pc">${pct(x.pa)}</td><td class="c pc d">${x.pd == null ? "–" : pct(x.pd)}</td><td class="c pc">${pct(x.pb)}</td></tr>`;
    }).join("");
    return `<table><thead><tr><th class="h-sport">Sport</th><th>Match</th><th>Date / Heure</th><th class="c">P(Équipe 1)</th><th class="c">P(Nul)</th><th class="c">P(Équipe 2)</th></tr></thead><tbody>${rows}</tbody></table>`
      + (items.length > lim ? `<button type="button" class="tbl-more" id="hMore">Afficher les ${items.length - lim} autres matchs</button>` : "");
  }

  // ---- tennis : prochains tournois
  const SURFN = { Hard: "Dur", Clay: "Terre battue", Grass: "Gazon" };
  function toursHtml() {
    let T = []; try { T = window.TennisAPI && TennisAPI.tournaments ? TennisAPI.tournaments() : []; } catch (e) {}
    if (!T.length) return "";
    const t0 = todayKey(), o = { day: "numeric", month: "short" }, d = k => new Date(k + "T12:00:00");
    return `<section class="tours"><h2>Prochains tournois</h2><div class="tlist">${T.slice(0, 10).map(t => {
      const live = t.start <= t0;
      return `<a class="trow" href="#tennis"><span class="td">${d(t.start).toLocaleDateString("fr-FR", o)} – ${d(t.end).toLocaleDateString("fr-FR", o)}${live ? '<small>En cours</small>' : ""}</span>
        <span class="tn"><b>${esc(t.name)}</b><span>${[t.tour, t.city, SURFN[t.surface] || t.surface, t.bo === 5 ? "3 sets gagnants" : ""].filter(Boolean).map(esc).join(" · ")}</span></span></a>`;
    }).join("")}</div></section>`;
  }

  // ---- classement d'un championnat de foot
  function footTable(L) {
    const f = v => (v > 0 ? "+" : "") + v.toFixed(2).replace(".", ",");
    const T = [...L.teams].sort((a, b) => b.pts - a.pts || (b.gf - b.ga) - (a.gf - a.ga) || b.gf - a.gf);
    const form = s => (s || "").split("").map(c => `<i class="fm fm-${c}">${c}</i>`).join("");
    return `<section class="tours"><h2>${esc(L.name)} : classement</h2><div class="pcard ftab"><table><thead><tr><th>#</th><th>Équipe</th><th class="c">J</th><th class="c">Pts</th><th class="c">Diff.</th><th class="c hf">Forme</th><th class="c hf">Attaque</th><th class="c hf">Défense</th></tr></thead><tbody>${T.map((t, i) =>
      `<tr><td class="c">${i + 1}</td><td><span class="mt">${crest(t.name, "sm")}<span>${esc(t.name)}</span></span></td><td class="c">${t.p}</td><td class="c"><b>${t.pts}</b></td><td class="c">${t.gf - t.ga > 0 ? "+" : ""}${t.gf - t.ga}</td><td class="c hf">${form(t.form)}</td><td class="c hf">${f(t.att)}</td><td class="c hf">${f(-t.dfn)}</td></tr>`).join("")}</tbody></table></div>
      <p class="note">V victoire · N nul · D défaite</p></section>`;
  }

  // ---- WNBA hors saison : classement selon le modèle
  function basketTable(comp) {
    const W = BK[comp]; if (!W) return "";
    const f = v => (v > 0 ? "+" : "") + v.toFixed(1).replace(".", ",");
    return `<section class="tours"><h2>${comp} ${comp === "EuroLeague" ? W.season + "-" + String(W.season + 1).slice(2) : W.season} : les équipes</h2><div class="tlist">${W.teams.map((t, i) =>
      `<div class="trow wrow"><span class="td">${i + 1}. ${crest(t.name, "sm")}</span><span class="tn"><b>${esc(t.name)}</b><span>Bilan ${t.w}–${t.l} · attaque ${f(t.o)} · défense ${f(t.d)} pts</span></span></div>`).join("")}</div>
      <p class="note">Attaque et défense : points de plus ou de moins qu'une équipe moyenne.</p></section>`;
  }

  // ---- dessin de l'accueil
  function drawHome() {
    load();
    const sp = curSport(), day = pickDay(sp);
    S.day = day;
    const ds = days(sp);
    const opts = [WEEK, ...ds].map(d => { const n = count(sp, d); return `<option value="${d}"${d === day ? " selected" : ""}>${dayName(d)}${n ? " · " + n + " match" + (n > 1 ? "s" : "") : " · aucun match"}</option>`; }).join("");
    $("hDate").innerHTML = opts; $("hDateM").innerHTML = opts;
    $("hDayLab").textContent = dayName(day);
    const di = day === WEEK ? -1 : ds.indexOf(day); $("hPrev").disabled = day === WEEK; $("hNext").disabled = di >= ds.length - 1;
    $("hStrip").innerHTML = stripHtml(sp, day);
    $("hComps").innerHTML = sp ? compsHtml(sp) : "";
    const on = $("hStrip").querySelector('[aria-pressed="true"]'); if (on) on.scrollIntoView({ block: "nearest", inline: "center" });
    document.querySelectorAll("#hChips button").forEach(b => b.setAttribute("aria-pressed", b.dataset.s === S.sport));
    document.querySelectorAll("#hTabs button").forEach(b => b.setAttribute("aria-pressed", b.dataset.s === sp));
    let items = pool(sp).filter(x => day === WEEK ? inWeek(x) && upcoming(x) : dkey(x.dt) === day), note = "", multi = day === WEEK;
    if (!items.length) {                                   // jour vide : on montre ce qui arrive ensuite
      const nxt = pool(sp).filter(x => dkey(x.dt) > (day === WEEK ? todayKey() : day) && upcoming(x));
      if (nxt.length) {
        const first = dkey(nxt[0].dt);
        items = nxt.filter(x => dkey(x.dt) === first); multi = false;
        note = `<p class="hnote">${day === WEEK ? "Aucun match cette semaine, voici les suivants." : day === todayKey() ? "Aucun match aujourd'hui, voici les suivants." : "Aucun match ce jour-là, voici les suivants."}</p>`;
      }
    }
    items = [...items.filter(upcoming), ...items.filter(x => !upcoming(x))];   // matchs commencés à la fin
    $("hNote").innerHTML = note;
    const bc = sp === "NBA" ? (S.comp || {}).NBA : "", wOff = bc === "WNBA" && !items.length;
    if (wOff) { $("hNote").innerHTML = `<p class="hnote">Saison terminée, reprise en mai. Voici le classement.</p>`; items = []; }
    const fc = sp === "Foot" ? (S.comp || {}).Foot : "";
    let FL = null; try { FL = fc && window.FootAPI && FootAPI.leagues ? FootAPI.leagues().find(l => l.k === fc && !l.cup) : null; } catch (e) {}
    if ((FL || BK[bc]) && !items.length && !wOff) $("hNote").innerHTML = `<p class="hnote">Pas encore de match programmé. Voici le classement.</p>`;
    $("hTours").innerHTML = sp === "Tennis" ? toursHtml() : BK[bc] ? basketTable(bc) : FL ? footTable(FL) : "";
    $("view-jour").classList.toggle("noitems", !items.length && !!(FL || BK[bc]));
    if (small()) {
      $("hList").innerHTML = items.length ? groupedList(items, multi) : wOff || BK[bc] || FL ? "" : `<p class="mempty">Aucun match ${sp === "Tennis" ? "de tennis" : sp === "NBA" ? "de basket" : "de football"} programmé pour l'instant.</p>`;
    } else {
      const motd = matchOfDay(items.filter(accOk));
      $("hMotd").innerHTML = motdCard(motd);
      const st = statsOfDay(items.filter(accOk), motd);
      $("hStats").innerHTML = st.length ? st.map(statRow).join("") : `<p class="empty">Pas de statistique marquante pour ces matchs.</p>`;
      const rest = items.filter(x => x !== motd);
      $("hTable").innerHTML = rest.length ? tableRows(rest) : `<p class="empty" style="padding:18px 16px">Pas d'autre match.</p>`;
    }
    saveS();
  }

  // ---- analyse complète : le bloc de l'outil détaillé (événements, combiné, cotes, prono, partage, simulation…) est déplacé dans la fiche
  const BPFX = { NBA: "nb", EuroLeague: "el", WNBA: "wn" };
  const embIds = x => x.sport === "Foot" ? ["ftResult"] : x.sport === "Tennis" ? ["result"] : (x.comp === "NBA" ? ["nbInj", "nbResult"] : [BPFX[x.comp] + "Result"]);
  let moved = [], embKey = null;
  function restore() {
    for (const m of moved.reverse()) m.parent.insertBefore(m.el, m.next && m.next.parentNode === m.parent ? m.next : null);
    moved = []; embKey = null;
  }
  function embed(x) {
    const box = $("mFull"); if (!box) return;
    const here = location.hash;
    try { x.open(); } catch (e) { console.error(e); }       // choisit le match dans l'outil (change l'adresse : on la remet aussitôt)
    history.replaceState(null, "", here);
    const take = el => { moved.push({ el, parent: el.parentNode, next: el.nextSibling }); box.appendChild(el); };
    for (const id of embIds(x)) {
      const el = $(id); if (!el) continue;
      const host = el.closest(".card"), sim = host && host.nextElementSibling;
      if (sim && sim.classList.contains("sm-card")) take(sim);       // la carte « Simulation du match », en premier
      take(el);
    }
    embKey = x.k;
  }

  // ---- accueil : fil horaire des matchs du jour, en tuiles
  let aDay = null;
  function atile(x) {
    const past = new Date(x.dt).getTime() < Date.now();
    const cand = [[x.pa, x.a], [x.pb, x.b]]; if (x.pd != null) cand.push([x.pd, null]);
    const [p, w] = cand.sort((u, v) => v[0] - u[0])[0];
    const nm = n => esc(x.sport === "NBA" ? bn(x, n) : short(x, n));
    const lab = w == null ? "Match nul" : `${x.sport === "NBA" ? bn(x, w) : short(x, w)} gagne`;
    return `<a class="atile${past ? " past" : ""}" href="#m/${encodeURIComponent(x.k)}"><span class="ac">${esc(compLabel(x))}${past ? " · Commencé" : ""}</span>
      <span class="am">${nm(x.a)}<br><i>contre</i> ${nm(x.b)}</span><span class="ap"><b>${pct(p)}</b><small>${esc(lab)}</small></span></a>`;
  }
  // accueil : pas d'équipe israélienne, pas de match à 50 % – 50 %
  const ISR = /maccabi|hapoel|beitar|bnei |ironi |isra[eë]l/i;
  const accOk = x => !ISR.test(x.a + " " + x.b + " " + (x.country || "")) && !(x.pd == null && Math.abs(x.pa - x.pb) < 0.04);
  function drawAccueil() {
    load();
    const now = Date.now(), up = ALL.filter(x => !x.few && new Date(x.dt).getTime() > now - 2 * 3600e3 && accOk(x));
    const ds = [...new Set(up.map(x => dkey(x.dt)))].sort().slice(0, 6);
    if (!ds.includes(aDay)) aDay = ds[0] || todayKey();
    $("aDays").innerHTML = ds.map(d => {
      const [y, m, dd] = d.split("-").map(Number), dt = new Date(y, m - 1, dd), n = Math.round((dt - new Date(new Date().setHours(0, 0, 0, 0))) / 864e5);
      const t = n === 0 ? "Aujourd'hui" : n === 1 ? "Demain" : dt.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric" });
      return `<button type="button" data-d="${d}" aria-pressed="${d === aDay}">${t}</button>`;
    }).join("");
    $("aDays").querySelectorAll("button").forEach(b => b.onclick = () => { aDay = b.dataset.d; drawAccueil(); });
    const items = up.filter(x => dkey(x.dt) === aDay).sort((p, q) => new Date(p.dt) - new Date(q.dt) || fame(p) - fame(q));
    const by = []; items.forEach(x => { const h = hm(x), g = by[by.length - 1]; if (g && g.h === h) g.xs.push(x); else by.push({ h, xs: [x] }); });
    const nowI = aDay !== todayKey() ? -1 : by.findIndex(g => g.xs.some(x => new Date(x.dt).getTime() > now - 2 * 3600e3));
    $("aTl").innerHTML = by.length ? by.map((g, i) => `<div class="aslot${i === nowI ? " on" : ""}"><span class="ah">${g.h}</span><span class="adot"></span><div class="agrid">${g.xs.map(atile).join("")}</div></div>`).join("")
      : `<p class="mempty">Aucun match programmé pour l'instant.</p>`;
    // ordinateur : match du jour + stats du jour
    const first = up.find(x => new Date(x.dt).getTime() > now), d0 = first ? dkey(first.dt) : todayKey();
    const its = up.filter(x => dkey(x.dt) === d0), motd = matchOfDay(its);
    $("aMotd").innerHTML = motdCard(motd);
    const st = statsOfDay(its, motd, 5);
    $("aStats").innerHTML = st.length ? st.map(statRow).join("") : `<p class="empty">Pas de statistique marquante pour l'instant.</p>`;
  }

  // ---- fiche d'un match
  // ---- résultat du match : une barre unique (favori en rouge, le reste en gris clair)
  function rbar(x, cells) {
    const r = cells.map(c => Math.round(c[1] * 100)), top = Math.max(...r), n = cells.length;
    const mx = r.filter(v => v === top).length > 1 ? -1 : cells[r.indexOf(top)][1];   // égalité : pas de favori
    const al = i => i === 0 ? "l" : i === n - 1 ? "r" : "c";
    const seg = cells.map(([nm, p], i) => `<div class="rs ${al(i)}${p === mx ? " fav" : i === 1 && n === 3 ? " mid" : ""}" style="flex:${Math.max(p, 0.12)} 1 0">${pct(p)}</div>`).join("");
    const lab = cells.map(([nm, p], i) => `<span class="${al(i)}${p === mx ? " fav" : ""}" style="flex:${Math.max(p, 0.12)} 1 0">${esc(x.sport === "NBA" ? bn(x, nm) : nm === "Match nul" ? "Nul" : nm)}</span>`).join("");
    return `<div class="rbar">${seg}</div><div class="rlab">${lab}</div>`;
  }
  function drawMatch(k) {
    restore();
    load();
    const x = findKey(k), box = $("mBody");
    if (!x) { box.innerHTML = `<div class="dcard"><p class="empty">Ce match n'est plus au programme.</p><a class="more-link" href="#jour">Voir les matchs</a></div>`; return; }
    const cr = x.sport !== "Tennis", rows = (l, v) => `<div class="prow"><span>${esc(l)}</span><b>${esc(v)}</b></div>`;
    const favI = x.pd != null && x.pd > Math.max(x.pa, x.pb) ? 1 : (x.pa >= x.pb ? 0 : (x.pd == null ? 1 : 2));
    const cells = x.pd == null ? [[short(x, x.a), x.pa], [short(x, x.b), x.pb]] : [[x.a, x.pa], ["Match nul", x.pd], [x.b, x.pb]];
    let body = "";
    if (x.sport === "Foot") {
      const m = footM(x);
      body = `<div class="dgrp">Buts</div>${rows("Au moins 2 buts", pct(m.o(2)))}${rows("Au moins 3 buts", pct(m.o(3)))}${rows("Au moins 4 buts", pct(m.o(4)))}${rows("Les deux équipes marquent", pct(m.btts))}
        <div class="dgrp">Par équipe</div>${rows(`${x.a} marque au moins un but`, pct(m.ha))}${rows(`${x.b} marque au moins un but`, pct(m.aa))}
        <div class="dgrp">Scores possibles</div>${m.sc.slice(0, 3).map(s => rows(`${x.a} ${s[0]}–${s[1]} ${x.b}`, pct(s[2]))).join("")}`;
    } else if (x.sport === "Tennis") {
      const t = tennisS(x);
      body = `<div class="dgrp">Sets</div>${rows(`${short(x, x.a)} gagne au moins un set`, pct(t.setA))}${rows(`${short(x, x.b)} gagne au moins un set`, pct(t.setB))}${rows(t.bo === 3 ? "Match en 3 sets" : "Match en 5 sets", pct(t.bo === 3 ? 2 * t.s * (1 - t.s) : 6 * t.s * t.s * (1 - t.s) ** 2))}
        <div class="dgrp">Scores possibles</div>${t.sc.slice(0, 3).map(c => rows(setScore(x, c), pct(c[1]))).join("")}`;
    } else {
      const [a5, b5] = nbaBy(x, 5), [a10, b10] = nbaBy(x, 10), close = 1 - a5 - b5, fav = x.mg >= 0 ? x.a : x.b;
      body = `<div class="dgrp">Écart</div>${rows("Écart prévu", (Math.abs(x.mg) < 1 ? "Moins d'1 pt" : `${bn(x, fav)} +${Math.abs(x.mg).toFixed(0)} pts`))}${rows("Match serré (5 pts ou moins)", pct(close))}
        <div class="dgrp">Par équipe</div>${rows(`${bn(x, x.a)} : victoire par plus de 5 pts`, pct(a5))}${rows(`${bn(x, x.a)} : victoire par plus de 10 pts`, pct(a10))}${rows(`${bn(x, x.b)} : victoire par plus de 5 pts`, pct(b5))}${rows(`${bn(x, x.b)} : victoire par plus de 10 pts`, pct(b10))}`;
    }
    const fl = x.sport === "Foot" ? `<span class="fl">${FLAG[x.country] || ""}</span>` : x.sport === "NBA" ? `<span class="fl">${x.comp === "EuroLeague" ? FLAG.Europe : FLAG["États-Unis"]}</span>` : "";
    box.innerHTML = `<div class="dcard">
      <div class="dhead"><span class="lg">${fl}${esc(compLabel(x))}</span><span class="dstar"><span class="when">${whenTxt(x)}</span>${Fav.star(x.sport, x.dt, x.a, x.b, x.comp)}</span></div>
      <div class="dteams">${cr ? crest(x.a, "lg") : "<span></span>"}<span class="mt"><span>${esc(short(x, x.a))}</span><i style="font-style:normal">—</i><span>${esc(short(x, x.b))}</span></span>${cr ? crest(x.b, "lg") : "<span></span>"}</div>
      <div class="dsec">Résultat du match</div>
      ${rbar(x, cells)}${body}
      <div class="dgrp">Cotes justes</div>${cells.map(([n, p]) => rows(n, (1 / Math.max(p, 1e-4)).toFixed(2).replace(".", ","))).join("")}</div>
      <div class="dsec dmore">Analyse détaillée</div>
      <div class="mfull" id="mFull"></div>
      <button type="button" class="dbtn" id="mOpen">Comparer avec d'autres ${x.sport === "Tennis" ? "joueurs" : "équipes"} et voir le classement <span aria-hidden="true">→</span></button>`;
    if (x.open) { embed(x); $("mOpen").onclick = () => { restore(); x.open(); }; }
    else { $("mOpen").remove(); const dm = box.querySelector(".dmore"); if (dm) dm.remove(); }
  }

  // ---- favoris
  function drawFav() {
    load();
    const favs = Fav.all(), keys = Object.keys(favs);
    const items = keys.map(k => findKey(k)).filter(Boolean);
    $("favList").innerHTML = items.length ? groupedList(items, true)
      : `<p class="mempty">${keys.length ? "Vos matchs favoris sont terminés." : "Aucun favori pour l'instant. Touchez ☆ à côté d'un match."}</p>`;
  }

  // ---- navigation
  const VIEWS = ["accueil", "jour", "foot", "tennis", "basket", "euroleague", "wnba", "fav", "match"].filter(k => $("view-" + k));
  const NAVOF = { accueil: "accueil", jour: "jour", match: "jour", foot: "jour", tennis: "jour", basket: "jour", euroleague: "jour", wnba: "jour", fav: "fav" };
  let lastHome = "#jour";
  function show(force) {
    const h = location.hash.slice(1);
    const v = h.startsWith("m/") ? "match" : (VIEWS.includes(h) ? h : (small() ? "accueil" : "jour"));   // téléphone : on arrive sur l'accueil
    if (!force && v === "match" && embKey && embKey === decodeURIComponent(h.slice(2)) && moved.length && !$("view-match").hidden) return;   // déjà affichée
    if (v !== "match") restore();
    VIEWS.forEach(k => { $("view-" + k).hidden = k !== v; });
    document.body.className = document.body.className.replace(/\bv-\w+/g, "").trim() + " v-" + v;
    document.querySelectorAll(".topnav a, .bnav a").forEach(a => a.dataset.v === NAVOF[v] ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
    if (v === "jour") drawHome();
    if (v === "accueil") drawAccueil();
    if (v === "match") drawMatch(decodeURIComponent(h.slice(2)));
    if (v === "fav") drawFav();
    if (v !== "match") lastHome = location.hash || "#jour";
  }
  addEventListener("hashchange", () => { show(); window.scrollTo(0, 0); });

  // ---- clics
  const compPop = open => {
    const pop = $("hComps").querySelector(".cpop"), btn = $("hComps").querySelector(".cbtn"); if (!pop) return;
    pop.hidden = !open; btn.setAttribute("aria-expanded", open); document.body.classList.toggle("cpop-open", open && small());
    if (open) { const on = pop.querySelector('[aria-selected="true"]'); if (on) on.scrollIntoView({ block: "center" }); on && on.focus({ preventScroll: true }); }
  };
  $("hComps").addEventListener("click", e => {
    if (e.target.closest(".cbtn")) { compPop($("hComps").querySelector(".cpop").hidden); return; }
    if (e.target.closest(".cx") || e.target === $("hComps").querySelector(".cpop")) { compPop(false); return; }
    const b = e.target.closest(".copt"); if (!b) return;
    S.comp = S.comp || {}; S.comp[curSport()] = b.dataset.c; S.day = null; S.more = false; compPop(false); drawHome();
  });
  document.addEventListener("click", e => { if (!e.target.closest("#hComps")) compPop(false); });
  document.addEventListener("keydown", e => {
    const pop = $("hComps").querySelector(".cpop"); if (!pop || pop.hidden) return;
    if (e.key === "Escape") { compPop(false); $("hComps").querySelector(".cbtn").focus(); }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { const all = [...pop.querySelectorAll(".copt")], i = all.indexOf(document.activeElement); const n = all[Math.max(0, Math.min(all.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)))]; if (n) { n.focus(); e.preventDefault(); } }
  });
  $("hChips").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; S.sport = b.dataset.s; S.more = false; drawHome(); });
  $("hTabs").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; S.sport = b.dataset.s; drawHome(); });
  const setDay = d => { S.day = d; S.more = false; drawHome(); };
  $("hDate").addEventListener("change", e => setDay(e.target.value));
  $("hDateM").addEventListener("change", e => setDay(e.target.value));
  const step = n => { const ds = days(curSport()), i = S.day === WEEK ? -1 : ds.indexOf(S.day); if (i + n < 0) setDay(WEEK); else if (ds[i + n]) setDay(ds[i + n]); };
  $("hPrev").onclick = () => step(-1); $("hNext").onclick = () => step(1);
  $("hStrip").addEventListener("click", e => { const b = e.target.closest("button[data-d]"); if (b) setDay(b.dataset.d); });
  document.addEventListener("click", e => {
    if (e.target.closest(".star")) return;
    if (e.target.closest("#hMore")) { S.more = true; drawHome(); return; }
    const r = e.target.closest(".mcard[data-k], .tbl tr[data-k]");
    if (r) location.hash = "#m/" + r.dataset.k;
  });
  document.addEventListener("keydown", e => { if (e.key === "Enter" && e.target.matches(".mcard[data-k]")) location.hash = "#m/" + e.target.dataset.k; });
  const back = document.querySelector(".hback");
  if (back) back.onclick = () => { if (history.length > 1 && document.referrer !== undefined && lastHome) history.back(); else location.hash = "#jour"; };
  addEventListener("favchange", () => { if (location.hash === "#fav") drawFav(); });
  let wasSmall = small();
  addEventListener("resize", () => { if (small() !== wasSmall) { wasSmall = small(); if (!$("view-jour").hidden) drawHome(); } });

  // ---- langue (page À propos, sur téléphone)
  const L = (window.I18N && I18N.lang) || "fr";
  document.querySelectorAll(".alang button").forEach(b => { b.setAttribute("aria-pressed", b.dataset.l === L); b.onclick = () => { if (b.dataset.l === L) return; try { localStorage.setItem("pronostat-lang", b.dataset.l); } catch (x) {} location.reload(); }; });

  window.Home = { show, items: () => ALL };
  show();
})();
