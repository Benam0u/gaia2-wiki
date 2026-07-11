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
import json
import re
import sys
import time
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
# Chaque entree liste les cles possibles du JSON (l'export reel utilise les
# cles courtes dex/emp/sag/int ; les longues sont gardees par robustesse).
ATTR_ORDER = [
    (("force",), "Force"),
    (("dex", "dexterite"), "Dextérité"),
    (("emp", "empathie"), "Empathie"),
    (("sag", "sagesse"), "Sagesse"),
    (("int", "intelligence"), "Intelligence"),
]

# [[Nom]] ou [[Nom|texte affiche]]
WIKILINK = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]")
# Bloc prive %%...%% (non-greedy, multi-lignes)
PRIVATE_RE = re.compile(r"%%(.*?)%%", re.S)
# Fence ```...``` ou code inline `...` : masque les [[liens]] et %% qu'ils contiennent
CODE_SPAN_RE = re.compile(r"```.*?```|`[^`]+`", re.S)
# Premier H1 du corps (cle de resolution)
H1_RE = re.compile(r"^#\s+(.+)$", re.M)
# Slugs speciaux (pages generees) -> ancre reelle de la page qui les affiche.
SPECIAL_PAGE = {"questions": "accueil", "chronologie": "chronologie"}


class UnbalancedPrivateError(Exception):
    """Levee si une fiche a un nombre impair de %% : build fail-closed (exit 2)."""

    def __init__(self, slugs):
        self.slugs = list(slugs)
        super().__init__("Blocs prives non fermes : %s" % ", ".join(self.slugs))


