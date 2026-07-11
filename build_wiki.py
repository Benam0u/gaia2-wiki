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

import html
import re
import unicodedata
from pathlib import Path

# [[Nom]] ou [[Nom|texte affiche]]
WIKILINK = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]")
# Bloc prive %%...%% (non-greedy, multi-lignes)
PRIVATE_RE = re.compile(r"%%(.*?)%%", re.S)
# Premier H1 du corps (cle de resolution)
H1_RE = re.compile(r"^#\s+(.+)$", re.M)


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


# ===========================================================================
#  Convertisseur Markdown -> HTML (sous-ensemble porte de board.build_board)
# ===========================================================================

TASK_ICONS = {  # marqueur de checkbox -> (glyphe, classe css)
    " ": ("☐", "open"),
    "x": ("☑", "done"),
    "X": ("☑", "done"),
    "~": ("◐", "wip"),
    "!": ("⚠", "blocked"),
}


def inline(text, resolver=None, ctx=None):
    """Formatage inline : code, liens, gras, italique. Echappe le HTML.

    resolver/ctx sont branches en Task 4/5 (wikilinks, marqueur hypothese).
    """
    codes = []

    def stash(m):
        codes.append(m.group(1))
        return "\x00%d\x00" % (len(codes) - 1)

    text = re.sub(r"`([^`]+)`", stash, text)
    text = html.escape(text, quote=False)

    if resolver is not None:
        def _wl(m):
            name = m.group(1).strip()
            label = (m.group(2) or m.group(1)).strip()
            target = resolver.get(norm_key(name))
            if target:
                return '<a class="wl" href="#%s">%s</a>' % (target, label)
            return '<span class="deadlink" title="Fiche a creer">%s</span>' % label
        text = WIKILINK.sub(_wl, text)

    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: '<a href="%s" target="_blank" rel="noopener">%s</a>'
        % (html.escape(m.group(2), quote=True), m.group(1)),
        text,
    )
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\s][^*]*?)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"(?<![\w\\])_([^_]+)_(?![\w])", r"<em>\1</em>", text)
    text = re.sub(
        r"\{\?:\s*([^}]+)\}",
        r'<span class="hyp"><span class="hyp-b">?</span> \1</span>',
        text,
    )

    def unstash(m):
        return "<code>%s</code>" % html.escape(codes[int(m.group(1))], quote=False)

    return re.sub(r"\x00(\d+)\x00", unstash, text)


def split_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def is_table_sep(s):
    s = s.strip()
    return bool(re.match(r"^\|?[\s:|-]+\|?$", s)) and "-" in s and "|" in s


def render_cell(text, resolver=None, ctx=None):
    """Cellule de tableau : un marqueur de statut en tete devient un glyphe colore."""
    m = re.match(r"^\[([ xX~!])\]\s*(.*)$", text)
    if m:
        glyph, state = TASK_ICONS[m.group(1)]
        inner = '<span class="g">%s</span>' % glyph
        if m.group(2):
            inner += " " + inline(m.group(2), resolver, ctx)
        return '<span class="st %s">%s</span>' % (state, inner)
    return inline(text, resolver, ctx)


def render_table(header, rows, resolver=None, ctx=None):
    head = "".join("<th>%s</th>" % inline(c, resolver, ctx) for c in header)
    body = ""
    for r in rows:
        body += "<tr>%s</tr>" % "".join(
            "<td>%s</td>" % render_cell(c, resolver, ctx) for c in r)
    return ('<div class="tablewrap"><table><thead><tr>%s</tr></thead>'
            "<tbody>%s</tbody></table></div>") % (head, body)


def parse_list_items(lines, start):
    """Collecte les items de liste contigus (+ lignes de continuation indentees)."""
    items = []
    i = start
    while i < len(lines):
        l = lines[i]
        if l.strip() == "":
            break
        m = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", l)
        if m:
            indent = len(m.group(1))
            ordered = bool(re.match(r"^\d+\.", m.group(2)))
            items.append([indent, ordered, m.group(3)])
            i += 1
        elif items and l[:1] in (" ", "\t"):
            items[-1][2] += " " + l.strip()
            i += 1
        else:
            break
    return items, i


def items_to_tree(items):
    root = []
    stack = [(-1, root)]
    for indent, ordered, text in items:
        node = {"ordered": ordered, "text": text, "children": []}
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            stack = [(-1, root)]
        stack[-1][1].append(node)
        stack.append((indent, node["children"]))
    return root


def render_tree(nodes, resolver=None, ctx=None):
    if not nodes:
        return ""
    ordered = nodes[0]["ordered"]
    is_tasks = (not ordered) and all(
        re.match(r"^\[([ xX~!])\]\s+", n["text"]) for n in nodes
    )
    tag = "ol" if ordered else "ul"
    cls = ' class="tasklist"' if is_tasks else ""
    parts = ["<%s%s>" % (tag, cls)]
    for nd in nodes:
        text = nd["text"]
        tm = re.match(r"^\[([ xX~!])\]\s+(.*)$", text)
        if tm:
            glyph, state = TASK_ICONS[tm.group(1)]
            li = '<li class="task %s"><span class="cb">%s</span><div class="txt">%s</span>' % (
                state, glyph, inline(tm.group(2), resolver, ctx))
        else:
            li = "<li>%s" % inline(text, resolver, ctx)
        if nd["children"]:
            li += render_tree(nd["children"], resolver, ctx)
        if tm:
            li += "</div>"
        parts.append(li + "</li>")
    parts.append("</%s>" % tag)
    return "".join(parts)


