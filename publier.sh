#!/usr/bin/env bash
# Build du wiki + publication :
#  - index.html                 -> servi par GitHub Pages (https://benam0u.github.io/gaia2-wiki/)
#  - OneDrive/Gaia2-wiki/       -> acces telephone hors-ligne via l'app OneDrive
# Le deploiement Pages part au commit+push (index.html est committe avec le reste).
set -e
cd "$(dirname "$0")"
# Garde-fou : repo public => refus bloquant si du contenu prive existe (voir scripts/guard_prive.sh)
scripts/guard_prive.sh wiki
python3 build_wiki.py
cp wiki.html index.html
# OneDrive = plan B hors-ligne OPTIONNEL : copie seulement si le dossier existe.
# Supprime, il ne revient pas ; pour reactiver : mkdir "/mnt/c/Users/benoi/OneDrive/Gaia2-wiki"
ONEDRIVE="/mnt/c/Users/benoi/OneDrive/Gaia2-wiki"
if [ -d "$ONEDRIVE" ]; then
  cp wiki.html wiki_partage.html "$ONEDRIVE/"
  echo "Publie : index.html (Pages au prochain push) + OneDrive/Gaia2-wiki/"
else
  echo "Publie : index.html (Pages au prochain push) - OneDrive absent, copie sautee"
fi