def _unbalanced_private(body):
    """True si le nombre de %% (hors code) est impair."""
    return CODE_SPAN_RE.sub("", body).count("%%") % 2 != 0


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
            raw_label = m.group(2)
            label = (raw_label or m.group(1)).strip()          # deja echappe, pour l'affichage
            name = html.unescape(m.group(1)).strip()           # desechappe pour le lookup (& < >)
            target = resolver.get(norm_key(name))
            if target:
                if ctx and ctx.get("share") and target in ctx.get("private_targets", ()):
                    # Partage (spec §8) : le nom reste en texte simple, le lien saute
                    # (pas de lien mort : ne pas teaser l'existence de la fiche privee).
                    return '<span class="flat">%s</span>' % label
                return '<a class="wl" href="#%s">%s</a>' % (target, label)
            return '<span class="deadlink" title="Fiche a creer">%s</span>' % label
        text = WIKILINK.sub(_wl, text)

    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        # L'URL est deja html.escape-ee (& < >) ; on ne protege plus que les quotes.
        lambda m: '<a href="%s" target="_blank" rel="noopener">%s</a>'
        % (m.group(2).replace('"', "&quot;"), m.group(1)),
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
    # Protege les pipes internes de [[X|label]] et de `code|pipe` avant le decoupage.
    protect = []

    def _stash(m):
        protect.append(m.group(0))
        return "\x00T%d\x00" % (len(protect) - 1)

    s = re.sub(r"\[\[[^\]]*\]\]|`[^`]*`", _stash, line).strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]

    def _restore(cell):
        return re.sub(r"\x00T(\d+)\x00", lambda m: protect[int(m.group(1))], cell)

    return [_restore(c.strip()) for c in s.split("|")]


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
            li = '<li class="task %s"><span class="cb">%s</span><div class="txt">%s' % (
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
        if path.name.startswith("_"):
            continue  # gabarits (_template.md) : jamais rendus
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


def _claims(fiches, key_fn):
    """{norm_key -> [slugs]} pour les cles produites par key_fn(fiche)."""
    claims = {}
    for f in fiches:
        for k in key_fn(f):
            nk = norm_key(k)
            if not nk:
                continue
            claims.setdefault(nk, [])
            if f["slug"] not in claims[nk]:
                claims[nk].append(f["slug"])
    return claims


def _aliases(f):
    alias = f["meta"].get("alias") or []
    return [alias] if isinstance(alias, str) else alias


def build_resolver(fiches):
    """Map norm_key(titre|alias) -> slug. Precedence : titre H1 avant alias (spec §6).

    Deux passes : d'abord les titres, puis les alias uniquement sur les cles
    encore libres. Un alias qui heurte un titre = conflit signale, titre garde.
    Retourne (resolver, conflicts) ou conflicts = [(cle, slug_garde, slug_ignore)].
    """
    resolver, conflicts = {}, []
    for nk, slugs in _claims(fiches, lambda f: [f["title"]]).items():
        ordered = sorted(slugs)
        resolver[nk] = ordered[0]
        for ignored in ordered[1:]:
            conflicts.append((nk, ordered[0], ignored))
    for nk, slugs in _claims(fiches, _aliases).items():
        if nk in resolver:
            for ignored in sorted(slugs):
                if ignored != resolver[nk]:
                    conflicts.append((nk, resolver[nk], ignored))
            continue
        ordered = sorted(slugs)
        resolver[nk] = ordered[0]
        for ignored in ordered[1:]:
            conflicts.append((nk, ordered[0], ignored))
    return resolver, conflicts


def extract_private(body):
    """Remplace chaque bloc %%...%% par un token \\x02PRIVn\\x03.

    Les %% situes dans du code (fence ``` ou inline `...`) sont litteraux.
    Retourne (body_tokenise, blocs, unbalanced). Si nombre de %% (hors code)
    impair : (body inchange, [], True).
    """
    if _unbalanced_private(body):
        return body, [], True

    # Protege le code pour que ses %% ne soient pas pris pour des blocs prives.
    code = []

    def _stash_code(m):
        code.append(m.group(0))
        return "\x00C%d\x00" % (len(code) - 1)

    protected = CODE_SPAN_RE.sub(_stash_code, body)

    blocks = []

    def repl(m):
        blocks.append(m.group(1))
        return "\x02PRIV%d\x03" % (len(blocks) - 1)

    tokenized = PRIVATE_RE.sub(repl, protected)

    def _restore(text):
        return re.sub(r"\x00C(\d+)\x00", lambda m: code[int(m.group(1))], text)

    tokenized = _restore(tokenized)
    blocks = [_restore(b) for b in blocks]
    return tokenized, blocks, False


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
        body = CODE_SPAN_RE.sub(" ", f["body"])  # les [[liens]] en code ne comptent pas
        if not include_private:
            body = PRIVATE_RE.sub(" ", body)
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


# Registre des images du build en cours : chaque image n'est embarquee qu'UNE
# fois (dans __IMGDATA__) ; les <img class="pimg"> sont hydratees par JS.
IMG_REGISTRY = {}


def img_ref(wiki_root, relpath, alt=""):
    """Enregistre l'image et retourne un <img> hydrate au chargement. "" si introuvable."""
    uri = embed_img(Path(wiki_root) / relpath)
    if not uri:
        return ""
    key = str(relpath)
    IMG_REGISTRY[key] = uri
    return '<img class="pimg" data-img="%s" alt="%s">' % (
        html.escape(key), html.escape(alt))


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


def render_infobox(fiche, wiki_root, resolver=None, ctx=None):
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
        rows.append(("Decouverte", inline(str(meta["decouverte"]), resolver, ctx)))
    tags = meta.get("tags")
    if tags:
        if isinstance(tags, str):
            tags = [tags]
        rows.append(("Tags", html.escape(", ".join(str(t) for t in tags))))
    box = meta.get("infobox")
    if isinstance(box, dict):
        for k, v in box.items():
            rows.append((html.escape(str(k)), inline(str(v), resolver, ctx)))

    portrait = meta.get("portrait")
    img_html = ""
    if portrait:
        img_html = img_ref(wiki_root, portrait, alt=str(fiche.get("title", "")))
    if not rows and not img_html:
        return ""
    parts = ['<aside class="infobox">', img_html]
    for label, val in rows:
        parts.append('<div class="k">%s</div><div class="v">%s</div>' % (label, val))
    parts.append("</aside>")
    return "".join(parts)


def render_fusion_warning(meta, resolver, ctx=None):
    """Avertissement anti-fusion (affaires). "" si non present."""
    names = meta.get("ne-pas-fusionner")
    if not names:
        return ""
    if isinstance(names, str):
        names = [names]
    links = ", ".join(inline("[[%s]]" % n, resolver, ctx) for n in names)
    return ('<div class="warn-fusion">Ne pas fusionner avec %s '
            "sans preuve en seance.</div>") % links


def _die_expr(entry):
    """Formule de des "(D12+4)" depuis {diceCount, diceType, bonus} ('D12' ou '12')."""
    t = str(entry.get("diceType", "")).strip()
    if t[:1] in ("D", "d"):
        t = t[1:]
    n = _int(entry.get("diceCount")) or 1
    core = ("%dD%s" % (n, t)) if n > 1 else ("D%s" % t)
    b = _int(entry.get("bonus"))
    return "(%s+%d)" % (core, b) if b else "(%s)" % core


def _ft_box(label, value_html, cls=""):
    """Boite bordee facon fiche PDF : libelle centre au-dessus de la valeur."""
    cls = (" " + cls) if cls else ""
    return ('<div class="ft-box%s"><div class="ft-l">%s</div>'
            '<div class="ft-v">%s</div></div>'
            % (cls, html.escape(label), value_html))


def _ft_notes_html(notes):
    """Puces du bloc Notes : 1 ligne source = 1 item, '•' internes en separateurs."""
    items = []
    for line in notes.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        frags = [f.strip() for f in line.split("•") if f.strip()]
        items.append("<li>%s</li>" % '<span class="ft-sep">•</span>'.join(
            html.escape(f) for f in frags))
    return "<ul>%s</ul>" % "".join(items)


def render_fiche_technique(profile, wiki_root):
    """Rendu de data/zogzork_profile.json au layout de la fiche PDF officielle.

    Boites bordees : identite, attributs, PV/PF/alignement, notes, degats/RD,
    bonus de race, competences, avantages. bonusRace / abilities = HTML de
    confiance de l'outil de fiche (non echappe) ; tout le reste est echappe.
    Le narratif (descriptions) vit dans zogzork.md (spec section 5).
    """
    sheet = profile.get("sheet", {})
    out = ['<div class="fiche-tech">',
           '<div class="ft-title">Gaïa 2 - Fiche de personnage</div>']

    # Rang identite : Nom / Niveau / Race / Classe
    idboxes = [_ft_box("Nom du personnage", html.escape(str(sheet.get("name", ""))))]
    if sheet.get("level"):
        idboxes.append(_ft_box("Niveau", html.escape(str(sheet["level"]))))
    for key, label in (("race", "Race"), ("classe", "Classe")):
        if sheet.get(key):
            idboxes.append(_ft_box(label, html.escape(str(sheet[key]))))
    out.append('<div class="ft-row ft-id">%s</div>' % "".join(idboxes))

    # Zone principale : attributs | vitaux | notes
    attrs = sheet.get("attributes", {}) or {}
    bonuses = sheet.get("attributeBonuses", {}) or {}
    aboxes = []
    for keys, label in ATTR_ORDER:
        key = next((k for k in keys if k in attrs), None)
        if key is None:
            continue
        val = html.escape(str(attrs[key]))
        bonus = html.escape(str(bonuses.get(key, "")).strip())
        v = '%s <span class="ft-die">(D%s)</span>' % (val, val)
        if bonus:
            v += ' <span class="ft-bonus">%s</span>' % bonus
        aboxes.append(_ft_box(label, v))
    vit = sheet.get("vitals", {}) or {}
    vboxes = []
    if vit.get("pvMax"):
        vboxes.append(_ft_box("PV", html.escape(str(vit["pvMax"])), "ft-big"))
    if vit.get("pfMax"):
        vboxes.append(_ft_box("PF", html.escape(str(vit["pfMax"])), "ft-big"))
    if sheet.get("alignement"):
        vboxes.append(_ft_box("Alignement", html.escape(str(sheet["alignement"]))))
    notes = str(sheet.get("notes", "")).strip()
    nbox = (_ft_box("Notes - Quêtes - Équipements", _ft_notes_html(notes),
                    "ft-list") if notes else "")
    out.append('<div class="ft-main"><div class="ft-col">%s</div>'
               '<div class="ft-col">%s</div>%s</div>'
               % ("".join(aboxes), "".join(vboxes), nbox))

    # Combat : degats | reduction de degats
    cboxes = []
    dmg = sheet.get("damageEntries", []) or []
    if dmg:
        formula = " + ".join(_die_expr(d) for d in dmg)
        labels = " + ".join(str(d.get("label", "")).strip()
                            for d in dmg if str(d.get("label", "")).strip())
        v = html.escape(formula)
        if labels:
            v += '<div class="ft-sub">%s</div>' % html.escape(labels)
        cboxes.append(_ft_box("Dégâts", v))
    rd = sheet.get("rdEntries", []) or []
    if rd:
        total = sum(_int(e.get("value")) for e in rd)
        base = sum(_int(e.get("value")) for e in rd if not e.get("conditional"))
        detail = " • ".join(
            "%s %d%s" % (str(e.get("label", "")).strip(), _int(e.get("value")),
                         " (conditionnel)" if e.get("conditional") else "")
            for e in rd)
        v = "RD %d (%d)" % (total, base)
        v += '<div class="ft-sub">%s</div>' % html.escape(detail)
        cboxes.append(_ft_box("Réduction de dégâts", v))
    if cboxes:
        out.append('<div class="ft-row ft-combat">%s</div>' % "".join(cboxes))

    # Bonus de race | Competences
    duo = []
    race_bonus = sheet.get("bonusRace", []) or []
    if race_bonus:
        duo.append(_ft_box(
            "Bonus de race",
            "<ul>%s</ul>" % "".join("<li>%s</li>" % b for b in race_bonus),
            "ft-list"))
    skills = sheet.get("skills", []) or []
    if skills:
        srows = "".join(
            "<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                html.escape(str(s.get("name", ""))),
                html.escape(str(s.get("attr", ""))),
                html.escape(str(s.get("bonus", ""))))
            for s in skills)
        duo.append(_ft_box(
            "Compétences",
            '<div class="tablewrap"><table><thead><tr><th>Nom</th>'
            "<th>Attribut</th><th>Bonus</th></tr></thead>"
            "<tbody>%s</tbody></table></div>" % srows, "ft-list"))
    if duo:
        out.append('<div class="ft-row ft-duo">%s</div>' % "".join(duo))

    # Avantages / Capacites (pleine largeur, HTML de confiance)
    abilities = sheet.get("abilities", []) or []
    if abilities:
        out.append(_ft_box(
            "Avantages / Capacités",
            "<ul>%s</ul>" % "".join("<li>%s</li>" % a for a in abilities),
            "ft-list"))

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


