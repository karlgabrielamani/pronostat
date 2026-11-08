"""Coupes d'Europe (Ligue des Champions, Europa League, Conference League).

Une note commune à toute l'Europe : un seul modèle de Poisson (attaque/défense par équipe, avantage du terrain,
matchs récents plus importants) ajusté sur les 19 championnats ET les matchs de coupes d'Europe, qui relient les
championnats entre eux. Résultats et calendrier des coupes : ESPN. Historique stocké dans data/cups_history.csv.
"""
import json, re, unicodedata, urllib.request, difflib
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import numpy as np
import pandas as pd
from scipy.optimize import minimize

CUPS = {"UCL": ("uefa.champions", "Ligue des Champions"), "UEL": ("uefa.europa", "Europa League"), "UECL": ("uefa.europa.conf", "Conference League")}
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/scoreboard?dates={d:%Y%m%d}"
XI = 0.0019                       # demi-vie d'environ un an, comme les championnats

ALIASES = {"paris saint germain": "Paris SG", "internazionale": "Inter", "inter milan": "Inter", "borussia dortmund": "Dortmund",
           "bayer leverkusen": "Leverkusen", "eintracht frankfurt": "Ein Frankfurt", "vfb stuttgart": "Stuttgart",
           "atletico madrid": "Ath Madrid", "athletic club": "Ath Bilbao", "athletic bilbao": "Ath Bilbao", "real sociedad": "Sociedad",
           "real betis": "Betis", "manchester city": "Man City", "manchester united": "Man United", "tottenham hotspur": "Tottenham",
           "newcastle united": "Newcastle", "nottingham forest": "Nott'm Forest", "feyenoord rotterdam": "Feyenoord",
           "ajax amsterdam": "Ajax", "union st gilloise": "St. Gilloise", "union saint gilloise": "St. Gilloise", "sporting cp": "Sp Lisbon",
           "sporting lisbon": "Sp Lisbon", "sc braga": "Sp Braga", "braga": "Sp Braga", "olympiacos": "Olympiakos", "paok salonika": "PAOK",
           "olympique marseille": "Marseille", "olympique lyonnais": "Lyon", "lyon": "Lyon", "stade rennais": "Rennes", "ac milan": "Milan",
           "as roma": "Roma", "celta vigo": "Celta", "rayo vallecano": "Vallecano", "west ham united": "West Ham", "brighton hove albion": "Brighton",
           "wolverhampton wanderers": "Wolves", "rb leipzig": "RB Leipzig", "tsg hoffenheim": "Hoffenheim", "sc freiburg": "Freiburg",
           "mainz": "Mainz", "fsv mainz 05": "Mainz", "1 fsv mainz 05": "Mainz", "vitoria guimaraes": "Guimaraes", "fc twente": "Twente",
           "fc utrecht": "Utrecht", "az alkmaar": "AZ Alkmaar", "psv eindhoven": "PSV Eindhoven", "go ahead eagles": "Go Ahead Eagles",
           "kaa gent": "Gent", "krc genk": "Genk", "royal antwerp": "Antwerp", "rsc anderlecht": "Anderlecht", "cercle brugge": "Cercle Brugge",
           "heart of midlothian": "Hearts", "hibernian": "Hibernian", "aberdeen": "Aberdeen", "celtic": "Celtic", "rangers": "Rangers",
           "istanbul basaksehir": "Buyuksehyr", "basaksehir": "Buyuksehyr", "besiktas": "Besiktas", "fenerbahce": "Fenerbahce",
           "galatasaray": "Galatasaray", "aek athens": "AEK", "panathinaikos": "Panathinaikos", "fc porto": "Porto", "sl benfica": "Benfica",
           "racing genk": "Genk", "nec nijmegen": "Nijmegen", "heidenheim 1846": "Heidenheim", "cercle brugge ksv": "Cercle Brugge",
           "vitoria guimaraes": "Guimaraes", "vitoria de guimaraes": "Guimaraes", "afc bournemouth": "Bournemouth"}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s.replace("-", " ").replace(".", " "))
    words = [w for w in s.split() if w not in {"fc", "cf", "ac", "sc", "afc", "club", "de", "fk", "sk", "bk", "if", "cd", "ssc", "as", "ss", "us", "rcd", "rc", "ogc", "losc", "1"}]
    return " ".join(words)


def fetch(lg, d):
    req = urllib.request.Request(ESPN.format(lg=lg, d=d), headers={"User-Agent": "pronos-weekly-update"})
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read())
        except Exception: pass
    return {}


