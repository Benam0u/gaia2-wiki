#!/usr/bin/env bash
# Garde-fou confidentialite (2026-07-13) : tant que le repo gaia2-wiki est
# PUBLIC (necessaire a GitHub Pages gratuit), les sources wiki/ ET wiki.html
# complet sont lisibles par n'importe qui - l'URL Pages est devinable.
# Ce script REFUSE donc la publication si du contenu prive existe.
# Usage : guard_prive.sh [dossier_wiki]   (defaut : wiki)
set -e
WIKI_DIR="${1:-wiki}"
bad_prive=$(grep -rl '^prive: *true' "$WIKI_DIR" --include='*.md' 2>/dev/null || true)
bad_blocs=$(grep -rl '%%' "$WIKI_DIR" --include='*.md' 2>/dev/null || true)
if [ -n "$bad_prive$bad_blocs" ]; then
  {
    echo "PUBLICATION REFUSEE - contenu prive detecte alors que le repo est PUBLIC."
    echo
    echo "Le repo gaia2-wiki expose les sources ET wiki.html complet a quiconque"
    echo "devine l'URL. Le mecanisme prive/partage ne protege que wiki_partage.html,"
    echo "pas le repo. Fichiers en cause :"
    [ -n "$bad_prive" ] && echo "$bad_prive" | sed 's/^/  prive: true  -> /'
    [ -n "$bad_blocs" ] && echo "$bad_blocs" | sed 's/^/  bloc %%...%% -> /'
    echo
    echo "Solutions : retirer le contenu prive, OU (le jour du vrai besoin)"
    echo "spliter : repo PRIVE pour les sources + repo public servant uniquement"
    echo "wiki_partage.html. NB : un %% legitime (ex. dans un bloc de code)"
    echo "declenche aussi ce refus - le caractere est reserve."
  } >&2
  exit 1
fi
