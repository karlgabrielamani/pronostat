"""Portefeuilles virtuels : chaque stratégie part de 100 € et parie sur les matchs du jour avec les vraies cotes.

Foot : cotes de football-data (fixtures.csv : Bet365, meilleure cote, cote moyenne) pour les championnats suivis.
NBA : cotes DraftKings publiées par ESPN (vainqueur du match).
Les paris sont enregistrés avant le match, jamais modifiés, puis réglés avec les résultats réels.
Journal : data/paper_bets.csv (republié avec la page).
"""
import json, math, os, urllib.request
from datetime import timedelta
import pandas as pd
import strategies as S
from history import nba_prob

COLS = ["id", "strat", "sport", "comp", "dt", "match", "a", "b", "sel", "odds", "stake", "edge", "placed_at", "legs", "result", "profit"]


def foot_probs5(L, h, a, maxg=10):
    lam, mu = math.exp(h["att"] + a["dfn"] + L["home"]), math.exp(a["att"] + h["dfn"])
    pois = lambda k, l: math.exp(-l) * l ** k / math.factorial(k)
    r = dict(H=0., D=0., A=0., O=0., U=0.); tot = 0.
    for i in range(maxg + 1):
        for j in range(maxg + 1):
            q = pois(i, lam) * pois(j, mu)
            if i == 0 and j == 0: q *= 1 - lam * mu * L["rho"]
            elif i == 0 and j == 1: q *= 1 + lam * L["rho"]
            elif i == 1 and j == 0: q *= 1 + mu * L["rho"]
            elif i == 1 and j == 1: q *= 1 - L["rho"]
            tot += q
            r["H" if i > j else "D" if i == j else "A"] += q
            r["O" if i + j > 2 else "U"] += q
    return {k: v / tot for k, v in r.items()}


def american(s):
    try: v = float(str(s).replace("+", ""))
    except ValueError: return None
    if v == 0: return None
    return round(1 + (v / 100 if v > 0 else 100 / -v), 3)


def nba_odds(today):
    out = {}
    for k in (0, 1):
        d = today + timedelta(days=k)
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={d:%Y%m%d}"
        req = urllib.request.Request(url, headers={"User-Agent": "pronos-weekly-update"})
        with urllib.request.urlopen(req, timeout=60) as r: data = json.loads(r.read())
        for e in data.get("events", []):
            c = e["competitions"][0]; o = (c.get("odds") or [{}])[0]
            ml = o.get("moneyline") or {}
            pick = lambda side: american(((ml.get(side) or {}).get("close") or {}).get("odds") or ((ml.get(side) or {}).get("open") or {}).get("odds"))
            hm = next((x for x in c["competitors"] if x["homeAway"] == "home"), None); aw = next((x for x in c["competitors"] if x["homeAway"] == "away"), None)
            if hm and aw:
                out[(hm["team"]["displayName"], aw["team"]["displayName"])] = dict(H=pick("home"), A=pick("away"))
    return out