def _dewrap_blocks(out, blocks):
    """Sort les tokens de niveau bloc (fiche technique, %% multi-lignes) de leur
    <p> pour eviter le <p><div>...</div></p> invalide apres substitution."""
    out = out.replace("<p>\x02TECH\x03</p>", "\x02TECH\x03")
    for i, b in enumerate(blocks):
        if "\n" in b:
            out = out.replace("<p>\x02PRIV%d\x03</p>" % i, "\x02PRIV%d\x03" % i)
    return out


def _render_markdown(body, resolver, share, ctx, tech_html=""):
    """Pipeline complet d'un corps : blocs prives + directive fiche technique +
    markdown. Partage par les fiches et par les pages speciales embarquees."""
    tokbody, blocks, _ = extract_private(body)
    tokbody = tokbody.replace("{{fiche_technique}}", "\x02TECH\x03")
    out = md_convert(tokbody, resolver, ctx)
    out = _dewrap_blocks(out, blocks)
    out = render_private(out, blocks, share, resolver, ctx)
    return out.replace("\x02TECH\x03", tech_html)


LEAD_H1_RE = re.compile(r"\A\s*#\s+[^\n]*\n?")


def render_body(fiche, resolver, share, profile, wiki_root, report, ctx=None):
    """Corps d'une fiche : blocs prives + directive fiche technique + markdown."""
    tech = render_fiche_technique(profile, wiki_root) if profile is not None else ""
    # Le H1 d'ouverture est la cle de resolution ; render_section affiche deja
    # le titre (avec badges) : on ne le rend pas une deuxieme fois.
    body = LEAD_H1_RE.sub("", fiche["body"], count=1)
    return _render_markdown(body, resolver, share, ctx, tech)


