#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generateur du wiki de campagne Gaia 2 (single-file, style board.html).

Scanne wiki/**/*.md (frontmatter YAML minimal + wikilinks [[...]]), resout les
liens en deux passes, calcule backlinks et liens morts, embarque les images en
data URI, et emet deux fichiers autonomes :
- wiki.html          : complet (usage perso)
- wiki_partage.html  : filtre (sans fiches `prive: true` ni blocs %%)

Python 3 stdlib uniquement. A relancer a chaque mise a jour du contenu :
    python3 build_wiki.py

Spec de reference : docs/2026-07-10-wiki-gaia2-spec.md
"""

import re
import unicodedata


# ===========================================================================
#  Normalisation, slugs, frontmatter
# ===========================================================================

def norm_key(s):
    """Cle de comparaison : sans accents, espaces reduits, casse repliee."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().casefold()


def slugify(s):
    """Slug ascii-kebab pour les noms de fichiers et les ids."""
    return re.sub(r"[^a-z0-9]+", "-", norm_key(s)).strip("-")


def _scalar(v):
    """Valeur scalaire de frontmatter : str, bool, ou liste inline."""
    v = v.strip()
    if v.startswith('"') and '"' in v[1:]:
        return v[1:v.index('"', 1)]
    v = re.split(r"\s+#", v, 1)[0].strip()
    if v in ("true", "false"):
        return v == "true"
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [x.strip() for x in inner.split(",") if x.strip()] if inner else []
    return v


def parse_frontmatter(text):
    """Retourne (meta, body). Supporte scalaires, listes inline, UNE map indentee."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw, body = text[4:end], text[end + 4:]
    body = body.lstrip("\n")
    meta, cur = {}, None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("  ") and cur is not None:
            k, _, v = line.strip().partition(":")
            meta[cur][k.strip()] = _scalar(v)
            continue
        cur = None
        k, _, v = line.partition(":")
        k = k.strip()
        if v.strip() == "":
            meta[k], cur = {}, k
        else:
            meta[k] = _scalar(v)
    return meta, body
