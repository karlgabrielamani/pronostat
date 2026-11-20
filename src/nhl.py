"""Hockey : NHL (api-web.nhle.com, gratuit, sans clé).

Historique des matchs gardé dans data/nhl_games.csv (score après 60 min, tirs cadrés, buts de 1re période,
buts dans la cage vide) ; chaque jour on ne télécharge que les journées manquantes.

Modèle des buts après 60 min, pensé pour les événements (totaux, équipe qui marque 3 buts, 1re période…) :
- niveau de buts de la ligue : moyenne des 30 derniers jours (domicile et extérieur à part) ;
- force de chaque équipe : moitié buts, moitié tirs cadrés (les tirs sont bien plus stables que les buts),
  moyennes pondérées dans le temps (demi-vie d'environ 4 mois) et ramenées vers la moyenne ;
- loi de Poisson, plus deux corrections propres au hockey : nuls après 60 min plus fréquents (facteur dk)
  et but dans la cage vide (une partie des matchs à un but d'écart finit avec deux buts d'écart, facteur en) ;
- 1re période : environ 29,5 % des buts (part mesurée sur l'historique).
Backtest (saison 2025-26 et début 2026-27, modèle jamais nourri des matchs testés) : voir TEST.
"""
import json, os, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd

API = "https://api-web.nhle.com/v1"
XI, N0, K, LVL_DAYS, DK, EN = 0.006, 8, 0.5, 30, 1.55, 0.3
# événements après 60 min : gain de précision (score de Brier) par rapport à la moyenne NHL des 30 derniers jours
TEST = dict(n=1744, acc=0.546, events_gain=0.013)   # vainqueur final juste 54,6 % (52,5 % avec l’ancien modèle sur les buts seuls)


def _get(url):
    for k in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pronos-weekly-update"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 * (k + 1))
    return None


def _rows(d, js):
    out = []
    for g in (js or {}).get("games", []):
        if g.get("gameType") not in (2, 3) or g.get("gameState") not in ("OFF", "FINAL"):
            continue
        h, a = g["homeTeam"], g["awayTeam"]
        last = (g.get("gameOutcome") or {}).get("lastPeriodType", "REG")
        hs, as_ = int(h["score"]), int(a["score"])
        rh, ra = (hs, as_) if last == "REG" else (min(hs, as_),) * 2
        G = g.get("goals", [])
        cnt = lambda ab, ok: sum(1 for x in G if x.get("teamAbbrev") == ab and ok(x))
        out.append(dict(id=g["id"], date=d, season=g["season"], type=g["gameType"], habbr=h["abbrev"], aabbr=a["abbrev"],
                        hs=hs, as_=as_, last=last, rh=rh, ra=ra, hsog=h.get("sog"), asog=a.get("sog"),
                        h1=cnt(h["abbrev"], lambda x: x.get("period") == 1), a1=cnt(a["abbrev"], lambda x: x.get("period") == 1),
                        hen=cnt(h["abbrev"], lambda x: x.get("period", 9) <= 3 and x.get("goalModifier") == "empty-net"),
                        aen=cnt(a["abbrev"], lambda x: x.get("period", 9) <= 3 and x.get("goalModifier") == "empty-net")))
    return out


def history(root, today):
    """Charge data/nhl_games.csv et ajoute les journées manquantes (les 3 derniers jours sont toujours revérifiés)."""
    path = f"{root}/data/nhl_games.csv"
    old = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()
    start = pd.Timestamp(old.date.max()) - pd.Timedelta(days=3) if len(old) else pd.Timestamp(f"{today.year - 2}-10-01")
    days = [d.date() for d in pd.date_range(start, today) if d.month not in (7, 8, 9)]
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda d: _get(f"{API}/score/{d}"), days))
    new = pd.DataFrame([r for d, js in zip(days, res) for r in _rows(str(d), js)])
    df = pd.concat([old, new]).drop_duplicates("id", keep="last") if len(new) else old
    df = df.dropna(subset=["hsog", "asog"]).sort_values(["date", "id"]).reset_index(drop=True)
    df.to_csv(path, index=False)
    print(f"  hockey NHL : {len(new)} matchs récupérés sur {len(days)} journées, {len(df)} matchs en historique")
    df["dt"] = pd.to_datetime(df.date)
    return df


