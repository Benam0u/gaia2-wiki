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

import base64
import datetime
import html
import re
import unicodedata
from pathlib import Path

# Types de campagne : ordre de la nav + libelle des index.
NAV_TYPES = [
    ("personnages", "Personnages"), ("lieux", "Lieux"), ("factions", "Factions"),
    ("affaires", "Affaires"), ("objets", "Objets"), ("creatures", "Creatures"),
    ("concepts", "Concepts"), ("sessions", "Sessions"),
]
# Types dont on signale les orphelines dans le rapport.
CAMPAGNE_TYPES = {"personnages", "lieux", "factions", "affaires",
                  "objets", "creatures", "concepts"}
# Fiches speciales a la racine de wiki/ (consommees par accueil/chronologie).
SPECIAL_SLUGS = {"chronologie", "questions"}

TYPE_LABELS = {
    "personnages": "Personnage", "lieux": "Lieu", "factions": "Faction",
    "affaires": "Affaire", "objets": "Objet", "creatures": "Creature",
    "concepts": "Concept", "sessions": "Session", "systeme/races": "Race",
    "systeme/classes": "Classe", "": "Page",
}

MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp"}

# Ordre d'affichage + libelle des attributs de la fiche technique.
ATTR_ORDER = [
    ("force", "Force"), ("dexterite", "Dexterite"), ("empathie", "Empathie"),
    ("sagesse", "Sagesse"), ("intelligence", "Intelligence"),
]

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


# ===========================================================================
#  Images, infobox, badges, fiche technique
# ===========================================================================

def embed_img(path):
    """Data URI d'une image (mime par extension). "" si introuvable."""
    path = Path(path)
    if not path.is_file():
        return ""
    mime = MIME.get(path.suffix.lower(), "application/octet-stream")
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return "data:%s;base64,%s" % (mime, data)


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return 0


def render_badges(meta):
    """Badges de statut/etat. "" si confirme et sans etat."""
    out = []
    statut = meta.get("statut")
    if statut == "hypothese":
        out.append('<span class="st st-hyp">? HYPOTHESE</span>')
    elif statut == "fragment":
        out.append('<span class="st st-frag">~ FRAGMENT</span>')
    etat_labels = {
        "en-cours": ("st-encours", "EN COURS"),
        "resolu": ("st-resolu", "RESOLU"),
        "ferme": ("st-ferme", "FERME"),
    }
    etat = meta.get("etat")
    if etat in etat_labels:
        cls, lab = etat_labels[etat]
        out.append('<span class="st %s">%s</span>' % (cls, lab))
    return "".join(out)


def render_infobox(fiche, wiki_root, resolver=None):
    """Bloc infobox flottant : portrait + lignes cle/valeur. "" si rien a montrer."""
    meta = fiche["meta"]
    rows = []  # (label, valeur_html)
    rows.append(("Type", html.escape(TYPE_LABELS.get(fiche["reldir"], "Page"))))
    statut = meta.get("statut")
    if statut and statut != "confirme":
        rows.append(("Statut", html.escape(str(statut))))
    if meta.get("etat"):
        rows.append(("Etat", html.escape(str(meta["etat"]))))
    if meta.get("decouverte"):
        rows.append(("Decouverte", inline(str(meta["decouverte"]), resolver)))
    tags = meta.get("tags")
    if tags:
        if isinstance(tags, str):
            tags = [tags]
        rows.append(("Tags", html.escape(", ".join(str(t) for t in tags))))
    box = meta.get("infobox")
    if isinstance(box, dict):
        for k, v in box.items():
            rows.append((html.escape(str(k)), inline(str(v), resolver)))

    portrait = meta.get("portrait")
    img_html = ""
    if portrait:
        uri = embed_img(Path(wiki_root) / portrait)
        if uri:
            img_html = '<img src="%s" alt="%s">' % (
                uri, html.escape(str(fiche.get("title", ""))))
    if not rows and not img_html:
        return ""
    parts = ['<aside class="infobox">', img_html]
    for label, val in rows:
        parts.append('<div class="k">%s</div><div class="v">%s</div>' % (label, val))
    parts.append("</aside>")
    return "".join(parts)


