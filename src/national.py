"""Équipes nationales : un modèle de Poisson (attaque / défense par sélection, avantage du terrain, matchs récents plus importants)
ajusté sur tous les matchs internationaux des 8 dernières années.

Données : github.com/martj42/international_results (tous les matchs depuis 1872, mis à jour chaque mois),
complétées par ESPN pour les résultats les plus récents et le calendrier à venir.
Test sur 2025-2026 (matchs jamais vus au réglage) : voir TEST.
"""
import difflib, json, os, urllib.request
import numpy as np
import pandas as pd

RESULTS = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={ym}&limit=500"
# compétitions affichées (code, nom, zone, slugs ESPN)
COMPS = [("UNL", "Ligue des nations", "Europe", ["uefa.nations"]),
         ("EUQ", "Qualifications Euro", "Europe", ["uefa.euroq"]),
         ("WCQ", "Qualifications Coupe du monde", "Monde", ["fifa.worldq.uefa", "fifa.worldq.conmebol", "fifa.worldq.concacaf", "fifa.worldq.afc", "fifa.worldq.caf"]),
         ("WC", "Coupe du monde", "Monde", ["fifa.world"]),
         ("EURO", "Euro", "Europe", ["uefa.euro"]),
         ("FRI", "Matchs amicaux", "Monde", ["fifa.friendly"])]
TEST = dict(n=0, acc=0.0)          # rempli par le test (voir __main__)
# noms ESPN → noms de la base des résultats
ALIAS = {"Türkiye": "Turkey", "Czechia": "Czech Republic", "USA": "United States", "Korea Republic": "South Korea", "South Korea": "South Korea",
         "Côte d'Ivoire": "Ivory Coast", "Cote d'Ivoire": "Ivory Coast", "Bosnia-Herzegovina": "Bosnia and Herzegovina", "IR Iran": "Iran",
         "Cabo Verde": "Cape Verde", "Congo DR": "DR Congo", "Republic of Ireland": "Republic of Ireland", "North Macedonia": "North Macedonia",
         "Chinese Taipei": "Taiwan", "China PR": "China PR", "Curacao": "Curaçao", "Kyrgyz Republic": "Kyrgyzstan", "Eswatini": "Eswatini"}