def matches(foot, fixtures, nba, today):
    """Matchs à venir avec probabilités du modèle et cotes."""
    num = lambda r, c: float(r[c]) if c in r and pd.notna(r[c]) else None
    M = []
    fx = fixtures.copy()
    for r in fx.to_dict("records"):
        L = foot["leagues"].get(r["Div"])
        if not L or L.get("cup"): continue
        T = {t["name"]: t for t in L["teams"]}
        if r["HomeTeam"] not in T or r["AwayTeam"] not in T or pd.isna(r["Date"]): continue
        tm = r["Time"] if isinstance(r.get("Time"), str) else "15:00"
        dt = pd.Timestamp(f"{r['Date'].date()} {tm}").tz_localize("Europe/London").tz_convert("UTC")
        M.append(dict(sport="Foot", comp=L["name"], div=r["Div"], dt=dt, a=r["HomeTeam"], b=r["AwayTeam"],
                      key=f"Foot|{r['Div']}|{r['Date'].date()}|{r['HomeTeam']}|{r['AwayTeam']}",
                      p=foot_probs5(L, T[r["HomeTeam"]], T[r["AwayTeam"]]),
                      b_={"H": num(r, "B365H"), "D": num(r, "B365D"), "A": num(r, "B365A"), "O": num(r, "B365>2.5"), "U": num(r, "B365<2.5")},
                      mx={"H": num(r, "MaxH"), "D": num(r, "MaxD"), "A": num(r, "MaxA")},
                      avg={"H": num(r, "AvgH"), "D": num(r, "AvgD"), "A": num(r, "AvgA")}))
    try:
        od = nba_odds(today)
    except Exception as e:
        print("  ATTENTION cotes NBA indisponibles :", repr(e)); od = {}
    names = {t["name"] for t in nba["teams"]}
    for g in nba["games"]:
        o = od.get((g["home"], g["away"]))
        if not o or g["home"] not in names or g["away"] not in names: continue
        p = nba_prob(nba, g["home"], g["away"])
        M.append(dict(sport="NBA", comp="NBA", dt=pd.Timestamp(g["dt"]), a=g["home"], b=g["away"],
                      key=f"NBA|{g['dt'][:10]}|{g['home']}|{g['away']}", p={"H": p, "A": 1 - p}, b_=o, mx={}, avg={}))
    for m in M: m["b"] = m.pop("b_")
    return M


