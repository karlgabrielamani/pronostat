"""Modèle Dixon-Coles avec pondération temporelle.

Estime pour chaque équipe une force d'attaque et de défense, plus un avantage
du terrain et le paramètre rho de Dixon-Coles (correction des petits scores).
"""
import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

MAX_GOALS = 10


def _tau(x, y, lam, mu, rho):
    """Correction de Dixon-Coles pour les scores 0-0, 1-0, 0-1, 1-1."""
    t = np.ones_like(lam)
    m00 = (x == 0) & (y == 0)
    m01 = (x == 0) & (y == 1)
    m10 = (x == 1) & (y == 0)
    m11 = (x == 1) & (y == 1)
    t[m00] = 1 - lam[m00] * mu[m00] * rho
    t[m01] = 1 + lam[m01] * rho
    t[m10] = 1 + mu[m10] * rho
    t[m11] = 1 - rho
    return t


class DixonColes:
    def __init__(self, xi=0.0019):
        # xi : décroissance par jour (0.0019 ≈ demi-vie d'environ 1 an)
        self.xi = xi
        self.params = None

    def fit(self, home, away, hg, ag, days_ago, init=None):
        teams = sorted(set(home) | set(away))
        self.teams = teams
        idx = {t: i for i, t in enumerate(teams)}
        n = len(teams)
        hi = np.array([idx[t] for t in home])
        ai = np.array([idx[t] for t in away])
        hg = np.asarray(hg, dtype=int)
        ag = np.asarray(ag, dtype=int)
        w = np.exp(-self.xi * np.asarray(days_ago, dtype=float))

        lgam_h = np.array([np.sum(np.log(np.arange(1, k + 1))) for k in hg])
        lgam_a = np.array([np.sum(np.log(np.arange(1, k + 1))) for k in ag])

        def unpack(p):
            att = p[:n]
            att = att - att.mean()          # contrainte d'identifiabilité
            dfn = p[n:2 * n]
            return att, dfn, p[2 * n], p[2 * n + 1]

        def nll(p):
            att, dfn, home_adv, rho = unpack(p)
            lam = np.exp(att[hi] + dfn[ai] + home_adv)
            mu = np.exp(att[ai] + dfn[hi])
            tau = _tau(hg, ag, lam, mu, rho)
            if np.any(tau <= 0):
                return 1e10
            ll = (np.log(tau)
                  + hg * np.log(lam) - lam - lgam_h
                  + ag * np.log(mu) - mu - lgam_a)
            return -np.sum(w * ll) + 1e-3 * np.sum(p[:2 * n] ** 2)

        if init is None:
            p0 = np.concatenate([np.zeros(n), np.zeros(n), [0.25, -0.05]])
        else:
            p0 = init
        bounds = [(None, None)] * (2 * n) + [(None, None), (-0.3, 0.3)]
        res = minimize(nll, p0, method="L-BFGS-B", bounds=bounds,
                       options={"maxiter": 500})
        att, dfn, home_adv, rho = unpack(res.x)
        self.params = dict(att=dict(zip(teams, att)), dfn=dict(zip(teams, dfn)),
                           home_adv=home_adv, rho=rho)
        self.raw = res.x
        return self

    def score_matrix(self, home, away):
        p = self.params
        lam = np.exp(p["att"][home] + p["dfn"][away] + p["home_adv"])
        mu = np.exp(p["att"][away] + p["dfn"][home])
        g = np.arange(MAX_GOALS + 1)
        m = np.outer(poisson.pmf(g, lam), poisson.pmf(g, mu))
        rho = p["rho"]
        m[0, 0] *= 1 - lam * mu * rho
        m[0, 1] *= 1 + lam * rho
        m[1, 0] *= 1 + mu * rho
        m[1, 1] *= 1 - rho
        return m / m.sum(), lam, mu

    def predict(self, home, away):
        m, lam, mu = self.score_matrix(home, away)
        tot = np.add.outer(np.arange(MAX_GOALS + 1), np.arange(MAX_GOALS + 1))
        top = np.dstack(np.unravel_index(np.argsort(-m, axis=None)[:3], m.shape))[0]
        return {
            "pH": np.tril(m, -1).sum(), "pD": np.trace(m), "pA": np.triu(m, 1).sum(),
            "pOver": m[tot > 2.5].sum(), "pUnder": m[tot < 2.5].sum(),
            "pBTTS": m[1:, 1:].sum(),
            "xg_home": lam, "xg_away": mu,
            "top_scores": [(f"{i}-{j}", m[i, j]) for i, j in top],
        }
