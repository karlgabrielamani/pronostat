"""Historique public des pronostics.

Chaque passage :
  1. enregistre le pronostic de chaque match qui n'a pas encore commencé (dans les 36 h), sans jamais le modifier ensuite ;
  2. règle les pronostics passés avec les résultats réels ;
  3. renvoie un résumé (bilan par sport + derniers pronostics) pour la page.
Le journal (data/predictions_log.csv) est republié avec la page pour s'accumuler d'un jour à l'autre.
"""
import math, os
from datetime import timedelta
import numpy as np
import pandas as pd

COLS = ["key", "sport", "comp", "dt", "a", "b", "pa", "pd", "pb", "logged_at", "result", "score"]


# ------------------------------------------------------------------ probabilités (mêmes formules que la page)
def foot_probs(L, h, a, maxg=10, neutral=False):
    lam, mu = math.exp(h["att"] + a["dfn"] + (0 if neutral else L["home"])), math.exp(a["att"] + h["dfn"])
    pois = lambda k, l: math.exp(-l) * l ** k / math.factorial(k)
    pH = pD = pA = tot = 0.0
    for i in range(maxg + 1):
        for j in range(maxg + 1):
            q = pois(i, lam) * pois(j, mu)
            if i == 0 and j == 0: q *= 1 - lam * mu * L["rho"]
            elif i == 0 and j == 1: q *= 1 + lam * L["rho"]
            elif i == 1 and j == 0: q *= 1 + mu * L["rho"]
            elif i == 1 and j == 1: q *= 1 - L["rho"]
            tot += q
            if i > j: pH += q
            elif i == j: pD += q
            else: pA += q
    return pH / tot, pD / tot, pA / tot


def nba_prob(N, home, away):
    T = {t["name"]: t for t in N["teams"]}
    a, b = T[home], T[away]
    miss = lambda tm: sum(x["v"] * x["w"] for x in tm.get("inj", []))
    m = (N["mu"] + a["o"] - b["d"] + N["hca"] / 2 - N.get("beta", 0) * miss(a)) - (N["mu"] + b["o"] - a["d"] - N["hca"] / 2 - N.get("beta", 0) * miss(b))
    s = N["sd_team"] * math.sqrt(2 * (1 - N["corr"]))
    return 0.5 * (1 + math.erf(m / s / math.sqrt(2)))


def tennis_prob(D, p1, p2, surface, bo):
    P = {p["name"]: p for p in D["players"]}
    a, b = P[p1], P[p2]
    E = lambda x, y: 1 / (1 + 10 ** ((y - x) / 400))
    cl = lambda p: min(max(p, 1e-4), 1 - 1e-4)
    logit = lambda p: math.log(p / (1 - p))
    s = {"Hard": "hard", "Clay": "clay", "Grass": "grass"}[surface]; g = {"Hard": "gHard", "Clay": "gClay", "Grass": "gGrass"}[surface]
    today = pd.Timestamp(D["updated"])
    days = lambda d: max(0, (today - pd.Timestamp(d)).days)
    load = lambda p: sum(1 for d in p["hist"] if days(d) <= 14)
    eloB = logit(cl(E((a["elo"] + a[s]) / 2, (b["elo"] + b[s]) / 2)))
    eloS = logit(cl(E(a[s], b[s])))
    gelB = logit(cl(E((a["g"] + a[g]) / 2, (b["g"] + b[g]) / 2)))
    rank = math.log((b["rank"] or 500) / (a["rank"] or 500))
    inact = math.log1p(min(days(a["last"]), 365)) - math.log1p(min(days(b["last"]), 365))
    bo5 = 1 if bo == 5 else 0
    x = [eloB, eloS, gelB, rank, inact, load(a) - load(b), a["ret"] - b["ret"], eloB * bo5, eloS * bo5]
    z = sum(v * w for v, w in zip(x, D["coef"]["w"])) + D["coef"]["c"]
    return 1 / (1 + math.exp(-z))


