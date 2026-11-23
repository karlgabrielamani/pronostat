(() => {
  const N = __NBA__;
  const g = id => document.getElementById(id);
  let curGame = null;
  const f = (x, d = 0) => x.toFixed(d).replace(".", ",");
  const T = Object.fromEntries(N.teams.map(t => [t.name, t]));
  const byName = [...N.teams].sort((a, b) => a.name.localeCompare(b.name));
  g("nbUpd").textContent = new Date(N.updated).toLocaleDateString("fr-FR", { day: "numeric", month: "long" });
  g("nbAcc").textContent = f(N.test.acc * 100) + " %";
  g("nbMae").textContent = f(N.test.mae_margin);
  { const u = new Date(N.updated), y = u.getMonth() >= 8 ? u.getFullYear() : u.getFullYear() - 1; g("nbSeason").textContent = `${y}–${String((y + 1) % 100).padStart(2, "0")}`; }
  const opts = byName.map(t => `<option value="${t.name}">${t.name}</option>`).join("");
  g("nbA").innerHTML = opts; g("nbB").innerHTML = opts;

  // prochains matchs (à partir de maintenant)
  const now = Date.now();
  const sod = new Date(); sod.setHours(0, 0, 0, 0);   // les matchs du jour restent visibles jusqu'au lendemain
  const games = N.games.filter(x => new Date(x.dt).getTime() >= sod.getTime()).slice(0, 16);
  g("nbTz").textContent = "· heure locale";
  g("nbGames").innerHTML = games.length ? games.map((x, i) => {
    const d = new Date(x.dt);
    const when = d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric" }) + " " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    const past = d.getTime() < now;
    return `<div class="gw"><button class="game${past ? " past" : ""}" data-i="${i}"><span class="when">${when}${past ? " · commencé" : ""}</span><span><b>${T[x.away].abbr}</b> @ <b>${T[x.home].abbr}</b></span></button>${Fav.star("NBA", x.dt, x.home, x.away, "NBA")}</div>`;
  }).join("") : `<p class="note">Aucun match à venir dans les données.</p>`;
  g("nbGames").addEventListener("click", e => {
    const b = e.target.closest(".game"); if (!b) return;
    const x = games[+b.dataset.i]; curGame = x;
    g("nbA").value = x.home; g("nbB").value = x.away; g("nbN").checked = false;
    g("nbBa").checked = false; g("nbBb").checked = false;
    // dos-à-dos automatique si l'équipe a joué la veille du match (d'après les données)
    const day = new Date(x.dt); day.setUTCHours(day.getUTCHours() - 10);
    const prev = new Date(day); prev.setUTCDate(prev.getUTCDate() - 1);
    const iso = prev.toISOString().slice(0, 10);
    if (T[x.home].last === iso) g("nbBa").checked = true;
    if (T[x.away].last === iso) g("nbBb").checked = true;
    document.querySelectorAll(".game").forEach(el => el.setAttribute("aria-pressed", el === b));
    render();
  });

  // ---------- simulation ----------
  let s = 1;
  const rnd = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
  const gauss = () => { let u = 0; while (u === 0) u = rnd(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * rnd()); };
  const rho = N.corr, sd = N.sd_team;
  function pair(sdx) { const z1 = gauss(), z2 = gauss(); return [sdx * z1, sdx * (rho * z1 + Math.sqrt(1 - rho * rho) * z2)]; }
  // absents : chaque joueur important blessé retire beta × sa valeur (× probabilité qu'il manque le match)
  // l'utilisateur peut retirer un blessé (il joue finalement) ou ajouter un absent choisi dans la liste des joueurs importants
  const OFF = {}, ADD = {};                         // OFF[équipe|joueur] : blessé remis ; ADD[équipe] : {joueur: valeur}
  const missDefault = t => (t.inj || []).reduce((s, x) => s + x.v * x.w, 0);
  const missNow = t => (t.inj || []).reduce((s, x) => s + (OFF[t.name + "|" + x.name] ? 0 : x.v * x.w), 0) + Object.values(ADD[t.name] || {}).reduce((s, v) => s + v, 0);
  function drawInj(a, b) {
    const st = { "Out": "absent", "Doubtful": "incertain", "Questionable": "incertain", "Day-To-Day": "au jour le jour", "Probable": "probable" };
    const esc = x => String(x).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
    const blk = t => {
      const out = (t.inj || []).filter(x => !OFF[t.name + "|" + x.name]), add = Object.keys(ADD[t.name] || {});
      const taken = new Set([...out.map(x => x.name), ...add]);
      const chips = out.map(x => `<span class="ichip">${esc(x.name)} <small>${st[x.status] || x.status}</small><button type="button" data-off="${esc(t.name + "|" + x.name)}" aria-label="Retirer ${esc(x.name)}">×</button></span>`)
        .concat(add.map(n => `<span class="ichip">${esc(n)} <small>ajouté</small><button type="button" data-rm="${esc(t.name)}" data-p="${esc(n)}" aria-label="Retirer ${esc(n)}">×</button></span>`)).join("");
      const back = (t.inj || []).filter(x => OFF[t.name + "|" + x.name]);
      const opts = (t.roster || []).filter(p => !taken.has(p.name));
      const sel = opts.length || back.length ? `<label class="isel"><select data-team="${esc(t.name)}" aria-label="Ajouter un absent">
          <option value="">+ Ajouter un absent</option>${back.map(x => `<option value="back|${esc(x.name)}">${esc(x.name)} (blessé)</option>`).join("")}${opts.map(p => `<option value="${esc(p.name)}" data-v="${p.v}">${esc(p.name)}</option>`).join("")}</select></label>` : "";
      return `<div class="irow"><b>${esc(t.abbr || t.name)}</b><div class="ilist">${chips || '<span class="muted">aucun absent</span>'}${sel}</div></div>`;
    };
    g("nbInj").innerHTML = `<div class="eyebrow">Absents pris en compte</div>${blk(a)}${blk(b)}`;
  }
  g("nbInj").addEventListener("click", e => {
    const o = e.target.closest("[data-off]"); if (o) { OFF[o.dataset.off] = true; render(); return; }
    const r = e.target.closest("[data-rm]"); if (r) { delete (ADD[r.dataset.rm] || {})[r.dataset.p]; render(); }
  });
  g("nbInj").addEventListener("change", e => {
    const s = e.target.closest("select[data-team]"); if (!s || !s.value) return;
    const team = s.dataset.team;
    if (s.value.startsWith("back|")) delete OFF[team + "|" + s.value.slice(5)];
    else { const op = s.selectedOptions[0]; (ADD[team] = ADD[team] || {})[s.value] = +op.dataset.v || 0; }
    render();
  });
  function expected(a, b) {
    const neutral = g("nbN").checked;
    const h = neutral ? 0 : N.hca / 2;
    const beta = N.beta || 0;
    const ea = N.mu + a.o - b.d + h - (g("nbBa").checked ? N.b2b : 0) - beta * missNow(a);
    const eb = N.mu + b.o - a.d - h - (g("nbBb").checked ? N.b2b : 0) - beta * missNow(b);
    return [ea, eb];
  }
  function simGame(ea, eb, quarters) {
    const qs = [];
    let ta = 0, tb = 0;
    for (let q = 0; q < 4; q++) {
      const [na, nb] = pair(sd / 2);
      const qa = Math.max(10, Math.round(ea / 4 + na)), qb = Math.max(10, Math.round(eb / 4 + nb));
      ta += qa; tb += qb; if (quarters) qs.push([qa, qb]);
    }
    let ot = 0;
    while (ta === tb) {
      const [na, nb] = pair(sd * Math.sqrt(5 / 48));
      const oa = Math.max(0, Math.round(ea * 5 / 48 + na)), ob = Math.max(0, Math.round(eb * 5 / 48 + nb));
      ta += oa; tb += ob; ot++; if (quarters) qs.push([oa, ob]);
    }
    return { ta, tb, ot, qs };
  }

  let cur = null, timer = null;
  function render() {
    const a = T[g("nbA").value], b = T[g("nbB").value];
    g("nbBaL").textContent = `${a.name} a joué la veille`;
    g("nbBbL").textContent = `${b.name} a joué la veille`;
    if (a === b) { g("nbErr").hidden = false; g("nbErr").textContent = "Choisissez deux équipes différentes."; g("nbResult").style.opacity = .35; return; }
    g("nbErr").hidden = true; g("nbResult").style.opacity = 1;
    drawInj(a, b);
    const [ea, eb] = expected(a, b);
    s = 20261107;
    const M = 10000; let wa = 0, ot = 0, a10 = 0, b10 = 0, close = 0; const tot = [], sims = [];
    const exp = ea + eb, base = Math.round(exp) + 0.5, lines = [base - 10, base, base + 10];
    for (let i = 0; i < M; i++) {
      const r = simGame(ea, eb, true);
      if (r.ta > r.tb) wa++; if (r.ot) ot++;
      if (r.ta - r.tb >= 10) a10++; if (r.tb - r.ta >= 10) b10++;
      if (Math.abs(r.ta - r.tb) <= 5) close++;
      tot.push(r.ta + r.tb); sims.push(r);
    }
    const p = wa / M;
    g("nbNA").textContent = a.name; g("nbNB").textContent = b.name;
    g("nbWA").textContent = f(p * 100) + " %"; g("nbWB").textContent = f((1 - p) * 100) + " %";
    g("nbBarA").style.width = `calc(${p * 100}% - 1px)`; g("nbBarB").style.width = `calc(${(1 - p) * 100}% - 1px)`;
    g("nbOA").textContent = "Cote juste " + f(1 / p, 2); g("nbOB").textContent = "Cote juste " + f(1 / (1 - p), 2);
    const fav = p >= .5 ? a : b, pf = Math.max(p, 1 - p), spread = Math.abs(ea - eb);
    const lvl = pf >= .8 ? "grand favori" : pf >= .65 ? "favori net" : "léger favori";
    g("nbVerdict").innerHTML = pf < .55 ? `<b>Match très serré</b>` : `<b>${fav.name}</b> est ${lvl} (+${f(spread)} pts)`;
    g("nbScore").innerHTML = [
      ["Score prévu", `${Math.round(ea)} – ${Math.round(eb)}`],
      ["Écart prévu", `${f(spread, 1)} pts pour ${ea >= eb ? a.abbr : b.abbr}`],
      ["Total prévu", `${f(exp, 1)} pts`],
      ["Bilan cette saison", `${a.w}-${a.l} · ${b.w}-${b.l}`],
    ].map(([l, v]) => `<div class="fact"><span class="l">${l}</span><span class="v num">${v}</span></div>`).join("");
    const rows = [
      ["A", `${a.name} gagne de 10 points ou plus`, a10 / M],
      ["B", `${b.name} gagne de 10 points ou plus`, b10 / M],
      ["N", "Match serré (5 points d'écart ou moins)", close / M],
      ["N", "Prolongation", ot / M],
      ...lines.map(l => ["N", `Plus de ${f(l, 1)} points au total`, tot.filter(x => x > l).length / M]),
    ];
    const med = k => { const v = sims.map(r => r[k]).sort((x, y) => x - y); return Math.round(v[v.length >> 1]) - 0.5; };
    cur = { a, b, ea, eb, sims, lines, half: Math.round(exp / 2) + 0.5, ta: med("ta"), tb: med("tb") };
    drawNev();
    if (plKey !== a.name + "|" + b.name) { PSEL.clear(); plTeam = 0; plKey = a.name + "|" + b.name; }   // autre match : on repart de zéro
    drawPl();
    s = 4242; drawBoard(simGame(ea, eb, true), 99);
  }
  function drawBoard(m, upto) {
    const { a, b } = cur, n = m.qs.length;
    const head = `<div class="board-row nb head" style="grid-template-columns:minmax(0,1fr) repeat(${n},34px) 48px"><span class="who"></span>${m.qs.map((_, i) => `<span>${i < 4 ? "Q" + (i + 1) : "P" + (i - 3)}</span>`).join("")}<span>Total</span></div>`;
    const done = upto >= n;
    const row = (t, k) => {
      const mine = k === 0, won = mine ? m.ta > m.tb : m.tb > m.ta;
      let run = 0;
      const cells = m.qs.map((q, i) => { if (i < upto) run += q[k]; return i < upto ? `<span class="${i === upto - 1 && !done ? "set-in" : ""}">${q[k]}</span>` : `<span></span>`; }).join("");
      return `<div class="board-row nb ${done && won ? "winner" : ""}" style="grid-template-columns:minmax(0,1fr) repeat(${n},34px) 48px"><span class="who" style="border-left:4px solid ${mine ? "var(--a)" : "var(--b)"}">${t.name}</span>${cells}<span class="${done ? (won ? "win" : "lose") : ""}">${run || ""}</span></div>`;
    };
    g("nbBoard").innerHTML = head + row(a, 0) + row(b, 1);
  }
  g("nbSim").addEventListener("click", () => {
    if (!cur) return;
    s = (Date.now() ^ (Math.random() * 1e9)) >>> 0;
    const m = simGame(cur.ea, cur.eb, true);
    clearInterval(timer); let k = 0; drawBoard(m, 0);
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { drawBoard(m, 99); return; }
    timer = setInterval(() => { k++; drawBoard(m, k); if (k >= m.qs.length) clearInterval(timer); }, 600);
  });
  ["nbA", "nbB", "nbBa", "nbBb", "nbN"].forEach(id => g(id).addEventListener("change", render));
  g("nbSwap").addEventListener("click", () => { const t = g("nbA").value; g("nbA").value = g("nbB").value; g("nbB").value = t; const c = g("nbBa").checked; g("nbBa").checked = g("nbBb").checked; g("nbBb").checked = c; render(); });

  // ---------- combiné ----------
  const NEV = [
    ["A gagne", r => r.ta > r.tb], ["B gagne", r => r.tb > r.ta],
    ["A gagne de 10 points ou plus", r => r.ta - r.tb >= 10], ["B gagne de 10 points ou plus", r => r.tb - r.ta >= 10],
    ["A gagne de 5 points ou moins", r => r.ta > r.tb && r.ta - r.tb <= 5], ["B gagne de 5 points ou moins", r => r.tb > r.ta && r.tb - r.ta <= 5],
    ["Match serré (5 points ou moins)", r => Math.abs(r.ta - r.tb) <= 5], ["Prolongation", r => r.ot > 0],
    ["A marque plus de TA points", r => r.ta > cur.ta], ["B marque plus de TB points", r => r.tb > cur.tb],
    ["Plus de L0 points au total", (r, l) => r.ta + r.tb > l[0]], ["Plus de L1 points au total", (r, l) => r.ta + r.tb > l[1]],
    ["Moins de L1 points au total", (r, l) => r.ta + r.tb < l[1]], ["Plus de L2 points au total", (r, l) => r.ta + r.tb > l[2]],
    ["A mène à la mi-temps", r => r.qs[0][0] + r.qs[1][0] > r.qs[0][1] + r.qs[1][1]],
    ["B mène à la mi-temps", r => r.qs[0][0] + r.qs[1][0] < r.qs[0][1] + r.qs[1][1]],
    ["A gagne le 1er quart-temps", r => r.qs[0][0] > r.qs[0][1]], ["B gagne le 1er quart-temps", r => r.qs[0][0] < r.qs[0][1]],
    ["Plus de HH points en 1re mi-temps", r => r.qs[0][0] + r.qs[0][1] + r.qs[1][0] + r.qs[1][1] > cur.half],
  ];
  const nLab = lab => lab.replace(/^A /, cur.a.name + " ").replace(/^B /, cur.b.name + " ").replace(/L(\d)/, (_, k) => f(cur.lines[+k], 1)).replace("HH", f(cur.half, 1)).replace("TA", f(cur.ta, 1)).replace("TB", f(cur.tb, 1));
  const nSel = () => [...document.querySelectorAll("#nbEv input:checked")].map(x => +x.dataset.i);
  const nJoint = idx => cur.sims.filter(r => idx.every(k => NEV[k][1](r, cur.lines))).length / cur.sims.length;
  function drawNev() {
    g("nbEv").innerHTML = NEV.map(([lab], k) => `<label for="ne${k}"><input type="checkbox" id="ne${k}" data-i="${k}"><span>${nLab(lab)}</span><span class="q num">${f(nJoint([k]) * 100)} %</span></label>`).join("");
    const labs = NEV.map(e => nLab(e[0]));
    renderSugg(g("nbSug"), suggestCombos(NEV.length, nJoint), labs, o => Combo.add("NBA", `${cur.a.name} – ${cur.b.name}`, [labs[o.i], labs[o.j]], o.p),
      "En NBA, le vainqueur et le total de points sont presque indépendants : aucune paire d'événements ne se renforce vraiment pour ce match. Les combinés du même match y apportent donc peu.");
    nUpd();
  }
  function nUpd() {
    const idx = nSel(), q = idx.length ? nJoint(idx) : 0, pn = idx.reduce((x, k) => x * nJoint([k]), 1);
    g("nbSel").textContent = idx.length ? `${f(q * 100)} % · cote juste ${f(1 / Math.max(q, 1e-4), 2)}${idx.length > 1 ? naiveTxt(q, pn) : ""}` : "Cochez un ou plusieurs événements.";
    g("nbAdd").disabled = !idx.length;
  }
  g("nbEv").addEventListener("change", nUpd);
  g("nbAdd").addEventListener("click", () => {
    const idx = nSel(); if (!idx.length) return;
    Combo.add("NBA", `${cur.a.name} – ${cur.b.name}`, idx.map(k => nLab(NEV[k][0])), nJoint(idx));
    document.querySelectorAll("#nbEv input").forEach(x => x.checked = false); nUpd();
  });

  // classement
  let key = "net", dir = -1;
  function table() {
    const rows = N.teams.map(t => ({ ...t, net: t.o + t.d }));
    rows.sort((x, y) => { const p = x[key], q = y[key]; return (typeof p === "string" ? p.localeCompare(q) : p - q) * dir; });
    const sg = v => (v >= 0 ? "+" : "−") + f(Math.abs(v), 1);
    g("nbTb").innerHTML = rows.map((t, i) => `<tr><td class="num">${i + 1}</td><td class="name">${t.name}</td><td class="num">${t.w}-${t.l}</td><td class="num">${sg(t.o)}</td><td class="num">${sg(t.d)}</td><td class="num"><b>${sg(t.net)}</b></td><td><button data-n="${t.name}" data-s="A">Dom.</button> <button data-n="${t.name}" data-s="B">Ext.</button></td></tr>`).join("");
  }
  document.querySelectorAll("th[data-nk]").forEach(th => th.addEventListener("click", () => {
    const k = th.dataset.nk; if (k === "i") return;
    dir = key === k ? -dir : (k === "name" ? 1 : -1); key = k;
    document.querySelectorAll("th[data-nk]").forEach(x => x.removeAttribute("aria-sort"));
    th.setAttribute("aria-sort", dir > 0 ? "ascending" : "descending"); table();
  }));
  g("nbTb").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; g(b.dataset.s === "A" ? "nbA" : "nbB").value = b.dataset.n; render(); window.scrollTo({ top: 0, behavior: "smooth" }); });

  // ---------- joueurs : probabilités individuelles (src/players.py) ----------
  // loi binomiale négative (moyenne m, variance v) ; points ajustés au score prévu de l'équipe pour ce match
  const PLY = N.players || {};
  const LINES = { pts: [5, 10, 15, 20, 25, 30, 35, 40, 45], reb: [2, 4, 6, 8, 10, 12, 14, 16], ast: [2, 4, 6, 8, 10, 12, 14], tpm: [1, 2, 3, 4, 5, 6, 7] };
  const SLAB = { pts: "points", reb: "rebonds", ast: "passes", tpm: "tirs à 3 pts" };
  const sf = (m, v, k) => {                          // P(X ≥ k)
    if (k <= 0) return 1; m = Math.max(m, 0.05); let c = 0, p;
    if (v <= m * 1.0001) { p = Math.exp(-m); for (let i = 0; i < k; i++) { c += p; p *= m / (i + 1); } }
    else { const r = m * m / (v - m), q = m / v; p = Math.pow(q, r); for (let i = 0; i < k; i++) { c += p; p *= (i + r) / (i + 1) * (1 - q); } }
    return Math.min(1, Math.max(0, 1 - c));
  };
  const adj = p => 0.955 * p + 0.01;                 // sorties sur blessure, banc en fin de match (voir le backtest)
  const PSEL = new Map();                            // clé → {lab, p}
  let plTeam = 0, plKey = "";
  function plOut(t, name) {
    const inj = (t.inj || []).find(x => x.name === name && !OFF[t.name + "|" + x.name]);
    if ((ADD[t.name] || {})[name] !== undefined) return "absent";
    return inj ? (inj.status === "Out" ? "absent" : "incertain") : "";
  }
  function drawPl() {
    const box = g("nbPlBox"), { a, b, ea, eb } = cur;
    if (!PLY[a.name] && !PLY[b.name]) { box.hidden = true; return; }
    box.hidden = false;
    const tms = [a, b];
    g("nbPlT").innerHTML = tms.map((t, i) => `<button type="button" data-t="${i}" aria-pressed="${i === plTeam}">${t.abbr || t.name}</button>`).join("");
    const t = tms[plTeam], d = PLY[t.name], st = g("nbPlS").value;
    if (!d) { g("nbPl").innerHTML = `<p class="note">Pas de données joueurs pour cette équipe.</p>`; plUpd(); return; }
    const fac = Math.min(1.15, Math.max(0.85, (plTeam === 0 ? ea : eb) / d.ppg));
    const esc = x => String(x).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
    const list = st === "dd" ? d.pl.filter(p => p.dd >= 0.05) : d.pl;
    g("nbPl").innerHTML = !list.length ? `<p class="note">Aucun double-double récent.</p>` : list.map(p => {
      const o = plOut(t, p.name);
      let avg, chips;
      if (st === "dd") {
        avg = `${f(p.dd * 100)} % de ses matchs`;
        chips = p.dd >= 0.05 ? [{ k: 0, pr: adj(p.dd) }] : [];
      } else {
        const m = p[st] * (st === "pts" ? fac : 1), v = p[st + "v"] * (st === "pts" ? fac : 1);
        avg = `moy. ${f(m, 1)}`;
        const all = LINES[st].map(k => ({ k, pr: adj(sf(m, v, k)) })).filter(x => x.pr >= 0.12 && x.pr <= 0.93);
        chips = all.sort((x, y) => Math.abs(x.pr - .6) - Math.abs(y.pr - .6)).slice(0, 3).sort((x, y) => x.k - y.k);
      }
      const cells = o === "absent" ? "" : chips.map(c => {
        const key = `${t.name}|${p.name}|${st}|${c.k}`;
        const lab = st === "dd" ? `${p.name} double-double` : `${p.name} ${c.k}+ ${SLAB[st]}`;
        if (PSEL.has(key)) PSEL.get(key).p = c.pr;
        return `<label class="pchip"><input type="checkbox" data-key="${esc(key)}" data-lab="${esc(lab)}" data-p="${c.pr}"${PSEL.has(key) ? " checked" : ""}><span>${st === "dd" ? "oui" : c.k + "+"}</span><b>${f(c.pr * 100)} %</b></label>`;
      }).join("");
      return `<div class="plr${o === "absent" ? " out" : ""}"><span class="pn">${esc(p.name)}<small>${o ? o + " · " : ""}${avg}</small></span><div class="plc">${cells}</div></div>`;
    }).join("");
    plUpd();
  }
  function plUpd() {
    const v = [...PSEL.values()], q = v.reduce((x, s) => x * s.p, 1);
    g("nbPlSel").textContent = v.length ? `${f(q * 100)} % · cote juste ${f(1 / Math.max(q, 1e-4), 2)}` : "Cochez un ou plusieurs événements.";
    g("nbPlAdd").disabled = !v.length;
  }
  g("nbPlT").addEventListener("click", e => { const b = e.target.closest("[data-t]"); if (!b) return; plTeam = +b.dataset.t; drawPl(); });
  g("nbPlS").addEventListener("change", drawPl);
  g("nbPl").addEventListener("change", e => {
    const x = e.target.closest("input[data-key]"); if (!x) return;
    if (x.checked) PSEL.set(x.dataset.key, { lab: x.dataset.lab, p: +x.dataset.p }); else PSEL.delete(x.dataset.key);
    plUpd();
  });
  g("nbPlAdd").addEventListener("click", () => {
    const v = [...PSEL.values()]; if (!v.length) return;
    Combo.add("NBA", `${cur.a.name} – ${cur.b.name}`, v.map(s => s.lab), v.reduce((x, s) => x * s.p, 1));
    PSEL.clear(); drawPl();
  });

  // ---------- accès pour l'onglet « Aujourd'hui » ----------
  const erf = x => { const s = Math.sign(x); x = Math.abs(x); const u = 1 / (1 + 0.3275911 * x);
    return s * (1 - (((((1.061405429 * u - 1.453152027) * u) + 1.421413741) * u - 0.284496736) * u + 0.254829592) * u * Math.exp(-x * x)); };
  window.NbaAPI = {
    updated: N.updated,
    teams() {
      return N.teams.map(t => ({ sport: "NBA", name: t.name, sub: "NBA", open: () => {
        location.hash = "#basket";
        const i = games.findIndex(y => y.home === t.name || y.away === t.name);
        const btn = i >= 0 && g("nbGames").querySelector(`.game[data-i="${i}"]`);
        if (btn) btn.click(); else { g("nbA").value = t.name; if (g("nbB").value === t.name) g("nbB").value = N.teams.find(x => x.name !== t.name).name; render(); } } }));
    },
    current: () => cur && { sport: "nba", h: cur.a.name, a: cur.b.name, ea: cur.ea, eb: cur.eb, p: cur.sims.filter(r => r.ta > r.tb).length / cur.sims.length,
      dt: curGame && curGame.home === cur.a.name && curGame.away === cur.b.name ? curGame.dt : null },
    list() {
      return N.games.filter(x => T[x.home] && T[x.away]).map(x => {
        const a = T[x.home], b = T[x.away];
        const be = N.beta || 0;
        const m = (N.mu + a.o - b.d + N.hca / 2 - be * missDefault(a)) - (N.mu + b.o - a.d - N.hca / 2 - be * missDefault(b));
        const p = 0.5 * (1 + erf(m / (sd * Math.sqrt(2 * (1 - rho))) / Math.SQRT2));
        return { sport: "NBA", dt: x.dt, comp: "NBA", a: x.home, b: x.away, pa: p, pb: 1 - p, mg: m, sg: sd * Math.sqrt(2 * (1 - rho)),
          open: () => { location.hash = "#basket"; const i = games.findIndex(y => y.home === x.home && y.away === x.away && y.dt === x.dt);
            const btn = g("nbGames").querySelector(`.game[data-i="${i}"]`);
            if (btn) btn.click(); else { g("nbA").value = x.home; g("nbB").value = x.away; render(); } } };
      });
    }
  };

  // match par défaut : le premier match à venir, sinon les deux meilleures équipes
  if (games.length) { (g("nbGames").querySelector(".game:not(.past)") || g("nbGames").querySelector(".game")).click(); }
  else { g("nbA").value = N.teams[0].name; g("nbB").value = N.teams[1].name; render(); }
  table();
})();
