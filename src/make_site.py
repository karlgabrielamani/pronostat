"""Transforme out/pronos.html en site autonome (index.html) et recopie les données mises à jour dans data/."""
import os, re, shutil, sys
ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
OUT = f"{ROOT}/out"
page = open(f"{OUT}/pronos.html", encoding="utf-8").read()
page = re.sub(r'<meta name="claude:[^>]*>\s*', "", page)
head = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Pronostics foot, tennis et NBA : probabilités, combinés et simulations de match.">
<meta name="theme-color" content="#D0202E">
<link rel="icon" href="icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="icon-180.png">
<link rel="manifest" href="manifest.json">
<style>html{-webkit-text-size-adjust:100%}body{margin:0;font-size:14px}img{max-width:100%}[hidden]{display:none!important}:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}</style>
</head>
<body>
"""
open(f"{ROOT}/index.html", "w", encoding="utf-8").write(head + page + "\n</body>\n</html>\n")
for name in ["tennis_history.csv", "tennis_tool.json", "wta_history.csv", "wta_tool.json", "cups_history.csv", "predictions_log.csv", "paper_bets.csv"]:
    src = f"{OUT}/{name}"
    if os.path.exists(src) and os.path.getsize(src) > 0:
        shutil.copy(src, f"{ROOT}/data/{name}")
print("Site écrit :", f"{ROOT}/index.html")
