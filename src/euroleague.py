"""EuroLeague : notes d'attaque et de défense mises à jour match après match (même principe que la NBA, sans les absents).

Données : site officiel de l'EuroLeague (api-live.euroleague.net), calendrier et résultats depuis 2018-19.
Réglage sur 2022-23 à 2024-25, test sur 2025-26 jamais vue au réglage : bon vainqueur 64,2 % (402 matchs), écart moyen 9,1 points.
La saison « E2026 » est la saison 2026-27.
"""
import json
import pandas as pd

P = dict(lr=0.04, carry=0.7, hca=4.0)
TEST = dict(n=402, acc=0.642, mae_margin=9.12)
API = "https://api-live.euroleague.net/v2/competitions/E/seasons/E{y}/games"


def update(fetch, RAW, TODAY):
    cur = TODAY.year if TODAY.month >= 8 else TODAY.year - 1            # saison en cours (année de départ)
    rows, upcoming, crest = [], [], {}
    for y in range(2018, cur + 1):
        dest = f"{RAW}/euroleague_{y}.json" if y < cur else f"{RAW}/euroleague_{y}_{TODAY.date()}.json"
        for x in json.load(open(fetch(API.format(y=y), dest)))["data"]:
            hc, ac = x["local"]["club"], x["road"]["club"]
            for c in (hc, ac):
                if (c.get("images") or {}).get("crest"): crest[c["name"]] = c["images"]["crest"]
            dt = pd.to_datetime(x["utcDate"], utc=True)
            if x["played"] and x["local"]["score"] and x["road"]["score"]:
                rows.append(dict(season=y, date=dt, home=hc["name"], away=ac["name"], hs=x["local"]["score"], as_=x["road"]["score"],
                                 neutral=bool(x.get("isNeutralVenue"))))
            elif y == cur and not x["played"]:
                upcoming.append(dict(dt=dt, home=hc["name"], away=ac["name"], neutral=bool(x.get("isNeutralVenue"))))
    g = pd.DataFrame(rows).sort_values("date")
    O, D, mu, season, res = {}, {}, 80.0, None, []
    for r in g.itertuples(index=False):
        if r.season != season:
            season = r.season
            for k in O: O[k] *= P["carry"]; D[k] *= P["carry"]
        hn, an = r.home, r.away
        oh, dh, oa, da = O.get(hn, 0.), D.get(hn, 0.), O.get(an, 0.), D.get(an, 0.)
        hh = 0 if r.neutral else P["hca"]
        eh, ea = mu + oh - da + hh / 2, mu + oa - dh - hh / 2
        res.append((r.season, r.hs, r.as_, eh, ea))
        e1, e2 = r.hs - eh, r.as_ - ea
        O[hn] = oh + P["lr"] * e1; D[an] = da - P["lr"] * e1
        O[an] = oa + P["lr"] * e2; D[hn] = dh - P["lr"] * e2
        mu += 0.01 * (e1 + e2) / 2
    R = pd.DataFrame(res, columns=["season", "hs", "as_", "eh", "ea"])
    v = R[R.season >= cur - 2]
    Vm = ((v.hs - v.as_) - (v.eh - v.ea)).var(); Vt = ((v.hs + v.as_) - (v.eh + v.ea)).var()
    var, cov = (Vm + Vt) / 4, (Vt - Vm) / 4
    c = g[g.season == cur]
    names = set(c.home) | set(c.away) | {u["home"] for u in upcoming} | {u["away"] for u in upcoming}
    teams = []
    for n in sorted(names):
        w = int(((c.home == n) & (c.hs > c.as_)).sum() + ((c.away == n) & (c.as_ > c.hs)).sum())
        l = int(((c.home == n) | (c.away == n)).sum()) - w
        teams.append(dict(name=n, o=round(O.get(n, 0), 2), d=round(D.get(n, 0), 2), w=w, l=l, crest=crest.get(n, "")))
    teams.sort(key=lambda x: -(x["o"] + x["d"]))
    now = TODAY.tz_localize("UTC")
    games = [dict(dt=u["dt"].isoformat(), home=u["home"], away=u["away"], neutral=u["neutral"]) for u in sorted(upcoming, key=lambda u: u["dt"])
             if now <= u["dt"] < now + pd.Timedelta(days=8)]
    print(f"  EuroLeague {len(teams)} équipes, {len(games)} matchs à venir, dernier résultat {g.date.max().date()}")
    return dict(teams=teams, mu=round(mu, 2), hca=P["hca"], sd_team=round(var ** .5, 2), corr=round(cov / var, 3), test=TEST,
                season=int(cur), updated=str(g.date.max().date()), games=games)
