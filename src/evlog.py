"""Journal des événements : pour chaque match à venir (dans les 36 h), enregistre les % de quelques événements tels que l'appli
les calcule, puis les règle avec le résultat réel. Sert à mesurer la justesse des événements sur l'appli elle-même (data/events_log.csv)."""
import math, os
from datetime import timedelta
import pandas as pd
import history

COLS = ["key", "sport", "dt", "ev", "p", "logged_at", "y"]
MOM, SHRINK = 0.4, 0.75
pois = lambda k, l: math.exp(-l) * l ** k / math.factorial(k)
sig = lambda z: 1 / (1 + math.exp(-z))
lg = lambda p: math.log(p / (1 - p))


def foot_grid(L, h, a, neutral=False, G=10):
    lam, mu = math.exp(h["att"] + a["dfn"] + (0 if neutral else L["home"])), math.exp(a["att"] + h["dfn"])
    if "_m" not in L:
        s = n = 0
        for x in L["teams"]:
            for y in L["teams"]:
                if x is not y: s += math.exp(x["att"] + y["dfn"] + L["home"]) + math.exp(y["att"] + x["dfn"]); n += 1
        L["_m"] = s / n if n else 0
    if L["_m"]:
        f = (L["_m"] / (lam + mu)) ** (1 - SHRINK); lam, mu = lam * f, mu * f
    M = {}; tot = 0
    for i in range(G + 1):
        for j in range(G + 1):
            q = pois(i, lam) * pois(j, mu)
            if i == 0 and j == 0: q *= 1 - lam * mu * L["rho"]
            elif i == 0 and j == 1: q *= 1 + lam * L["rho"]
            elif i == 1 and j == 0: q *= 1 + mu * L["rho"]
            elif i == 1 and j == 1: q *= 1 - L["rho"]
            M[i, j] = q; tot += q
    return {k: v / tot for k, v in M.items()}


FOOT_EV = {"Plus de 1,5 but": lambda i, j: i + j >= 2, "Plus de 2,5 buts": lambda i, j: i + j >= 3, "Moins de 2,5 buts": lambda i, j: i + j <= 2,
           "Moins de 3,5 buts": lambda i, j: i + j <= 3, "Moins de 4,5 buts": lambda i, j: i + j <= 4, "Domicile marque": lambda i, j: i >= 1,
           "Extérieur marque": lambda i, j: j >= 1, "Les deux équipes marquent": lambda i, j: i >= 1 and j >= 1}


def tennis_events(p, need):
    setAt = lambda s, lead: s if lead == 0 else sig(lg(s) + (MOM if lead > 0 else -MOM))
    def match(s):
        memo = {}
        def f(x, y):
            if x == need: return 1.
            if y == need: return 0.
            if (x, y) not in memo: q = setAt(s, x - y); memo[x, y] = q * f(x + 1, y) + (1 - q) * f(x, y + 1)
            return memo[x, y]
        return f(0, 0)
    lo, hi = 1e-6, 1 - 1e-6
    for _ in range(50):
        m = (lo + hi) / 2; lo, hi = (m, hi) if match(m) < p else (lo, m)
    s = (lo + hi) / 2
    def reach(x, y):
        if x < 0 or y < 0: return 0.
        if x == 0 and y == 0: return 1.
        r = 0.
        if x > 0 and x - 1 < need and y < need: r += reach(x - 1, y) * setAt(s, x - 1 - y)
        if y > 0 and y - 1 < need and x < need: r += reach(x, y - 1) * (1 - setAt(s, x - y + 1))
        return r
    A = {l: reach(need, l) for l in range(need)}; B = {l: reach(l, need) for l in range(need)}
    return {"A gagne au moins un set": 1 - B[0], "B gagne au moins un set": 1 - A[0], "A gagne sans perdre de set": A[0],
            "B gagne sans perdre de set": B[0], "Match qui va au bout": A[need - 1] + B[need - 1], "A gagne le 1er set": s}