# ------------------------------------------------------------------ journal
def update(log_path, out_dir, now, foot, nba, tennis, foot_res, nba_res, tennis_hist):
    now = pd.Timestamp(now, tz="UTC") if pd.Timestamp(now).tzinfo is None else pd.Timestamp(now)
    log = pd.read_csv(log_path, dtype={"result": str, "score": str}) if os.path.exists(log_path) else pd.DataFrame(columns=COLS)
    have = set(log.key)
    new = []
    horizon = now + timedelta(hours=36)

    def add(key, sport, comp, dt, a, b, pa, pd_, pb):
        if key in have or not (now < dt <= horizon): return
        have.add(key)
        new.append(dict(key=key, sport=sport, comp=comp, dt=dt.isoformat(), a=a, b=b, pa=round(pa, 4),
                        pd=None if pd_ is None else round(pd_, 4), pb=round(pb, 4), logged_at=now.isoformat(), result=None, score=None))

    # foot
    for div, L in foot["leagues"].items():
        T = {t["name"]: t for t in L["teams"]}
        for gm in L["games"]:
            if gm["home"] not in T or gm["away"] not in T: continue
            dt = pd.Timestamp(gm["dt"]).tz_localize("UTC")
            pH, pD, pA = foot_probs(L, T[gm["home"]], T[gm["away"]], neutral=bool(gm.get("neutral")))
            add(f"Foot|{div}|{gm['dt'][:10]}|{gm['home']}|{gm['away']}", "Foot", L["name"], dt, gm["home"], gm["away"], pH, pD, pA)
    # NBA
    names = {t["name"] for t in nba["teams"]}
    for gm in nba["games"]:
        if gm["home"] not in names or gm["away"] not in names: continue
        dt = pd.Timestamp(gm["dt"])
        p = nba_prob(nba, gm["home"], gm["away"])
        add(f"NBA|{gm['dt'][:10]}|{gm['home']}|{gm['away']}", "NBA", "NBA", dt, gm["home"], gm["away"], p, None, 1 - p)
    # tennis (ATP et WTA)
    for circuit, TD in tennis:
        if not TD: continue
        for gm in TD.get("live", []):
            if not (gm.get("k1") and gm.get("k2")): continue
            dt = pd.Timestamp(gm["dt"])
            p = tennis_prob(TD, gm["p1"], gm["p2"], gm["surface"], gm["bo"])
            add(f"Tennis|{gm['dt'][:10]}|{gm['p1']}|{gm['p2']}", "Tennis", f"{circuit} · {gm['tour']} · {gm['round']}", dt, gm["p1"], gm["p2"], p, None, 1 - p)
    if new:
        log = pd.concat([log, pd.DataFrame(new)], ignore_index=True)

    # ---- règlement des pronostics passés
    fr = foot_res.copy(); fr["Date"] = pd.to_datetime(fr.Date, errors="coerce"); fr = fr.dropna(subset=["Date", "FTHG", "FTAG"]); fr["d"] = fr.Date.dt.strftime("%Y-%m-%d")
    fidx = {(r.Div, r.d, r.HomeTeam, r.AwayTeam): (int(r.FTHG), int(r.FTAG)) for r in fr.itertuples()}
    nr = nba_res.copy(); nr["d"] = pd.to_datetime(nr.date).dt.date
    nidx = {}
    for r in nr.itertuples(): nidx.setdefault((r.home, r.away), []).append((r.d, int(r.hs), int(r.as_)))
    th = tennis_hist.copy(); th["Date"] = pd.to_datetime(th.Date).dt.date
    tidx = {}
    for r in th[th.Comment != "Walkover"].itertuples(): tidx.setdefault(frozenset((r.Winner, r.Loser)), []).append((r.Date, r.Winner, r.gw, r.gl))
    for i, r in log[log.result.isna()].iterrows():
        dt = pd.Timestamp(r["dt"])
        if dt > now: continue
        if r.sport == "Foot":
            div = r.key.split("|")[1]
            for k in (0, -1, 1):
                sc = fidx.get((div, str((dt + timedelta(days=k)).date()), r.a, r.b))
                if sc: log.at[i, "result"] = "A" if sc[0] > sc[1] else "N" if sc[0] == sc[1] else "B"; log.at[i, "score"] = f"{sc[0]}-{sc[1]}"; break
        elif r.sport == "NBA":
            for d, hs, as_ in nidx.get((r.a, r.b), []):
                if abs((d - dt.date()).days) <= 1:
                    log.at[i, "result"] = "A" if hs > as_ else "B"; log.at[i, "score"] = f"{hs}-{as_}"; break
        else:
            for d, w, gw, gl in tidx.get(frozenset((r.a, r.b)), []):
                if abs((d - dt.date()).days) <= 1:
                    log.at[i, "result"] = "A" if w == r.a else "B"; break
        if pd.isna(log.at[i, "result"]) and now - dt > timedelta(days=4):
            log.at[i, "result"] = "X"            # match reporté ou résultat introuvable : exclu du bilan
    log.to_csv(f"{out_dir}/predictions_log.csv", index=False)

    # ---- résumé
    done = log[log.result.isin(["A", "N", "B"])].copy()
    def fav(r):
        opts = [("A", r.pa), ("B", r.pb)] + ([("N", r.pd)] if pd.notna(r.pd) else [])
        return max(opts, key=lambda x: x[1])
    summary = {"since": str(pd.Timestamp(log.logged_at.min()).date()) if len(log) else None, "pending": int(log.result.isna().sum()), "sports": {}, "recent": []}
    for sp in ("Foot", "Tennis", "NBA"):
        d = done[done.sport == sp]
        if not len(d):
            summary["sports"][sp] = dict(n=0); continue
        hits = [fav(r)[0] == r.result for r in d.itertuples()]
        pfav = [fav(r)[1] for r in d.itertuples()]
        summary["sports"][sp] = dict(n=int(len(d)), hits=int(sum(hits)), expected=round(float(np.mean(pfav)), 4))
    for r in done.sort_values("dt", ascending=False).head(30).itertuples():
        f_, p = fav(r)
        summary["recent"].append(dict(sport=r.sport, comp=r.comp, dt=r.dt, a=r.a, b=r.b,
                                      pick=r.a if f_ == "A" else r.b if f_ == "B" else "Match nul", p=round(p, 3),
                                      ok=bool(f_ == r.result), score=None if pd.isna(r.score) else r.score))
    print(f"  historique : {len(new)} pronostics enregistrés, {len(done)} réglés au total, {summary['pending']} en attente")
    return summary
