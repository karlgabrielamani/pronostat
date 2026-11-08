"""Mise à jour de l'outil Pronos (foot, NBA, tennis).

Usage : python src/update_all.py <dossier_de_travail>
Le dossier doit contenir src/ et data/ (tennis_tool.json, tennis_history.csv). Résultats dans <dossier>/out/ :
pronos.html (la page), puis tennis_history.csv, tennis_tool.json, wta_history.csv, wta_tool.json et predictions_log.csv (à republier dans data/).
Arrête avec une erreur claire si une source ne répond pas ou change de format.
"""
import glob, json, os, sys, urllib.request
from datetime import date
import numpy as np
import pandas as pd

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
SRC, RAW, OUT = f"{ROOT}/src", f"{ROOT}/raw", f"{ROOT}/out"
sys.path.insert(0, SRC)
from model import DixonColes  # noqa: E402

os.makedirs(RAW, exist_ok=True); os.makedirs(OUT, exist_ok=True)
TODAY = pd.Timestamp(date.today())
RESULTS = {}                      # résultats réels, pour régler l'historique des pronostics


def fetch(url, dest, min_bytes=500):
    if os.path.exists(dest) and os.path.getsize(dest) > min_bytes:
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": "pronos-weekly-update"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if len(data) < min_bytes:
        raise RuntimeError(f"Fichier trop petit ({len(data)} octets) : {url}")
    open(dest, "wb").write(data)
    return dest


# ------------------------------------------------------------------ FOOT
LEAGUES = {"N1": ("Eredivisie", "Pays-Bas"), "B1": ("Jupiler Pro League", "Belgique"), "E0": ("Premier League", "Angleterre"),
           "SP1": ("La Liga", "Espagne"), "I1": ("Serie A", "Italie"), "D1": ("Bundesliga", "Allemagne"), "F1": ("Ligue 1", "France"),
           "P1": ("Liga Portugal", "Portugal"), "E1": ("Championship", "Angleterre"), "D2": ("2. Bundesliga", "Allemagne"),
           "SP2": ("Segunda", "Espagne"), "I2": ("Serie B", "Italie"), "F2": ("Ligue 2", "France"), "E2": ("League One", "Angleterre"),
           "E3": ("League Two", "Angleterre"), "SC0": ("Scottish Prem", "Écosse"), "SC1": ("Scottish Championship", "Écosse"),
           "T1": ("Süper Lig", "Turquie"), "G1": ("Super League Grèce", "Grèce")}
FOOT_ACC, FOOT_N = 0.4943, 34259          # mesuré au backtest walk-forward (2021-2026)


def season_codes():
    y = TODAY.year if TODAY.month >= 7 else TODAY.year - 1
    return [f"{(y - k) % 100:02d}{(y - k + 1) % 100:02d}" for k in (2, 1, 0)]


def read_fd(f):
    d = pd.read_csv(f, encoding="utf-8-sig", encoding_errors="ignore", on_bad_lines="skip").dropna(axis=1, how="all")
    d["Date"] = pd.to_datetime(d["Date"], dayfirst=True, errors="coerce")
    return d