def ratings(df, t):
    past = df[(df.dt < t) & (df.dt >= t - pd.Timedelta(days=730))]
    w = np.exp(-XI * (t - past.dt).dt.days.values)
    X = pd.concat([pd.DataFrame(dict(team=past.habbr, gf=past.rh, ga=past.ra, sf=past.hsog, sa=past.asog, w=w)),
                   pd.DataFrame(dict(team=past.aabbr, gf=past.ra, ga=past.rh, sf=past.asog, sa=past.hsog, w=w))])
    for c in ("gf", "ga", "sf", "sa"):
        X[c] = X[c] * X.w
    S = X.groupby("team")[["gf", "ga", "sf", "sa", "w"]].sum()
    lg, ls = S.gf.sum() / S.w.sum(), S.sf.sum() / S.w.sum()
    r = lambda c, m: (S[c] + N0 * m) / (S.w + N0) / m
    off = r("gf", lg) ** K * r("sf", ls) ** (1 - K)
    dfn = r("ga", lg) ** K * r("sa", ls) ** (1 - K)
    before = df[df.dt < t]
    rc = before[before.dt >= t - pd.Timedelta(days=LVL_DAYS)]
    if len(rc) < 150:
        rc = before.tail(400)
    f1 = float((before.h1 + before.a1).sum() / max((before.rh + before.ra).sum(), 1))
    o = before[before["last"] != "REG"]
    ot = float((o.hs > o.as_).mean()) if len(o) > 50 else 0.52
    return off, dfn, dict(lh=float(rc.rh.mean()), la=float(rc.ra.mean()), f1=f1, ot=ot)


def update(root, today, test=TEST):
    df = history(root, today)
    if df.empty:
        raise RuntimeError("NHL : aucun résultat")
    t = pd.Timestamp(today.date()) + pd.Timedelta(days=1)
    off, dfn, lv = ratings(df, t)
    st = (_get(f"{API}/standings/now") or {}).get("standings", [])
    if not st:
        raise RuntimeError("NHL : classement indisponible")
    name = {s["teamAbbrev"]["default"]: s["teamName"]["default"] for s in st}
    cs = df.season.max()
    form = {}
    for r in df[(df.season == cs) & (df.type == 2)].itertuples():
        for ab, f_, c in ((r.habbr, r.hs, r.as_), (r.aabbr, r.as_, r.hs)):
            form[ab] = (form.get(ab, "") + ("V" if f_ > c else "P" if r.last != "REG" else "D"))[-5:]
    T = []
    for s in st:
        ab = s["teamAbbrev"]["default"]
        logo = s.get("teamLogo", "")
        T.append(dict(name=name[ab], abbr=ab, logo=[logo, logo.replace("_light", "_dark")],
                      off=round(float(off.get(ab, 1)), 4), dfn=round(float(dfn.get(ab, 1)), 4),
                      p=s["gamesPlayed"], pts=s["points"], w=s["wins"], l=s["losses"], otl=s["otLosses"],
                      gf=s["goalFor"], ga=s["goalAgainst"], form=form.get(ab, "")))
    T.sort(key=lambda x: (-x["pts"], x["p"], -(x["gf"] - x["ga"])))
    # matchs à venir : semaine en cours et suivante
    now, games, seen = pd.Timestamp.now(tz="UTC"), [], set()
    for d in (today.date(), (today + pd.Timedelta(days=7)).date()):
        for w in (_get(f"{API}/schedule/{d}") or {}).get("gameWeek", []):
            for g in w.get("games", []):
                if g["id"] in seen or g.get("gameType") not in (2, 3) or g.get("gameState") not in ("FUT", "PRE"): continue
                seen.add(g["id"])
                h, a, dt = g["homeTeam"]["abbrev"], g["awayTeam"]["abbrev"], pd.Timestamp(g["startTimeUTC"])
                if h in name and a in name and now - pd.Timedelta(hours=4) <= dt <= now + pd.Timedelta(days=8):
                    games.append(dict(dt=dt.strftime("%Y-%m-%dT%H:%M"), home=name[h], away=name[a]))
    games.sort(key=lambda x: x["dt"])
    L = dict(name="NHL", country="Amérique du Nord", lh=round(lv["lh"], 4), la=round(lv["la"], 4), f1=round(lv["f1"], 4),
             ot=round(lv["ot"], 3), dk=DK, en=EN, rho=0, teams=T, games=games, last=str(df.date.max()))
    print(f"  hockey NHL {len(T)} équipes, {len(games)} matchs à venir, dernier résultat {L['last']}, "
          f"buts attendus {L['lh']:.2f}-{L['la']:.2f}, 1re période {L['f1']:.1%}")
    return dict(leagues={"NHL": L}, order=["NHL"], acc=test["acc"], n_test=test["n"], updated=str(today.date()))
