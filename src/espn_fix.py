"""Calendrier de secours : matchs à venir des championnats pris sur ESPN, quand football-data n'a pas encore publié ses fixtures.
Les noms ESPN sont ramenés aux noms football-data de la saison en cours (une équipe ESPN = une équipe football-data, au mieux)."""
import difflib, gzip, json, re, unicodedata, urllib.request
import pandas as pd

SLUG = {"E0": "eng.1", "E1": "eng.2", "E2": "eng.3", "E3": "eng.4", "SP1": "esp.1", "SP2": "esp.2", "I1": "ita.1", "I2": "ita.2",
        "D1": "ger.1", "D2": "ger.2", "F1": "fra.1", "F2": "fra.2", "N1": "ned.1", "B1": "bel.1", "P1": "por.1",
        "SC0": "sco.1", "SC1": "sco.2", "T1": "tur.1", "G1": "gre.1"}
ALIAS = {"utd": "united", "nott'm": "nottingham", "nottm": "nottingham", "wolves": "wolverhampton", "weds": "wednesday",
         "ath": "atletico", "m'gladbach": "monchengladbach", "ein": "eintracht", "sp": "sporting", "inter": "internazionale",
         "psg": "paris saint germain", "sg": "saint germain", "qpr": "queens park rangers", "mk": "milton keynes",
         "st": "saint", "afc": "", "fc": "", "cf": "", "ac": "", "sc": "", "fk": "", "sk": ""}
FDNAME = {"La Coruna": "Deportivo La Coruna", "Sp Lisbon": "Sporting CP", "Sp Braga": "Braga", "Guimaraes": "Vitoria Guimaraes",
          "Espanol": "Espanyol", "Ath Bilbao": "Athletic Club", "Santander": "Racing Santander", "Man United": "Manchester United",
          "Man City": "Manchester City", "Sheffield Weds": "Sheffield Wednesday", "Sheffield United": "Sheffield United",
          "FC Koln": "Koln", "Paris SG": "Paris Saint Germain", "PSV Eindhoven": "PSV", "Nijmegen": "NEC", "For Sittard": "Fortuna Sittard"}
_cache = {}


def norm(s):
    s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().lower().replace("&", " ")
    s = re.sub(r"[^a-z0-9' ]", " ", s)
    return " ".join(w for w in (ALIAS.get(w, w) for w in s.split()) if w)


def score(fd, names):
    a = norm(FDNAME.get(fd, fd)); best = 0
    for n in names:
        b = norm(n)
        if not a or not b:
            continue
        r = difflib.SequenceMatcher(None, a, b).ratio()
        A, B = a.split(), b.split()
        hit = sum(1 for w in A if any(v == w or (len(w) >= 3 and len(v) >= 3 and (v.startswith(w) or w.startswith(v))) for v in B))
        best = max(best, r, hit / max(len(A), 1) * 0.9)
    return best


def board(slug, ymd):
    k = (slug, ymd)
    if k not in _cache:
        req = urllib.request.Request(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={ymd}",
                                     headers={"User-Agent": "pronos-weekly-update", "Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
        _cache[k] = json.loads(raw)
    return _cache[k]


def fixtures(div, teams, today, days=8):
    """[(Date, Time 'HH:MM' heure de Londres, Home, Away)] des matchs pas encore joués."""
    slug = SLUG.get(div)
    if not slug or not teams:
        return []
    evs = []
    for k in range(days):
        ymd = (today + pd.Timedelta(days=k)).strftime("%Y%m%d")
        try:
            evs += board(slug, ymd).get("events", [])
        except Exception as e:
            print("  ESPN indisponible", div, ymd, repr(e)); return []
    pairs, seen = [], set()
    for e in evs:
        if e.get("id") in seen:
            continue
        seen.add(e.get("id"))
        c = (e.get("competitions") or [{}])[0]
        if ((c.get("status") or e.get("status") or {}).get("type") or {}).get("state") != "pre":
            continue
        H = next((x for x in c.get("competitors", []) if x.get("homeAway") == "home"), None)
        A = next((x for x in c.get("competitors", []) if x.get("homeAway") == "away"), None)
        if not H or not A:
            continue
        nm = lambda t: [t.get("displayName", ""), t.get("shortDisplayName", ""), t.get("name", ""), t.get("location", "")]
        pairs.append((pd.Timestamp(e["date"]).tz_convert("Europe/London"), nm(H["team"]), nm(A["team"])))
    # chaque équipe ESPN ramenée à une équipe football-data (affectation gloutonne, du plus sûr au moins sûr)
    esp = {}
    for _, h, a in pairs:
        esp[h[0]] = h; esp[a[0]] = a
    cand = sorted(((score(t, ns), key, t) for key, ns in esp.items() for t in teams), reverse=True)
    m, used = {}, set()
    for s, key, t in cand:
        if s < 0.6 or key in m or t in used:
            continue
        m[key] = t; used.add(t)
    out = []
    for ts, h, a in pairs:
        if h[0] in m and a[0] in m:
            out.append((ts.tz_localize(None).normalize(), ts.strftime("%H:%M"), m[h[0]], m[a[0]]))
    return out
