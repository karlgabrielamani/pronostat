"""WNBA : même modèle que la NBA (notes d'attaque et de défense mises à jour match après match), sans les absents.

Données : sportsdataverse (feuilles de match ESPN), comme la NBA.
Réglage sur 2023-2025, test sur la saison 2026 jamais vue au réglage : bon vainqueur 66,9 % (354 matchs), écart moyen 10,2 points.
La saison WNBA va de mai à octobre ; hors saison il n'y a pas de match à venir, la page montre alors le classement.
"""
import pandas as pd

P = dict(lr=0.08, carry=0.3, hca=1.0, b2b=1.5)
TEST = dict(n=354, acc=0.669, mae_margin=10.16)
REL = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"


def update(fetch, RAW, TODAY):
    last_season = TODAY.year if TODAY.month >= 5 else TODAY.year - 1      # dernière saison commencée
    fr = []
    for y in range(2019, last_season + 1):
        dest = f"{RAW}/wnba_team_box_{y}.csv" if y < last_season else f"{RAW}/wnba_team_box_{y}_{TODAY.date()}.csv"
        fr.append(pd.read_csv(fetch(f"{REL}/espn_wnba_team_boxscores/team_box_{y}.csv", dest), low_memory=False))
    t = pd.concat(fr, ignore_index=True)
    t = t[t.season_type.isin([2, 3])]
    h = t[t.team_home_away == "home"][["game_id", "season", "game_date", "team_display_name", "opponent_team_display_name", "team_score", "opponent_team_score"]]
    h.columns = ["game_id", "season", "game_date", "home", "away", "hs", "as_"]
    g = h.dropna(); g = g[(g.hs > 0) & (g.as_ > 0)].copy()
    g["date"] = pd.to_datetime(g.game_date); g = g.drop_duplicates("game_id").sort_values(["date", "game_id"])
    cnt = pd.concat([g[["season", "home"]].rename(columns={"home": "t"}), g[["season", "away"]].rename(columns={"away": "t"})]).value_counts()
    ok = lambda se, tm: cnt.get((se, tm), 0) >= 5                       # écarte le All-Star Game (« Team … »)
    g = g[[ok(a, b) and ok(a, c) for a, b, c in zip(g.season, g.home, g.away)]]
    t = t[[ok(a, b) for a, b in zip(t.season, t.team_display_name)]]
    O, D, last, mu, season, res = {}, {}, {}, 80.0, None, []
    for r in g.itertuples(index=False):
        if r.season != season:
            season = r.season
            for k in O: O[k] *= P["carry"]; D[k] *= P["carry"]
        hn, an = r.home, r.away
        oh, dh, oa, da = O.get(hn, 0.), D.get(hn, 0.), O.get(an, 0.), D.get(an, 0.)
        rh = (r.date - last[hn]).days if hn in last else 5
        ra = (r.date - last[an]).days if an in last else 5
        eh = mu + oh - da + P["hca"] / 2 - P["b2b"] * (rh <= 1)
        ea = mu + oa - dh - P["hca"] / 2 - P["b2b"] * (ra <= 1)
        res.append((r.season, r.hs, r.as_, eh, ea))
        e1, e2 = r.hs - eh, r.as_ - ea
        O[hn] = oh + P["lr"] * e1; D[an] = da - P["lr"] * e1
        O[an] = oa + P["lr"] * e2; D[hn] = dh - P["lr"] * e2
        mu += 0.01 * (e1 + e2) / 2
        last[hn] = last[an] = r.date
    R = pd.DataFrame(res, columns=["season", "hs", "as_", "eh", "ea"])
    v = R[R.season >= last_season - 2]
    Vm = ((v.hs - v.as_) - (v.eh - v.ea)).var(); Vt = ((v.hs + v.as_) - (v.eh + v.ea)).var()
    var, cov = (Vm + Vt) / 4, (Vt - Vm) / 4
    cur = t[(t.season == last_season) & (t.season_type == 2)]
    rec = cur.groupby("team_display_name").team_winner.agg(["sum", "count"])
    teams = []
    for n in sorted(set(cur.team_display_name)):
        w, c = (int(rec.loc[n, "sum"]), int(rec.loc[n, "count"])) if n in rec.index else (0, 0)
        teams.append(dict(name=n, o=round(O.get(n, 0), 2), d=round(D.get(n, 0), 2), w=w, l=c - w))
    teams.sort(key=lambda x: -(x["o"] + x["d"]))
    games = []
    try:                                       # calendrier de la saison qui vient, s'il est publié
        nxt = last_season + 1 if TODAY.month >= 10 or TODAY.month < 5 else last_season
        sched = pd.read_csv(fetch(f"{REL}/espn_wnba_schedules/wnba_schedule_{nxt}.csv", f"{RAW}/wnba_schedule_{nxt}_{TODAY.date()}.csv"), low_memory=False)
        sched["dt"] = pd.to_datetime(sched["date"], utc=True)
        up = sched[(sched.status_type_completed == False) & (sched.dt >= TODAY.tz_localize("UTC")) &  # noqa: E712
                   (sched.dt < TODAY.tz_localize("UTC") + pd.Timedelta(days=8))].sort_values("dt")
        names = {x["name"] for x in teams}
        games = [dict(dt=r.dt.isoformat(), home=r.home_display_name, away=r.away_display_name) for r in up.itertuples()
                 if r.home_display_name in names and r.away_display_name in names]
    except Exception as e:
        print("  WNBA : pas encore de calendrier pour la prochaine saison", repr(e)[:60])
    print(f"  WNBA {len(teams)} équipes, {len(games)} matchs à venir, dernier résultat {g.date.max().date()}")
    return dict(teams=teams, mu=round(mu, 2), hca=P["hca"], sd_team=round(var ** .5, 2), corr=round(cov / var, 3), test=TEST,
                season=int(last_season), updated=str(g.date.max().date()), games=games)