def parse(code, data):
    out = []
    for e in data.get("events", []):
        c = e["competitions"][0]
        comp = {x["homeAway"]: x for x in c["competitors"]}
        if "home" not in comp or "away" not in comp: continue
        st = c["status"]["type"]
        out.append(dict(id=e["id"], cup=code, dt=e["date"], home=comp["home"]["team"]["displayName"], away=comp["away"]["team"]["displayName"],
                        hg=comp["home"].get("score"), ag=comp["away"].get("score"), done=bool(st.get("completed")), state=st.get("state"),
                        neutral=bool(c.get("neutralSite"))))
    return out


def fetch_range(start, end, threads=8):
    days = [start + timedelta(days=k) for k in range((end - start).days + 1)]
    jobs = [(code, lg, d) for code, (lg, _) in CUPS.items() for d in days]
    with ThreadPoolExecutor(threads) as ex:
        res = list(ex.map(lambda j: parse(j[0], fetch(j[1], j[2])), jobs))
    rows = {r["id"]: r for lst in res for r in lst}
    return pd.DataFrame(rows.values())


def map_names(espn_names, fd_names):
    """Relie les noms ESPN des clubs des 19 championnats aux noms football-data. Les autres clubs gardent leur nom ESPN."""
    fd_norm = {norm(n): n for n in fd_names}
    out = {}
    for n in espn_names:
        k = norm(n)
        if k in ALIASES and ALIASES[k] in fd_names: out[n] = ALIASES[k]; continue
        if k in fd_norm: out[n] = fd_norm[k]; continue
        best = difflib.get_close_matches(k, list(fd_norm), n=1, cutoff=0.86)
        if best: out[n] = fd_norm[best[0]]; continue
        out[n] = n                                   # club d'un championnat non suivi : note tirée des seules coupes
    return out


def fit(H, A, hg, ag, days, home_flag):
    """Poisson attaque/défense avec avantage du terrain, pondéré dans le temps — gradient analytique (rapide)."""
    teams = sorted(set(H) | set(A)); idx = {t: i for i, t in enumerate(teams)}; n = len(teams)
    hi, ai = np.array([idx[t] for t in H]), np.array([idx[t] for t in A])
    hg, ag, w, hf = np.asarray(hg, float), np.asarray(ag, float), np.exp(-XI * np.asarray(days, float)), np.asarray(home_flag, float)
    lam_reg = 1e-2
    def f(p):
        att, dfn, home, base = p[:n], p[n:2 * n], p[2 * n], p[2 * n + 1]
        ll_h = base + att[hi] - dfn[ai] + home * hf; ll_a = base + att[ai] - dfn[hi]
        lh, la = np.exp(ll_h), np.exp(ll_a)
        nll = -np.sum(w * (hg * ll_h - lh + ag * ll_a - la)) + lam_reg * (att @ att + dfn @ dfn)
        rh, ra = w * (hg - lh), w * (ag - la)
        g = np.zeros_like(p)
        g[:n] = -(np.bincount(hi, rh, n) + np.bincount(ai, ra, n)) + 2 * lam_reg * att
        g[n:2 * n] = (np.bincount(ai, rh, n) + np.bincount(hi, ra, n)) + 2 * lam_reg * dfn
        g[2 * n] = -np.sum(rh * hf); g[2 * n + 1] = -np.sum(rh + ra)
        return nll, g
    p0 = np.zeros(2 * n + 2); p0[2 * n] = 0.2; p0[2 * n + 1] = 0.3
    r = minimize(f, p0, jac=True, method="L-BFGS-B", options={"maxiter": 2000})
    att, dfn = r.x[:n], r.x[n:2 * n]
    return dict(att=dict(zip(teams, att)), dfn=dict(zip(teams, dfn)), home=float(r.x[2 * n]), base=float(r.x[2 * n + 1]))


def probs(m, h, a, neutral=False, maxg=10):
    lam = np.exp(m["base"] + m["att"].get(h, 0) - m["dfn"].get(a, 0) + (0 if neutral else m["home"]))
    mu = np.exp(m["base"] + m["att"].get(a, 0) - m["dfn"].get(h, 0))
    from math import factorial
    g = np.arange(maxg + 1)
    ph = np.array([np.exp(-lam) * lam ** k / factorial(k) for k in g]); pa = np.array([np.exp(-mu) * mu ** k / factorial(k) for k in g])
    M = np.outer(ph, pa); M /= M.sum()
    return np.tril(M, -1).sum(), np.trace(M), np.triu(M, 1).sum()