def foot():
    codes = season_codes()
    fx = read_fd(fetch("https://www.football-data.co.uk/fixtures.csv", f"{RAW}/fixtures_{TODAY.date()}.csv"))
    fx = fx[fx.Date >= TODAY]
    RESULTS["fixtures"] = fx
    leagues = {}
    for div, (name, country) in LEAGUES.items():
        frames = []
        for c in codes:
            dest = f"{RAW}/{div}_{c}.csv" if c != codes[-1] else f"{RAW}/{div}_{c}_{TODAY.date()}.csv"
            try:
                frames.append(read_fd(fetch(f"https://www.football-data.co.uk/mmz4281/{c}/{div}.csv", dest)))
            except Exception as e:
                if c == codes[-1]:
                    raise
                print("  saison ignorée", div, c, e)
        cur = frames[-1].dropna(subset=["FTHG", "FTAG", "HomeTeam"])
        RESULTS.setdefault("dom", []).extend(fr_[["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"]] for fr_ in frames if "FTHG" in fr_)
        RESULTS.setdefault("foot", []).append(cur.assign(Div=div)[["Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"]])
        hist = pd.concat(frames, ignore_index=True).dropna(subset=["FTHG", "FTAG", "HomeTeam", "Date"])
        hist = hist[hist.Date >= TODAY - pd.Timedelta(days=730)].drop_duplicates(["Date", "HomeTeam", "AwayTeam"])
        m = DixonColes().fit(hist.HomeTeam.values, hist.AwayTeam.values, hist.FTHG.astype(int).values,
                             hist.FTAG.astype(int).values, (TODAY - hist.Date).dt.days.values)
        teams = sorted(set(cur.HomeTeam) | set(cur.AwayTeam))
        tab = {t: dict(p=0, w=0, d=0, l=0, gf=0, ga=0) for t in teams}
        form = {t: "" for t in teams}
        for r in cur.sort_values("Date").itertuples():
            for t, f_, c in ((r.HomeTeam, int(r.FTHG), int(r.FTAG)), (r.AwayTeam, int(r.FTAG), int(r.FTHG))):
                s = tab[t]; s["p"] += 1; s["gf"] += f_; s["ga"] += c
                s["w"] += f_ > c; s["d"] += f_ == c; s["l"] += f_ < c
                form[t] = (form[t] + ("V" if f_ > c else "N" if f_ == c else "D"))[-5:]
        T = [dict(name=t, att=round(float(m.params["att"].get(t, 0)), 4), dfn=round(float(m.params["dfn"].get(t, 0)), 4),
                  pts=3 * tab[t]["w"] + tab[t]["d"], **tab[t], form=form[t]) for t in teams]
        T.sort(key=lambda x: (-x["pts"], -(x["gf"] - x["ga"]), -x["gf"]))
        games = [dict(dt=f"{r.Date.date()}T{r.Time if isinstance(r.Time, str) else '15:00'}", home=r.HomeTeam, away=r.AwayTeam)
                 for r in fx[fx.Div == div].sort_values(["Date", "Time"]).itertuples() if r.HomeTeam in tab and r.AwayTeam in tab]
        leagues[div] = dict(name=name, country=country, home=round(float(m.params["home_adv"]), 4), rho=round(float(m.params["rho"]), 4),
                            teams=T, games=games, last=str(cur.Date.max().date()))
        print(f"  foot {div:4s} {len(T)} équipes, {len(games)} matchs à venir, dernier résultat {leagues[div]['last']}")
    order = list(LEAGUES)
    try:                                         # coupes d'Europe : ne bloquent pas les championnats
        import cups
        dom = pd.concat(RESULTS["dom"], ignore_index=True).dropna()
        names = set(t["name"] for L in leagues.values() for t in L["teams"]) | set(dom.HomeTeam) | set(dom.AwayTeam)
        cl, cres, info = cups.update(f"{ROOT}/data/cups_history.csv", OUT, TODAY, dom, names)
        leagues.update(cl); order = order[:2] + list(cl) + order[2:]
        if len(cres): RESULTS["foot"].append(cres)
    except Exception as e:
        import traceback; print("  ATTENTION coupes d'Europe non mises à jour :", repr(e)); traceback.print_exc(limit=2)
    return dict(leagues=leagues, order=order, acc=FOOT_ACC, n_test=FOOT_N, updated=str(TODAY.date()))


# ------------------------------------------------------------------ NBA
NBA_P = dict(lr=0.06, carry=0.5, hca=2.0, b2b=3.0, beta=0.15)   # beta : points perdus par point de « Game Score » absent
NBA_TEST = dict(n=1320, acc=0.697, mae_margin=11.18, mae_total=15.434)   # test 2025-26 avec absents, jamais vu au réglage
INJ_W = {"Out": 1.0, "Doubtful": 0.75, "Questionable": 0.5, "Day-To-Day": 0.5, "Probable": 0.1}


