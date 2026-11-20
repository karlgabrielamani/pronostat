"""Hockey : NHL (api-web.nhle.com, gratuit, sans clé).

Modèle : Dixon-Coles sur les buts du temps réglementaire (60 min), comme le foot.
- un match terminé en prolongation ou aux tirs au but compte comme un nul après 60 min ;
- la prolongation se joue à pile ou face, un peu penchée vers l'équipe la plus forte (paramètre « ot »).
Sortie : même forme que l'outil foot (leagues / order), pour pouvoir ajouter d'autres championnats plus tard.
"""
import json, os, urllib.request
import numpy as np
import pandas as pd
from model import DixonColes

API = "https://api-web.nhle.com/v1"
XI = 0.0035                    # demi-vie d'environ 200 jours (réglé au backtest)
TEST = dict(n=1749, acc=0.525, logloss=1.072)   # walk-forward 2025-26 + début 2026-27 (vainqueur final juste 52,5 % ; la NHL est proche du pile ou face)


def _get(url, dest, fetch):
    return json.load(open(fetch(url, dest, min_bytes=200)))


def season_start(today):
    return today.year if today.month >= 8 else today.year - 1


def results(fetch, raw, today):
    """Matchs NHL (saison régulière et séries) des deux dernières saisons et de la saison en cours, semaine par semaine."""
    y0 = season_start(today) - 2
    day, rows, seen = pd.Timestamp(f"{y0}-10-01"), [], set()
    upcoming = []
    while day <= today + pd.Timedelta(days=7):
        cur = day >= today - pd.Timedelta(days=8)          # semaines récentes : rechargées chaque jour
        dest = f"{raw}/nhl_{day.date()}" + (f"_{today.date()}" if cur else "") + ".json"
        try:
            d = _get(f"{API}/schedule/{day.date()}", dest, fetch)
        except Exception as e:
            print("  NHL semaine ignorée", day.date(), repr(e)[:80]); day += pd.Timedelta(days=7); continue
        for w in d.get("gameWeek", []):
            for g in w.get("games", []):
                if g["id"] in seen or g.get("gameType") not in (2, 3): continue
                seen.add(g["id"])
                h, a = g["homeTeam"], g["awayTeam"]
                info = dict(id=g["id"], dt=pd.Timestamp(g["startTimeUTC"]), type=g["gameType"], season=g["season"],
                            home=_name(h), away=_name(a), habbr=h["abbrev"], aabbr=a["abbrev"],
                            hlogo=(h.get("logo", ""), h.get("darkLogo", "")), alogo=(a.get("logo", ""), a.get("darkLogo", "")))
                if g.get("gameState") in ("OFF", "FINAL") and "score" in h:
                    last = (g.get("gameOutcome") or {}).get("lastPeriodType", "REG")
                    hs, as_ = int(h["score"]), int(a["score"])
                    rh, ra = (hs, as_) if last == "REG" else (min(hs, as_), min(hs, as_))
                    rows.append(dict(info, hs=hs, as_=as_, rh=rh, ra=ra, last=last))
                elif g.get("gameState") in ("FUT", "PRE") and g.get("gameScheduleState", "OK") == "OK":
                    upcoming.append(info)
        nxt = d.get("nextStartDate")
        day = pd.Timestamp(nxt) if nxt and pd.Timestamp(nxt) > day else day + pd.Timedelta(days=7)
    return pd.DataFrame(rows).sort_values("dt").reset_index(drop=True), upcoming


def _name(t):
    pl, cn = t.get("placeName", {}).get("default", ""), t.get("commonName", {}).get("default", "")
    return f"{pl} {cn}".strip() if cn and not cn.startswith(pl) else (cn or pl or t.get("abbrev", "?"))


def fit(df, today, xi=None):
    xi = xi or XI
    h = df[df.dt >= today.tz_localize("UTC") - pd.Timedelta(days=730)]
    m = DixonColes(xi=xi).fit(h.home.values, h.away.values, h.rh.values, h.ra.values,
                              (today.tz_localize("UTC") - h.dt).dt.days.values)
    return m


def ot_param(df):
    """Prolongation : part gagnée par l'équipe à domicile, et poids de la différence de force (régression simple)."""
    o = df[df["last"] != "REG"]
    return round(float((o.hs > o.as_).mean()), 3) if len(o) > 50 else 0.52


def draw_k(m, df):
    """Les nuls après 60 min sont plus fréquents que ne le dit le modèle de Poisson (fin de match prudente, but dans la cage vide…) :
    facteur appliqué à la diagonale pour retrouver la part de nuls observée."""
    d = df[df.home.isin(m.params["att"]) & df.away.isin(m.params["att"])].tail(1500)
    pd_ = float(np.mean([np.trace(m.score_matrix(r.home, r.away)[0]) for r in d.itertuples()]))
    obs = float((d.rh == d.ra).mean())
    return round(obs * (1 - pd_) / (pd_ * (1 - obs)), 3)