def render_fusion_warning(meta, resolver):
    """Avertissement anti-fusion (affaires). "" si non present."""
    names = meta.get("ne-pas-fusionner")
    if not names:
        return ""
    if isinstance(names, str):
        names = [names]
    links = ", ".join(inline("[[%s]]" % n, resolver) for n in names)
    return ('<div class="warn-fusion">Ne pas fusionner avec %s '
            "sans preuve en seance.</div>") % links


def render_fiche_technique(profile, wiki_root):
    """Rendu de data/zogzork_profile.json (attributs, PV/PF, degats, RD, etc.).

    Les champs bonusRace / abilities / descriptions viennent de l'outil de fiche
    de Benoit : HTML de confiance insere sans echappement. Les valeurs libres
    (attributs, notes, competences) sont echappees.
    """
    sheet = profile.get("sheet", {})
    out = ['<div class="fiche-tech">']

    # Identite
    out.append("<h3>%s</h3>" % html.escape(str(sheet.get("name", ""))))
    parts = []
    if sheet.get("level"):
        parts.append("Niveau %s" % sheet["level"])
    for key in ("race", "classe", "alignement"):
        if sheet.get(key):
            parts.append(str(sheet[key]))
    if parts:
        out.append('<p class="tech-ident">%s</p>'
                   % " &middot; ".join(html.escape(p) for p in parts))

    # Attributs
    attrs = sheet.get("attributes", {}) or {}
    bonuses = sheet.get("attributeBonuses", {}) or {}
    arows = []
    for key, label in ATTR_ORDER:
        if key in attrs:
            val = html.escape(str(attrs[key]))
            bonus = html.escape(str(bonuses.get(key, "")))
            cell = "%s (D%s) %s" % (val, val, bonus)
            arows.append("<tr><td>%s</td><td>%s</td></tr>" % (label, cell.strip()))
    if arows:
        out.append('<h4>Attributs</h4><div class="tablewrap"><table><thead><tr>'
                   "<th>Attribut</th><th>Valeur</th></tr></thead><tbody>%s"
                   "</tbody></table></div>" % "".join(arows))

    # Vitaux
    vit = sheet.get("vitals", {}) or {}
    vparts = []
    if vit.get("pvMax"):
        vparts.append("PV %s" % html.escape(str(vit["pvMax"])))
    if vit.get("pfMax"):
        vparts.append("PF %s" % html.escape(str(vit["pfMax"])))
    if vparts:
        out.append('<p class="tech-vitals">%s</p>' % " &middot; ".join(vparts))

    # Degats
    dmg = sheet.get("damageEntries", []) or []
    if dmg:
        items = []
        for d in dmg:
            expr = "%sd%s" % (d.get("diceCount", ""), d.get("diceType", ""))
            bonus = str(d.get("bonus", "")).strip()
            if bonus and bonus not in ("0",):
                expr += "+%s" % bonus
            label = str(d.get("label", "")).strip()
            items.append("<li>%s</li>" % html.escape(
                ("%s %s" % (expr, label)).strip()))
        out.append("<h4>Degats</h4><ul>%s</ul>" % "".join(items))

    # Reduction de degats
    rd = sheet.get("rdEntries", []) or []
    if rd:
        items, total, base = [], 0, 0
        for e in rd:
            v = _int(e.get("value"))
            total += v
            cond = bool(e.get("conditional"))
            if not cond:
                base += v
            label = html.escape(str(e.get("label", "")).strip())
            suffix = " (conditionnel)" if cond else ""
            items.append("<li>%s : %d%s</li>" % (label, v, suffix))
        out.append("<h4>Reduction de degats</h4><ul>%s</ul>"
                   "<p>RD max %d (base %d)</p>" % ("".join(items), total, base))

    # Competences
    skills = sheet.get("skills", []) or []
    if skills:
        srows = ""
        for s in skills:
            srows += "<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                html.escape(str(s.get("name", ""))),
                html.escape(str(s.get("attr", ""))),
                html.escape(str(s.get("bonus", ""))))
        out.append('<h4>Competences</h4><div class="tablewrap"><table><thead><tr>'
                   "<th>Nom</th><th>Attribut</th><th>Bonus</th></tr></thead>"
                   "<tbody>%s</tbody></table></div>" % srows)

    # Bonus de race (HTML de confiance)
    race_bonus = sheet.get("bonusRace", []) or []
    if race_bonus:
        out.append("<h4>Bonus de race</h4><ul>%s</ul>"
                   % "".join("<li>%s</li>" % b for b in race_bonus))

    # Capacites (HTML de confiance)
    abilities = sheet.get("abilities", []) or []
    if abilities:
        out.append("<h4>Capacites</h4><ul>%s</ul>"
                   % "".join("<li>%s</li>" % a for a in abilities))

    # Descriptions (HTML de confiance, meme outil)
    desc = sheet.get("descriptions", {}) or {}
    for label, txt in desc.items():
        if str(txt).strip():
            out.append("<h4>%s</h4><p>%s</p>" % (html.escape(str(label)), txt))

    # Notes (texte libre, echappe, pre-wrap)
    notes = str(sheet.get("notes", "")).strip()
    if notes:
        out.append('<h4>Notes</h4><div class="tech-notes">%s</div>'
                   % html.escape(notes))

    out.append("</div>")
    return "".join(out)


