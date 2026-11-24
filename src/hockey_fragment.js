(() => {
  const H = __HOCKEY__;
  const g = id => document.getElementById(id);
  const f = (x, d = 0) => x.toFixed(d).replace(".", ",");
  const MAXG = 12;
  g("hkAcc").textContent = f(H.acc * 100) + " %";
  g("hkN").textContent = H.n_test.toLocaleString("fr-FR");
  g("hkL").innerHTML = H.order.map(k => `<option value="${k}">${H.leagues[k].name} · ${H.leagues[k].country}</option>`).join("");
  // logos des équipes (version claire ou sombre selon le thème)
  window.HKLOGOS = {};
  for (const k of H.order) for (const t of H.leagues[k].teams) if (t.logo && t.logo[0]) window.HKLOGOS[t.name] = t.logo;

  let L = null, T = {}, games = [];
  const pois = (k, l) => { let p = Math.exp(-l); for (let i = 1; i <= k; i++) p *= l / i; return p; };
  // buts attendus après 60 min : niveau de la ligue (30 derniers jours) × attaque × défense adverse (moitié buts, moitié tirs cadrés)
  const lams = (Lg, h, a) => [Lg.lh * h.off * a.dfn, Lg.la * a.off * h.dfn];
  // prolongation et tirs au but : part gagnée à domicile, penchée vers l'équipe qui marque le plus
  const otq = (Lg, lam, mu) => Math.min(.75, Math.max(.25, (Lg.ot || .52) + 0.5 * (lam / (lam + mu) - 0.5)));
  // poids d'un score après 60 min : Poisson + correction Dixon-Coles + nuls plus fréquents (facteur dk)
  const cellW = (Lg, i, j, lam, mu) => {
    let p = pois(i, lam) * pois(j, mu);
    if (i === 0 && j === 0) p *= 1 - lam * mu * Lg.rho; else if (i === 0 && j === 1) p *= 1 + lam * Lg.rho;
    else if (i === 1 && j === 0) p *= 1 + mu * Lg.rho; else if (i === 1 && j === 1) p *= 1 - Lg.rho;
    return i === j ? p * (Lg.dk || 1) : p;
  };
  // tableau des scores après 60 min, avec le but dans la cage vide : une part (en) des matchs à un but d'écart finit à deux buts d'écart
  function scoreM(Lg, lam, mu) {
    const m = []; let tot = 0;
    for (let i = 0; i <= MAXG; i++) { m.push([]); for (let j = 0; j <= MAXG; j++) { const p = cellW(Lg, i, j, lam, mu); m[i].push(p); tot += p; } }
    for (const r of m) for (let j = 0; j <= MAXG; j++) r[j] /= tot;
    const e = Lg.en || 0;
    if (e) for (let i = MAXG - 1; i >= 0; i--) for (let j = MAXG - 1; j >= 0; j--) {
      if (i - j === 1) { const x = m[i][j] * e; m[i][j] -= x; m[i + 1][j] += x; }
      else if (j - i === 1) { const x = m[i][j] * e; m[i][j] -= x; m[i][j + 1] += x; }
    }
    return m;
  }
  function matrix(h, a) {
    const [lam, mu] = lams(L, h, a);
    return { m: scoreM(L, lam, mu), lam, mu, q: otq(L, lam, mu) };
  }
  const sum = (m, fn) => { let s = 0; for (let i = 0; i <= MAXG; i++) for (let j = 0; j <= MAXG; j++) if (fn(i, j)) s += m[i][j]; return s; };

  let curKey = null, curGame = null;
  function setLeague(k) {
    L = H.leagues[k]; curKey = k;
    T = Object.fromEntries(L.teams.map(t => [t.name, t]));
    const opts = [...L.teams].sort((a, b) => a.name.localeCompare(b.name)).map(t => `<option value="${t.name}">${t.name}</option>`).join("");
    g("hkA").innerHTML = opts; g("hkB").innerHTML = opts;
    const now = Date.now();
    const sod = new Date(); sod.setHours(0, 0, 0, 0);
    games = L.games.filter(x => new Date(x.dt + "Z").getTime() >= sod.getTime()).slice(0, 20);
    g("hkGames").innerHTML = games.length ? games.map((x, i) => {
      const d = new Date(x.dt + "Z");
      const when = d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric" }) + " " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
      const past = d.getTime() < now;
      return `<div class="gw"><button class="game wide${past ? " past" : ""}" data-i="${i}"><span class="when">${when}${past ? " · commencé" : ""}</span><span><b>${x.home}</b> – <b>${x.away}</b></span></button>${Fav.star("Hockey", x.dt + "Z", x.home, x.away, L.name)}</div>`;
    }).join("") : `<p class="note">Pas de match programmé dans les données pour l'instant. Choisissez deux équipes ci-dessous.</p>`;
    table();
    if (games.length) (g("hkGames").querySelector(".game:not(.past)") || g("hkGames").querySelector(".game")).click();
    else { g("hkA").value = L.teams[0].name; g("hkB").value = L.teams[1].name; render(); }
  }
  g("hkL").addEventListener("change", () => setLeague(g("hkL").value));
  g("hkGames").addEventListener("click", e => {
    const b = e.target.closest(".game"); if (!b) return;
    const x = games[+b.dataset.i]; curGame = x;
    g("hkA").value = x.home; g("hkB").value = x.away;
    g("hkGames").querySelectorAll(".game").forEach(el => el.setAttribute("aria-pressed", el === b));
    render();
  });

  let cur = null, timer = null;
  function render() {
    const h = T[g("hkA").value], a = T[g("hkB").value];
    if (h === a) { g("hkErr").hidden = false; g("hkErr").textContent = "Choisissez deux équipes différentes."; g("hkResult").style.opacity = .35; return; }
    g("hkErr").hidden = true; g("hkResult").style.opacity = 1;
    const { m, lam, mu, q } = matrix(h, a);
    const pH = sum(m, (i, j) => i > j), pD = sum(m, (i, j) => i === j), pA = sum(m, (i, j) => i < j);
    const fH = pH + pD * q, fA = 1 - fH;
    g("hkNA").textContent = h.name; g("hkNB").textContent = a.name;
    g("hkPH").textContent = f(pH * 100) + " %"; g("hkPD").textContent = f(pD * 100) + " %"; g("hkPA").textContent = f(pA * 100) + " %";
    g("hkOH").textContent = "Cote juste " + f(1 / pH, 2); g("hkOD").textContent = "Cote juste " + f(1 / pD, 2); g("hkOA").textContent = "Cote juste " + f(1 / pA, 2);
    g("hkBarH").style.width = `calc(${pH * 100}% - 2px)`; g("hkBarD").style.width = `calc(${pD * 100}% - 2px)`; g("hkBarA").style.width = `calc(${pA * 100}% - 2px)`;
    const best = Math.max(fH, fA), fav = fH >= fA ? h : a;
    g("hkVerdict").innerHTML = best < .55 ? `<b>Match très ouvert</b>`
      : `<b>${fav.name}</b> est ${best >= .68 ? "grand favori" : best >= .6 ? "favori" : "légèrement favori"}.`;
    g("hkFinal").innerHTML = [[`${h.name} gagne (prolongation comprise)`, fH], [`${a.name} gagne (prolongation comprise)`, fA]]
      .map(([l, p]) => `<div class="fact"><span class="l">${l}</span><span class="v num">${f(p * 100)} % · cote juste ${f(1 / p, 2)}</span></div>`).join("");
    let bi = 0, bj = 0; for (let i = 0; i <= MAXG; i++) for (let j = 0; j <= MAXG; j++) if (m[i][j] > m[bi][bj]) { bi = i; bj = j; }
    const rank = t => L.teams.indexOf(t) + 1;
    g("hkFacts").innerHTML = [
      ["Buts attendus (60 min)", `${f(lam, 1)} – ${f(mu, 1)}`],
      ["Score le plus probable (60 min)", `${bi}-${bj} (${f(m[bi][bj] * 100)} %)`],
      ["Match nul après 60 min", `${f(pD * 100)} %, prolongation gagnée par ${h.name} ${f(q * 100)} %`],
      ["Forme récente", `${h.form || "–"} · ${a.form || "–"}`],
      ["Classement", `${rank(h)}e (${h.pts} pts) · ${rank(a)}e (${a.pts} pts)`],
    ].map(([l, v]) => `<div class="fact"><span class="l">${l}</span><span class="v num">${v}</span></div>`).join("");
    cur = { h, a, m, lam, mu, q };
    seed = 777; drawTl(simMatch(), 99);
    drawEv();
  }

  // ---------- un match simulé : buts avec leur minute, prolongation et tirs au but ----------
  let seed = 1;
  const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  function simMatch() {
    let r = rnd(), hi = 0, aj = 0;
    outer: for (let i = 0; i <= MAXG; i++) for (let j = 0; j <= MAXG; j++) { r -= cur.m[i][j]; if (r <= 0) { hi = i; aj = j; break outer; } }
    const goals = [];
    for (let k = 0; k < hi; k++) goals.push({ t: "A", min: 1 + Math.floor(rnd() * 60) });
    for (let k = 0; k < aj; k++) goals.push({ t: "B", min: 1 + Math.floor(rnd() * 60) });
    goals.sort((x, y) => x.min - y.min);
    let end = null;
    if (hi === aj) {
      const win = rnd() < cur.q ? "A" : "B", so = rnd() < 0.32;          // environ un tiers des prolongations finissent aux tirs au but
      if (so) end = { t: win, so: true }; else { end = { t: win, so: false }; goals.push({ t: win, min: 61 + Math.floor(rnd() * 5), ot: true }); }
    }
    return { goals, hi, aj, end };
  }
  function drawTl(s, upto) {
    const { h, a } = cur;
    let sh = 0, sa = 0;
    const shown = s.goals.slice(0, upto);
    const items = shown.map((x, i) => {
      x.t === "A" ? sh++ : sa++;
      const min = x.ot ? `Prol. ${x.min - 60}'` : `${x.min}'`;
      return `<li class="${x.t === "A" ? "ga" : "gb"} ${i === upto - 1 && upto < s.goals.length + 1 ? "set-in" : ""}"><span class="min num">${min}</span><span class="dot"></span><span>But ${x.t === "A" ? h.name : a.name}</span><span class="sc num">${sh}–${sa}</span></li>`;
    }).join("");
    const done = upto > s.goals.length;
    const fh = s.hi + (s.end && s.end.t === "A" ? 1 : 0), fa = s.aj + (s.end && s.end.t === "B" ? 1 : 0);
    const endTxt = !s.end ? "Fin du match" : s.end.so ? `Tirs au but gagnés par ${s.end.t === "A" ? h.name : a.name}` : "Fin de la prolongation";
    g("hkTl").innerHTML = `<div class="tlhead"><span>${h.name}</span><span class="num big">${done ? fh : sh} – ${done ? fa : sa}</span><span>${a.name}</span></div>
      <ol>${items || (done ? `<li class="none">Aucun but en 60 min</li>` : "")}</ol>${done ? `<p class="note" style="text-align:center">${endTxt}</p>` : ""}`;
  }
  g("hkSim").addEventListener("click", () => {
    if (!cur) return;
    seed = (Date.now() ^ (Math.random() * 1e9)) >>> 0;
    const s = simMatch(); clearInterval(timer); let k = 0; drawTl(s, 0);
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { drawTl(s, 99); return; }
    timer = setInterval(() => { k++; drawTl(s, k); if (k > s.goals.length) clearInterval(timer); }, 700);
  });
  ["hkA", "hkB"].forEach(id => g(id).addEventListener("change", render));
  g("hkSwap").addEventListener("click", () => { const t = g("hkA").value; g("hkA").value = g("hkB").value; g("hkB").value = t; render(); });

  // ---------- événements du match (tous combinables) ----------
  // chaque événement donne un poids à un score (i, j) après 60 min et aux buts de la 1re période (a, b) ;
  // « gagne, prolongation comprise » vaut q (ou 1 − q) quand le score est nul après 60 min
  const EV = [
    ["Résultat après 60 min"],
    ["H gagne", (i, j) => i > j, ["reg","H"]], ["Match nul", (i, j) => i === j, ["reg","D"]], ["A gagne", (i, j) => i < j, ["reg","A"]],
    ["H ou nul", (i, j) => i >= j, ["reg","HD"]], ["A ou nul", (i, j) => i <= j, ["reg","AD"]],
    ["H gagne de 2 buts ou plus", (i, j) => i - j >= 2, ["reg","Hm",2]], ["A gagne de 2 buts ou plus", (i, j) => j - i >= 2, ["reg","Am",2]],
    ["Vainqueur, prolongation et tirs au but compris"],
    ["H gagne (prolongation comprise)", (i, j, a, b, q) => i > j ? 1 : i === j ? q : 0, ["ft","H"]], ["A gagne (prolongation comprise)", (i, j, a, b, q) => i < j ? 1 : i === j ? 1 - q : 0, ["ft","A"]],
    ["Buts après 60 min"],
    ["Plus de 4,5 buts", (i, j) => i + j > 4.5, ["reg","O",4.5]], ["Plus de 5,5 buts", (i, j) => i + j > 5.5, ["reg","O",5.5]], ["Moins de 5,5 buts", (i, j) => i + j < 5.5, ["reg","U",5.5]], ["Plus de 6,5 buts", (i, j) => i + j > 6.5, ["reg","O",6.5]],
    ["Les deux équipes marquent", (i, j) => i > 0 && j > 0, ["reg","BT"]],
    ["H marque 3 buts ou plus", (i, j) => i >= 3, ["reg","Hg",2.5]], ["A marque 3 buts ou plus", (i, j) => j >= 3, ["reg","Ag",2.5]],
    ["H n'encaisse aucun but", (i, j) => j === 0, ["reg","Hcs"]], ["A n'encaisse aucun but", (i, j) => i === 0, ["reg","Acs"]],
    ["1re période"],
    ["But en 1re période", (i, j, a, b) => a + b > 0, ["p1","O",0.5]], ["Plus de 1,5 but en 1re période", (i, j, a, b) => a + b > 1.5, ["p1","O",1.5]],
    ["H mène après la 1re période", (i, j, a, b) => a > b, ["p1","H"]], ["A mène après la 1re période", (i, j, a, b) => a < b, ["p1","A"]],
  ];
  function buildJoint(lam, mu) {
    const G = 9, F1 = L.f1 || 0.295, e = L.en || 0, l1 = lam * F1, m1 = mu * F1, l2 = lam - l1, m2 = mu - m1;
    const A1 = [], B1 = [], A2 = [], B2 = [];
    for (let k = 0; k <= G; k++) { A1.push(pois(k, l1)); B1.push(pois(k, m1)); A2.push(pois(k, l2)); B2.push(pois(k, m2)); }
    const cells = []; let tot = 0;
    for (let a1 = 0; a1 <= G; a1++) for (let b1 = 0; b1 <= G; b1++) for (let a2 = 0; a2 <= G; a2++) for (let b2 = 0; b2 <= G; b2++) {
      const i = a1 + a2, j = b1 + b2; let w = A1[a1] * B1[b1] * A2[a2] * B2[b2];
      if (w < 1e-9) continue;
      w *= cellW(L, i, j, lam, mu) / (pois(i, lam) * pois(j, mu));       // mêmes corrections que le tableau des scores
      tot += w;
      // but dans la cage vide en fin de match : ne change pas la 1re période
      if (e && Math.abs(i - j) === 1) { cells.push([i, j, a1, b1, w * (1 - e)]); cells.push(i > j ? [i + 1, j, a1, b1, w * e] : [i, j + 1, a1, b1, w * e]); }
      else cells.push([i, j, a1, b1, w]);
    }
    cells.forEach(c => c[4] /= tot);
    return cells;
  }
  const joint = idx => { const q = cur.q; let s = 0; for (const c of cur.J) { let w = c[4]; for (const k of idx) { w *= +EV[k][1](c[0], c[1], c[2], c[3], q); if (!w) break; } s += w; } return s; };
  const lab = (t, h, a) => t.replace(/^H /, h.name + " ").replace(/^A /, a.name + " ");
  // de quoi régler le combiné après le match (seulement pour un match du calendrier)
  const hMeta = idx => { const C = HockeyAPI.current(); return C && C.dt ? { dt: C.dt, lg: C.k, h: C.h, a: C.a, rules: idx.map(k => EV[k][2] || null) } : null; };
  const sel = () => [...document.querySelectorAll("#hkEv input:checked")].map(x => +x.dataset.i);
  function drawEv() {
    cur.J = buildJoint(cur.lam, cur.mu);
    g("hkEv").innerHTML = EV.map((e, k) => !e[1] ? `<p class="evh">${e[0]}</p>`
      : `<label for="hke${k}"><input type="checkbox" id="hke${k}" data-i="${k}"><span>${lab(e[0], cur.h, cur.a)}</span><span class="q num">${f(joint([k]) * 100)} %</span></label>`).join("");
    const labs = EV.map(e => lab(e[0], cur.h, cur.a));
    const ok = EV.map((e, k) => e[1] ? k : -1).filter(k => k >= 0);
    const sug = suggestCombos(ok.length, idx => joint(idx.map(t => ok[t]))).map(o => ({ ...o, i: ok[o.i], j: ok[o.j] }));
    renderSugg(g("hkSug"), sug, labs, o => Combo.add("Hockey", `${cur.h.name} – ${cur.a.name}`, [labs[o.i], labs[o.j]], o.p, hMeta([o.i, o.j])));
    upd();
  }
  function upd() {
    const idx = sel(), q = idx.length ? joint(idx) : 0, pn = idx.reduce((x, k) => x * joint([k]), 1);
    g("hkSel").textContent = idx.length ? `${f(q * 100)} % · cote juste ${f(1 / Math.max(q, 1e-4), 2)}${idx.length > 1 ? naiveTxt(q, pn) : ""}` : "Cochez un ou plusieurs événements.";
    g("hkAdd").disabled = !idx.length;
  }
  g("hkEv").addEventListener("change", upd);
  g("hkAdd").addEventListener("click", () => {
    const idx = sel(); if (!idx.length) return;
    Combo.add("Hockey", `${cur.h.name} – ${cur.a.name}`, idx.map(k => lab(EV[k][0], cur.h, cur.a)), joint(idx), hMeta(idx));
    document.querySelectorAll("#hkEv input").forEach(x => x.checked = false); upd();
  });

  function table() {
    const sg = v => (v >= 0 ? "+" : "−") + f(Math.abs(v * 100)) + " %";
    const fm = s => s.split("").map(c => `<span class="fm fm-${c === "P" ? "N" : c}">${c}</span>`).join("");
    g("hkTb").innerHTML = L.teams.map((t, i) => `<tr><td class="num">${i + 1}</td><td class="name">${t.name}</td><td class="num">${t.p}</td><td class="num"><b>${t.pts}</b></td><td class="num">${t.w}-${t.l}-${t.otl}</td><td class="num">${t.gf - t.ga > 0 ? "+" : ""}${t.gf - t.ga}</td><td class="form">${fm(t.form)}</td><td class="num">${sg(t.off - 1)}</td><td class="num">${sg(1 - t.dfn)}</td><td><button data-n="${t.name}" data-s="A">Dom.</button> <button data-n="${t.name}" data-s="B">Ext.</button></td></tr>`).join("");
  }
  g("hkTb").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; g(b.dataset.s === "A" ? "hkA" : "hkB").value = b.dataset.n; render(); window.scrollTo({ top: 0, behavior: "smooth" }); });

  // ---------- accès pour l'accueil et la liste des matchs ----------
  function pure(Lg, h, a) {
    const [lam, mu] = lams(Lg, h, a), m = scoreM(Lg, lam, mu);
    let pH = 0, pD = 0, pA = 0;
    for (let i = 0; i <= MAXG; i++) for (let j = 0; j <= MAXG; j++) { const w = m[i][j]; if (i > j) pH += w; else if (i === j) pD += w; else pA += w; }
    return [pH, pD, pA, lam, mu];
  }
  const openGame = (k, home, away) => {
    location.hash = "#hockey"; g("hkL").value = k; setLeague(k);
    const i = games.findIndex(y => y.home === home && y.away === away);
    const btn = i >= 0 && g("hkGames").querySelector(`.game[data-i="${i}"]`);
    if (btn) btn.click(); else { g("hkA").value = home; if (away) g("hkB").value = away; render(); }
  };
  window.HockeyAPI = {
    updated: H.updated,
    leagues: () => H.order.map(k => ({ k, name: H.leagues[k].name, country: H.leagues[k].country, teams: H.leagues[k].teams })),
    teams() {
      const out = [];
      for (const k of H.order) for (const t of H.leagues[k].teams) out.push({ sport: "Hockey", name: t.name, sub: H.leagues[k].name, open: () => {
        const x = H.leagues[k].games.find(y => y.home === t.name || y.away === t.name);
        if (x) openGame(k, x.home, x.away); else openGame(k, t.name, H.leagues[k].teams.find(y => y.name !== t.name).name); } });
      return out;
    },
    current: () => cur && { sport: "hockey", h: cur.h.name, a: cur.a.name, lh: cur.lam, la: cur.mu, comp: L.name, k: curKey,
      dt: curGame && curGame.home === cur.h.name && curGame.away === cur.a.name ? curGame.dt + "Z" : null },
    list() {
      const out = [];
      for (const k of H.order) {
        const Lg = H.leagues[k], TT = Object.fromEntries(Lg.teams.map(t => [t.name, t]));
        for (const x of Lg.games) {
          const h = TT[x.home], a = TT[x.away]; if (!h || !a) continue;
          const [pH, pD, pA, lam, mu] = pure(Lg, h, a), q = otq(Lg, lam, mu);
          out.push({ sport: "Hockey", lg: k, dt: x.dt + "Z", comp: Lg.name, country: Lg.country, a: x.home, b: x.away, pa: pH, pd: pD, pb: pA,
            pf: pH + pD * q, lh: lam, la: mu, rho: Lg.rho, dk: Lg.dk || 1, str: Math.log(h.off / h.dfn) + Math.log(a.off / a.dfn), en: Lg.en || 0,
            open: () => openGame(k, x.home, x.away) });
        }
      }
      return out;
    }
  };

  setLeague(H.order[0]);
})();