def probs(m, home, away, ot, dk=1.0):
    mat, lam, mu = m.score_matrix(home, away)
    mat = mat.copy(); np.fill_diagonal(mat, np.diag(mat) * dk); mat /= mat.sum()
    pH, pD, pA = np.tril(mat, -1).sum(), np.trace(mat), np.triu(mat, 1).sum()
    q = ot + 0.5 * (lam / (lam + mu) - 0.5)
    return pH, pD, pA, pH + pD * q


def backtest(df, today):
    """Walk-forward sur la saison passée et la saison en cours : modèle réajusté tous les 14 jours, jamais sur les matchs testés."""
    start = pd.Timestamp(f"{season_start(today) - 1}-10-01", tz="UTC")
    t, ok, ll, n, dsum, dobs = start, 0, 0.0, 0, 0.0, 0
    ot = ot_param(df[df.dt < start])
    while t < df.dt.max():
        past, test = df[df.dt < t], df[(df.dt >= t) & (df.dt < t + pd.Timedelta(days=14))]
        if len(test) and len(past) > 500:
            m = fit(past, t.tz_localize(None)); dk = draw_k(m, past)
            for r in test.itertuples():
                if r.home not in m.params["att"] or r.away not in m.params["att"]: continue
                pH, pD, pA, pF = probs(m, r.home, r.away, ot, dk)
                ok += (pF >= .5) == (r.hs > r.as_); n += 1
                p = pH if r.rh > r.ra else pD if r.rh == r.ra else pA
                ll -= np.log(max(p, 1e-9)); dsum += pD; dobs += r.rh == r.ra
        t += pd.Timedelta(days=14)
    return dict(n=n, acc=round(ok / max(n, 1), 4), logloss=round(ll / max(n, 1), 4), draw_pred=round(dsum / max(n, 1), 3), draw_obs=round(dobs / max(n, 1), 3))


def update(fetch, raw, today, test=TEST):
    df, up = results(fetch, raw, today)
    if df.empty:
        raise RuntimeError("NHL : aucun résultat")
    m = fit(df, today)
    ot, dk = ot_param(df), draw_k(m, df)
    cs = df.season.max()
    cur = df[(df.season == cs) & (df.type == 2)]
    names = sorted(set(cur.home) | set(cur.away)) or sorted(set(df[df.season == cs].home))
    tab = {t: dict(p=0, w=0, l=0, otl=0, gf=0, ga=0) for t in names}
    form = {t: "" for t in names}
    for r in cur.itertuples():
        for t, f_, c in ((r.home, r.hs, r.as_), (r.away, r.as_, r.hs)):
            s = tab[t]; s["p"] += 1; s["gf"] += f_; s["ga"] += c
            win = f_ > c
            s["w"] += win; s["l"] += (not win) and r.last == "REG"; s["otl"] += (not win) and r.last != "REG"
            form[t] = (form[t] + ("V" if win else "P" if r.last != "REG" else "D"))[-5:]
    info = {}
    for r in df.itertuples():
        info[r.home] = (r.habbr, r.hlogo); info[r.away] = (r.aabbr, r.alogo)
    T = [dict(name=t, abbr=info.get(t, ("", ""))[0], logo=list(info.get(t, ("", ("", "")))[1]),
              att=round(float(m.params["att"].get(t, 0)), 4), dfn=round(float(m.params["dfn"].get(t, 0)), 4),
              pts=2 * tab[t]["w"] + tab[t]["otl"], **tab[t], form=form[t]) for t in names]
    T.sort(key=lambda x: (-x["pts"], x["p"], -(x["gf"] - x["ga"])))
    now = pd.Timestamp.now(tz="UTC")
    games = [dict(dt=g["dt"].strftime("%Y-%m-%dT%H:%M"), home=g["home"], away=g["away"]) for g in sorted(up, key=lambda g: g["dt"])
             if g["home"] in tab and g["away"] in tab and now - pd.Timedelta(hours=4) <= g["dt"] <= now + pd.Timedelta(days=8)]
    L = dict(name="NHL", country="Amérique du Nord", home=round(float(m.params["home_adv"]), 4), rho=round(float(m.params["rho"]), 4),
             ot=ot, dk=dk, teams=T, games=games, last=str(df.dt.max().date()))
    print(f"  hockey NHL {len(T)} équipes, {len(games)} matchs à venir, dernier résultat {L['last']}, prolongation gagnée à domicile {ot:.0%}, facteur nuls {dk}")
    t = test or {}
    return dict(leagues={"NHL": L}, order=["NHL"], acc=t.get("acc", 0), n_test=t.get("n", 0), updated=str(today.date()))


if __name__ == "__main__":                 # backtest : python src/nhl.py <dossier>
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from update_all import fetch, RAW, TODAY  # noqa
    df, _ = results(fetch, RAW, TODAY)
    print(len(df), "matchs")
    for xi in (0.0035,):
        XI = xi
        print(xi, backtest(df, TODAY))
