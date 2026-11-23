"""Stats individuelles des joueurs (NBA, WNBA) pour les probabilités « joueur X+ points / rebonds / passes / 3 pts ».

Données : feuilles de match ESPN (sportsdataverse), les mêmes que pour les absents NBA.
Pour chaque joueur régulier : moyenne pondérée de ses 15 derniers matchs (les plus récents comptent plus, 0,93 par match)
et dispersion observée sur ces matchs. La page en tire une loi binomiale négative et ajuste les points
selon le score prévu de son équipe pour ce match (adversaire, domicile, absents).

Backtest sur toute la saison NBA 2025-26 (436 543 probabilités, sans regarder le futur) :
annoncé 55 % → arrivé 57 %, annoncé 75 % → 75 %, annoncé 95 % → 91 % (sorties sur blessure, banc en fin de match) ;
la page corrige ce dernier point avec p × 0,955 + 0,01.
"""
import numpy as np
import pandas as pd

DECAY, N_LAST, VAR_K = 0.93, 15, 1.2
STATS = (("pts", "points"), ("reb", "rebounds"), ("ast", "assists"), ("tpm", "three_point_field_goals_made"))


def load(P):
    """Nettoie un fichier player_box ESPN (une ou plusieurs saisons concaténées)."""
    P = P[P.season_type.isin([2, 3])].copy()
    P["min"] = pd.to_numeric(P.minutes, errors="coerce").fillna(0)
    P = P[(P["min"] > 0) & (P.did_not_play != True)].copy()            # noqa: E712
    for _, c in STATS: P[c] = pd.to_numeric(P[c], errors="coerce").fillna(0)
    P["date"] = pd.to_datetime(P.game_date)
    return P.sort_values(["date", "game_id"])


def build(P, teams, max_per_team=9):
    """{équipe: {"ppg": points marqués (15 derniers matchs), "pl": [joueurs]}} pour les équipes de la liste `teams`."""
    P = load(P)
    tg = (P.groupby(["team_display_name", "game_id", "date"]).points.sum().reset_index().sort_values("date"))
    out = {}
    last_team = P.drop_duplicates("athlete_id", keep="last").set_index("athlete_id").team_display_name
    for team in teams:
        g = tg[tg.team_display_name == team]
        if len(g) < 3: continue
        last5 = set(g.game_id.tail(5))
        ppg = float(g.points.tail(15).mean())
        pl = []
        for pid, h in P[P.team_display_name == team].groupby("athlete_id"):
            if last_team.get(pid) != team: continue                    # transféré depuis
            if len(set(h.game_id) & last5) < 2: continue                # ne joue plus (blessé longue durée, hors rotation)
            H = P[P.athlete_id == pid].tail(N_LAST)                     # ses derniers matchs, toutes équipes confondues
            if len(H) < 5 or H["min"].tail(10).mean() < 15: continue
            w = DECAY ** np.arange(len(H))[::-1]; w = w / w.sum()
            row = dict(id=int(pid), name=str(H.athlete_display_name.iloc[-1]), n=int(len(H)), min=round(float((w * H["min"]).sum()), 1))
            for k, c in STATS:
                x = H[c].to_numpy(float); m = float((w * x).sum())
                row[k] = round(m, 2)
                row[k + "v"] = round(VAR_K * float((w * (x - m) ** 2).sum()) + 0.15 * m + 0.5, 2)
            dd = ((H[["points", "rebounds", "assists"]] >= 10).sum(axis=1) >= 2).to_numpy(float)
            row["dd"] = round((float((w * dd).sum()) * len(H) + 0.25) / (len(H) + 1), 3)
            pl.append(row)
        pl.sort(key=lambda r: -r["min"])
        if pl: out[team] = dict(ppg=round(ppg, 1), pl=pl[:max_per_team])
    return out