def render_backlinks(slug, backlinks, share, by_slug):
    srcs = sorted(backlinks.get(slug, ()))
    links = []
    for s in srcs:
        src = by_slug.get(s)
        if not src:
            continue
        if share and src["meta"].get("prive"):
            continue
        href = SPECIAL_PAGE.get(s, s)  # questions -> accueil, etc.
        links.append('<a class="wl" href="#%s">%s</a>' % (href, html.escape(src["title"])))
    if not links:
        return ""
    return '<div class="backlinks">Mentionne dans : %s</div>' % ", ".join(links)


def render_section(f, resolver, backlinks, share, profile, wiki_root, by_slug, report, ctx):
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
        render_infobox(f, wiki_root, resolver, ctx),
        render_fusion_warning(meta, resolver, ctx),
        render_body(f, resolver, share, profile, wiki_root, report, ctx),
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


def render_accueil(entity_fiches, by_slug, resolver, dead, ctx=None):
    share = bool(ctx and ctx.get("share"))
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
        left.append(_render_markdown(_strip_h1(questions["body"]), resolver, share, ctx))

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


def render_chronologie(chrono, sessions, resolver, ctx=None):
    share = bool(ctx and ctx.get("share"))
    parts = ['<section class="page" id="p-chronologie"><h1>Chronologie</h1>']
    if chrono:
        parts.append(_render_markdown(_strip_h1(chrono["body"]), resolver, share, ctx))
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
            img = ""
            if f["meta"].get("portrait"):
                img = img_ref(wiki_root, f["meta"]["portrait"])
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
.flat{color:var(--text-2)}
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
.fiche-tech{clear:both;margin-top:8px}
.ft-title{text-align:center;font-family:var(--mono);font-size:12px;font-weight:600;
  letter-spacing:.2em;text-transform:uppercase;color:var(--gold);
  border:1px solid var(--line-strong);padding:10px;margin-bottom:12px}
