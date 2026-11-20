"""Vérifie que chaque source a été mise à jour récemment (data/status.json, écrit par update_all.py).

Usage : python src/check_fresh.py <dossier> [heures, 48 par défaut]
Sort en erreur (le workflow devient rouge et GitHub envoie un e-mail) si une source n'a pas réussi depuis plus longtemps.
Une panne ponctuelle d'une source ne déclenche rien : seule une panne qui dure alerte.
"""
import json, os, sys
from datetime import datetime, timezone

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
MAX_H = float(sys.argv[2]) if len(sys.argv) > 2 else 48
p = f"{ROOT}/data/status.json"
if not os.path.exists(p):
    sys.exit(f"ERREUR : {p} introuvable (update_all.py n'a pas écrit l'état des sources)")
now = datetime.now(timezone.utc)
late = []
for k, v in sorted(json.load(open(p)).items()):
    h = (now - datetime.fromisoformat(v)).total_seconds() / 3600
    print(f"  {k:<12} dernière réussite il y a {h:5.1f} h")
    if h > MAX_H:
        late.append(f"{k} ({h:.0f} h)")
if late:
    print(f"::error title=Source bloquée::Pas de mise à jour depuis plus de {MAX_H:.0f} h : {', '.join(late)}")
    sys.exit(1)
print("Toutes les sources sont à jour.")
