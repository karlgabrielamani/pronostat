"""Corners, cartons et mi-temps : notes simples par équipe (multiplicatives, pondérées dans le temps, avec un peu de
« rétrécissement » vers la moyenne du championnat). Utilisé par update_all.py pour l'onglet Foot."""
import numpy as np
import pandas as pd

XI = 0.0019          # même pondération dans le temps que le modèle des buts
PRIOR = 60.0


def _ratings(H, A, yh, ya, w, it=30):
    """yh ~ base_h * att[H] * dfn[A] ; ya ~ base_a * att[A] * dfn[H]."""
    teams = sorted(set(H) | set(A)); ix = {t: i for i, t in enumerate(teams)}; n = len(teams)
    hi, ai = np.array([ix[t] for t in H]), np.array([ix[t] for t in A])
    bh, ba = np.sum(w * yh) / np.sum(w), np.sum(w * ya) / np.sum(w)
    att, dfn = np.ones(n), np.ones(n)
    for _ in range(it):
        num = np.bincount(hi, w * yh, n) + np.bincount(ai, w * ya, n) + PRIOR
        den = np.bincount(hi, w * bh * dfn[ai], n) + np.bincount(ai, w * ba * dfn[hi], n) + PRIOR
        att = num / den
        num = np.bincount(ai, w * yh, n) + np.bincount(hi, w * ya, n) + PRIOR
        den = np.bincount(ai, w * bh * att[hi], n) + np.bincount(hi, w * ba * att[ai], n) + PRIOR
        dfn = num / den
    return float(bh), float(ba), dict(zip(teams, att)), dict(zip(teams, dfn))


def fit(hist, today):
    """hist : matchs football-data (2 dernières saisons). Renvoie (paramètres du championnat, notes par équipe) ou (None, {})."""
    need = ["HC", "AC", "HY", "AY", "HR", "AR", "HTHG", "HTAG"]
    if any(c not in hist for c in need): return None, {}
    d = hist.dropna(subset=need + ["FTHG", "FTAG"])
    if len(d) < 80: return None, {}
    w = np.exp(-XI * (today - d.Date).dt.days.values.astype(float))
    H, A = d.HomeTeam.values, d.AwayTeam.values
    ch, ca, catt, cdef = _ratings(H, A, d.HC.values.astype(float), d.AC.values.astype(float), w)
    kh_, ka_ = (d.HY + d.HR).values.astype(float), (d.AY + d.AR).values.astype(float)
    kh, ka, katt, kdef = _ratings(H, A, kh_, ka_, w)
    goals = (d.FTHG + d.FTAG).values.astype(float); ht = (d.HTHG + d.HTAG).values.astype(float)
    f1 = float(np.sum(w * ht) / max(np.sum(w * goals), 1))
    red = float(np.sum(w * ((d.HR + d.AR).values > 0)) / np.sum(w))
    # dispersion des corners (variance / moyenne du total), pour des probabilités plus réalistes que Poisson
    tot = (d.HC + d.AC).values.astype(float); disp = float(max(1.0, np.var(tot) / max(np.mean(tot), 1)))
    lg = dict(ch=round(ch, 3), ca=round(ca, 3), kh=round(kh, 3), ka=round(ka, 3), f1=round(f1, 3), red=round(red, 3), cd=round(disp, 3))
    teams = {t: dict(c=[round(catt[t], 3), round(cdef[t], 3)], k=[round(katt[t], 3), round(kdef[t], 3)]) for t in catt}
    return lg, teams


# ------------------------------------------------------------------ petit test hors échantillon
if __name__ == "__main__":
    import sys, glob, math
    raw = sys.argv[1]
    from scipy.stats import nbinom, poisson
    res = []
    for div in ["E0", "SP1", "I1", "D1", "F1", "N1", "E1", "B1"]:
        fr = [pd.read_csv(f, encoding_errors="ignore") for f in sorted(glob.glob(f"{raw}/{div}_2425.csv")) + sorted(glob.glob(f"{raw}/{div}_2526.csv"))]
        d = pd.concat(fr); d["Date"] = pd.to_datetime(d.Date, dayfirst=True, errors="coerce"); d = d.dropna(subset=["HC", "AC", "HY", "AY", "FTHG"]).sort_values("Date")
        cut = pd.Timestamp("2026-01-01"); train, test = d[d.Date < cut], d[d.Date >= cut]
        lg, T = fit(train, cut)
        for r in test.itertuples():
            if r.HomeTeam not in T or r.AwayTeam not in T: continue
            h, a = T[r.HomeTeam], T[r.AwayTeam]
            lc = lg["ch"] * h["c"][0] * a["c"][1] + lg["ca"] * a["c"][0] * h["c"][1]
            lk = lg["kh"] * h["k"][0] * a["k"][1] + lg["ka"] * a["k"][0] * h["k"][1]
            v = lg["cd"]; p_ = 1 / v; nb = lambda k: nbinom.sf(k, lc * p_ / (1 - p_) if v > 1 else 1e9, p_) if v > 1 else poisson.sf(k, lc)
            base_c = lg["ch"] + lg["ca"]; base_k = lg["kh"] + lg["ka"]
            res.append(dict(div=div, c95=nb(9), c95_0=(nbinom.sf(9, base_c * p_ / (1 - p_), p_) if v > 1 else poisson.sf(9, base_c)),
                            yc=int(r.HC + r.AC > 9.5), k45=poisson.sf(4, lk), k45_0=poisson.sf(4, base_k), yk=int(r.HY + r.AY + r.HR + r.AR > 4.5),
                            hm=int(r.HC > r.AC)))
    R = pd.DataFrame(res)
    br = lambda p, y: float(np.mean((p - y) ** 2))
    print("matchs testés :", len(R))
    print("corners > 9,5  Brier modèle %.4f · moyenne championnat %.4f · fréquence %.3f · prédit %.3f" % (br(R.c95, R.yc), br(R.c95_0, R.yc), R.yc.mean(), R.c95.mean()))
    print("cartons > 4,5  Brier modèle %.4f · moyenne championnat %.4f · fréquence %.3f · prédit %.3f" % (br(R.k45, R.yk), br(R.k45_0, R.yk), R.yk.mean(), R.k45.mean()))