# ===========================================================================
#  Assemblage single-file : template, sections, pages generees
# ===========================================================================

def _strip_h1(body):
    """Retire le premier H1 d'un corps (pour les pages speciales embarquees)."""
    return re.sub(r"^#\s+.*(?:\n|$)", "", body, count=1)


def _session_num(fiche):
    m = re.search(r"(\d+)", fiche["slug"])
    return int(m.group(1)) if m else -1


def _attr(s):
    return html.escape(str(s), quote=True)


def render_body(fiche, resolver, share, profile, wiki_root, report):
    """Corps d'une fiche : blocs prives + directive fiche technique + markdown."""
    body = fiche["body"]
    tokbody, blocks, unbalanced = extract_private(body)
    if unbalanced:
        report["unbalanced"].append(fiche["slug"])
    tokbody = tokbody.replace("{{fiche_technique}}", "\x02TECH\x03")
    out = md_convert(tokbody, resolver)
    out = render_private(out, blocks, share, resolver)
    tech = render_fiche_technique(profile, wiki_root) if profile is not None else ""
    return out.replace("\x02TECH\x03", tech)


def render_backlinks(slug, backlinks, share, by_slug):
    srcs = sorted(backlinks.get(slug, ()))
    links = []
    for s in srcs:
        src = by_slug.get(s)
        if not src:
            continue
        if share and src["meta"].get("prive"):
            continue
        links.append('<a class="wl" href="#%s">%s</a>' % (s, html.escape(src["title"])))
    if not links:
        return ""
    return '<div class="backlinks">Mentionne dans : %s</div>' % ", ".join(links)


def render_section(f, resolver, backlinks, share, profile, wiki_root, by_slug, report):
    meta = f["meta"]
    alias = meta.get("alias") or []
    if isinstance(alias, str):
        alias = [alias]
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    attrs = (' data-title="%s" data-alias="%s" data-resume="%s"'
             ' data-tags="%s" data-type="%s"') % (
        _attr(f["title"]), _attr(", ".join(alias)), _attr(meta.get("resume", "")),
        _attr(", ".join(tags)), _attr(TYPE_LABELS.get(f["reldir"], "Page")))
    return ('<section class="page" id="p-%s"%s>'
            "<h1>%s%s</h1>%s%s%s%s</section>") % (
        f["slug"], attrs, html.escape(f["title"]), render_badges(meta),
        render_infobox(f, wiki_root, resolver),
        render_fusion_warning(meta, resolver),
        render_body(f, resolver, share, profile, wiki_root, report),
        render_backlinks(f["slug"], backlinks, share, by_slug))


