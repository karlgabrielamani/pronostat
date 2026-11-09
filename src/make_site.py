"""Construit le site public à partir de la sortie de update_all.py :
- app.html  : l'appli (out/pronos.html dans une page autonome)
- index.html : la page d'accueil (promesse, stats du jour, match du jour, offres, questions)
et recopie les données mises à jour dans data/."""
import html, json, math, os, re, shutil, sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
OUT, SRC = f"{ROOT}/out", f"{ROOT}/src"
sys.path.insert(0, SRC)
SITE = "https://karlgabrielamani.github.io/pronostat/"
FORM_ACTION = ""   # adresse Formspree (https://formspree.io/f/xxxx) pour la liste d'attente Premium ; vide = bouton « bientôt »
esc = lambda s: html.escape(str(s), quote=True)
page = open(f"{OUT}/pronos.html", encoding="utf-8").read()
page = re.sub(r'<meta name="claude:[^>]*>\s*', "", page)
fonts = "\n".join(re.findall(r'<link[^>]+fonts\.(?:googleapis|gstatic)\.com[^>]*>', page))
I18N = open(f"{SRC}/i18n.html", encoding="utf-8").read()
THEME = open(f"{SRC}/theme.css", encoding="utf-8").read()


def head(title, desc, extra=""):
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{SITE}">
<meta property="og:image" content="{SITE}icon-512.png">
<meta name="theme-color" content="#D0202E">
<link rel="icon" href="icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="icon-180.png">
<link rel="manifest" href="manifest.json">
<style>html{{-webkit-text-size-adjust:100%}}body{{margin:0;font-size:14px}}img{{max-width:100%}}[hidden]{{display:none!important}}:root{{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}</style>
{extra}
</head>
<body>
"""


# ---------------------------------------------------------------- l'appli
open(f"{ROOT}/app.html", "w", encoding="utf-8").write(
    head("Pronostat · l'appli", "Probabilités foot, tennis et NBA : chaque match, événement par événement.") + page + "\n</body>\n</html>\n")

# ---------------------------------------------------------------- calculs pour la page d'accueil
load = lambda n: json.load(open(f"{OUT}/{n}", encoding="utf-8")) if os.path.exists(f"{OUT}/{n}") else None
F, N, T, W = load("foot_tool.json"), load("nba_tool.json"), load("tennis_tool.json"), load("wta_tool.json")
now = datetime.now(timezone.utc)
until = now + timedelta(hours=40)
pct = lambda p: f"{round(p * 100)} %"
dec = lambda x: f"{x:.1f}".replace(".", ",")
def when(s):
    d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
soon = lambda s: now <= when(s) <= until
PRIO = ["UCL", "E0", "SP1", "I1", "D1", "F1", "N1", "UEL", "B1", "P1", "UECL", "E1", "SC0", "T1", "G1", "D2", "SP2", "I2", "F2", "E2", "E3", "SC1"]


def foot_events(L, h, a, neutral=False):
    lam = math.exp(h["att"] + a["dfn"] + (0 if neutral else L["home"])); mu = math.exp(a["att"] + h["dfn"]); rho = L["rho"]
    pois = lambda k, l: math.exp(-l) * l ** k / math.factorial(k)
    M = {}
    for i in range(11):
        for j in range(11):
            q = pois(i, lam) * pois(j, mu)
            if (i, j) == (0, 0): q *= 1 - lam * mu * rho
            elif (i, j) == (0, 1): q *= 1 + lam * rho
            elif (i, j) == (1, 0): q *= 1 + mu * rho
            elif (i, j) == (1, 1): q *= 1 - rho
            M[i, j] = q
    tot = sum(M.values()); P = lambda f: sum(q for (i, j), q in M.items() if f(i, j)) / tot
    best = max(M, key=M.get)
    hn, an = h["name"], a["name"]
    return {"H": P(lambda i, j: i > j), "D": P(lambda i, j: i == j), "A": P(lambda i, j: i < j), "score": f"{best[0]}-{best[1]}",
            "ev": [("Les deux équipes marquent", P(lambda i, j: i > 0 and j > 0), 1),
                   ("Plus de 2,5 buts", P(lambda i, j: i + j > 2), 1),
                   ("Moins de 2,5 buts", P(lambda i, j: i + j < 3), 1),
                   (f"{hn} gagne", P(lambda i, j: i > j), 0), (f"{an} gagne", P(lambda i, j: i < j), 0),
                   (f"{hn} ou nul", P(lambda i, j: i >= j), 0), (f"{an} ou nul", P(lambda i, j: i <= j), 0),
                   (f"{hn} n'encaisse aucun but", P(lambda i, j: j == 0), 1), (f"{an} n'encaisse aucun but", P(lambda i, j: i == 0), 1)]}


cands, match_day = [], None
try:
    if F:
        for k in sorted(F["order"], key=lambda x: PRIO.index(x) if x in PRIO else 99):
            L = F["leagues"][k]; TM = {t["name"]: t for t in L["teams"]}
            for g in L.get("games", []):
                if g["home"] not in TM or g["away"] not in TM or not (now <= when(g["dt"]) <= now + timedelta(days=21)): continue
                e = foot_events(L, TM[g["home"]], TM[g["away"]], g.get("neutral", False))
                m = {"sport": "Football", "comp": L["name"], "dt": g["dt"], "a": g["home"], "b": g["away"], **e}
                if match_day is None or (not soon(match_day["dt"]) and soon(g["dt"])): match_day = m
                if not soon(g["dt"]): continue
                for txt, p, novel in e["ev"]:
                    if .66 <= p <= .9: cands.append((p + .06 * novel - .004 * (PRIO.index(k) if k in PRIO else 30), txt, p, m))
except Exception as ex:
    print("  ATTENTION accueil foot :", repr(ex))
try:
    import history
    if N:
        for g in N.get("games", []):
            if not soon(g["dt"]): continue
            p = history.nba_prob(N, g["home"], g["away"]); fav, pf = (g["home"], p) if p >= .5 else (g["away"], 1 - p)
            m = {"sport": "NBA", "comp": "NBA", "dt": g["dt"], "a": g["home"], "b": g["away"]}
            if .7 <= pf <= .9: cands.append((pf - .03, f"{fav} gagne", pf, m))
    for tour, D in (("ATP", T), ("WTA", W)):
        if not D: continue
        names = {p["name"] for p in D["players"]}
        for g in D.get("live", []):
            if not soon(g["dt"]) or g["p1"] not in names or g["p2"] not in names: continue
            p = history.tennis_prob(D, g["p1"], g["p2"], g.get("surface", "Hard"), g.get("bo", 3))
            fav, pf = (g["p1"], p) if p >= .5 else (g["p2"], 1 - p)
            # probabilité de gagner un set, déduite de la probabilité de gagner le match (2 ou 3 sets gagnants)
            lo, hi = .5, .9999
            for _ in range(50):
                s = (lo + hi) / 2; pm = s * s * (3 - 2 * s) if g.get("bo", 3) == 3 else s ** 3 * (10 - 15 * s + 6 * s * s)
                lo, hi = (s, hi) if pm < pf else (lo, s)
            und = g["p2"] if fav == g["p1"] else g["p1"]
            m = {"sport": "Tennis", "comp": f'{g.get("tour", tour)} · {tour}', "dt": g["dt"], "a": g["p1"], "b": g["p2"]}
            if .7 <= pf <= .9: cands.append((pf - .02, f"{fav} gagne", pf, m))
            pset = 1 - s ** (2 if g.get("bo", 3) == 3 else 3)
            if .3 <= pset <= .6: cands.append((.66 + pset / 4, f"{und} gagne au moins un set", pset, m))
except Exception as ex:
    print("  ATTENTION accueil tennis/NBA :", repr(ex))

cands.sort(key=lambda c: -c[0])
stats, seen = [], set()
for sc, txt, p, m in cands:
    key = (m["a"], m["b"])
    if key in seen: continue
    seen.add(key); stats.append((txt, p, m))
    if len(stats) == 4: break

n_test = 0
for D in (F, N, T):
    try: n_test += int((D or {}).get("n_test") or (D or {}).get("test", {}).get("n") or 0)
    except Exception: pass
n_txt = f"plus de {n_test // 1000 * 1000:,}".replace(",", " ") if n_test >= 2000 else "des milliers de"
comps = [F["leagues"][k]["name"] for k in sorted(F["order"], key=lambda x: PRIO.index(x) if x in PRIO else 99)] if F else []

# ---------------------------------------------------------------- page d'accueil
SP = {"Football": "Football", "Tennis": "Tennis", "NBA": "NBA"}
t_ = lambda m: f'<time data-dt="{when(m["dt"]).isoformat()}"></time>'
def stat_card(txt, p, m, big=False):
    return f"""<article class="st{' big' if big else ''}"><b class="pc">{pct(p)}</b><div><p class="ev">{esc(txt)}</p>
      <p class="mt"><span class="tag">{esc(SP[m["sport"]])}</span> {esc(m["a"])} – {esc(m["b"])} · {t_(m)}</p></div></article>"""

stats_html = ""
if stats:
    stats_html = f"""<section class="blk" id="stat"><h2>La stat du jour</h2>{stat_card(*stats[0], big=True)}
      <div class="sts">{''.join(stat_card(*s) for s in stats[1:])}</div></section>"""

md_html = ""
if match_day:
    m = match_day
    evs = [("Les deux équipes marquent", next(p for t, p, _ in m["ev"] if t == "Les deux équipes marquent")),
           ("Plus de 2,5 buts", next(p for t, p, _ in m["ev"] if t == "Plus de 2,5 buts")),
           (f'{m["a"]} n\'encaisse aucun but', m["ev"][7][1]), (f'{m["b"]} n\'encaisse aucun but', m["ev"][8][1])]
    md_html = f"""<section class="blk"><h2>Le match du jour</h2>
    <article class="md"><p class="mt"><span class="tag">{esc(m["comp"])}</span> {t_(m)}</p>
      <div class="md-t"><div><b>{esc(m["a"])}</b><span class="pa">{pct(m["H"])}</span></div><div class="dr"><b>Nul</b><span>{pct(m["D"])}</span></div><div class="r"><b>{esc(m["b"])}</b><span class="pb">{pct(m["A"])}</span></div></div>
      <div class="bar"><i style="width:{m["H"]*100:.1f}%;background:var(--a)"></i><i style="width:{m["D"]*100:.1f}%;background:var(--ink-3)"></i><i style="width:{m["A"]*100:.1f}%;background:var(--b)"></i></div>
      <ul class="evs">{''.join(f'<li><span>{esc(t)}</span><b>{pct(p)}</b></li>' for t, p in evs)}<li><span>Score le plus probable</span><b>{esc(m["score"])}</b></li></ul>
      <a class="btn" href="app.html#foot">Voir tous les événements du match</a></article></section>"""

ICON = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" aria-hidden="true"><path d="M6 19 V13 M12 19 V5 M18 19 V10"/></svg>'
FEATS = [("Chaque événement en %", "Les deux équipes marquent, plus de 2,5 buts, gagne au moins un set… Pas seulement 1, N ou 2."),
         ("Combinés cohérents", "Les événements qui vont ensemble, avec leur vraie probabilité commune et leur cote juste."),
         ("Simulation du match", "Regardez le match se jouer avec les forces du modèle, ou rejouez-le 10 000 fois."),
         ("Recherche et favoris", "Trouvez une équipe ou un joueur en deux lettres, suivez vos matchs d'une étoile.")]
waitlist = (f"""<form class="wl" action="{esc(FORM_ACTION)}" method="POST"><input type="email" name="email" required placeholder="Votre e-mail" autocomplete="email"><button type="submit">Me prévenir</button></form>"""
            if FORM_ACTION else '<span class="btn ghost" aria-disabled="true">Bientôt disponible</span>')
FAQ = [("Est-ce un conseil de pari ?", "Non. Pronostat donne des probabilités calculées par un modèle statistique. Ce n'est pas une garantie de résultat, et les bookmakers ont souvent raison."),
       ("D'où viennent les chiffres ?", f"D'un modèle statistique entraîné sur les résultats passés, testé sur {n_txt} matchs. Il est recalculé chaque matin avec les derniers résultats."),
       ("Quels sports et compétitions ?", "Le football (grands championnats européens et coupes d'Europe), le tennis ATP et WTA, et la NBA."),
       ("Est-ce gratuit ?", "Oui. Une offre Premium arrivera bientôt pour les fonctions avancées.")]

css = """<style>
.lp { max-width: 960px; margin: 0 auto; padding: 12px max(16px, env(safe-area-inset-right, 0px)) 40px max(16px, env(safe-area-inset-left, 0px)); display: grid; gap: 34px; }
.appbar { max-width: none; margin: 0; }
.appbar .open { margin-left: auto; font: inherit; font-weight: 700; font-size: 14px; color: #fff; background: var(--hot); border-radius: 999px; padding: 9px 16px; text-decoration: none; white-space: nowrap; }
.appbar .open + .lang { margin-left: 0; }
.hero { display: grid; gap: 14px; padding-top: 10px; }
.hero h1 { font-size: clamp(30px, 7vw, 46px); line-height: 1.08; margin: 0; text-wrap: balance; letter-spacing: -0.02em; }
.hero h1 em { font-style: normal; color: var(--hot); }
.hero p { font-size: 17px; color: var(--ink-2); line-height: 1.5; margin: 0; max-width: 60ch; }
.ctas { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 4px; }
.btn { display: inline-flex; align-items: center; justify-content: center; min-height: 46px; padding: 0 20px; border-radius: 12px; background: var(--hot); color: #fff; font-weight: 700; font-size: 15px; text-decoration: none; border: 1px solid var(--hot); }
.btn.ghost { background: var(--surface); color: var(--ink); border-color: var(--line2); }
.blk { display: grid; gap: 12px; }
.blk h2 { margin: 0; font-size: 22px; }
.blk > p.sub { margin: -4px 0 0; }
.st { display: flex; gap: 14px; align-items: center; background: var(--surface); border: 1px solid var(--line); border-radius: 16px; padding: 14px 16px; }
.st .pc { font-size: 26px; font-weight: 700; color: var(--hot); min-width: 74px; font-variant-numeric: tabular-nums; }
.st.big { padding: 20px; } .st.big .pc { font-size: 46px; min-width: 120px; } .st.big .ev { font-size: 19px; }
.st .ev { margin: 0; font-weight: 700; font-size: 15px; } .st > div { min-width: 0; }
.mt { margin: 4px 0 0; font-size: 13px; color: var(--ink-3); }
.tag { display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; background: var(--track); color: var(--ink-2); margin-right: 4px; }
.sts { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.md { background: var(--surface); border: 1px solid var(--line); border-radius: 16px; padding: 18px; display: grid; gap: 14px; }
.md .mt { margin: 0; }
.md-t { display: grid; grid-template-columns: 1fr auto 1fr; gap: 10px; align-items: end; }
.md-t div { display: grid; gap: 2px; min-width: 0; } .md-t b { font-size: 15px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.md-t span { font-size: 30px; font-weight: 700; font-variant-numeric: tabular-nums; } .md-t .pa { color: var(--a); } .md-t .pb { color: var(--b); }
.md-t .dr { text-align: center; } .md-t .dr span { font-size: 22px; color: var(--ink-2); } .md-t .r { text-align: right; }
.bar { display: flex; gap: 4px; height: 8px; } .bar i { display: block; border-radius: 4px; }
.evs { list-style: none; margin: 0; padding: 0; display: grid; gap: 0; }
.evs li { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-top: 1px solid var(--line); font-size: 15px; }
.evs b { font-variant-numeric: tabular-nums; }
.feats { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); }
.feats div { background: var(--surface); border: 1px solid var(--line); border-radius: 16px; padding: 16px; }
.feats b { display: block; font-size: 16px; margin-bottom: 6px; } .feats p { margin: 0; color: var(--ink-3); line-height: 1.45; }
.cov { display: flex; flex-wrap: wrap; gap: 6px; } .cov span { padding: 6px 12px; border-radius: 999px; background: var(--surface); border: 1px solid var(--line); font-size: 13px; font-weight: 600; }
.plans { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); }
.plan { background: var(--surface); border: 1px solid var(--line); border-radius: 16px; padding: 18px; display: grid; gap: 10px; align-content: start; }
.plan.top { border: 2px solid var(--hot); }
.plan h3 { margin: 0; font-size: 18px; } .plan .pr { font-size: 28px; font-weight: 700; } .plan .pr small { font-size: 14px; color: var(--ink-3); font-weight: 600; }
.plan ul { margin: 0; padding-left: 18px; color: var(--ink-2); line-height: 1.6; }
.plan .lab { justify-self: start; font-size: 11px; font-weight: 700; color: #fff; background: var(--hot); border-radius: 999px; padding: 3px 10px; }
.wl { display: flex; gap: 8px; flex-wrap: wrap; } .wl input { flex: 1; min-width: 0; font: inherit; font-size: 16px; padding: 0 12px; height: 46px; border-radius: 12px; border: 1px solid var(--line2); background: var(--bg); color: var(--ink); }
.wl button { font: inherit; font-weight: 700; height: 46px; padding: 0 16px; border-radius: 12px; border: 0; background: var(--hot); color: #fff; cursor: pointer; }
.faq details { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px; margin-bottom: 8px; }
.faq summary { font-weight: 700; font-size: 15px; cursor: pointer; } .faq p { margin: 8px 0 0; color: var(--ink-2); line-height: 1.5; }
.foot { color: var(--ink-3); font-size: 13px; line-height: 1.5; border-top: 1px solid var(--line); padding-top: 18px; }
@media (max-width: 520px) { .st.big { flex-direction: column; align-items: flex-start; gap: 6px; } .st.big .pc { font-size: 52px; } .appbar .open { padding: 8px 12px; font-size: 13px; } }
</style>"""

landing = head("Pronostat · Probabilités foot, tennis et NBA",
               f"Les probabilités de chaque match, événement par événement : football, tennis et NBA, recalculées chaque matin.",
               fonts + "\n<style>" + THEME + "</style>\n" + css) + f"""
<div class="lp">
  <header class="appbar"><a class="logo" href="./"><i>{ICON}</i>Pronostat</a><a class="open" href="app.html">Ouvrir l'appli</a></header>
  <section class="hero">
    <h1>Les probabilités de chaque match, <em>événement par événement.</em></h1>
    <p>Football, tennis et NBA. Pas seulement qui va gagner : les deux équipes marquent, le nombre de buts, les sets… Calculé chaque matin par un modèle testé sur {esc(n_txt)} matchs.</p>
    <div class="ctas"><a class="btn" href="app.html">Ouvrir l'appli gratuitement</a><a class="btn ghost" href="#offres">Voir les offres</a></div>
  </section>
  {stats_html}
  {md_html}
  <section class="blk"><h2>Ce que vous trouvez dans Pronostat</h2>
    <div class="feats">{''.join(f'<div><b>{esc(a)}</b><p>{esc(b)}</p></div>' for a, b in FEATS)}</div></section>
  <section class="blk"><h2>Compétitions couvertes</h2>
    <div class="cov">{''.join(f'<span>{esc(c)}</span>' for c in comps)}<span>Tennis ATP</span><span>Tennis WTA</span><span>NBA</span></div></section>
  <section class="blk" id="offres"><h2>Offres</h2>
    <div class="plans">
      <div class="plan"><h3>Gratuit</h3><div class="pr">0 €</div><ul><li>Tous les matchs du jour</li><li>Probabilités 1, N, 2</li><li>Recherche et favoris</li></ul><a class="btn ghost" href="app.html">Ouvrir l'appli</a></div>
      <div class="plan top"><span class="lab">Bientôt</span><h3>Premium</h3><div class="pr">3,99 € <small>/ mois</small></div><ul><li>Tous les événements en %</li><li>Combinés cohérents</li><li>Simulations et 10 000 matchs simulés</li><li>Sans publicité</li></ul>{waitlist}</div>
      <div class="plan"><h3>Pros</h3><div class="pr">Sur devis</div><ul><li>Médias, blogs, créateurs</li><li>Widget ou flux de probabilités</li><li>Vos championnats</li></ul></div>
    </div></section>
  <section class="blk faq"><h2>Questions fréquentes</h2>{''.join(f'<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in FAQ)}</section>
  <footer class="foot">Pronostat · Probabilités à titre informatif, pas un conseil de pari. Réservé aux plus de 18 ans.</footer>
</div>
<script>
document.querySelectorAll("time[data-dt]").forEach(t => {{ const d = new Date(t.dataset.dt), td = new Date(); const day = d.toDateString() === td.toDateString() ? "Aujourd'hui" : d.toLocaleDateString("fr-FR", d - td < 6 * 864e5 ? {{ weekday: "long" }} : {{ weekday: "short", day: "numeric", month: "short" }}); t.textContent = day + " " + d.toLocaleTimeString("fr-FR", {{ hour: "2-digit", minute: "2-digit" }}); }});
</script>
{I18N}
</body>
</html>
"""
# i18n doit s'exécuter avant le script des heures (correction des dates) : on le place en tête
landing = landing.replace("<body>\n", "<body>\n" + I18N, 1).replace(f"</script>\n{I18N}\n</body>", "</script>\n</body>")
open(f"{ROOT}/index.html", "w", encoding="utf-8").write(landing)

for name in ["tennis_history.csv", "tennis_tool.json", "wta_history.csv", "wta_tool.json", "cups_history.csv", "predictions_log.csv", "paper_bets.csv"]:
    src = f"{OUT}/{name}"
    if os.path.exists(src) and os.path.getsize(src) > 0:
        shutil.copy(src, f"{ROOT}/data/{name}")
print("Site écrit :", f"{ROOT}/index.html", "et", f"{ROOT}/app.html", f"· {len(stats)} stats du jour", "· match du jour :" , (match_day or {}).get("a"), "-", (match_day or {}).get("b"))
