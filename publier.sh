#!/usr/bin/env bash
# Build du wiki + copie vers OneDrive (accessible depuis le telephone via l'app OneDrive).
set -e
cd "$(dirname "$0")"
python3 build_wiki.py
cp wiki.html wiki_partage.html "/mnt/c/Users/benoi/OneDrive/Gaia2/"
echo "Publie dans OneDrive/Gaia2/ (sync auto vers le telephone)"