def render_index(reldir, label, entity_fiches):
    rows = sorted((f for f in entity_fiches if f["reldir"] == reldir),
                  key=lambda f: norm_key(f["title"]))
    body = ""
    for f in rows:
        tags = f["meta"].get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        body += ('<tr><td><a class="wl" href="#%s">%s</a></td>'
                 "<td>%s</td><td>%s</td><td>%s</td></tr>") % (
            f["slug"], html.escape(f["title"]),
            html.escape(f["meta"].get("resume", "")),
            render_badges(f["meta"]), html.escape(", ".join(tags)))
    if not body:
        body = '<tr><td colspan="4" class="empty">Aucune fiche.</td></tr>'
    table = ('<div class="tablewrap"><table><thead><tr><th>Nom</th><th>Resume</th>'
             "<th>Statut</th><th>Tags</th></tr></thead><tbody>%s</tbody></table></div>") % body
    return '<section class="page" id="p-index-%s"><h1>%s</h1>%s</section>' % (
        reldir, html.escape(label), table)


def render_accueil(entity_fiches, by_slug, resolver, dead):
    ec = [f for f in entity_fiches
          if f["reldir"] == "affaires" and f["meta"].get("etat") == "en-cours"]
    questions = by_slug.get("questions")
    sessions = [f for f in entity_fiches if f["reldir"] == "sessions"]
    recent = sorted(entity_fiches, key=lambda f: f["mtime"], reverse=True)[:10]

    left = []
    if ec:
        left.append("<h2>Affaires en cours</h2><ul>")
        for f in ec:
            left.append('<li><a class="wl" href="#%s">%s</a> - %s</li>' % (
                f["slug"], html.escape(f["title"]),
                html.escape(f["meta"].get("resume", ""))))
        left.append("</ul>")
    if questions:
        left.append(md_convert(_strip_h1(questions["body"]), resolver))

    right = []
    if sessions:
        last = max(sessions, key=_session_num)
        right.append('<h2>Derniere session</h2><p><a class="wl" href="#%s">%s</a> - %s</p>' % (
            last["slug"], html.escape(last["title"]),
            html.escape(last["meta"].get("resume", ""))))
    if dead:
        grouped = {}
        for src, name in dead:
            grouped.setdefault(name, set()).add(src)
        right.append("<h2>Fiches a creer</h2><ul>")
        for name in sorted(grouped, key=norm_key):
            srcs = ", ".join(
                '<a class="wl" href="#%s">%s</a>' % (s, html.escape(by_slug[s]["title"]))
                for s in sorted(grouped[name]) if s in by_slug)
            right.append("<li><strong>%s</strong> - cite dans %s</li>"
                         % (html.escape(name), srcs))
        right.append("</ul>")
    if recent:
        right.append("<h2>Recemment modifiees</h2><ul>")
        for f in recent:
            right.append('<li><a class="wl" href="#%s">%s</a></li>' % (
                f["slug"], html.escape(f["title"])))
        right.append("</ul>")

    return ('<section class="page" id="p-accueil"><h1>Archives de ZogZork</h1>'
            '<div class="home-cols"><div>%s</div><div>%s</div></div></section>') % (
        "".join(left), "".join(right))


def render_chronologie(chrono, sessions, resolver):
    parts = ['<section class="page" id="p-chronologie"><h1>Chronologie</h1>']
    if chrono:
        parts.append(md_convert(_strip_h1(chrono["body"]), resolver))
    if sessions:
        parts.append("<h2>Sessions</h2><ul>")
        for f in sorted(sessions, key=_session_num):
            parts.append('<li><a class="wl" href="#%s">%s</a> - %s</li>' % (
                f["slug"], html.escape(f["title"]),
                html.escape(f["meta"].get("resume", ""))))
        parts.append("</ul>")
    parts.append("</section>")
    return "".join(parts)