def update(log_path, out_dir, now, foot, nba, tennis, foot_res, nba_res, tennis_hist):
    now = pd.Timestamp(now)
    log = pd.read_csv(log_path) if os.path.exists(log_path) else pd.DataFrame(columns=COLS)
    have = set(zip(log.key, log.ev)); new = []; horizon = now + timedelta(hours=36)
    def add(key, sport, dt, evs):
        if not (now < dt <= horizon): return
        for ev, p in evs.items():
            if (key, ev) in have: continue
            have.add((key, ev)); new.append(dict(key=key, sport=sport, dt=dt.isoformat(), ev=ev, p=round(p, 4), logged_at=now.isoformat(), y=None))
    for div, L in foot["leagues"].items():
        T = {t["name"]: t for t in L["teams"]}
        for gm in L["games"]:
            if gm["home"] not in T or gm["away"] not in T: continue
            M = foot_grid(L, T[gm["home"]], T[gm["away"]], neutral=bool(gm.get("neutral")))
            add(f"Foot|{div}|{gm['dt'][:10]}|{gm['home']}|{gm['away']}", "Foot", pd.Timestamp(gm["dt"]).tz_localize("UTC"),
                {ev: sum(v for (i, j), v in M.items() if fn(i, j)) for ev, fn in FOOT_EV.items()})
    if nba:
        Tn = {t["name"]: t for t in nba["teams"]}
        sd, corr = nba["sd_team"], nba["corr"]; st = sd * math.sqrt(2 * (1 + corr)); sm = sd * math.sqrt(2 * (1 - corr))
        Phi = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))
        for gm in nba["games"]:
            if gm["home"] not in Tn or gm["away"] not in Tn: continue
            a, b = Tn[gm["home"]], Tn[gm["away"]]
            miss = lambda tm: sum(x["v"] * x["w"] for x in tm.get("inj", []))
            eh = nba["mu"] + a["o"] - b["d"] + nba["hca"] / 2 - nba.get("beta", 0) * miss(a)
            ea = nba["mu"] + b["o"] - a["d"] - nba["hca"] / 2 - nba.get("beta", 0) * miss(b)
            tot, m = eh + ea, eh - ea
            Lt, Lh, La = round(tot) - 15.5, round(eh) - 10.5, round(ea) - 10.5
            evs = {f"Total plus de {Lt} pts": 1 - Phi((Lt - tot) / st), f"Total moins de {Lt + 30} pts": Phi((Lt + 30 - tot) / st),
                   f"Domicile plus de {Lh} pts": 1 - Phi((Lh - eh) / sd), f"Extérieur plus de {La} pts": 1 - Phi((La - ea) / sd)}
            add(f"NBA|{gm['dt'][:10]}|{gm['home']}|{gm['away']}", "NBA", pd.Timestamp(gm["dt"]), evs)
    for circuit, TD in tennis:
        if not TD: continue
        for gm in TD.get("live", []):
            if not (gm.get("k1") and gm.get("k2")): continue
            p = history.tennis_prob(TD, gm["p1"], gm["p2"], gm["surface"], gm["bo"])
            add(f"Tennis|{gm['dt'][:10]}|{gm['p1']}|{gm['p2']}", "Tennis", pd.Timestamp(gm["dt"]), tennis_events(p, 3 if gm["bo"] == 5 else 2))
    if new: log = pd.concat([log, pd.DataFrame(new)], ignore_index=True)
    # ---- règlement
    fr = foot_res.copy(); fr["Date"] = pd.to_datetime(fr.Date, errors="coerce"); fr = fr.dropna(subset=["Date", "FTHG", "FTAG"]); fr["d"] = fr.Date.dt.strftime("%Y-%m-%d")
    fidx = {(r.Div, r.d, r.HomeTeam, r.AwayTeam): (int(r.FTHG), int(r.FTAG)) for r in fr.itertuples()}
    nr = nba_res.copy(); nr["d"] = pd.to_datetime(nr.date).dt.date; nidx = {}
    for r in nr.itertuples(): nidx.setdefault((r.home, r.away), []).append((r.d, int(r.hs), int(r.as_)))
    th = tennis_hist.copy(); th["Date"] = pd.to_datetime(th.Date).dt.date; tidx = {}
    if "ws" in th:
        for r in th[(th.Comment == "Completed") & th.ws.notna()].itertuples():
            tidx.setdefault(frozenset((r.Winner, r.Loser)), []).append((r.Date, r.Winner, int(r.ws), int(r.ls), r.first))
    import re
    for i, r in log[log.y.isna()].iterrows():
        dt = pd.Timestamp(r["dt"])
        if dt > now: continue
        parts = r.key.split("|"); y = None
        if r.sport == "Foot":
            div, d0, h, a = parts[1], pd.Timestamp(parts[2]), parts[3], parts[4]
            sc = next((fidx[k] for k in [(div, str((d0 + timedelta(days=x)).date()), h, a) for x in (0, -1, 1)] if k in fidx), None)
            if sc: y = int(FOOT_EV[r.ev](*sc))
        elif r.sport == "NBA":
            h, a = parts[2], parts[3]
            sc = next(((hs, as_) for d, hs, as_ in nidx.get((h, a), []) if abs((d - dt.date()).days) <= 1), None)
            if sc:
                L = float(re.findall(r"[\d.]+", r.ev)[0]) if re.search(r"\d", r.ev) and "15 pts" not in r.ev else None
                if r.ev.startswith("Total plus"): y = int(sum(sc) > L)
                elif r.ev.startswith("Total moins"): y = int(sum(sc) < L)
                elif r.ev.startswith("Domicile"): y = int(sc[0] > L)
                elif r.ev.startswith("Extérieur"): y = int(sc[1] > L)
        else:
            A_, B_ = parts[2], parts[3]
            res = next((x for x in tidx.get(frozenset((A_, B_)), []) if abs((x[0] - dt.date()).days) <= 1), None)
            if res:
                _, w, ws, ls, first = res; aw = w == A_; sa, sb = (ws, ls) if aw else (ls, ws)
                need = max(ws, ls)
                y = int({"A gagne au moins un set": sa >= 1, "B gagne au moins un set": sb >= 1, "A gagne sans perdre de set": aw and sb == 0,
                         "B gagne sans perdre de set": (not aw) and sa == 0, "Match qui va au bout": sa + sb == 2 * need - 1,
                         "A gagne le 1er set": (first == 1) == aw}.get(r.ev, False))
        if y is not None: log.at[i, "y"] = y
        elif now - dt > timedelta(days=4): log.at[i, "y"] = -1          # résultat introuvable : exclu
    log.to_csv(f"{out_dir}/events_log.csv", index=False)
    done = log[log.y.isin([0, 1])]
    print(f"  événements : {len(log)} enregistrés, {len(done)} réglés")
