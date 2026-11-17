"""Logos des équipes (foot et NBA) pour la page : data/logos.json = {nom dans les données: image en data URI}.

Usage : python src/logos.py <dossier> [<football-logos> <nba.json>]
  Sans option : complète data/logos.json avec ESPN pour les équipes qui n'ont pas encore de logo
  (lancé chaque jour par la mise à jour, après update_all.py : il lit out/foot_tool.json et out/nba_tool.json).
  <football-logos> : copie de github.com/luukhopman/football-logos (dossiers logos/ et history/), source principale
  <nba.json>       : {"Atlanta Hawks": "<svg…>", …} (paquet npm react-nba-logos rendu en SVG)
La page affiche les initiales quand une équipe n'a pas de logo.
"""
import base64, glob, html, io, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
REPO = sys.argv[2] if len(sys.argv) > 2 else None
NBA = sys.argv[3] if len(sys.argv) > 3 else None
DEST = f"{ROOT}/data/logos.json"

COUNTRY = {"Angleterre": "England", "France": "France", "Espagne": "Spain", "Italie": "Italy", "Allemagne": "Germany", "Pays-Bas": "Netherlands",
           "Belgique": "Belgium", "Portugal": "Portugal", "Écosse": "Scotland", "Turquie": "Türkiye", "Grèce": "Greece"}
# noms courts de football-data.co.uk → nom complet
ALIAS = {"man city": "manchester city", "man united": "manchester united", "nott m forest": "nottingham forest", "paris sg": "paris saint germain",
         "ath madrid": "atletico madrid", "ath bilbao": "athletic bilbao", "sociedad": "real sociedad", "betis": "real betis", "espanol": "espanyol",
         "vallecano": "rayo vallecano", "la coruna": "deportivo a coruna", "santander": "racing santander", "celta": "celta vigo",
         "ein frankfurt": "eintracht frankfurt", "m gladbach": "borussia monchengladbach", "fc koln": "1 fc koln", "leverkusen": "bayer leverkusen",
         "dortmund": "borussia dortmund", "inter": "inter milan", "internazionale": "inter milan", "milan": "ac milan", "for sittard": "fortuna sittard",
         "nijmegen": "nec nijmegen", "den haag": "ado den haag", "st gilloise": "union saint gilloise", "st truiden": "sint truidense",
         "waregem": "zulte waregem", "sp lisbon": "sporting cp", "sp braga": "sc braga", "guimaraes": "vitoria guimaraes", "standard": "standard liege",
         "bayern munich": "bayern munchen", "wolves": "wolverhampton wanderers", "sheffield weds": "sheffield wednesday",
         "qpr": "queens park rangers", "west brom": "west bromwich albion", "hertha": "hertha bsc", "greuther furth": "spvgg greuther furth",
         "st pauli": "fc st pauli", "olympiakos": "olympiacos", "paok": "paok thessaloniki", "lyon": "olympique lyon", "marseille": "olympique marseille",
         "rennes": "stade rennais", "brest": "stade brestois", "hamburg": "hamburger sv", "mainz": "mainz 05", "hearts": "heart of midlothian",
         "goztep": "goztepe", "buyuksehyr": "istanbul basaksehir", "aek": "aek athens", "fc cologne": "1 fc koln", "hertha berlin": "hertha bsc",
         "f c kobenhavn": "fc copenhagen", "agf": "aarhus gf", "st etienne": "saint etienne", "lask linz": "lask",
         "union st gilloise": "union saint gilloise", "amedspor": "amed sk", "sp gijon": "sporting gijon", "peterboro": "peterborough united",
         "bristol rvs": "bristol rovers", "raith rvs": "raith rovers", "inverness c": "inverness caledonian thistle", "milton keynes dons": "mk dons",
         "nurnberg": "1 fc nurnberg", "virtus entella": "entella"}
STOP = {"fc", "afc", "ac", "sc", "cf", "sco", "as", "rc", "ssc", "cfc", "fk", "sk", "bk", "sv", "vfb", "vfl", "tsg", "ud", "cd", "rcd", "sd", "ca", "ogc",
        "losc", "estac", "us", "club", "de", "da", "the", "1", "04", "05", "1846", "1899", "1907", "1909", "29", "kv", "krc", "kaa", "rsc", "royal"}