def render_systeme(entity_fiches, wiki_root):
    races = sorted((f for f in entity_fiches if f["reldir"] == "systeme/races"),
                   key=lambda f: norm_key(f["title"]))
    classes = sorted((f for f in entity_fiches if f["reldir"] == "systeme/classes"),
                     key=lambda f: norm_key(f["title"]))
    tables = [f for f in entity_fiches if f["reldir"] == "systeme"]
    by = {f["slug"]: f for f in tables}

    def grid(items):
        cells = []
        for f in items:
            uri = ""
            if f["meta"].get("portrait"):
                uri = embed_img(Path(wiki_root) / f["meta"]["portrait"])
            img = "<img src='%s' alt=''>" % uri if uri else ""
            cells.append('<a href="#%s">%s%s</a>' % (
                f["slug"], img, html.escape(f["title"])))
        return '<div class="portrait-grid">%s</div>' % "".join(cells)

    parts = ['<section class="page" id="p-systeme"><h1>Systeme</h1>']
    if races:
        parts.append("<h2>Races</h2>" + grid(races))
    if classes:
        parts.append("<h2>Classes</h2>" + grid(classes))
    links = []
    if "competences" in by:
        links.append('<a class="wl" href="#competences">Table des competences</a>')
    if "avantages" in by:
        links.append('<a class="wl" href="#avantages">Avantages generaux</a>')
    if links:
        parts.append("<h2>References</h2><p>%s</p>" % " &middot; ".join(links))
    parts.append("</section>")
    return "".join(parts)


TEMPLATE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,400;9..144,500;9..144,600&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0E0F11; --surface:#15171B; --surface-2:#1C1F25;
  --line:#2A2D34; --line-strong:#3A3E48;
  --text:#ECE7DA; --text-2:#9D968A; --text-3:#6A6660;
  --gold:#D4A85A; --rust:#E25C3D; --green:#6FAE96; --blue:#7E9CC8;
  --serif:'Fraunces','Times New Roman',serif;
  --sans:'Inter','Helvetica Neue',Arial,sans-serif;
  --mono:'JetBrains Mono','Menlo','Consolas',monospace;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--text);
  font-family:var(--sans);font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}

/* header : topbar + nav */
header{position:sticky;top:0;z-index:10;background:rgba(14,15,17,.92);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.topbar{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;
  padding:16px 40px 0;font-family:var(--mono);font-size:11px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--text-3)}