def nba_absences(g, cur_season):
    """Valeur des joueurs (Game Score moyen) et absents de chaque match, à partir des feuilles de match."""
    P = []
    for y in range(cur_season - 2, cur_season + 1):
        dest = f"{RAW}/player_box_{y}.csv" if y < cur_season else f"{RAW}/player_box_{y}_{TODAY.date()}.csv"
        P.append(pd.read_csv(fetch(f"{REL}/espn_nba_player_boxscores/player_box_{y}.csv", dest), low_memory=False))
    P = pd.concat(P, ignore_index=True)
    P = P[P.season_type.isin([2, 3])]
    P["min"] = pd.to_numeric(P.minutes, errors="coerce").fillna(0)
    P = P[(P["min"] > 0) & (P.did_not_play != True)]                 # noqa: E712
    f = lambda c: pd.to_numeric(P[c], errors="coerce").fillna(0)
    P["gmsc"] = (f("points") + .4 * f("field_goals_made") - .7 * f("field_goals_attempted") - .4 * (f("free_throws_attempted") - f("free_throws_made"))
                 + .7 * f("offensive_rebounds") + .3 * f("defensive_rebounds") + f("steals") + .7 * f("assists") + .7 * f("blocks")
                 - .4 * f("fouls") - f("turnovers"))
    played, names = {}, {}
    for r in P[["game_id", "team_display_name", "athlete_id", "athlete_display_name", "min", "gmsc"]].itertuples(index=False):
        played.setdefault((r.game_id, r.team_display_name), {})[r.athlete_id] = (r.min, r.gmsc)
        names[r.athlete_id] = r.athlete_display_name
    team_games, hist, miss = {}, {}, {}
    def regulars(team):
        last5 = team_games.get(team, [])[-5:]; out = {}
        for pid, h in hist.get(team, {}).items():
            if len(h) < 3: continue
            if sum(1 for gid in last5 if pid in played.get((gid, team), {})) >= 2 and np.mean([x[0] for x in h[-10:]]) >= 18:
                out[pid] = float(np.mean([x[1] for x in h[-10:]]))
        return out
    for r in g[g.season >= cur_season - 2].itertuples():
        row = []
        for team in (r.home, r.away):
            now = played.get((r.game_id, team), {})
            regs = regulars(team)
            row.append(sum(v for pid, v in regs.items() if pid not in now) if now else 0.0)
            team_games.setdefault(team, []).append(r.game_id)
            for pid, s in now.items(): hist.setdefault(team, {}).setdefault(pid, []).append(s)
        miss[r.game_id] = row
    return miss, {team: regulars(team) for team in team_games}, names


def nba_injuries(regs, names):
    """Blessés annoncés par ESPN, gardés seulement s'ils font partie des joueurs importants de leur équipe."""
    req = urllib.request.Request("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries", headers={"User-Agent": "pronos-weekly-update"})
    with urllib.request.urlopen(req, timeout=60) as r: data = json.loads(r.read())
    out = {}
    for tm in data.get("injuries", []):
        team = tm.get("displayName"); rg = regs.get(team, {})
        for it in tm.get("injuries", []):
            ath = it.get("athlete", {}); href = " ".join(l.get("href", "") for l in ath.get("links", []))
            m = __import__("re").search(r"/id/(\d+)", href)
            pid = float(m.group(1)) if m else None
            w = INJ_W.get(it.get("status"), 0.5)
            if pid in rg and w > 0:
                out.setdefault(team, []).append(dict(name=ath.get("displayName") or names.get(pid, "?"), status=it.get("status"),
                                                     v=round(rg[pid], 1), w=w))
    return out
REL = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"