def update(log_path, out_dir, now, foot, fixtures, nba, foot_res, nba_res):
    now = pd.Timestamp(now)
    log = pd.read_csv(log_path, dtype={"result": str, "legs": str}) if os.path.exists(log_path) else pd.DataFrame(columns=COLS)
    # ---- règlement
    fr = foot_res.copy(); fr["Date"] = pd.to_datetime(fr.Date, errors="coerce"); fr = fr.dropna(subset=["Date", "FTHG", "FTAG"])
    fidx = {(r.Div, str(r.Date.date()), r.HomeTeam, r.AwayTeam): (int(r.FTHG), int(r.FTAG)) for r in fr.itertuples()}
    nidx = {}
    for r in nba_res.itertuples(): nidx.setdefault((r.home, r.away), []).append((pd.Timestamp(r.date).date(), int(r.hs), int(r.as_)))

    def outcome(match_key):
        parts = match_key.split("|")
        if parts[0] == "Foot":
            _, div, d, h, a = parts
            for k in (0, -1, 1):
                sc = fidx.get((div, str((pd.Timestamp(d) + timedelta(days=k)).date()), h, a))
                if sc: return {"H": sc[0] > sc[1], "D": sc[0] == sc[1], "A": sc[0] < sc[1], "O": sum(sc) > 2.5, "U": sum(sc) < 2.5}
        else:
            _, d, h, a = parts
            for dd, hs, as_ in nidx.get((h, a), []):
                if abs((dd - pd.Timestamp(d).date()).days) <= 1: return {"H": hs > as_, "A": hs < as_}
        return None

    for i, r in log[log.result.isna()].iterrows():
        dt = pd.Timestamp(r["dt"])
        if dt > now: continue
        legs = json.loads(r["legs"]) if isinstance(r["legs"], str) and r["legs"] else [[r["match"], r["sel"]]]
        outs = [outcome(k) for k, _ in legs]
        if all(o is not None for o in outs):
            win = all(o[s] for o, (_, s) in zip(outs, legs))
            log.at[i, "result"] = "W" if win else "L"
            log.at[i, "profit"] = round(r["stake"] * (r["odds"] - 1), 2) if win else -r["stake"]
        elif now - dt > timedelta(days=4):
            log.at[i, "result"] = "X"; log.at[i, "profit"] = 0.0          # reporté / introuvable : mise rendue

    # ---- nouveaux paris (matchs qui commencent dans les 36 h)
    M = [m for m in matches(foot, fixtures, nba, now.tz_convert(None).normalize()) if now < m["dt"] <= now + timedelta(hours=36)]
    have = set(log.id)
    new = []
    def state(sid):
        d = log[log.strat == sid]
        settled = d[d.result.isin(["W", "L", "X"])].sort_values("dt")
        bank = S.START + settled.profit.astype(float).sum() - d[d.result.isna()].stake.astype(float).sum()
        bank -= sum(b["stake"] for b in new if b["strat"] == sid)
        losses = 0
        for res in settled.result[::-1]:
            if res == "L": losses += 1
            elif res == "W": break
        return bank, losses
    for sid, name, _ in S.STRATS:
        if sid == "combi2":
            by = {}
            for m in M: by.setdefault(str(m["dt"].tz_convert("Europe/Amsterdam").date()), []).append(m)
            for day, ms in by.items():
                bid = f"combi2|{day}"
                if bid in have: continue
                c = S.combi_pick(ms)
                if not c: continue
                legs, o = c; bank, _ = state(sid); st = S.stake("flat", bank)
                if st <= 0: continue
                idx = {m["key"]: m for m in ms}
                lm = [idx[k] for k, _, _ in legs]
                new.append(dict(id=bid, strat=sid, sport="+".join(sorted({m["sport"] for m in lm})), comp="Combiné", dt=max(m["dt"] for m in lm).isoformat(),
                                match=" + ".join(f"{m['a']} – {m['b']}" for m in lm), a=None, b=None,
                                sel=" + ".join(S.LABEL[s] for _, s, _ in legs), odds=round(o, 3), stake=st, edge=None,
                                placed_at=now.isoformat(), legs=json.dumps([[k, s] for k, s, _ in legs]), result=None, profit=None))
            continue
        for m in sorted(M, key=lambda x: x["dt"]):
            for sel, o, kind, e in S.picks(sid, m):
                bid = f"{sid}|{m['key']}|{sel}"
                if bid in have: continue
                bank, losses = state(sid)
                st = S.stake(kind, bank, e, o, losses)
                if st <= 0: continue
                new.append(dict(id=bid, strat=sid, sport=m["sport"], comp=m["comp"], dt=m["dt"].isoformat(), match=m["key"], a=m["a"], b=m["b"],
                                sel=sel, odds=o, stake=st, edge=None if e is None else round(e, 4), placed_at=now.isoformat(),
                                legs=None, result=None, profit=None))
    if new: log = pd.concat([log, pd.DataFrame(new)], ignore_index=True)
    log.to_csv(f"{out_dir}/paper_bets.csv", index=False)

    # ---- résumé pour la page
    summ = []
    for sid, name, desc in S.STRATS:
        d = log[log.strat == sid]; s = d[d.result.isin(["W", "L"])]
        staked, prof = float(s.stake.sum()), float(s.profit.astype(float).sum())
        summ.append(dict(id=sid, name=name, desc=desc, n=int(len(s)), won=int((s.result == "W").sum()), staked=round(staked, 2),
                         profit=round(prof, 2), bank=round(S.START + prof, 2), roi=round(prof / staked, 4) if staked else None,
                         pending=int(d.result.isna().sum())))
    up = log[log.result.isna()].sort_values("dt")
    open_bets = [dict(strat=S.NAMES[r.strat], sport=r.sport, dt=r.dt, match=(f"{r.a} – {r.b}" if isinstance(r.a, str) else r.match),
                      sel=r.sel if r.legs == r.legs and isinstance(r.legs, str) else S.LABEL.get(r.sel, r.sel), odds=float(r.odds), stake=float(r.stake))
                 for r in up.itertuples()][:150]
    print(f"  stratégies : {len(new)} paris virtuels placés, {int(log.result.isin(['W', 'L']).sum())} réglés au total")
    return dict(since=str(pd.Timestamp(log.placed_at.min()).date()) if len(log) else None, strats=summ, open=open_bets)
