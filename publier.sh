#!/usr/bin/env bash
# Build du wiki + publication :
#  - OneDrive/Gaia2/       -> acces telephone via l'app OneDrive
#  - public/index.html     -> servi par l'hebergeur (Cloudflare Pages) si configure
# Penser a commit + git push apres une mise a jour (le deploiement suit le push).
set -e
cd "$(dirname "$0")"
python3 build_wiki.py
cp wiki.html wiki_partage.html "/mnt/c/Users/benoi/OneDrive/Gaia2/"
mkdir -p public
cp wiki.html public/index.html
echo "Publie : OneDrive/Gaia2/ + public/index.html (commit+push pour deployer)"
