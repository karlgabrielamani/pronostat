"""Stratégies de paris testées avec un capital virtuel de 100 €.

Chaque match est décrit par un dict :
  p   : probabilités du modèle  {"H","D","A"} (+ "O","U" pour plus/moins de 2,5 buts au foot)
  b   : cotes du bookmaker de référence (Bet365 au foot, DraftKings en NBA), mêmes clés
  mx  : meilleure cote du marché (foot seulement), mêmes clés — peut être vide
  avg : cote moyenne du marché (foot seulement), mêmes clés — peut être vide
  key : identifiant stable du match (sert au tirage « au hasard », reproductible)
Une mise « flat » vaut 1 € (1 % du capital de départ). Kelly et martingale dépendent du capital.
"""
import hashlib

START = 100.0
FLAT = 1.0

STRATS = [
    ("hasard", "Au hasard", "Une issue tirée au sort à chaque match (Bet365). Sert de point de comparaison."),
    ("fav_marche", "Favori des bookmakers", "La cote la plus basse de chaque match (Bet365)."),
    ("fav_modele", "Favori du modèle", "L'issue que le modèle juge la plus probable (Bet365)."),
    ("fav_sur", "Favori très probable", "Favori du modèle seulement s'il a au moins 60 % de chances."),
    ("accord", "Modèle et bookmakers d'accord", "Même favori pour les deux, cote entre 1,60 et 2,30."),
    ("value3", "Cote trop haute (+3 %)", "Le modèle estime la cote Bet365 au moins 3 % trop généreuse."),
    ("value10", "Cote trop haute (+10 %)", "Même idée, mais seulement quand l'écart dépasse 10 %."),
    ("value5_max", "Cote trop haute + meilleure cote", "Écart de 5 % ou plus, en prenant la meilleure cote du marché."),
    ("kelly", "Cote trop haute, mise selon la confiance", "Écart de 5 % ou plus ; mise = quart de Kelly (max 5 % du capital)."),
    ("outsider", "Outsiders sous-estimés", "Cote d'au moins 3,50 et écart de 5 % ou plus selon le modèle."),
    ("nul", "Matchs nuls", "Le nul quand le modèle l'estime au moins 5 % sous-coté."),
    ("buts", "Plus / moins de 2,5 buts", "Plus ou moins de 2,5 buts quand le modèle voit un écart de 5 % ou plus."),
    ("marche_seul", "Sans modèle : meilleure cote vs moyenne", "Meilleure cote au moins 5 % au-dessus de la cote moyenne « juste » (marge retirée)."),
    ("combi2", "Combiné de 2 favoris sûrs", "Chaque jour, les 2 favoris les plus probables du modèle (cote ≥ 1,30) en un combiné."),
    ("martingale", "Martingale sur favoris", "Favori des bookmakers ; mise doublée après chaque perte, 1 € après un gain."),
]
NAMES = {s[0]: s[1] for s in STRATS}
LABEL = {"H": "1", "D": "N", "A": "2", "O": "+2,5", "U": "−2,5"}


def _ok(o):
    return o is not None and o == o and o > 1.0


def _best_edge(p, odds, keys, thr, min_odds=1.0):
    best = None
    for k in keys:
        o = odds.get(k)
        if k in p and _ok(o) and o >= min_odds:
            e = p[k] * o - 1
            if e > thr and (best is None or e > best[2]): best = (k, o, e)
    return best


def picks(sid, m):
    """Paris d'une stratégie sur un match : liste de (sélection, cote, type de mise, écart)."""
    p, b, mx, avg = m["p"], m["b"], m.get("mx") or {}, m.get("avg") or {}
    res = [k for k in ("H", "D", "A") if k in p and _ok(b.get(k))]
    if len(res) < 2: return []
    if sid == "hasard":
        k = res[int(hashlib.md5(m["key"].encode()).hexdigest(), 16) % len(res)]
        return [(k, b[k], "flat", None)]
    if sid in ("fav_marche", "martingale"):
        k = min(res, key=lambda x: b[x]); return [(k, b[k], "mart" if sid == "martingale" else "flat", None)]
    fav = max(res, key=lambda x: p[x])
    if sid == "fav_modele": return [(fav, b[fav], "flat", None)]
    if sid == "fav_sur": return [(fav, b[fav], "flat", None)] if p[fav] >= 0.60 else []
    if sid == "accord":
        mk = min(res, key=lambda x: b[x])
        return [(fav, b[fav], "flat", None)] if mk == fav and 1.60 <= b[fav] <= 2.30 else []
    if sid == "value3":
        x = _best_edge(p, b, res, 0.03); return [(x[0], x[1], "flat", x[2])] if x else []
    if sid == "value10":
        x = _best_edge(p, b, res, 0.10); return [(x[0], x[1], "flat", x[2])] if x else []
    if sid == "value5_max":
        x = _best_edge(p, mx, res, 0.05); return [(x[0], x[1], "flat", x[2])] if x else []
    if sid == "kelly":
        x = _best_edge(p, b, res, 0.05); return [(x[0], x[1], "kelly", x[2])] if x else []
    if sid == "outsider":
        x = _best_edge(p, b, res, 0.05, min_odds=3.5); return [(x[0], x[1], "flat", x[2])] if x else []
    if sid == "nul":
        x = _best_edge(p, b, ["D"], 0.05); return [(x[0], x[1], "flat", x[2])] if x else []
    if sid == "buts":
        x = _best_edge(p, b, ["O", "U"], 0.05); return [(x[0], x[1], "flat", x[2])] if x else []
    if sid == "marche_seul":
        if not all(_ok(avg.get(k)) for k in res): return []
        inv = {k: 1 / avg[k] for k in res}; s = sum(inv.values())
        fair = {k: v / s for k, v in inv.items()}
        x = _best_edge(fair, mx, res, 0.05); return [(x[0], x[1], "flat", x[2])] if x else []
    return []


def combi_pick(day_matches):
    """Combiné du jour : les 2 favoris du modèle les plus probables, cote Bet365 ≥ 1,30 chacun."""
    cand = []
    for m in day_matches:
        res = [k for k in ("H", "D", "A") if k in m["p"] and _ok(m["b"].get(k))]
        if len(res) < 2: continue
        fav = max(res, key=lambda x: m["p"][x])
        if m["b"][fav] >= 1.30: cand.append((m["p"][fav], m, fav))
    cand.sort(key=lambda x: -x[0])
    if len(cand) < 2: return None
    legs = [(c[1]["key"], c[2], c[1]["b"][c[2]]) for c in cand[:2]]
    return legs, legs[0][2] * legs[1][2]


def stake(kind, bank, edge=None, odds=None, losses=0):
    if bank <= 0: return 0.0
    if kind == "kelly":
        f = min(0.05, 0.25 * edge / (odds - 1)); return round(max(0.0, f * bank), 2)
    if kind == "mart":
        return round(min(bank, FLAT * 2 ** losses), 2)
    return min(FLAT, bank)