def nba():
    cur_season = TODAY.year + 1 if TODAY.month >= 9 else TODAY.year
    fr = []
    for y in range(2015, cur_season + 1):
        dest = f"{RAW}/team_box_{y}.csv" if y < cur_season else f"{RAW}/team_box_{y}_{TODAY.date()}.csv"
        try:
            fr.append(pd.read_csv(fetch(f"{REL}/espn_nba_team_boxscores/team_box_{y}.csv", dest), low_memory=False))
        except Exception as e:
            if y >= cur_season - 1:
                raise
            print("  saison NBA ignorée", y, e)
    t = pd.concat(fr, ignore_index=True)
    t = t[t.season_type.isin([2, 3])]
    h = t[t.team_home_away == "home"]
    g = h[["game_id", "season", "game_date", "team_display_name", "opponent_team_display_name", "team_score", "opponent_team_score"]]
    g.columns = ["game_id", "season", "game_date", "home", "away", "hs", "as_"]
    g = g.dropna(subset=["hs", "as_"]); g = g[(g.hs > 0) & (g.as_ > 0)].copy()
    g["date"] = pd.to_datetime(g.game_date)
    g = g.drop_duplicates("game_id").sort_values(["date", "game_id"])
    RESULTS["nba"] = g[g.date >= TODAY - pd.Timedelta(days=30)][["date", "home", "away", "hs", "as_"]]
    try:
        MISS, REGS, PNAMES = nba_absences(g, cur_season)
    except Exception as e:
        print("  ATTENTION absents NBA indisponibles :", repr(e)); MISS, REGS, PNAMES = {}, {}, {}
    O, D, last, mu, season, res = {}, {}, {}, 113.0, None, []
    for r in g.itertuples(index=False):
        if r.season != season:
            season = r.season
            for k in O: O[k] *= NBA_P["carry"]; D[k] *= NBA_P["carry"]
        hn, an = r.home, r.away
        oh, dh, oa, da = O.get(hn, 0.), D.get(hn, 0.), O.get(an, 0.), D.get(an, 0.)
        rh = (r.date - last[hn]).days if hn in last else 5
        ra = (r.date - last[an]).days if an in last else 5
        mh, ma = MISS.get(r.game_id, (0.0, 0.0))
        eh = mu + oh - da + NBA_P["hca"] / 2 - NBA_P["b2b"] * (rh <= 1) - NBA_P["beta"] * mh
        ea = mu + oa - dh - NBA_P["hca"] / 2 - NBA_P["b2b"] * (ra <= 1) - NBA_P["beta"] * ma
        res.append((r.season, r.hs, r.as_, eh, ea))
        e1, e2 = r.hs - eh, r.as_ - ea
        O[hn] = oh + NBA_P["lr"] * e1; D[an] = da - NBA_P["lr"] * e1
        O[an] = oa + NBA_P["lr"] * e2; D[hn] = dh - NBA_P["lr"] * e2
        mu += 0.01 * (e1 + e2) / 2
        last[hn] = last[an] = r.date
    R = pd.DataFrame(res, columns=["season", "hs", "as_", "eh", "ea"])
    v = R[R.season >= cur_season - 2]
    Vm = ((v.hs - v.as_) - (v.eh - v.ea)).var(); Vt = ((v.hs + v.as_) - (v.eh + v.ea)).var()
    var, cov = (Vm + Vt) / 4, (Vt - Vm) / 4
    cur = t[(t.season == cur_season) & (t.season_type == 2)]
    rec = cur.groupby("team_display_name").team_winner.agg(["sum", "count"])
    info = t.sort_values("season").drop_duplicates("team_display_name", keep="last").set_index("team_display_name")
    names = set(cur.team_display_name) if len(cur) else set(t[t.season == cur_season - 1].team_display_name)
    teams = []
    for n in names:
        w, c = (int(rec.loc[n, "sum"]), int(rec.loc[n, "count"])) if n in rec.index else (0, 0)
        teams.append(dict(name=n, abbr=str(info.loc[n, "team_abbreviation"]), o=round(O.get(n, 0), 2), d=round(D.get(n, 0), 2),
                          w=w, l=c - w, last=str(last[n].date()) if n in last else ""))
    teams.sort(key=lambda x: -(x["o"] + x["d"]))
    try:
        INJ = nba_injuries(REGS, PNAMES)
    except Exception as e:
        print("  ATTENTION blessures NBA indisponibles :", repr(e)); INJ = {}
    for tm in teams:
        tm["inj"] = INJ.get(tm["name"], [])
    print(f"  NBA absents : {sum(len(v) for v in INJ.values())} joueurs importants signalés")
    sched = pd.read_csv(fetch(f"{REL}/espn_nba_schedules/nba_schedule_{cur_season}.csv", f"{RAW}/nba_schedule_{cur_season}_{TODAY.date()}.csv"), low_memory=False)
    sched["dt"] = pd.to_datetime(sched["date"], utc=True)
    up = sched[(sched.status_type_completed == False) & (sched.dt >= TODAY.tz_localize("UTC")) &  # noqa: E712
               (sched.dt < TODAY.tz_localize("UTC") + pd.Timedelta(days=8))].sort_values("dt")
    games = [dict(dt=r.dt.isoformat(), home=r.home_display_name, away=r.away_display_name) for r in up.itertuples()
             if r.home_display_name in names and r.away_display_name in names]
    print(f"  NBA {len(teams)} équipes, {len(games)} matchs à venir, dernier résultat {g.date.max().date()}")
    return dict(teams=teams, mu=round(mu, 2), hca=NBA_P["hca"], b2b=NBA_P["b2b"], beta=NBA_P["beta"], sd_team=round(var ** .5, 2), corr=round(cov / var, 3),
                test=NBA_TEST, updated=str(g.date.max().date()), games=games)


