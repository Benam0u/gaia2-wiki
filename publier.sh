#!/usr/bin/env bash
# Build du wiki + publication :
#  - OneDrive/Gaia2/                    -> acces telephone via l'app OneDrive (offline)
#  - public/index.html                  -> copie locale du rendu (committee dans le repo prive)
#  - .deploy/gaia2-wiki (repo public)   -> GitHub Pages : https://benam0u.github.io/gaia2-wiki/
# Penser a commit + git push du repo prive apres une mise a jour de contenu.
set -e
cd "$(dirname "$0")"
python3 build_wiki.py
cp wiki.html wiki_partage.html "/mnt/c/Users/benoi/OneDrive/Gaia2/"
mkdir -p public && cp wiki.html public/index.html

if [ ! -d .deploy/gaia2-wiki ]; then
  mkdir -p .deploy && git clone -q https://github.com/Benam0u/gaia2-wiki.git .deploy/gaia2-wiki
fi
cp wiki.html .deploy/gaia2-wiki/index.html
if ! git -C .deploy/gaia2-wiki diff --quiet; then
  git -C .deploy/gaia2-wiki commit -aqm "publish wiki"
  git -C .deploy/gaia2-wiki push -q
  echo "Deploye : https://benam0u.github.io/gaia2-wiki/ (en ligne sous ~1 min)"
else
  echo "Pages deja a jour."
fi
echo "Publie : OneDrive/Gaia2/ + public/index.html"
