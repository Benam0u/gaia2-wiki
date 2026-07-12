#!/usr/bin/env python3
"""One-shot : embarque les polices Google Fonts en base64 dans assets/fonts.css.

Telecharge le CSS Google Fonts (UA moderne -> woff2 + unicode-range), garde les
sous-ensembles latin et latin-ext (suffisants pour le francais, y compris
oe/OE lies), telecharge chaque woff2 et remplace les url() par des data URI.

A relancer uniquement si les familles/graisses changent dans build_wiki.py.
Sortie : assets/fonts.css (committee), inlinee par build_wiki.py a la place
du CDN -> rendu identique 100% hors-ligne.
"""

import base64
import os
import re
import urllib.request

# Graisses reellement utilisees par le TEMPLATE (300/400/500 serif, 400/500/600 sans+mono).
CSS_URL = ("https://fonts.googleapis.com/css2"
           "?family=Fraunces:opsz,wght@9..144,300;9..144,400;9..144,500"
           "&family=Inter:wght@400;500;600"
           "&family=JetBrains+Mono:wght@400;500;600&display=swap")
# UA moderne : Google sert alors du woff2 decoupe par sous-ensembles unicode.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
KEEP_SUBSETS = ("latin", "latin-ext")
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts.css")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main():
    css = fetch(CSS_URL).decode("utf-8")
    # Blocs de la forme : /* subset */\n@font-face {...}
    blocks = re.findall(r"/\* ([a-z-]+) \*/\s*(@font-face \{[^}]+\})", css)
    kept, total = [], 0
    for subset, block in blocks:
        if subset not in KEEP_SUBSETS:
            continue
        m = re.search(r"url\((https://[^)]+\.woff2)\)", block)
        if not m:
            continue
        data = fetch(m.group(1))
        total += len(data)
        uri = "data:font/woff2;base64," + base64.b64encode(data).decode("ascii")
        kept.append("/* %s */\n%s" % (subset, block.replace(m.group(1), uri)))
    assert kept, "aucun bloc @font-face conserve - format Google change ?"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(kept) + "\n")
    print("%d blocs @font-face (%s), %d Ko de woff2 -> %s"
          % (len(kept), "+".join(KEEP_SUBSETS), total // 1024, os.path.relpath(OUT)))


if __name__ == "__main__":
    main()