# ------------------------------------------------------------------ PAGE
FONT_LINK = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;600;700&display=swap">'


def build(foot_data, nba_data, tennis_data, hist=None, wta_data=None, paper_data=None):
    t = open(f"{SRC}/tennis_tool_template.html").read()
    css = open(f"{SRC}/app.css").read()
    t = t.replace("@media (max-width: 520px) {", css + "@media (max-width: 520px) {", 1)
    t = t.replace("<title>Pronos Tennis ATP</title>", "<title>Pronostat</title>")
    t = t.replace('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Public+Sans:wght@400;500;600&display=swap">', FONT_LINK, 1)   # police Quicksand
    j = t.index("</style>"); t = t[:j] + open(f"{SRC}/theme.css").read() + t[j:]
    nav = ('<header class="appbar"><a class="logo" href="#jour"><i><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" aria-hidden="true"><path d="M6 19 V13 M12 19 V5 M18 19 V10"/></svg></i>Pronostat</a></header>'
           '<nav class="tabs" aria-label="Sport"><a href="#jour" id="tab-jour"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 11 L12 4 L21 11 V20 H3 Z"/></svg>Aujourd&#39;hui</a><a href="#foot" id="tab-foot"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7 L16 10 L14.5 15 H9.5 L8 10 Z"/></svg>Football</a>'
           '<a href="#tennis" id="tab-tennis"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M5 6 C10 9 10 15 5 18 M19 6 C14 9 14 15 19 18"/></svg>Tennis</a><a href="#basket" id="tab-basket"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12 H21 M12 3 V21 M5.5 5.5 C9 9 9 15 5.5 18.5 M18.5 5.5 C15 9 15 15 18.5 18.5"/></svg>NBA</a><a href="#fav" id="tab-fav"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M12 3.5 L14.6 8.9 L20.5 9.6 L16.1 13.6 L17.3 19.5 L12 16.6 L6.7 19.5 L7.9 13.6 L3.5 9.6 L9.4 8.9 Z"/></svg>Favoris</a></nav>\n')
    t = t.replace('<script', open(f"{SRC}/i18n.html").read() + '<script', 1)
    t = t.replace('<div class="wrap">', nav + open(f"{SRC}/fav.html").read() + '<div class="wrap" id="view-tennis" hidden>', 1)
    i = t.index("<script>")
    t = t[:i] + open(f"{SRC}/foot_fragment.html").read() + "\n" + open(f"{SRC}/nba_fragment.html").read() + "\n" + t[i:]
    js = lambda name, ph, data: "\n<script>\n" + open(f"{SRC}/{name}").read().replace(ph, json.dumps(data, ensure_ascii=False)) + "\n</script>"
    t = (t + js("nba_fragment.js", "__NBA__", nba_data) + js("foot_fragment.js", "__FOOT__", foot_data)
           + "\n<script>window.HIST = " + json.dumps(hist, ensure_ascii=False) + ";</script>"
           + open(f"{SRC}/router.html").read() + open(f"{SRC}/sim.html").read())          # Stratégies : suivies en arrière-plan (data/paper_bets.csv), plus affichées
    t = t.replace("__WTA__", json.dumps(wta_data or dict(players=[], coef=tennis_data["coef"], updated=tennis_data["updated"], test=dict(acc=0, acc_pin=None), live=[]), ensure_ascii=False))
    t = t.replace("__DATA__", json.dumps(tennis_data, ensure_ascii=False))
    open(f"{OUT}/pronos.html", "w").write(t)
    return f"{OUT}/pronos.html"


