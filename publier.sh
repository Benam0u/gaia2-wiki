#!/usr/bin/env bash
# Build du wiki + publication :
#  - index.html                 -> servi par GitHub Pages (https://benam0u.github.io/gaia2-wiki/)
#  - OneDrive/Gaia2-wiki/       -> acces telephone hors-ligne via l'app OneDrive
# Le deploiement Pages part au commit+push (index.html est committe avec le reste).
set -e
cd "$(dirname "$0")"
python3 build_wiki.py
cp wiki.html index.html
cp wiki.html wiki_partage.html "/mnt/c/Users/benoi/OneDrive/Gaia2-wiki/"
echo "Publie : index.html (Pages au prochain push) + OneDrive/Gaia2-wiki/"