FR = {"France": "France", "Germany": "Allemagne", "Spain": "Espagne", "Italy": "Italie", "England": "Angleterre", "Portugal": "Portugal",
      "Netherlands": "Pays-Bas", "Belgium": "Belgique", "Switzerland": "Suisse", "Austria": "Autriche", "Croatia": "Croatie", "Denmark": "Danemark",
      "Sweden": "Suède", "Norway": "Norvège", "Finland": "Finlande", "Poland": "Pologne", "Czech Republic": "Tchéquie", "Slovakia": "Slovaquie",
      "Hungary": "Hongrie", "Romania": "Roumanie", "Bulgaria": "Bulgarie", "Greece": "Grèce", "Turkey": "Turquie", "Serbia": "Serbie",
      "Slovenia": "Slovénie", "Bosnia and Herzegovina": "Bosnie-Herzégovine", "Montenegro": "Monténégro", "Albania": "Albanie",
      "North Macedonia": "Macédoine du Nord", "Kosovo": "Kosovo", "Scotland": "Écosse", "Wales": "Pays de Galles", "Northern Ireland": "Irlande du Nord",
      "Republic of Ireland": "Irlande", "Iceland": "Islande", "Ukraine": "Ukraine", "Belarus": "Biélorussie", "Russia": "Russie",
      "Georgia": "Géorgie", "Armenia": "Arménie", "Azerbaijan": "Azerbaïdjan", "Kazakhstan": "Kazakhstan", "Israel": "Israël", "Cyprus": "Chypre",
      "Malta": "Malte", "Luxembourg": "Luxembourg", "Lithuania": "Lituanie", "Latvia": "Lettonie", "Estonia": "Estonie", "Moldova": "Moldavie",
      "Faroe Islands": "Îles Féroé", "Andorra": "Andorre", "San Marino": "Saint-Marin", "Liechtenstein": "Liechtenstein", "Gibraltar": "Gibraltar",
      "Brazil": "Brésil", "Argentina": "Argentine", "Uruguay": "Uruguay", "Colombia": "Colombie", "Chile": "Chili", "Peru": "Pérou",
      "Ecuador": "Équateur", "Paraguay": "Paraguay", "Bolivia": "Bolivie", "Venezuela": "Venezuela", "Mexico": "Mexique", "United States": "États-Unis",
      "Canada": "Canada", "Costa Rica": "Costa Rica", "Panama": "Panama", "Jamaica": "Jamaïque", "Honduras": "Honduras", "Morocco": "Maroc",
      "Algeria": "Algérie", "Tunisia": "Tunisie", "Egypt": "Égypte", "Senegal": "Sénégal", "Ivory Coast": "Côte d'Ivoire", "Cameroon": "Cameroun",
      "Nigeria": "Nigeria", "Ghana": "Ghana", "Mali": "Mali", "DR Congo": "RD Congo", "South Africa": "Afrique du Sud", "Cape Verde": "Cap-Vert",
      "Japan": "Japon", "South Korea": "Corée du Sud", "Australia": "Australie", "Iran": "Iran", "Saudi Arabia": "Arabie saoudite", "Qatar": "Qatar",
      "Iraq": "Irak", "Uzbekistan": "Ouzbékistan", "Jordan": "Jordanie", "United Arab Emirates": "Émirats arabes unis", "China PR": "Chine",
      "New Zealand": "Nouvelle-Zélande", "Haiti": "Haïti", "Curaçao": "Curaçao", "Suriname": "Suriname"}


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "pronostat-update"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()


def load_results(fetch, RAW, TODAY):
    d = pd.read_csv(fetch(RESULTS, f"{RAW}/international_results_{TODAY.date()}.csv", min_bytes=100000))
    d["date"] = pd.to_datetime(d.date, errors="coerce")
    d = d.dropna(subset=["date", "home_score", "away_score"])
    d["neutral"] = d.neutral.astype(str).str.upper().eq("TRUE")
    return d


def espn_month(slug, ym, RAW, cache):
    p = f"{RAW}/espn_nat_{slug}_{ym}.json"
    if cache and os.path.exists(p): return json.load(open(p))
    try: data = json.loads(get(ESPN.format(slug=slug, ym=ym)))
    except Exception: return {"events": []}
    if cache: json.dump(data, open(p, "w"))
    return data


def espn_events(months, RAW, TODAY):
    """[(code, slug, dt, home, away, hg, ag, done, neutral, logos)] pour les compétitions suivies."""
    out = []
    cur_ym = TODAY.strftime("%Y%m")
    for code, name, zone, slugs in COMPS:
        for slug in slugs:
            for ym in months:
                for e in espn_month(slug, ym, RAW, cache=ym < cur_ym).get("events", []):
                    c = e["competitions"][0]
                    H = next((x for x in c["competitors"] if x["homeAway"] == "home"), None); A = next((x for x in c["competitors"] if x["homeAway"] == "away"), None)
                    if not H or not A: continue
                    st = e["status"]["type"]
                    out.append(dict(code=code, dt=pd.Timestamp(e["date"]), home=H["team"]["displayName"], away=A["team"]["displayName"],
                                    hg=H.get("score"), ag=A.get("score"), done=st.get("completed", False), neutral=bool(c.get("neutralSite")),
                                    logo_h=H["team"].get("logo", ""), logo_a=A["team"].get("logo", ""), id=e["id"]))
    return pd.DataFrame(out)


def to_db(name, names):
    n = ALIAS.get(name, name)
    if n in names: return n
    m = difflib.get_close_matches(n, names, n=1, cutoff=0.86)
    return m[0] if m else n