if __name__ == "__main__":
    print("Mise à jour du", TODAY.date())
    f = foot()
    n = nba()
    try:
        import tennis as tn
        tennis = tn.update(f"{ROOT}/data/tennis_history.csv", f"{ROOT}/data/tennis_tool.json", OUT, TODAY)
    except Exception as e:                       # le tennis ne bloque pas le foot et la NBA
        print("  ATTENTION tennis non mis à jour :", repr(e))
        tennis = json.load(open(f"{ROOT}/data/tennis_tool.json"))
    wta = None
    try:
        import tennis as tn
        wta = tn.update(f"{ROOT}/data/wta_history.csv", f"{ROOT}/data/wta_tool.json", OUT, TODAY, tour="wta")
    except Exception as e:
        print("  ATTENTION tennis WTA non mis à jour :", repr(e))
        if os.path.exists(f"{ROOT}/data/wta_tool.json"): wta = json.load(open(f"{ROOT}/data/wta_tool.json"))
    for k, v in (("foot", f), ("nba", n), ("tennis", tennis), ("wta", wta)):
        if v is None: continue
        json.dump(v, open(f"{OUT}/{k}_tool.json", "w"), ensure_ascii=False)
    hist = None
    try:
        import history
        ths = []
        for name in ("tennis_history.csv", "wta_history.csv"):
            pth = f"{OUT}/{name}" if os.path.exists(f"{OUT}/{name}") else f"{ROOT}/data/{name}"
            if os.path.exists(pth): ths.append(pd.read_csv(pth))
        hist = history.update(f"{ROOT}/data/predictions_log.csv", OUT, pd.Timestamp.now(tz="UTC"), f, n, [("ATP", tennis), ("WTA", wta)],
                              pd.concat(RESULTS["foot"], ignore_index=True), RESULTS["nba"], pd.concat(ths, ignore_index=True))
    except Exception as e:                       # l'historique ne bloque pas la mise à jour
        import traceback; print("  ATTENTION historique non mis à jour :", repr(e)); traceback.print_exc(limit=3)
    paper_data = None
    try:
        import paper
        paper_data = paper.update(f"{ROOT}/data/paper_bets.csv", OUT, pd.Timestamp.now(tz="UTC"), f, RESULTS["fixtures"], n,
                                  pd.concat(RESULTS["foot"], ignore_index=True), RESULTS["nba"])
    except Exception as e:                       # les portefeuilles virtuels ne bloquent pas la mise à jour
        import traceback; print("  ATTENTION stratégies non mises à jour :", repr(e)); traceback.print_exc(limit=3)
    print("Page :", build(f, n, tennis, hist, wta, paper_data))