.topbar .brand b{color:var(--gold);font-weight:600;letter-spacing:.2em}
.topbar .meta span+span{margin-left:18px}
.topbar .meta b{color:var(--text);font-weight:500}
nav{display:flex;gap:2px;flex-wrap:wrap;align-items:center;padding:14px 40px 0}
nav button{background:transparent;border:none;border-bottom:2px solid transparent;color:var(--text-3);
  font-family:var(--mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;
  padding:10px 15px 12px;cursor:pointer}
nav button:hover{color:var(--text)}
nav button.active{color:var(--gold);border-bottom-color:var(--gold)}
nav button.nav-search{margin-left:auto;font-size:14px}

/* layout */
main{max-width:1040px;margin:0 auto;padding:44px 40px 90px}
.page{display:none}
.page.active{display:block;animation:fade .18s ease}
@keyframes fade{from{opacity:0}to{opacity:1}}

/* typographie */
h1,h2,h3{font-family:var(--serif);font-weight:400;letter-spacing:-0.01em;line-height:1.15}
.page h1{font-size:42px;font-weight:300;color:var(--text);margin:.1em 0 .55em}
.page h2{font-size:27px;margin:1.5em 0 .55em;padding-bottom:10px;border-bottom:1px solid var(--line)}
.page h1:first-child,.page h2:first-child{margin-top:0}
.page h3{font-size:20px;font-weight:500;color:#d8d2c4;margin:1.4em 0 .4em}
.page h4{font-family:var(--sans);font-size:12px;font-weight:600;letter-spacing:.16em;
  text-transform:uppercase;color:var(--text-2);margin:1.3em 0 .4em}
.page h5,.page h6{font-family:var(--mono);font-size:11px;letter-spacing:.12em;
  text-transform:uppercase;color:var(--text-3);margin:1.1em 0 .3em}
p{color:var(--text-2);max-width:76ch;margin:.7em 0}
strong{color:var(--text);font-weight:500}
em{font-style:italic;color:var(--text)}
a{color:var(--gold);text-decoration:none}
a:hover{text-decoration:underline}
hr{border:none;border-top:1px solid var(--line);margin:2em 0}

/* code */
code{font-family:var(--mono);font-size:12.5px;background:var(--surface-2);color:#e3bd7d;
  padding:2px 6px;border-radius:3px}
pre{background:var(--surface);border:1px solid var(--line);border-left:2px solid var(--gold);
  padding:15px 18px;overflow:auto;margin:1.1em 0}
pre code{background:none;padding:0;color:#cfc9bb;font-size:12.5px;line-height:1.7}

/* citations / callouts */
blockquote{margin:1.2em 0;padding:2px 0 2px 18px;border-left:2px solid var(--rust);color:var(--text-2)}
blockquote p{margin:.3em 0;color:var(--text-2)}
blockquote strong{color:var(--text)}

/* listes */
ul,ol{padding-left:1.4em;margin:.6em 0;color:var(--text-2)}
li{margin:.28em 0}
ul.tasklist{list-style:none;padding-left:.1em}
ul.tasklist li.task{display:flex;gap:10px;align-items:flex-start;
  font-family:var(--mono);font-size:13px;letter-spacing:.01em}
li.task .cb{flex:none;font-size:14px;line-height:1.55}
li.task .txt{flex:1;min-width:0}
li.task.open .cb{color:var(--text-3)}    li.task.open{color:var(--text-2)}
li.task.done .cb{color:var(--green)}      li.task.done{color:var(--text-3)}
li.task.wip .cb{color:var(--gold)}        li.task.wip{color:var(--text)}
li.task.blocked .cb{color:var(--rust)}    li.task.blocked{color:#e0a99a}

/* tableaux */
.tablewrap{overflow-x:auto;margin:1.3em 0}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th{text-align:left;font-family:var(--mono);font-size:10px;letter-spacing:.2em;text-transform:uppercase;
  color:var(--text-3);border-bottom:1px solid var(--line-strong);padding:13px 12px;font-weight:500}
td{border-bottom:1px solid var(--line);padding:13px 12px;color:var(--text-2);vertical-align:top}
td strong{color:var(--text)}
tbody tr:hover td{background:rgba(212,168,90,.05)}
td.empty{color:var(--text-3);font-style:italic}

/* --- extensions wiki --------------------------------------------------- */
.infobox{float:right;width:280px;margin:0 0 18px 26px;background:var(--surface);
  border:1px solid var(--line);border-left:2px solid var(--gold);padding:16px 18px;font-size:13px}
.infobox img{max-width:100%;margin-bottom:10px}
.infobox .k{font-family:var(--mono);font-size:10px;text-transform:uppercase;
  letter-spacing:.16em;color:var(--text-3);margin-top:8px}
.infobox .v{color:var(--text-2)}
.st{font-family:var(--mono);font-size:10px;letter-spacing:.14em;padding:2px 7px;
  border:1px solid var(--line-strong);margin-left:10px;vertical-align:middle}
.st-hyp{color:var(--gold)}.st-frag{color:var(--text-3)}.st-encours{color:var(--gold)}
.st-resolu{color:var(--green)}.st-ferme{color:var(--text-3)}
a.wl{color:var(--gold);text-decoration:none;border-bottom:1px solid rgba(212,168,90,.35)}
a.wl:hover{border-bottom-color:var(--gold)}
.deadlink{color:var(--rust);border-bottom:1px dotted var(--rust);cursor:help}
.prive{background:var(--surface-2);border-left:2px solid var(--text-3);padding:2px 6px}
div.prive{padding:10px 14px;margin:12px 0}
.hyp{border-bottom:1px dashed var(--gold)}
.hyp-b{font-family:var(--mono);font-size:10px;color:var(--gold);border:1px solid var(--gold);padding:0 4px;margin-right:4px}
.warn-fusion{border:1px solid var(--rust);color:#e0a99a;padding:10px 14px;margin:14px 0;
  font-family:var(--mono);font-size:12px}
.backlinks{clear:both;margin-top:34px;padding-top:12px;border-top:1px solid var(--line);
  font-family:var(--mono);font-size:12px;color:var(--text-3)}
.backlinks a.wl{color:var(--text-2)}
.search-ov{display:none;position:fixed;inset:0;background:rgba(14,15,17,.7);z-index:50}
.search-ov.show{display:flex;align-items:flex-start;justify-content:center;padding-top:12vh}
.search-box{width:min(560px,90vw);background:var(--surface-2);border:1px solid var(--line-strong)}
.search-box input{width:100%;background:transparent;border:0;outline:0;color:var(--text);
  font:15px var(--sans);padding:14px 16px;border-bottom:1px solid var(--line)}
.search-box .res{max-height:50vh;overflow-y:auto}
.search-box .res a{display:block;padding:9px 16px;color:var(--text-2);text-decoration:none;font-size:13px}
.search-box .res a.sel,.search-box .res a:hover{background:rgba(212,168,90,.08);color:var(--text)}
.res .rtype{font-family:var(--mono);font-size:10px;color:var(--text-3);margin-left:8px}
.portrait-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:14px}
.portrait-grid a{text-align:center;color:var(--text-2);text-decoration:none;font-size:13px}
.portrait-grid img{width:100%;border:1px solid var(--line)}
.home-cols{display:grid;grid-template-columns:1fr 1fr;gap:28px}
.fiche-tech h4{margin-top:1.2em}
.tech-ident{font-family:var(--mono);color:var(--text-2)}
.tech-vitals{font-family:var(--mono);color:var(--text-2)}
.tech-notes{white-space:pre-wrap;font-family:var(--mono);font-size:12.5px;color:var(--text-2);
  background:var(--surface);border:1px solid var(--line);padding:12px 14px}
@media(max-width:680px){
  .topbar,nav{padding-left:22px;padding-right:22px}
  main{padding:28px 22px 72px}
  .page h1{font-size:32px}.page h2{font-size:23px}
  .home-cols{grid-template-columns:1fr}
  .infobox{float:none;width:auto;margin:0 0 18px}
}
</style>
</head>
<body>
<header>
  <div class="topbar">
    <div class="brand">&#9670; <b>GAIA 2 - ARCHIVES DE ZOGZORK</b></div>
    <div class="meta"><span>BUILD <b>__TIMESTAMP__</b></span><span>CTRL+K</span></div>
  </div>
  <nav>__NAV__</nav>
</header>
<main>
__SECTIONS__
</main>
<div class="search-ov" id="search-ov">
  <div class="search-box">
    <input id="search-input" type="text" placeholder="Rechercher une fiche..." autocomplete="off">
    <div class="res" id="search-res"></div>
  </div>
</div>
<script>
function show(slug){
  var id='p-'+slug;
  document.querySelectorAll('.page').forEach(function(p){p.classList.toggle('active',p.id===id);});
  document.querySelectorAll('nav button[data-target]').forEach(function(b){
    b.classList.toggle('active',b.dataset.target===slug);});
  if(history.replaceState) history.replaceState(null,'','#'+slug);
  window.scrollTo(0,0);
  closeSearch();
}
function route(){
  var h=location.hash.replace('#','')||'accueil';
  if(document.getElementById('p-'+h)) show(h); else show('accueil');
}
window.addEventListener('hashchange',route);

var SEARCH=[];
document.querySelectorAll('.page[data-title]').forEach(function(p){
  SEARCH.push({id:p.id.replace(/^p-/,''),title:p.dataset.title||'',alias:p.dataset.alias||'',
    resume:p.dataset.resume||'',tags:p.dataset.tags||'',type:p.dataset.type||''});
});
var sov=document.getElementById('search-ov'),sin=document.getElementById('search-input'),
    sres=document.getElementById('search-res'),sel=-1;
function openSearch(){sov.classList.add('show');sin.value='';renderRes('');sin.focus();}
function closeSearch(){sov.classList.remove('show');}
function renderRes(q){
  q=q.trim().toLowerCase();sel=-1;
  var hits=!q?[]:SEARCH.filter(function(e){
    return (e.title+' '+e.alias+' '+e.resume+' '+e.tags).toLowerCase().indexOf(q)>=0;}).slice(0,20);
  sres.innerHTML=hits.map(function(e){
    return '<a href="#'+e.id+'">'+e.title+'<span class="rtype">'+e.type+'</span></a>';}).join('');
}
sin.addEventListener('input',function(){renderRes(sin.value);});
sov.addEventListener('click',function(e){if(e.target===sov)closeSearch();});
document.addEventListener('keydown',function(e){
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openSearch();return;}
  if(!sov.classList.contains('show'))return;
  var items=sres.querySelectorAll('a');
  if(e.key==='Escape'){closeSearch();}
  else if(e.key==='ArrowDown'){sel=Math.min(sel+1,items.length-1);mark(items);e.preventDefault();}
  else if(e.key==='ArrowUp'){sel=Math.max(sel-1,0);mark(items);e.preventDefault();}
  else if(e.key==='Enter'){var t=items[sel]||items[0];if(t){location.hash=t.getAttribute('href');closeSearch();}}
});
function mark(items){items.forEach(function(a,i){a.classList.toggle('sel',i===sel);});}
route();
</script>
</body>
</html>
"""


def _nav_button(slug, label):
    return '<button data-target="%s" onclick="show(\'%s\')">%s</button>' % (
        slug, slug, html.escape(label))


def build_html(fiches, resolver, conflicts, wiki_root, share, profile):
    """Assemble le HTML complet + un rapport partiel. Voir docstring du module."""
    wiki_root = Path(wiki_root)
    report = {"counts": {}, "dead": [], "conflicts": list(conflicts), "orphans": [],
              "unbalanced": [], "missing_images": [], "n_fiches": 0}

    visible = [f for f in fiches if not (share and f["meta"].get("prive"))]
    by_slug = {f["slug"]: f for f in visible}
    _, backlinks, dead = collect_links(fiches, resolver, include_private=not share)
    report["dead"] = dead

    entity_fiches = [f for f in visible
                     if not (f["reldir"] == "" and f["slug"] in SPECIAL_SLUGS)]
    report["n_fiches"] = len(entity_fiches)
    for f in entity_fiches:
        report["counts"][f["reldir"]] = report["counts"].get(f["reldir"], 0) + 1
        p = f["meta"].get("portrait")
        if p and not (wiki_root / p).is_file():
            report["missing_images"].append("%s -> %s" % (f["slug"], p))
        if f["reldir"] in CAMPAGNE_TYPES and not backlinks.get(f["slug"]):
            report["orphans"].append(f["slug"])

    sections = [render_section(f, resolver, backlinks, share, profile,
                               wiki_root, by_slug, report)
                for f in entity_fiches]

    chrono = by_slug.get("chronologie")
    sessions = [f for f in entity_fiches if f["reldir"] == "sessions"]
    sections.append(render_accueil(entity_fiches, by_slug, resolver, dead))
    for reldir, label in NAV_TYPES:
        sections.append(render_index(reldir, label, entity_fiches))
    sections.append(render_chronologie(chrono, sessions, resolver))
    sections.append(render_systeme(entity_fiches, wiki_root))

    nav = [_nav_button("accueil", "Accueil"), _nav_button("chronologie", "Chronologie")]
    nav += [_nav_button("index-" + r, l) for r, l in NAV_TYPES]
    nav.append(_nav_button("systeme", "Systeme"))
    nav.append('<button class="nav-search" onclick="openSearch()" '
               'title="Rechercher (Ctrl+K)">&#9906;</button>')

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    title = "Gaia 2 - Archives de ZogZork"
    out = (TEMPLATE
           .replace("__TITLE__", title)
           .replace("__TIMESTAMP__", stamp)
           .replace("__NAV__", "\n    ".join(nav))
           .replace("__SECTIONS__", "\n".join(sections)))
    return out, report