ESPN = {"E0": "eng.1", "E1": "eng.2", "E2": "eng.3", "E3": "eng.4", "SP1": "esp.1", "SP2": "esp.2", "I1": "ita.1", "I2": "ita.2", "D1": "ger.1",
        "D2": "ger.2", "F1": "fra.1", "F2": "fra.2", "N1": "ned.1", "B1": "bel.1", "P1": "por.1", "SC0": "sco.1", "SC1": "sco.2", "T1": "tur.1",
        "G1": "gre.1", "UCL": "uefa.champions", "UEL": "uefa.europa", "UECL": "uefa.europa.conf", "FAC": "eng.fa", "EFL": "eng.league_cup",
        "CDR": "esp.copa_del_rey", "CIT": "ita.coppa_italia", "DFB": "ger.dfb_pokal", "CDF": "fra.coupe_de_france", "KNVB": "ned.cup",
        "TDP": "por.taca.portugal", "SCC": "sco.tennents", "SLC": "sco.cis"}


def norm(s):
    s = s.translate(str.maketrans({"ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "ß": "ss", "ı": "i", "đ": "d", "ł": "l"}))
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s); s = re.sub(r"\s+", " ", s).strip()
    return ALIAS.get(s, s)


def toks(s):
    return [w for w in norm(s).split() if w not in STOP] or norm(s).split()


def score(a, b):
    """0 si les noms ne correspondent pas ; sinon plus c'est haut, plus c'est sûr (10 = identiques)."""
    A, B = toks(a), toks(b)
    if not A or not B: return 0
    if " ".join(A) == " ".join(B): return 10
    hit = lambda w, v: w == v or (min(len(w), len(v)) >= 4 and min(len(w), len(v)) / max(len(w), len(v)) >= 0.6 and (w.startswith(v) or v.startswith(w)))
    ca = sum(any(hit(w, v) for v in B) for w in A) / len(A)
    cb = sum(any(hit(v, w) for w in A) for v in B) / len(B)
    return 2 + ca + cb if (ca == 1 or (cb == 1 and ca >= 0.67)) else 0


def best(name, pool):
    """pool : [(nom, source)] → source du meilleur nom (à égalité : le premier, c'est-à-dire le plus récent)."""
    c = max(((score(name, n), -i, src) for i, (n, src) in enumerate(pool)), key=lambda x: (x[0], x[1]), default=None)
    return c[2] if c and c[0] >= 2 else None


def img_uri(data, h=72):
    from PIL import Image
    if data.lstrip()[:5] in (b"<?xml", b"<svg ") or b"<svg" in data[:400]:
        import cairosvg
        data = cairosvg.svg2png(bytestring=data, output_height=h * 2)
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    if im.getbbox(): im = im.crop(im.getbbox())
    w = max(1, round(im.width * h / im.height)); im = im.resize((w, h), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "WEBP", quality=82, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


UA = "PronostatLogos/1.0 (https://karlgabrielamani.github.io/pronostat/; karlgabrielamani@users.noreply.github.com)"


def get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()


def from_repo(foot, res, report):
    by_c = {}
    for d in [f"{REPO}/logos"] + sorted(glob.glob(f"{REPO}/history/*"), reverse=True):
        for lg in sorted(glob.glob(f"{d}/*")):
            lst = by_c.setdefault(os.path.basename(lg).split(" - ")[0], [])
            for f in sorted(glob.glob(f"{lg}/*.png")):
                n = os.path.splitext(os.path.basename(f))[0]
                if not any(x == n for x, _ in lst): lst.append((n, f))
    allf = [x for v in by_c.values() for x in v]
    for k in foot["order"]:
        L = foot["leagues"][k]
        pool = by_c.get(COUNTRY[L["country"]], []) if L["country"] in COUNTRY else allf
        for t in L["teams"]:
            if t["name"] in res: continue
            f = best(t["name"], pool)
            if f: res[t["name"]] = img_uri(open(f, "rb").read()); report.append(f"{k:5} {t['name']} -> {os.path.basename(f)}")


def from_espn(foot, res, report):
    """ESPN : listes d'équipes des championnats, et feuilles de match des coupes (petits clubs compris)."""
    try: get("https://a.espncdn.com/i/teamlogos/soccer/500/86.png", 10)
    except Exception as e:
        print("  logos ESPN non joignables :", repr(e)[:90]); return
    for k, slug in ESPN.items():
        L = foot["leagues"].get(k)
        miss = [t["name"] for t in (L or {}).get("teams", []) if t["name"] not in res]
        if not miss: continue
        pool = []
        try:
            for t in json.loads(get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/teams"))["sports"][0]["leagues"][0]["teams"]:
                if t["team"].get("logos"): pool.append((t["team"]["displayName"], t["team"]["logos"][0]["href"]))
        except Exception as e: print("  ESPN équipes", slug, repr(e)[:60])
        dates = {str(g.get("dt", ""))[:10].replace("-", "") for g in L.get("games", []) if isinstance(g, dict)}
        try:                                               # derniers tours joués (data/cups_history.csv) : les petits clubs y figurent
            import csv
            rows = [r for r in csv.DictReader(open(f"{ROOT}/data/cups_history.csv")) if r["cup"] == k and (r["home"] in miss or r["away"] in miss)]
            dates |= {r["dt"][:10].replace("-", "") for r in rows}
        except Exception: pass
        for d in sorted(dates - {""}, reverse=True)[:25]:
            try:
                for e in json.loads(get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={d}")).get("events", []):
                    for c in e["competitions"][0]["competitors"]:
                        if c["team"].get("logo"): pool.append((c["team"]["displayName"], c["team"]["logo"]))
            except Exception as e: print("  ESPN matchs", slug, d, repr(e)[:60])
        for n in miss:
            href = best(n, pool)
            if not href: continue
            try: res[n] = img_uri(get(href)); report.append(f"{k:5} {n} -> ESPN")
            except Exception as e: print("  logo", n, repr(e)[:60])


WIKI_LANG = {"France": ["fr", "en"], "Espagne": ["es", "en"]}
COUNTRY_EN = {"Angleterre": "England", "Espagne": "Spain", "France": "France", "Italie": "Italy", "Allemagne": "Germany", "Pays-Bas": "Netherlands",
              "Belgique": "Belgium", "Portugal": "Portugal", "Écosse": "Scotland", "Turquie": "Turkey", "Grèce": "Greece"}


def wiki_get(url):
    """Wikipédia limite le débit : petite pause, et on réessaie après une pause plus longue en cas de refus."""
    for wait in (0.3, 5, 15):
        time.sleep(wait)
        try: return get(url)
        except urllib.error.HTTPError as e:
            if e.code != 429: raise
    raise RuntimeError("Wikipédia : trop de requêtes")


def wiki_logo(name, country, lang):
    """Cherche l'article du club et renvoie l'image de son infobox (le blason), ou None."""
    q = f"{name} {'club de football' if lang == 'fr' else 'club de fútbol' if lang == 'es' else 'football club ' + COUNTRY_EN.get(country, '')}"
    page = wiki_get(f"https://{lang}.wikipedia.org/w/index.php?" + urllib.parse.urlencode({"search": q, "fulltext": 1, "ns0": 1})).decode("utf-8", "ignore")
    for href in re.findall(r'class="mw-search-result-heading"><a href="/wiki/([^"#]+)"', page)[:3]:
        title = urllib.parse.unquote(href).replace("_", " ")
        if score(name, re.sub(r"\s*\(.*?\)", "", title)) < 2: continue
        art = wiki_get(f"https://{lang}.wikipedia.org/wiki/{href}").decode("utf-8", "ignore")
        i = art.find('class="infobox'); box = art[i:i + 12000] if i >= 0 else ""
        if not re.search(r"(?i)(ground|stadium|stade|estadio|campo|terrain|home stadium)", box): continue   # un club, pas une ville
        for src in re.findall(r'<img[^>]+src="(//[^"]+)"', box):
            f = urllib.parse.unquote(src.split("?")[0].split("/")[-1])
            if re.search(r"(?i)(flag|drapeau|bandera|kit_|maillot|equipaci|_arm|_body|_shorts|_socks|pictogram|icon)", f): continue
            m = re.match(r"//(?:thumb|upload)\.wikimedia\.org/wikipedia/([a-z]+)/thumb/(\w)/(\w\w)/([^/]+)/", src) or re.match(r"//upload\.wikimedia\.org/wikipedia/([a-z]+)/(\w)/(\w\w)/([^/?]+)", src)
            if not m: continue
            return wiki_get(f"https://upload.wikimedia.org/wikipedia/{m.group(1)}/{m.group(2)}/{m.group(3)}/{m.group(4)}"), title
    return None


def from_wiki(foot, res, report, limit=150, budget=420, workers=2):
    """Wikipédia : blasons des petits clubs des matchs à venir qu'aucune autre source n'a (2 en parallèle, durée limitée)."""
    from concurrent.futures import ThreadPoolExecutor
    todo, seen = [], set()
    for k in foot["order"]:
        L = foot["leagues"][k]
        for g in L.get("games", []):
            for n in (g["home"], g["away"]):
                if n not in res and n not in seen: seen.add(n); todo.append((k, n, L["country"]))
    todo, t0 = todo[:limit], time.time()

    def one(job):
        k, n, country = job
        if time.time() - t0 > budget: return None
        for lang in WIKI_LANG.get(country, ["en"])[:1] + (["en"] if country not in WIKI_LANG else []):
            try:
                r = wiki_logo(n, country, lang)
                if r: return k, n, img_uri(r[0]), f"Wikipédia {lang} : {r[1]}"
            except Exception as e: print("  wiki", n, lang, repr(e)[:80], flush=True)
            break
        return None
    with ThreadPoolExecutor(workers) as ex:
        for i, r in enumerate(ex.map(one, todo), 1):
            if r: res[r[1]] = r[2]; report.append(f"{r[0]:5} {r[1]} -> {r[3]}")
            if i % 20 == 0: print(f"  wiki {i}/{len(todo)} · {len(report)} trouvés", flush=True)


def reserves(foot, res):
    """Équipes réserves (« Celta B », « Sociedad B ») : logo du club."""
    for k in foot["order"]:
        for t in foot["leagues"][k]["teams"]:
            n = t["name"]; m = re.match(r"(.+?)\s+(B|II)$", n)
            if n not in res and m and m.group(1) in res: res[n] = res[m.group(1)]


def basket(res, report, league="wnba"):
    """Logos des équipes WNBA (ESPN)."""
    try:
        for t in json.loads(get(f"https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/teams"))["sports"][0]["leagues"][0]["teams"]:
            n, lg = t["team"]["displayName"], t["team"].get("logos")
            if n not in res and lg: res[n] = img_uri(get(lg[0]["href"])); report.append(f"{league} {n} -> ESPN")
    except Exception as e: print("  logos", league, repr(e)[:80])


def euroleague(res, report):
    """Logos des clubs d'EuroLeague : blason officiel (out/euroleague_tool.json), sinon ESPN."""
    p = f"{ROOT}/out/euroleague_tool.json"
    if not os.path.exists(p): return
    teams = json.load(open(p))["teams"]; pool = []
    try:
        pool = [(t["team"]["displayName"], t["team"]["logos"][0]["href"]) for t in json.loads(get("https://site.api.espn.com/apis/site/v2/sports/basketball/euroleague/teams"))["sports"][0]["leagues"][0]["teams"] if t["team"].get("logos")]
    except Exception as e: print("  logos EuroLeague ESPN", repr(e)[:60])
    for t in teams:
        n = t["name"]
        if n in res: continue
        for src in ([t["crest"]] if t.get("crest") else []) + ([best(n, pool)] if best(n, pool) else []):
            try: res[n] = img_uri(get(src)); report.append(f"EuroLeague {n}"); break
            except Exception as e: print("  logo", n, repr(e)[:50])


def team_logos(foot, res, report):
    """Logos fournis avec les données (drapeaux des sélections nationales, ESPN)."""
    for k in foot["order"]:
        for t in foot["leagues"][k]["teams"]:
            if t["name"] not in res and t.get("logo"):
                try: res[t["name"]] = img_uri(get(t["logo"])); report.append(f"{k} {t['name']}")
                except Exception as e: print("  logo", t["name"], repr(e)[:50])


def update(foot):
    """Appelé par update_all.py avant de construire la page : complète data/logos.json (ESPN)."""
    res = json.load(open(DEST)) if os.path.exists(DEST) else {}
    report = []; team_logos(foot, res, report); basket(res, report); euroleague(res, report); from_espn(foot, res, report); from_wiki(foot, res, report, limit=40, budget=120); reserves(foot, res)
    json.dump(res, open(DEST, "w"), separators=(",", ":"), sort_keys=True)
    return report


def nba(teams, res):
    svgs = json.load(open(NBA))
    nalias = {"LA Clippers": "Los Angeles Clippers", "LA Lakers": "Los Angeles Lakers"}
    for n in teams:
        s = svgs.get(nalias.get(n, n))
        if s: res[n] = "data:image/svg+xml;base64," + base64.b64encode(s.replace('viewBox="0 0 150 150"', 'viewBox="20 20 110 110"').encode()).decode()


if __name__ == "__main__":
    emb = f"{ROOT}/work/data/embedded.json"
    if os.path.exists(emb): E = json.load(open(emb)); foot, nb = E["F"], E["N"]
    else: foot, nb = json.load(open(f"{ROOT}/out/foot_tool.json")), json.load(open(f"{ROOT}/out/nba_tool.json"))
    res = json.load(open(DEST)) if os.path.exists(DEST) else {}
    before, report = len(res), []
    if NBA: nba([t["name"] for t in nb["teams"]], res)
    if REPO: from_repo(foot, res, report)
    from_espn(foot, res, report)
    basket(res, report)
    euroleague(res, report)
    from_wiki(foot, res, report, budget=int(os.environ.get("WIKI_BUDGET", "420")))
    reserves(foot, res)
    os.makedirs(f"{ROOT}/data", exist_ok=True)
    json.dump(res, open(DEST, "w"), separators=(",", ":"), sort_keys=True)
    print("\n".join(report)); print(f"{len(res)} logos ({len(res) - before:+d}), {os.path.getsize(DEST) // 1024} Ko")
