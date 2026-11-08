"""Tennis : ajoute les nouveaux résultats ATP (ESPN), recalcule les notes Elo et liste les matchs à venir.

L'historique (data/tennis_history.csv) grandit à chaque passage ; la version mise à jour est écrite dans out/
pour être republiée avec la page. Les coefficients du modèle restent ceux du dernier réglage (data/tennis_tool.json).
"""
import json, re, unicodedata, urllib.request
from datetime import timedelta
import numpy as np
import pandas as pd

ESPN = "https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard"
SINGLES = {"atp": "Men's Singles", "wta": "Women's Singles"}
ROUND = {"Round 1": 1, "Round 2": 2, "Round 3": 3, "Round 4": 4, "Round Robin": 4, "Quarterfinal": 5, "Quarterfinals": 5,
         "Semifinal": 6, "Semifinals": 6, "Final": 7}
ROUND_FR = {1: "1er tour", 2: "2e tour", 3: "3e tour", 4: "4e tour", 5: "Quart de finale", 6: "Demi-finale", 7: "Finale"}
CLAY = {"buenos aires", "rio de janeiro", "santiago", "marrakech", "bucharest", "houston", "estoril", "munich", "barcelona",
        "monte carlo", "monaco", "madrid", "rome", "geneva", "hamburg", "bastad", "gstaad", "umag", "kitzbuhel", "cordoba",
        "kitzbühel", "båstad", "roquebrune-cap-martin", "lyon_clay", "belgrade", "banja luka", "cagliari", "parma",
        "charleston", "bogota", "rabat", "strasbourg", "palermo", "prague", "lausanne", "warsaw", "iasi", "bucuresti",
        "budapest", "portoroz", "hamburg", "saint-malo", "parma", "florianopolis", "cluj-napoca", "oeiras", "makarska"}
GRASS = {"halle", "'s-hertogenbosch", "s-hertogenbosch", "mallorca", "eastbourne", "newport", "nottingham", "birmingham",
         "bad homburg", "ilkley", "surbiton"}
K_MUL, G_K = 0.8, 1.0
E = lambda a, b: 1 / (1 + 10 ** ((b - a) / 400))


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", " ", s.replace("-", " ")).split()


def keys_td(name):                       # « Carreno Busta P. »
    m = re.match(r"^(.*?)\s+([A-Za-z\-\.]+)\.?$", str(name).strip())
    if not m: return set()
    sur, ini = norm(m.group(1)), norm(m.group(2))
    if not sur or not ini: return set()
    return {"".join(sur) + "_" + ini[0][0], sur[-1] + "_" + ini[0][0], sur[0] + "_" + ini[0][0]}


def keys_full(name):                     # « Pablo Carreno Busta »
    t = norm(name)
    if len(t) < 2: return []
    out = ["".join(t[i:]) + "_" + t[0][0] for i in range(1, len(t))]
    out += [t[-1] + "_" + t[j][0] for j in range(1, len(t) - 1)]      # prénoms multiples : « Adolfo Daniel Vallejo »
    return out


def surface(city, month):
    c = city.lower()
    if c == "paris": return "Clay" if month in (5, 6) else "Hard"
    if c in ("london", "stuttgart", "berlin", "queens") and month in (6, 7): return "Grass"
    if c in ("stuttgart", "madrid", "rome", "berlin") and month in (4, 5): return "Clay"
    if c in GRASS: return "Grass"
    if c in CLAY: return "Clay"
    return "Hard"