.ft-row{display:grid;gap:10px;margin-bottom:10px}
.ft-id{grid-template-columns:2fr 1fr 1fr 1fr}
.ft-main{display:grid;grid-template-columns:11fr 8fr 19fr;gap:10px;margin-bottom:10px}
.ft-col{display:flex;flex-direction:column;gap:10px}
.ft-col .ft-box{flex:1;display:flex;flex-direction:column;justify-content:center}
.ft-box{border:1px solid var(--line);background:var(--surface);padding:10px 14px;min-width:0}
.ft-l{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.16em;
  color:var(--text-3);text-align:center;margin-bottom:6px}
.ft-v{text-align:center;color:var(--text)}
.ft-big .ft-v{font-family:var(--serif);font-size:26px;font-weight:500}
.ft-die{color:var(--text-3);font-size:12px}
.ft-bonus{color:var(--gold);font-weight:600}
.ft-sub{color:var(--text-3);font-size:12px;margin-top:5px;line-height:1.5}
.ft-combat{grid-template-columns:1fr 1fr}
.ft-duo{grid-template-columns:1fr 1fr;align-items:start}
.ft-list .ft-v{text-align:left}
.ft-list ul{margin:0;padding-left:16px}
.ft-list li{margin:5px 0;color:var(--text-2);font-size:13.5px}
.ft-sep{color:var(--text-3);margin:0 7px}
.fiche-tech .tablewrap{margin:0}
.fiche-tech table{width:100%}
@media(max-width:680px){
  .topbar,nav{padding-left:22px;padding-right:22px}
  nav{flex-wrap:nowrap;overflow-x:auto}
  nav button{white-space:nowrap;padding:10px 10px 12px}
  nav button.nav-search{margin-left:0}
  main{padding:28px 22px 72px}
  .page h1{font-size:32px}.page h2{font-size:23px}
  .home-cols{grid-template-columns:1fr}
  .infobox{float:none;width:auto;margin:0 0 18px}
  .ft-id,.ft-main,.ft-combat,.ft-duo{grid-template-columns:1fr}
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
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function renderRes(q){
  q=q.trim().toLowerCase();sel=-1;
  var hits=!q?[]:SEARCH.filter(function(e){
    return (e.title+' '+e.alias+' '+e.resume+' '+e.tags).toLowerCase().indexOf(q)>=0;}).slice(0,20);
  sres.innerHTML=hits.map(function(e){
    return '<a href="#'+esc(e.id)+'">'+esc(e.title)+'<span class="rtype">'+esc(e.type)+'</span></a>';}).join('');
}
sin.addEventListener('input',function(){renderRes(sin.value);});
sov.addEventListener('click',function(e){if(e.target===sov)closeSearch();});
sres.addEventListener('click',function(e){if(e.target.closest('a'))closeSearch();});
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
var IMGS=__IMGDATA__;
document.querySelectorAll('img.pimg').forEach(function(el){
  var u=IMGS[el.dataset.img];if(u)el.src=u;else el.style.display='none';});
route();
</script>
</body>
</html>
"""


def _js_json(obj):
    """json.dumps sur pour un bloc <script> : neutralise </ (ex. </script>)."""
    return json.dumps(obj, separators=(",", ":")).replace("</", "<\\/")


def _nav_button(slug, label):
    return '<button data-target="%s" onclick="show(\'%s\')">%s</button>' % (
        slug, slug, html.escape(label))


def build_html(fiches, resolver, conflicts, wiki_root, share, profile):
    """Assemble le HTML complet + un rapport partiel. Voir docstring du module.

    Leve UnbalancedPrivateError si une fiche a un bloc %% non ferme (fail-closed).
    """
    wiki_root = Path(wiki_root)
    IMG_REGISTRY.clear()
    bad = sorted({f["slug"] for f in fiches if _unbalanced_private(f["body"])})
    if bad:
        raise UnbalancedPrivateError(bad)
    report = {"counts": {}, "dead": [], "conflicts": list(conflicts), "orphans": [],
              "unbalanced": [], "missing_images": [], "n_fiches": 0}

    visible = [f for f in fiches if not (share and f["meta"].get("prive"))]
    by_slug = {f["slug"]: f for f in visible}
    _, backlinks, dead = collect_links(fiches, resolver, include_private=not share)
    report["dead"] = dead

    ctx = {"share": share,
           "private_targets": {f["slug"] for f in fiches if f["meta"].get("prive")}}

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
                               wiki_root, by_slug, report, ctx)
                for f in entity_fiches]

    chrono = by_slug.get("chronologie")
    sessions = [f for f in entity_fiches if f["reldir"] == "sessions"]
    sections.append(render_accueil(entity_fiches, by_slug, resolver, dead, ctx))
    for reldir, label in NAV_TYPES:
        sections.append(render_index(reldir, label, entity_fiches))
    sections.append(render_chronologie(chrono, sessions, resolver, ctx))
    sections.append(render_systeme(entity_fiches, wiki_root))

    nav = [_nav_button("accueil", "Accueil"), _nav_button("chronologie", "Chronologie")]
    nav += [_nav_button("index-" + r, l) for r, l in NAV_TYPES]
    nav.append(_nav_button("systeme", "Systeme"))
    nav.append('<button class="nav-search" onclick="openSearch()" '
               'title="Rechercher (Ctrl+K)">&#9906;</button>')

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    title = "Gaia 2 - Archives de ZogZork"
    # __SECTIONS__ substitue en DERNIER : un placeholder litteral dans un corps
    # de fiche ne doit pas etre reinterprete.
    out = (TEMPLATE
           .replace("__TITLE__", title)
           .replace("__TIMESTAMP__", stamp)
           .replace("__NAV__", "\n    ".join(nav))
           .replace("__IMGDATA__", _js_json(IMG_REGISTRY))
           .replace("__SECTIONS__", "\n".join(sections)))
    return out, report


# ===========================================================================
#  Rapport et point d'entree CLI
# ===========================================================================

def print_report(report, dt):
    counts = report["counts"]
    detail = ", ".join("%d %s" % (counts[r], r or "racine") for r in sorted(counts))
    print("%d fiches (%s)" % (report["n_fiches"], detail))
    if report["dead"]:
        print("Liens morts (%d) :" % len(report["dead"]))
        for src, name in report["dead"]:
            print("  %s -> %s" % (src, name))
    if report["conflicts"]:
        print("Conflits d'alias (%d) :" % len(report["conflicts"]))
        for key, kept, ignored in report["conflicts"]:
            print("  '%s' -> %s (ignore %s)" % (key, kept, ignored))
    if report["orphans"]:
        print("Orphelines (%d) : %s"
              % (len(report["orphans"]), ", ".join(report["orphans"])))
    if report["unbalanced"]:
        print("Blocs prives non fermes : %s" % ", ".join(report["unbalanced"]))
    if report["missing_images"]:
        print("Images manquantes : %s" % ", ".join(report["missing_images"]))
    print("Build en %.2f s" % dt)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(".")
    if "--root" in argv:
        root = Path(argv[argv.index("--root") + 1])
    wiki_root = root / "wiki"

    t0 = time.time()
    fiches = load_fiches(wiki_root)
    if not fiches:
        print("Aucune fiche trouvee dans %s" % wiki_root)
        return 1
    resolver, conflicts = build_resolver(fiches)

    profile = None
    prof_path = root / "data" / "zogzork_profile.json"
    if prof_path.is_file():
        profile = json.loads(prof_path.read_text(encoding="utf-8"))

    try:
        full, report = build_html(fiches, resolver, conflicts, wiki_root,
                                  share=False, profile=profile)
        share, _ = build_html(fiches, resolver, conflicts, wiki_root,
                              share=True, profile=profile)
    except UnbalancedPrivateError as e:
        print("ERREUR fail-closed : bloc prive %% non ferme dans : %s"
              % ", ".join(e.slugs), file=sys.stderr)
        print("Aucune sortie ecrite ; corrige la ou les fiches puis relance.",
              file=sys.stderr)
        return 2

    (root / "wiki.html").write_text(full, encoding="utf-8")
    (root / "wiki_partage.html").write_text(share, encoding="utf-8")

    print_report(report, time.time() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
