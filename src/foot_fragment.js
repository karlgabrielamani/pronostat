(() => {
  const F = __FOOT__;
  const g = id => document.getElementById(id);
  const f = (x, d = 0) => x.toFixed(d).replace(".", ",");
  const MAXG = 10;
  g("ftUpd").textContent = new Date(F.updated).toLocaleDateString("fr-FR", { day: "numeric", month: "long" });
  g("ftAcc").textContent = f(F.acc * 100) + " %";
  g("ftN").textContent = F.n_test.toLocaleString("fr-FR");
  g("ftL").innerHTML = F.order.map(k => `<option value="${k}">${F.leagues[k].name} · ${F.leagues[k].country}</option>`).join("");

  let L = null, T = {}, games = [], meanD = 0;
  const pois = (k, l) => { let p = Math.exp(-l); for (let i = 1; i <= k; i++) p *= l / i; return p; };
  function matrix(h, a) {
    const home = g("ftN0").checked ? 0 : L.home;
    const lam = Math.exp(h.att + a.dfn + home), mu = Math.exp(a.att + h.dfn);
    const m = []; let tot = 0;
    for (let i = 0; i <= MAXG; i++) { m.push([]); for (let j = 0; j <= MAXG; j++) {
      let p = pois(i, lam) * pois(j, mu);
      if (i === 0 && j === 0) p *= 1 - lam * mu * L.rho; else if (i === 0 && j === 1) p *= 1 + lam * L.rho;
      else if (i === 1 && j === 0) p *= 1 + mu * L.rho; else if (i === 1 && j === 1) p *= 1 - L.rho;
      m[i].push(p); tot += p; } }
    for (const r of m) for (let j = 0; j <= MAXG; j++) r[j] /= tot;
    return { m, lam, mu };
  }
  const sum = (m, fn) => { let s = 0; for (let i = 0; i <= MAXG; i++) for (let j = 0; j <= MAXG; j++) if (fn(i, j)) s += m[i][j]; return s; };

  function setLeague(k, keepTeams) {
    L = F.leagues[k];
    g("ftCupNote").hidden = !L.cup;
    T = Object.fromEntries(L.teams.map(t => [t.name, t]));
    meanD = L.teams.reduce((s, t) => s + t.dfn, 0) / L.teams.length;
    const opts = [...L.teams].sort((a, b) => a.name.localeCompare(b.name)).map(t => `<option value="${t.name}">${t.name}</option>`).join("");
    g("ftA").innerHTML = opts; g("ftB").innerHTML = opts;
    const now = Date.now();
    const sod = new Date(); sod.setHours(0, 0, 0, 0);   // les matchs du jour restent visibles jusqu'au lendemain
    games = L.games.filter(x => new Date(x.dt + "Z").getTime() >= sod.getTime()).slice(0, 16);
    g("ftGames").innerHTML = games.length ? games.map((x, i) => {
      const d = new Date(x.dt + "Z");
      const when = d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric" }) + " " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
      const past = d.getTime() < now;
      return `<div class="gw"><button class="game wide${past ? " past" : ""}" data-i="${i}"><span class="when">${when}${past ? " · commencé" : ""}</span><span><b>${x.home}</b> – <b>${x.away}</b></span></button>${Fav.star("Foot", x.dt + "Z", x.home, x.away, L.name)}</div>`;
    }).join("") : `<p class="note">Pas de match programmé dans les données pour l'instant. Choisis deux équipes ci-dessous.</p>`;
    table();
    if (games.length) (g("ftGames").querySelector(".game:not(.past)") || g("ftGames").querySelector(".game")).click();
    else { g("ftA").value = L.teams[0].name; g("ftB").value = L.teams[1].name; render(); }
  }
  g("ftL").addEventListener("change", () => setLeague(g("ftL").value));
  g("ftGames").addEventListener("click", e => {
    const b = e.target.closest(".game"); if (!b) return;
    const x = games[+b.dataset.i];
    g("ftA").value = x.home; g("ftB").value = x.away; g("ftN0").checked = !!x.neutral;
    g("ftGames").querySelectorAll(".game").forEach(el => el.setAttribute("aria-pressed", el === b));
    render();
  });

  let cur = null, timer = null;
  function render() {
    const h = T[g("ftA").value], a = T[g("ftB").value];
    if (h === a) { g("ftErr").hidden = false; g("ftErr").textContent = "Choisis deux équipes différentes."; g("ftResult").style.opacity = .35; return; }
    g("ftErr").hidden = true; g("ftResult").style.opacity = 1;
    const { m, lam, mu } = matrix(h, a);
    const pH = sum(m, (i, j) => i > j), pD = sum(m, (i, j) => i === j), pA = sum(m, (i, j) => i < j);
    g("ftNA").textContent = h.name; g("ftNB").textContent = a.name;
    g("ftPH").textContent = f(pH * 100) + " %"; g("ftPD").textContent = f(pD * 100) + " %"; g("ftPA").textContent = f(pA * 100) + " %";
    g("ftOH").textContent = "Cote juste " + f(1 / pH, 2); g("ftOD").textContent = "Cote juste " + f(1 / pD, 2); g("ftOA").textContent = "Cote juste " + f(1 / pA, 2);
    g("ftBarH").style.width = `calc(${pH * 100}% - 2px)`; g("ftBarD").style.width = `calc(${pD * 100}% - 2px)`; g("ftBarA").style.width = `calc(${pA * 100}% - 2px)`;
    const best = Math.max(pH, pA), fav = pH >= pA ? h : a;
    g("ftVerdict").innerHTML = best < .42 ? `<b>Match très ouvert</b>`
      : `<b>${fav.name}</b> est ${best >= .65 ? "grand favori" : best >= .5 ? "favori" : "légèrement favori"}.`;
    let bi = 0, bj = 0; for (let i = 0; i <= MAXG; i++) for (let j = 0; j <= MAXG; j++) if (m[i][j] > m[bi][bj]) { bi = i; bj = j; }
    g("ftFacts").innerHTML = [
      ["Buts attendus", `${f(lam, 1)} – ${f(mu, 1)}`],
      ["Score le plus probable", `${bi}-${bj} (${f(m[bi][bj] * 100)} %)`],
      ["Forme récente", `${h.form || "–"} · ${a.form || "–"}`],
      ["Classement", `${L.teams.indexOf(h) + 1}e (${h.pts} pts) · ${L.teams.indexOf(a) + 1}e (${a.pts} pts)`],
    ].map(([l, v]) => `<div class="fact"><span class="l">${l}</span><span class="v num">${v}</span></div>`).join("");
    const rows = [
      ["A", `${h.name} ou nul`, pH + pD],
      ["B", `${a.name} ou nul`, pA + pD],
      ["A", `${h.name} gagne de 2 buts ou plus`, sum(m, (i, j) => i - j >= 2)],
      ["B", `${a.name} gagne de 2 buts ou plus`, sum(m, (i, j) => j - i >= 2)],
      ["N", "Les deux équipes marquent", sum(m, (i, j) => i > 0 && j > 0)],
      ["N", "Plus de 1,5 but", sum(m, (i, j) => i + j > 1.5)],
      ["N", "Plus de 2,5 buts", sum(m, (i, j) => i + j > 2.5)],
      ["N", "Plus de 3,5 buts", sum(m, (i, j) => i + j > 3.5)],
      ["A", `${h.name} n'encaisse aucun but`, sum(m, (i, j) => j === 0)],
      ["B", `${a.name} n'encaisse aucun but`, sum(m, (i, j) => i === 0)],
    ];
    cur = { h, a, m, lam, mu };
    seed = 777; drawTl(simMatch(), 99);
    drawFev();
  }

  // ---------- un match simulé : buts avec leur minute ----------
  let seed = 1;
  const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  function simMatch() {
    let r = rnd(), hi = 0, aj = 0;
    outer: for (let i = 0; i <= MAXG; i++) for (let j = 0; j <= MAXG; j++) { r -= cur.m[i][j]; if (r <= 0) { hi = i; aj = j; break outer; } }
    const goals = [];
    for (let k = 0; k < hi; k++) goals.push({ t: "A", min: 1 + Math.floor(rnd() * 94) });
    for (let k = 0; k < aj; k++) goals.push({ t: "B", min: 1 + Math.floor(rnd() * 94) });
    goals.sort((x, y) => x.min - y.min);
    return { goals, hi, aj };
  }
  function drawTl(s, upto) {
    const { h, a } = cur;
    let sh = 0, sa = 0;
    const shown = s.goals.slice(0, upto);
    const items = shown.map((x, i) => {
      x.t === "A" ? sh++ : sa++;
      const min = x.min > 90 ? `90+${x.min - 90}'` : `${x.min}'`;
      return `<li class="${x.t === "A" ? "ga" : "gb"} ${i === upto - 1 && upto < s.goals.length + 1 ? "set-in" : ""}"><span class="min num">${min}</span><span class="dot"></span><span>But ${x.t === "A" ? h.name : a.name}</span><span class="sc num">${sh}–${sa}</span></li>`;
    }).join("");
    const done = upto > s.goals.length;
    g("ftTl").innerHTML = `<div class="tlhead"><span>${h.name}</span><span class="num big">${done ? s.hi : sh} – ${done ? s.aj : sa}</span><span>${a.name}</span></div>
      <ol>${items || (done ? `<li class="none">Aucun but : 0–0</li>` : "")}</ol>${done ? `<p class="note" style="text-align:center">Coup de sifflet final</p>` : ""}`;
  }
  g("ftSim").addEventListener("click", () => {
    if (!cur) return;
    seed = (Date.now() ^ (Math.random() * 1e9)) >>> 0;
    const s = simMatch(); clearInterval(timer); let k = 0; drawTl(s, 0);
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { drawTl(s, 99); return; }
    timer = setInterval(() => { k++; drawTl(s, k); if (k > s.goals.length) clearInterval(timer); }, 700);
  });
  ["ftA", "ftB", "ftN0"].forEach(id => g(id).addEventListener("change", render));
  g("ftSwap").addEventListener("click", () => { const t = g("ftA").value; g("ftA").value = g("ftB").value; g("ftB").value = t; render(); });

  // ---------- combiné ----------
  const FEV = [
    ["H gagne", (i, j) => i > j], ["Match nul", (i, j) => i === j], ["A gagne", (i, j) => i < j],
    ["H ou nul", (i, j) => i >= j], ["A ou nul", (i, j) => i <= j],
    ["H gagne de 2 buts ou plus", (i, j) => i - j >= 2], ["A gagne de 2 buts ou plus", (i, j) => j - i >= 2],
    ["Les deux équipes marquent", (i, j) => i > 0 && j > 0], ["Les deux équipes ne marquent pas", (i, j) => !(i > 0 && j > 0)],
    ["Plus de 1,5 but", (i, j) => i + j > 1.5], ["Plus de 2,5 buts", (i, j) => i + j > 2.5], ["Moins de 2,5 buts", (i, j) => i + j < 2.5],
    ["Plus de 3,5 buts", (i, j) => i + j > 3.5], ["H n'encaisse aucun but", (i, j) => j === 0], ["A n'encaisse aucun but", (i, j) => i === 0],
  ];
  const fLab = (lab, h, a) => lab.replace(/^H /, h.name + " ").replace(/^A /, a.name + " ");
  const fSel = () => [...document.querySelectorAll("#ftEv input:checked")].map(x => +x.dataset.i);
  const fJoint = idx => sum(cur.m, (i, j) => idx.every(k => FEV[k][1](i, j)));
  function drawFev() {
    g("ftEv").innerHTML = FEV.map(([lab, fn], k) => `<label for="fe${k}"><input type="checkbox" id="fe${k}" data-i="${k}"><span>${fLab(lab, cur.h, cur.a)}</span><span class="q num">${f(sum(cur.m, fn) * 100)} %</span></label>`).join("");
    const labs = FEV.map(e => fLab(e[0], cur.h, cur.a));
    renderSugg(g("ftSug"), suggestCombos(FEV.length, fJoint), labs, o => Combo.add("Foot", `${cur.h.name} – ${cur.a.name}`, [labs[o.i], labs[o.j]], o.p));
    fUpd();
  }
  function fUpd() {
    const idx = fSel(), q = idx.length ? fJoint(idx) : 0, pn = idx.reduce((x, k) => x * fJoint([k]), 1);
    g("ftSel").textContent = idx.length ? `${f(q * 100)} % · cote juste ${f(1 / Math.max(q, 1e-4), 2)}${idx.length > 1 ? naiveTxt(q, pn) : ""}` : "Coche un ou plusieurs événements.";
    g("ftAdd").disabled = !idx.length;
  }
  g("ftEv").addEventListener("change", fUpd);
  g("ftAdd").addEventListener("click", () => {
    const idx = fSel(); if (!idx.length) return;
    Combo.add("Foot", `${cur.h.name} – ${cur.a.name}`, idx.map(k => fLab(FEV[k][0], cur.h, cur.a)), fJoint(idx));
    document.querySelectorAll("#ftEv input").forEach(x => x.checked = false); fUpd();
  });

  function table() {
    const sg = v => (v >= 0 ? "+" : "−") + f(Math.abs(v * 100)) + " %";
    const fm = s => s.split("").map(c => `<span class="fm fm-${c}">${c}</span>`).join("");
    g("ftTb").innerHTML = L.teams.map((t, i) => `<tr><td class="num">${i + 1}</td><td class="name">${t.name}</td><td class="num">${t.p}</td><td class="num"><b>${t.pts}</b></td><td class="num">${t.gf - t.ga > 0 ? "+" : ""}${t.gf - t.ga}</td><td class="form">${fm(t.form)}</td><td class="num">${sg(Math.exp(t.att) - 1)}</td><td class="num">${sg(1 - Math.exp(t.dfn - meanD))}</td><td><button data-n="${t.name}" data-s="A">Dom.</button> <button data-n="${t.name}" data-s="B">Ext.</button></td></tr>`).join("");
  }
  g("ftTb").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; g(b.dataset.s === "A" ? "ftA" : "ftB").value = b.dataset.n; render(); window.scrollTo({ top: 0, behavior: "smooth" }); });

  // ---------- accès pour l'onglet « Aujourd'hui » ----------
  function pure(Lg, h, a, neutral) {
    const lam = Math.exp(h.att + a.dfn + (neutral ? 0 : Lg.home)), mu = Math.exp(a.att + h.dfn);
    let pH = 0, pD = 0, pA = 0, tot = 0;
    for (let i = 0; i <= MAXG; i++) for (let j = 0; j <= MAXG; j++) {
      let q = pois(i, lam) * pois(j, mu);
      if (i === 0 && j === 0) q *= 1 - lam * mu * Lg.rho; else if (i === 0 && j === 1) q *= 1 + lam * Lg.rho;
      else if (i === 1 && j === 0) q *= 1 + mu * Lg.rho; else if (i === 1 && j === 1) q *= 1 - Lg.rho;
      tot += q; if (i > j) pH += q; else if (i === j) pD += q; else pA += q;
    }
    return [pH / tot, pD / tot, pA / tot];
  }
  window.FootAPI = {
    updated: F.updated,
    current: () => cur && { sport: "foot", h: cur.h.name, a: cur.a.name, lh: cur.lam, la: cur.mu, comp: L.name },
    list() {
      const out = [];
      for (const k of F.order) {
        const Lg = F.leagues[k], TT = Object.fromEntries(Lg.teams.map(t => [t.name, t]));
        for (const x of Lg.games) {
          const h = TT[x.home], a = TT[x.away]; if (!h || !a) continue;
          const [pH, pD, pA] = pure(Lg, h, a, x.neutral);
          out.push({ sport: "Foot", dt: x.dt + "Z", comp: Lg.name, a: x.home, b: x.away, pa: pH, pd: pD, pb: pA,
            open: () => { location.hash = "#foot"; g("ftL").value = k; setLeague(k);
              const i = games.findIndex(y => y.home === x.home && y.away === x.away);
              const btn = g("ftGames").querySelector(`.game[data-i="${i}"]`);
              if (btn) btn.click(); else { g("ftA").value = x.home; g("ftB").value = x.away; render(); } } });
        }
      }
      return out;
    }
  };

  setLeague(F.order[0]);
})();