def fetch_day(d, tour="atp"):
    url = ESPN.format(tour=tour) + f"?dates={d:%Y%m%d}"
    req = urllib.request.Request(url, headers={"User-Agent": "pronos-weekly-update"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def parse_events(data, tour, seen, out):
    for e in data.get("events", []):
        city = ((e.get("venue") or {}).get("displayName") or "").split(",")[0].strip()
        for g in e.get("groupings", []):
            if g.get("grouping", {}).get("displayName") != SINGLES[tour]: continue
            for c in g.get("competitions", []):
                if c["id"] in seen: continue
                seen.add(c["id"])
                rname = c.get("round", {}).get("displayName", "")
                if rname.startswith("Qualifying") or rname not in ROUND: continue
                comp = sorted(c.get("competitors", []), key=lambda x: x.get("order", 0))
                if len(comp) != 2: continue
                names = [(x.get("athlete") or {}).get("displayName") for x in comp]
                out.append(dict(id=c["id"], dt=pd.Timestamp(c["date"]), tour=e["name"], city=city, major=bool(e.get("major")),
                                rnd=ROUND[rname], status=c["status"]["type"]["name"], names=names,
                                winner=[bool(x.get("winner")) for x in comp],
                                games=[sum(ls.get("value", 0) or 0 for ls in x.get("linescores", [])) for x in comp]))


def espn_matches(today, since, tour="atp"):
    """Tous les simples messieurs (tableau principal) des tournois actifs entre `since` et aujourd'hui + 7 jours."""
    seen, out = set(), []
    d = since
    while d <= today + timedelta(days=7):
        parse_events(fetch_day(d, tour), tour, seen, out)
        d += timedelta(days=3)          # un appel renvoie tout le tournoi en cours : un jour sur trois suffit
    return out


def espn_tours(today, weeks=5, tour="atp"):
    """Tournois ATP connus d'ESPN pour les prochaines semaines (nom, dates, ville, surface, Grand Chelem)."""
    tours = {}
    for k in range(weeks + 1):
        d = today + timedelta(days=7 * k)
        for e in fetch_day(d, tour).get("events", []):
            city = ((e.get("venue") or {}).get("displayName") or "").split(",")[0].strip()
            start = pd.Timestamp(e["date"]).tz_convert("America/New_York").date()
            end = (pd.Timestamp(e["endDate"]) - timedelta(hours=6)).tz_convert("America/New_York").date()
            tours[e["name"]] = dict(name=e["name"], start=str(start), end=str(end), city=city,
                                    surface=surface(city, start.month), major=bool(e.get("major")))
    return sorted(tours.values(), key=lambda x: x["start"]), str((today + timedelta(days=7 * weeks)).date())


def update(hist_path, tool_path, out_dir, today, tour="atp"):
    H = pd.read_csv(hist_path)
    tool = json.load(open(tool_path))
    # ---- correspondance des noms ESPN → noms de l'historique
    from collections import Counter
    index, freq = {}, Counter(pd.concat([H.Winner, H.Loser]))
    for n in freq:
        for k in keys_td(n): index.setdefault(k, set()).add(n)
    def map_name(full):
        if tour == "wta": return str(full)           # WTA : historique construit depuis ESPN, noms complets
        for k in keys_full(full):
            if k in index:                       # plusieurs graphies possibles : on garde la plus fréquente
                return max(index[k], key=lambda x: freq[x])
        t = str(full).split()
        return f"{t[-1]} {t[0][0]}." if len(t) > 1 else str(full)
    last_td = H.loc[H.src == "td", "Date"].max() if (H.src == "td").any() else "0000"
    last_any = pd.Timestamp(H.Date.max())
    since = max(last_any - timedelta(days=10), today - timedelta(days=40))
    M = espn_matches(today, since, tour)
    have = set(H.src)
    rank = {}
    for r in H[["Date", "Winner", "Loser", "WRank", "LRank"]].itertuples():
        if r.WRank == r.WRank: rank[r.Winner] = r.WRank
        if r.LRank == r.LRank: rank[r.Loser] = r.LRank
    new, upcoming, draws = [], [], {}
    for m in M:
        n1, n2 = map_name(m["names"][0]), map_name(m["names"][1])
        dr = draws.setdefault(m["tour"], dict(tour=m["tour"], city=m["city"], players=set(), out=set(), pending=0))
        for raw, nm in zip(m["names"], (n1, n2)):
            if raw and raw != "TBD": dr["players"].add(nm)
        if m["status"] in ("STATUS_FINAL", "STATUS_RETIRED", "STATUS_WALKOVER") and any(m["winner"]):
            dr["out"].add(n2 if m["winner"][0] else n1)
        elif m["status"] not in ("STATUS_FINAL", "STATUS_RETIRED", "STATUS_WALKOVER"):
            dr["pending"] += 1
        surf = surface(m["city"], m["dt"].month)
        st = m["status"]
        if st in ("STATUS_FINAL", "STATUS_RETIRED", "STATUS_WALKOVER") and any(m["winner"]):
            if f"espn:{m['id']}" in have or str(m["dt"].date()) <= last_td: continue
            w = 0 if m["winner"][0] else 1
            W, L = (n1, n2) if w == 0 else (n2, n1)
            new.append(dict(Date=str(m["dt"].date()), Tournament=m["tour"], rnd=m["rnd"], Surface=surf, bo5=int(m["major"]),
                            Winner=W, Loser=L, WRank=rank.get(W, np.nan), LRank=rank.get(L, np.nan),
                            Comment={"STATUS_FINAL": "Completed", "STATUS_RETIRED": "Retired", "STATUS_WALKOVER": "Walkover"}[st],
                            gw=m["games"][w] or np.nan, gl=m["games"][1 - w] or np.nan, src=f"espn:{m['id']}"))
        elif st == "STATUS_SCHEDULED" and all(x and x != "TBD" for x in m["names"]) and m["dt"] >= today.tz_localize("UTC") - timedelta(hours=3):
            upcoming.append(dict(dt=m["dt"].isoformat(), tour=m["tour"], city=m["city"], surface=surf, bo=5 if m["major"] else 3,
                                 round=ROUND_FR[m["rnd"]], p1=n1, p2=n2))
    if new:
        H = pd.concat([H, pd.DataFrame(new)], ignore_index=True).sort_values(["Date", "rnd"])
    H.to_csv(f"{out_dir}/{'tennis' if tour == 'atp' else 'wta'}_history.csv", index=False)
    # ---- recalcul des notes sur tout l'historique
    H["Date"] = pd.to_datetime(H.Date)
    K = lambda n: K_MUL * 250 / (n + 5) ** 0.4
    st_ = {}
    for r in H.itertuples():
        if r.Comment == "Walkover": continue
        w, l, s, d = r.Winner, r.Loser, r.Surface, r.Date
        sw = st_.setdefault(w, dict(e=1500., n=0, es={}, ns={}, g=1500., gs={}, last=None, hist=[], ret=0.))
        sl = st_.setdefault(l, dict(e=1500., n=0, es={}, ns={}, g=1500., gs={}, last=None, hist=[], ret=0.))
        if r.Comment == "Completed":
            pe = E(sw["e"], sl["e"]); kw, kl = K(sw["n"]), K(sl["n"])
            sw["e"] += kw * (1 - pe); sl["e"] -= kl * (1 - pe)
            a, b = sw["es"].get(s, 1500.), sl["es"].get(s, 1500.); pes = E(a, b)
            kws, kls = K(sw["ns"].get(s, 0)), K(sl["ns"].get(s, 0))
            sw["es"][s] = a + kws * (1 - pes); sl["es"][s] = b - kls * (1 - pes)
            if r.gw == r.gw and r.gl == r.gl and r.gw + r.gl > 0:
                share = r.gw / (r.gw + r.gl)
                pg = E(sw["g"], sl["g"]); sw["g"] += G_K * kw * (share - pg); sl["g"] -= G_K * kl * (share - pg)
                a, b = sw["gs"].get(s, 1500.), sl["gs"].get(s, 1500.); pgs = E(a, b)
                sw["gs"][s] = a + G_K * kws * (share - pgs); sl["gs"][s] = b - G_K * kls * (share - pgs)
            sw["n"] += 1; sl["n"] += 1
            sw["ns"][s] = sw["ns"].get(s, 0) + 1; sl["ns"][s] = sl["ns"].get(s, 0) + 1
        sw["ret"] = 0.; sl["ret"] = 1. if r.Comment == "Retired" else 0.
        for p in (sw, sl):
            p["last"] = d; p["hist"] = (p["hist"] + [d])[-8:]
    maxd = H.Date.max(); cut = maxd - pd.Timedelta(days=365)
    players = []
    for name, p in st_.items():
        if p["last"] is not None and p["last"] >= cut and p["n"] >= 15:
            rk = rank.get(name)
            players.append(dict(name=name, elo=round(p["e"], 1), hard=round(p["es"].get("Hard", 1500), 1), clay=round(p["es"].get("Clay", 1500), 1),
                                grass=round(p["es"].get("Grass", 1500), 1), g=round(p["g"], 1), gHard=round(p["gs"].get("Hard", 1500), 1),
                                gClay=round(p["gs"].get("Clay", 1500), 1), gGrass=round(p["gs"].get("Grass", 1500), 1),
                                rank=int(rk) if rk == rk and rk is not None else None, last=str(p["last"].date()),
                                hist=[str(x.date()) for x in p["hist"]], ret=p["ret"], n=p["n"]))
    players.sort(key=lambda p: -p["elo"])
    known = {p["name"] for p in players}
    for u in upcoming:
        u["k1"], u["k2"] = u["p1"] in known, u["p2"] in known
    upcoming.sort(key=lambda u: u["dt"])
    draw_list = [dict(tour=d["tour"], city=d["city"], players=sorted(d["players"] & known),
                      alive=sorted((d["players"] - d["out"]) & known), n=len(d["players"]))
                 for d in draws.values() if d["pending"] > 0]
    print(f"  tennis {tour.upper()} : {len(new)} nouveaux matchs ESPN, historique jusqu'au {maxd.date()}, {len(players)} joueurs, {len(upcoming)} matchs à venir")
    try:
        tours, until = espn_tours(today, tour=tour)
    except Exception as e:
        print("  calendrier ESPN indisponible :", repr(e)); tours, until = [], "0000"
    return dict(players=players, coef=tool["coef"], updated=str(maxd.date()), test=tool["test"], live=upcoming[:60], draws=draw_list,
                tours=tours, toursUntil=until)