def build_matches(dom, cups, mapping, today):
    """dom : DataFrame (Date, HomeTeam, AwayTeam, FTHG, FTAG) des 19 championnats ; cups : résultats ESPN des coupes."""
    d1 = dom.assign(H=dom.HomeTeam, A=dom.AwayTeam, hg=dom.FTHG, ag=dom.FTAG, hf=1.0)[["Date", "H", "A", "hg", "ag", "hf"]]
    c = cups[cups.done].copy()
    c["Date"] = pd.to_datetime(c.dt).dt.tz_convert(None)
    c["H"], c["A"] = c.home.map(mapping), c.away.map(mapping)
    c["hg"], c["ag"] = pd.to_numeric(c.hg), pd.to_numeric(c.ag)
    c["hf"] = np.where(c.neutral, 0.0, 1.0)
    allm = pd.concat([d1, c[["Date", "H", "A", "hg", "ag", "hf"]]], ignore_index=True).dropna()
    allm = allm[(allm.Date < today) & (allm.Date >= today - pd.Timedelta(days=730))]
    return allm, c


def update(hist_path, out_dir, today, dom, fd_names):
    H = pd.read_csv(hist_path, dtype={"id": str}) if hist_path and __import__("os").path.exists(hist_path) else pd.DataFrame()
    recent = fetch_range((today - timedelta(days=10)).date(), (today + timedelta(days=21)).date())
    allc = pd.concat([H, recent], ignore_index=True) if len(H) else recent
    allc["id"] = allc["id"].astype(str)
    allc = allc.drop_duplicates("id", keep="last").sort_values("dt").reset_index(drop=True)
    allc[allc.done == True].to_csv(f"{out_dir}/cups_history.csv", index=False)          # noqa: E712
    names = sorted(set(allc.home) | set(allc.away))
    mapping = map_names(names, set(fd_names))
    allm, cres = build_matches(dom, allc, mapping, today)
    m = fit(allm.H.values, allm.A.values, allm.hg.values, allm.ag.values, (today - allm.Date).dt.days.values, allm.hf.values)
    # ---- format attendu par l'onglet Foot : log λ = att(h) + dfn(a) + home  (dfn = base − défense)
    leagues, results = {}, []
    season_start = pd.Timestamp(year=today.year if today.month >= 7 else today.year - 1, month=7, day=1)
    for code, (_, name) in CUPS.items():
        cur = cres[(cres.cup == code) & (cres.Date >= season_start)]
        up = allc[(allc.cup == code) & (allc.done != True) & (pd.to_datetime(allc.dt).dt.tz_convert(None) >= today - pd.Timedelta(hours=3))]
        teams = sorted(set(cur.home) | set(cur.away) | set(up.home) | set(up.away))
        tab = {t: dict(p=0, w=0, d=0, l=0, gf=0, ga=0) for t in teams}; form = {t: "" for t in teams}
        for r in cur.sort_values("Date").itertuples():
            for t, f_, c_ in ((r.home, int(r.hg), int(r.ag)), (r.away, int(r.ag), int(r.hg))):
                s = tab[t]; s["p"] += 1; s["gf"] += f_; s["ga"] += c_; s["w"] += f_ > c_; s["d"] += f_ == c_; s["l"] += f_ < c_
                form[t] = (form[t] + ("V" if f_ > c_ else "N" if f_ == c_ else "D"))[-5:]
            results.append(dict(Div=code, Date=r.Date.normalize(), HomeTeam=r.home, AwayTeam=r.away, FTHG=int(r.hg), FTAG=int(r.ag)))
        T = []
        for t in teams:
            k = mapping.get(t, t)
            T.append(dict(name=t, att=round(float(m["att"].get(k, -0.3)), 4), dfn=round(float(m["base"] - m["dfn"].get(k, -0.3)), 4),
                          pts=3 * tab[t]["w"] + tab[t]["d"], **tab[t], form=form[t]))
        T.sort(key=lambda x: (-x["pts"], -(x["gf"] - x["ga"]), -x["gf"]))
        games = [dict(dt=pd.Timestamp(r.dt).tz_convert(None).strftime("%Y-%m-%dT%H:%M"), home=r.home, away=r.away, neutral=bool(r.neutral))
                 for r in up.sort_values("dt").itertuples()]
        leagues[code] = dict(name=name, country="Europe", cup=True, home=round(m["home"], 4), rho=0.0, teams=T, games=games,
                             last=str(cur.Date.max().date()) if len(cur) else "")
        print(f"  coupe {code:4s} {len(T)} équipes, {len(games)} matchs à venir")
    unmatched = [n for n in names if mapping[n] == n]
    return leagues, pd.DataFrame(results), dict(model=m, mapping=mapping, unmatched=unmatched, n_matches=len(allm))