def fit(d, TODAY, years=8):
    import cups
    d = d[(d.date >= TODAY - pd.Timedelta(days=365 * years)) & (d.date < TODAY)]
    return cups.fit(d.home_team.values, d.away_team.values, d.home_score.values, d.away_score.values,
                    (TODAY - d.date).dt.days.values, (~d.neutral).astype(float).values)


def update(fetch, RAW, TODAY):
    import cups
    d = load_results(fetch, RAW, TODAY)
    names = set(d.home_team) | set(d.away_team)
    last = d.date.max()
    months = sorted({(last + pd.Timedelta(days=k)).strftime("%Y%m") for k in range(0, (TODAY - last).days + 40, 10)} | {TODAY.strftime("%Y%m"), (TODAY + pd.Timedelta(days=20)).strftime("%Y%m")})
    E = espn_events(months, RAW, TODAY)
    if len(E):
        E["H"], E["A"] = [to_db(n, names) for n in E.home], [to_db(n, names) for n in E.away]
        new = E[E.done & (E.dt.dt.tz_convert(None) > last)].drop_duplicates("id")
        if len(new):
            d = pd.concat([d, pd.DataFrame(dict(date=new.dt.dt.tz_convert(None).dt.normalize(), home_team=new.H, away_team=new.A,
                                                home_score=pd.to_numeric(new.hg), away_score=pd.to_numeric(new.ag), tournament=new.code, neutral=new.neutral))], ignore_index=True)
    m = fit(d, TODAY)
    leagues = {}
    now = TODAY.tz_localize("UTC")
    for code, name, zone, slugs in COMPS:
        up = E[(E.code == code) & (~E.done) & (E.dt >= now - pd.Timedelta(hours=3)) & (E.dt < now + pd.Timedelta(days=21))].drop_duplicates("id") if len(E) else E
        if not len(up): continue
        logos, T, games = {}, {}, []
        for r in up.sort_values("dt").itertuples():
            hn, an = FR.get(r.H, r.H), FR.get(r.A, r.A)
            for disp, key, logo in ((hn, r.H, r.logo_h), (an, r.A, r.logo_a)):
                if disp not in T:
                    T[disp] = dict(name=disp, att=round(float(m["att"].get(key, -0.5)), 4), dfn=round(float(m["base"] - m["dfn"].get(key, -0.5)), 4),
                                   pts=0, p=0, w=0, d=0, l=0, gf=0, ga=0, form="", logo=logo)
            games.append(dict(dt=r.dt.tz_convert(None).strftime("%Y-%m-%dT%H:%M"), home=hn, away=an, neutral=bool(r.neutral)))
        leagues[code] = dict(name=name, country=zone, cup=True, nat=True, home=round(m["home"], 4), rho=0.0, teams=list(T.values()), games=games, last="")
        print(f"  sélections {code:4s} {len(T)} équipes, {len(games)} matchs à venir")
    return leagues


def backtest(fetch, RAW, TODAY, cut="2025-01-01"):
    """Réglage sur les matchs avant `cut`, test sur ceux d'après (compétitions officielles et amicaux)."""
    import cups
    d = load_results(fetch, RAW, TODAY)
    C = pd.Timestamp(cut)
    m = fit(d, C)
    t = d[(d.date >= C)]
    ok, n, ll = 0, 0, 0.0
    for r in t.itertuples():
        if r.home_team not in m["att"] or r.away_team not in m["att"]: continue
        ph, pd_, pa = cups.probs(m, r.home_team, r.away_team, neutral=r.neutral)
        res = 0 if r.home_score > r.away_score else 1 if r.home_score == r.away_score else 2
        pr = (ph, pd_, pa); ok += int(np.argmax(pr) == res); n += 1; ll -= np.log(max(pr[res], 1e-9))
    return dict(n=n, acc=round(ok / n, 3), logloss=round(ll / n, 3))