def md_convert(md, resolver=None, ctx=None):
    """Convertit un corps markdown en HTML (point d'entree du convertisseur)."""
    lines = md.split("\n")
    out, para = [], []
    i, n = 0, len(lines)

    def flush_para():
        if para:
            out.append("<p>%s</p>" % "<br>".join(
                inline(x, resolver, ctx) for x in para))
            para.clear()

    while i < n:
        line = lines[i]
        s = line.strip()

        if s.startswith("```"):
            flush_para()
            i += 1
            code = []
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>%s</code></pre>"
                       % html.escape("\n".join(code), quote=False))
            continue

        if s == "":
            flush_para()
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush_para()
            lvl = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (lvl, inline(m.group(2), resolver, ctx), lvl))
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            flush_para()
            out.append("<hr>")
            i += 1
            continue

        if "|" in line and i + 1 < n and is_table_sep(lines[i + 1]):
            flush_para()
            header = split_row(line)
            i += 2
            rows = []
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append(split_row(lines[i]))
                i += 1
            out.append(render_table(header, rows, resolver, ctx))
            continue

        if s.startswith(">"):
            flush_para()
            quote = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>%s</blockquote>"
                       % md_convert("\n".join(quote), resolver, ctx))
            continue

        if re.match(r"^(\s*)([-*+]|\d+\.)\s+", line):
            flush_para()
            items, i = parse_list_items(lines, i)
            out.append(render_tree(items_to_tree(items), resolver, ctx))
            continue

        para.append(s)
        i += 1

    flush_para()
    return "\n".join(out)


# ===========================================================================
#  Chargement des fiches, resolution, backlinks
# ===========================================================================

def load_fiches(root):
    """Scanne root/**/*.md. Retourne une liste de dicts fiche (tries par chemin)."""
    root = Path(root)
    fiches = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        reldir = rel.parent.as_posix()
        if reldir == ".":
            reldir = ""
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        m = H1_RE.search(body)
        slug = path.stem
        title = m.group(1).strip() if m else slug
        fiches.append({
            "path": path,
            "reldir": reldir,
            "slug": slug,
            "title": title,
            "meta": meta,
            "body": body,
            "mtime": path.stat().st_mtime,
        })
    return fiches


def build_resolver(fiches):
    """Map norm_key(titre|alias) -> slug ; premier gagnant par ordre de slug.

    Retourne (resolver, conflicts) ou conflicts = [(cle, slug_garde, slug_ignore)].
    """
    claims = {}
    for f in fiches:
        keys = [f["title"]]
        alias = f["meta"].get("alias") or []
        if isinstance(alias, str):
            alias = [alias]
        keys += alias
        for k in keys:
            nk = norm_key(k)
            if not nk:
                continue
            claims.setdefault(nk, [])
            if f["slug"] not in claims[nk]:
                claims[nk].append(f["slug"])
    resolver, conflicts = {}, []
    for nk, slugs in claims.items():
        ordered = sorted(slugs)
        resolver[nk] = ordered[0]
        for ignored in ordered[1:]:
            conflicts.append((nk, ordered[0], ignored))
    return resolver, conflicts


def extract_private(body):
    """Remplace chaque bloc %%...%% par un token \\x02PRIVn\\x03.

    Retourne (body_tokenise, blocs, unbalanced). Si nombre de %% impair :
    (body inchange, [], True).
    """
    if body.count("%%") % 2 != 0:
        return body, [], True
    blocks = []

    def repl(m):
        blocks.append(m.group(1))
        return "\x02PRIV%d\x03" % (len(blocks) - 1)

    return PRIVATE_RE.sub(repl, body), blocks, False


def render_private(html_text, blocks, share, resolver=None, ctx=None):
    """Substitue les tokens PRIVn dans le HTML deja converti.

    share=True : les blocs disparaissent. Sinon : bloc sans saut de ligne ->
    span.prive (inline) ; bloc avec saut de ligne -> div.prive (md_convert).
    """
    def repl(m):
        idx = int(m.group(1))
        if idx >= len(blocks):
            return ""
        block = blocks[idx]
        if share:
            return ""
        if "\n" in block:
            return '<div class="prive">%s</div>' % md_convert(block, resolver, ctx)
        return '<span class="prive">%s</span>' % inline(block, resolver, ctx)

    return re.sub(r"\x02PRIV(\d+)\x03", repl, html_text)


def collect_links(fiches, resolver, include_private):
    """Retourne (links_out, backlinks, dead).

    links_out : {slug: set(slugs cibles)} ; backlinks : {slug: set(slugs sources)} ;
    dead : [(slug_source, nom brut)]. Si include_private est False : ignore les
    fiches prive comme sources et retire les blocs %% avant analyse.
    """
    links_out = {f["slug"]: set() for f in fiches}
    backlinks = {f["slug"]: set() for f in fiches}
    dead = []
    for f in fiches:
        if not include_private and f["meta"].get("prive"):
            continue
        body = f["body"]
        if not include_private:
            body = PRIVATE_RE.sub("", body)
        for m in WIKILINK.finditer(body):
            name = m.group(1).strip()
            target = resolver.get(norm_key(name))
            if target:
                links_out[f["slug"]].add(target)
                backlinks[target].add(f["slug"])
            else:
                dead.append((f["slug"], name))
    return links_out, backlinks, dead
