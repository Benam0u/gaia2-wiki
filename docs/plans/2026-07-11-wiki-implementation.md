# Wiki Gaia 2 - Plan d'implementation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire `build_wiki.py` (generateur single-file style board.html) puis importer le contenu initial (~80 fiches campagne + systeme + ZogZork) depuis les sources validees.

**Architecture:** Sources = 1 fichier md par fiche dans `wiki/` (frontmatter YAML minimal + wikilinks `[[...]]`). Un script Python stdlib pur scanne, resout les liens en deux passes (collecte puis rendu), calcule les backlinks et emet DEUX fichiers HTML autonomes : `wiki.html` (complet) et `wiki_partage.html` (sans fiches `prive: true` ni blocs `%%`). Spec de reference : `docs/2026-07-10-wiki-gaia2-spec.md` (a lire par chaque implementeur).

**Tech Stack:** Python 3 stdlib uniquement pour build_wiki.py (os, re, html, json, base64, sys, time, datetime, unicodedata, pathlib). Tests unittest. Vanilla JS/CSS dans le template. Import : lecture des PDFs sources + Pillow ou ImageMagick (one-shot, hors build).

## Global Constraints

- build_wiki.py : AUCUNE dependance hors stdlib. Les scripts d'import one-shot (`scripts/`) peuvent utiliser Pillow/ImageMagick.
- Build complet < 2 s ; les HTML fonctionnent en `file://` sans reseau (hors Google Fonts, fallbacks propres).
- Design system = copie EXACTE du bloc CSS du TEMPLATE de `/home/benoi/claude/Game/Horde/docs/build_board.py` (~lignes 320-429), etendu (voir Task 7). Tokens : `--bg:#0E0F11 --surface:#15171B --surface-2:#1C1F25 --line:#2A2D34 --line-strong:#3A3E48 --text:#ECE7DA --text-2:#9D968A --text-3:#6A6660 --gold:#D4A85A --rust:#E25C3D --green:#6FAE96 --blue:#7E9CC8` ; fonts Google CDN Fraunces/Inter/JetBrains Mono ; zero border-radius, zero box-shadow.
- Tout en UTF-8. Contenu francais accentue. JAMAIS de tiret cadratin dans les md rediges : utiliser `-` (regle Benoit).
- Import FIDELE aux PDFs : aucune invention ; les hypotheses restent `statut: hypothese`, les fragments `statut: fragment` ; reprendre les etats RESOLU/FERME/EN COURS tels quels.
- Tests : `python3 -m unittest discover -s tests -v` depuis `Gaia2/`. Commit apres chaque task (message francais court + footer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`).
- Repo = `/home/benoi/claude/Gaia2/`, branche master, pas de remote. Les agents de contenu (Phase 2) n'executent AUCUNE commande git.

## Structure de fichiers cible

- `build_wiki.py` - tout le generateur (un seul fichier, pattern build_board.py).
- `tests/test_build_wiki.py` - tests unitaires + integration sur fixture.
- `tests/fixtures/mini_wiki/` - mini corpus de test (cree en Task 1).
- `tests/fixtures/mini_profile.json` - profil ZogZork reduit pour tester le rendu fiche technique.
- `scripts/extract_systeme.py` - one-shot : characterData -> fiches systeme + images.
- `wiki/**` - contenu (Phase 2). `data/zogzork_profile.json` - fiche technique.

---

# PHASE 1 - BUILD CORE (TDD, sequentiel, un seul implementeur)

### Task 1: Squelette + fixtures de test

**Files:**
- Create: arborescence `wiki/` complete (spec section 3), `tests/`, `scripts/`, `data/`, `.gitignore` (`__pycache__/`)
- Create: `tests/fixtures/mini_wiki/...` (contenu ci-dessous)

**Interfaces:**
- Produces: la fixture `tests/fixtures/mini_wiki/` utilisee par toutes les tasks suivantes.

- [ ] **Step 1: Creer les dossiers**

```bash
cd /home/benoi/claude/Gaia2
mkdir -p wiki/{personnages,lieux,factions,affaires,objets,creatures,concepts,sessions,img,systeme/races,systeme/classes} tests/fixtures/mini_wiki data scripts
printf '__pycache__/\n' > .gitignore
```

- [ ] **Step 2: Creer la fixture mini_wiki**

`tests/fixtures/mini_wiki/personnages/neros.md` :

```markdown
---
resume: Archimage au service de M. LeMaire
tags: [magie]
alias: [l'Archimage]
statut: confirme
---

# Neros

Archimage installe a [[Simpol]]. A aide le groupe dans la [[Prison des Mondes]].
Doit un cours gratuit a [[ZogZork]].

%%Note perso : il me doit AUSSI une biere.%%
```

`tests/fixtures/mini_wiki/lieux/simpol.md` :

```markdown
---
resume: Ville fortifiee sous controle imperial
infobox:
  Dirigeant: M. LeMaire
---

# Simpol

Ville dirigee par M. LeMaire. {?: L'Empire y prepare autre chose}
Frequentee par [[Neros]] et [[l'Archimage|le vieux mage]].
```

`tests/fixtures/mini_wiki/affaires/la-fleche.md` :

```markdown
---
resume: Signature annoncant un cambriolage
etat: en-cours
statut: hypothese
ne-pas-fusionner: [Canas]
---

# La Fleche

Message vise [[Kretel]].

%%Bloc prive
multi-lignes avec [[Neros]] dedans.%%
```

`tests/fixtures/mini_wiki/personnages/secret.md` :

```markdown
---
resume: Fiche entierement privee
prive: true
---

# Contact Secret

Il connait [[Neros]].
```

`tests/fixtures/mini_wiki/chronologie.md` :

```markdown
---
resume: Periodes reconstituees
---

# Chronologie

## Guerre
La [[Mere des Monstres]] est vaincue.
```

`tests/fixtures/mini_wiki/questions.md` :

```markdown
---
resume: Questions ouvertes
---

# Questions

## Questions ouvertes
- Qui est [[La Fleche]] ?

## A surveiller a la prochaine partie
- Le navire bloque.
```

`tests/fixtures/mini_wiki/sessions/session-21.md` :

```markdown
---
resume: Premiere session du wiki
---

# Session 21

On a revu [[Neros]].
```

Note : `[[Kretel]]`, `[[ZogZork]]`, `[[Prison des Mondes]]`, `[[Mere des Monstres]]` n'existent pas dans la fixture -> liens morts VOULUS pour les tests.

`tests/fixtures/mini_profile.json` :

```json
{
  "version": "1.0",
  "savedAt": "2026-07-10T13:29:00.000Z",
  "sheet": {
    "name": "ZogZork", "level": "3", "race": "Orc", "classe": "Enqueteur",
    "alignement": "Chaotique Bon",
    "attributes": {"force": "12", "dexterite": "12", "empathie": "12", "sagesse": "12", "intelligence": "8"},
    "attributeBonuses": {"force": "+4", "dexterite": "+2", "empathie": "+0", "sagesse": "+0", "intelligence": "+0"},
    "vitals": {"pvMax": "61", "pvTemp": "0", "pvCurrent": "", "pfMax": "59", "pfCurrent": ""},
    "bonusRace": ["<strong>Berz'Orc :</strong> ignore 1 blessure en combat"],
    "skills": [{"name": "Bagarre", "attr": "FOR", "bonus": "+5"}, {"name": "Esquive", "attr": "DEX", "bonus": "+5"}],
    "abilities": ["<strong>Paume de Boudh'Orc :</strong> 3 PF, ignore l'armure"],
    "descriptions": {"Description Physique": "Grand orc noueux.", "Histoire": "Ne dans les plaines.", "Relations - Allies et Enemies": ""},
    "notes": "Point d'espoir 1. 3 po / 72 pa / 19 pc.",
    "avatar": "",
    "damageEntries": [{"id": 1, "diceCount": "1", "diceType": "12", "bonus": "4", "label": "Poings"}],
    "rdEntries": [{"id": 1, "value": "18", "label": "Base"}, {"id": 2, "value": "14", "label": "Peau de Fer", "conditional": true}]
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "Squelette wiki + fixtures de test"
```

### Task 2: Frontmatter, slugs, normalisation

**Files:**
- Create: `build_wiki.py` (debut)
- Test: `tests/test_build_wiki.py`

**Interfaces:**
- Produces: `parse_frontmatter(text: str) -> tuple[dict, str]` ; `slugify(s: str) -> str` ; `norm_key(s: str) -> str`.
- Frontmatter supporte : scalaires (str/bool), listes inline `[a, b]`, UNE profondeur de map indentee (pour `infobox:`), commentaires `# ...` en fin de ligne hors quotes, valeurs quotees `"a: b"`.

- [ ] **Step 1: Ecrire les tests qui echouent**

```python
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from build_wiki import parse_frontmatter, slugify, norm_key

class TestFrontmatter(unittest.TestCase):
    def test_basic(self):
        meta, body = parse_frontmatter(
            "---\nresume: Un archimage\ntags: [magie, simpol]\nprive: true\n---\n\n# Neros\nTexte.")
        self.assertEqual(meta["resume"], "Un archimage")
        self.assertEqual(meta["tags"], ["magie", "simpol"])
        self.assertIs(meta["prive"], True)
        self.assertIn("# Neros", body)

    def test_no_frontmatter(self):
        meta, body = parse_frontmatter("# Titre\nTexte.")
        self.assertEqual(meta, {})
        self.assertTrue(body.startswith("# Titre"))

    def test_comment_et_quotes(self):
        meta, _ = parse_frontmatter('---\nstatut: confirme   # defaut\nresume: "a: b"\n---\nx')
        self.assertEqual(meta["statut"], "confirme")
        self.assertEqual(meta["resume"], "a: b")

    def test_map_indentee(self):
        meta, _ = parse_frontmatter("---\ninfobox:\n  Dirigeant: M. LeMaire\n  Population: dense\n---\nx")
        self.assertEqual(meta["infobox"], {"Dirigeant": "M. LeMaire", "Population": "dense"})

class TestSlug(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("Mère des Monstres"), "mere-des-monstres")
        self.assertEqual(slugify("L'Archimage !"), "l-archimage")

    def test_norm_key(self):
        self.assertEqual(norm_key("KRETEL"), norm_key("Kretel"))
        self.assertEqual(norm_key("Mère  des monstres"), norm_key("mere des Monstres"))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Verifier l'echec** - `python3 -m unittest discover -s tests -v` -> ImportError/AttributeError.

- [ ] **Step 3: Implementer**

```python
import re, unicodedata

def norm_key(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().casefold()

def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", norm_key(s)).strip("-")

def _scalar(v):
    v = v.strip()
    if v.startswith('"') and '"' in v[1:]:
        return v[1:v.index('"', 1)]
    v = re.split(r"\s+#", v, 1)[0].strip()
    if v in ("true", "false"): return v == "true"
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [x.strip() for x in inner.split(",") if x.strip()] if inner else []
    return v

def parse_frontmatter(text):
    if not text.startswith("---\n"): return {}, text
    end = text.find("\n---", 4)
    if end == -1: return {}, text
    raw, body = text[4:end], text[end + 4:]
    body = body.lstrip("\n")
    meta, cur = {}, None
    for line in raw.splitlines():
        if not line.strip(): continue
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
```

- [ ] **Step 4: Verifier le pass** - meme commande, tout vert.
- [ ] **Step 5: Commit** - `git add -A && git commit -m "build_wiki: frontmatter + slugs"`

### Task 3: Convertisseur markdown (port depuis build_board.py)

**Files:**
- Modify: `build_wiki.py`
- Test: `tests/test_build_wiki.py` (classe TestMarkdown)
- Reference: `/home/benoi/claude/Game/Horde/docs/build_board.py` (fonctions `inline`, `convert`, `render_table`, `render_cell`, tasklists, TASK_ICONS)

**Interfaces:**
- Produces: `md_convert(md: str, resolver=None, ctx=None) -> str` (HTML). `resolver`/`ctx` inutilises ici, branches en Task 4.
- Le sous-ensemble markdown du board est conserve tel quel : headings 1-6, hr, gras/italique, code inline/fenced, blockquotes, listes imbriquees, tables pipe, checkboxes `[ ]/[x]/[~]/[!]` -> glyphes colores.

- [ ] **Step 1: Tests qui echouent**

```python
class TestMarkdown(unittest.TestCase):
    def test_heading_et_gras(self):
        h = md_convert("## Titre\n\nDu **gras** et de l'*italique*.")
        self.assertIn("<h2", h); self.assertIn("<strong>gras</strong>", h)

    def test_table(self):
        h = md_convert("| A | B |\n|---|---|\n| 1 | 2 |")
        self.assertIn("tablewrap", h); self.assertIn("<td>1</td>", h)

    def test_tasklist(self):
        h = md_convert("- [x] fait\n- [ ] a faire")
        self.assertIn("tasklist", h)

    def test_echappement(self):
        self.assertIn("&lt;script&gt;", md_convert("du <script> mechant"))
```

- [ ] **Step 2: Verifier l'echec.**
- [ ] **Step 3: Porter le convertisseur** - copier depuis build_board.py les fonctions de conversion (inline, convert, render_table, render_cell, tasklists + TASK_ICONS), renommer le point d'entree en `md_convert(md, resolver=None, ctx=None)`. Ne PAS copier TABS/TEMPLATE/build du board. Conserver le stash `\x00` du code inline.
- [ ] **Step 4: Verifier le pass.**
- [ ] **Step 5: Commit** - `"build_wiki: convertisseur markdown porte du board"`

### Task 4: Wikilinks, alias, backlinks, liens morts

**Files:**
- Modify: `build_wiki.py`
- Test: `tests/test_build_wiki.py` (classe TestLinks)

**Interfaces:**
- Consumes: `norm_key`, `slugify`, `md_convert`.
- Produces:
  - `WIKILINK = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]")`
  - `load_fiches(root: Path) -> list[dict]` - scan `root/**/*.md` ; chaque fiche = `{"path", "reldir", "slug" (nom de fichier sans .md), "title" (premier H1, sinon slug), "meta", "body"}`. `reldir` ex : `personnages`, `systeme/races`, `""` (racine : chronologie/questions).
  - `build_resolver(fiches) -> tuple[dict, list]` - map `norm_key(titre|alias) -> slug` + liste de conflits `(cle, slug_garde, slug_ignore)` (premier gagnant par ordre alphabetique de slug).
  - `collect_links(fiches, resolver, include_private: bool) -> tuple[dict, dict, list]` - retourne `(links_out: {slug: set}, backlinks: {slug: set}, dead: [(slug_source, nom)])`. Si `include_private` est False : ignore les fiches `prive: true` ET les occurrences situees dans des blocs `%%`.
  - Dans `md_convert`, un wikilink resolu devient `<a class="wl" href="#SLUG">label</a>`, non resolu `<span class="deadlink" title="Fiche a creer">label</span>`. Label = partie apres `|` sinon le nom.

- [ ] **Step 1: Tests qui echouent**

```python
from build_wiki import load_fiches, build_resolver, collect_links, md_convert
FIX = Path(__file__).resolve().parent / "fixtures" / "mini_wiki"

class TestLinks(unittest.TestCase):
    def setUp(self):
        self.fiches = load_fiches(FIX)
        self.resolver, self.conflicts = build_resolver(self.fiches)

    def test_resolution_titre_alias_casse(self):
        self.assertEqual(self.resolver[norm_key("Neros")], "neros")
        self.assertEqual(self.resolver[norm_key("l'archimage")], "neros")

    def test_backlinks(self):
        _, back, _ = collect_links(self.fiches, self.resolver, include_private=True)
        self.assertIn("simpol", back["neros"])     # simpol.md cite [[Neros]]
        self.assertIn("session-21", back["neros"])

    def test_liens_morts(self):
        _, _, dead = collect_links(self.fiches, self.resolver, include_private=True)
        self.assertIn(("la-fleche", "Kretel"), dead)

    def test_partage_exclut_prive(self):
        _, back_full, _ = collect_links(self.fiches, self.resolver, include_private=True)
        _, back_share, _ = collect_links(self.fiches, self.resolver, include_private=False)
        self.assertIn("secret", back_full["neros"])       # fiche privee
        self.assertNotIn("secret", back_share["neros"])
        self.assertIn("la-fleche", back_full["neros"])    # via bloc %% de la-fleche
        self.assertNotIn("la-fleche", back_share["neros"])

    def test_rendu_lien(self):
        h = md_convert("Voir [[Neros|le mage]] et [[Inconnu]].", resolver=self.resolver)
        self.assertIn('href="#neros">le mage</a>', h)
        self.assertIn('class="deadlink"', h)
```

- [ ] **Step 2: Verifier l'echec.**
- [ ] **Step 3: Implementer** - le remplacement wikilink se fait dans `inline()` APRES l'echappement HTML et le stash du code (les crochets ne sont pas echappes). `collect_links` travaille sur le md brut avec `WIKILINK.finditer` ; pour `include_private=False`, retirer d'abord les blocs `%%(.*?)%%` (re.S) du corps et sauter les fiches privees comme SOURCES ; dans les deux modes une fiche privee reste une CIBLE valide pour la resolution (l'aplatissement cote partage arrive en Task 8).
- [ ] **Step 4: Verifier le pass.**
- [ ] **Step 5: Commit** - `"build_wiki: wikilinks + backlinks + liens morts"`

### Task 5: Blocs prives %%, marqueur {?:}, directive {{fiche_technique}}

**Files:**
- Modify: `build_wiki.py`
- Test: `tests/test_build_wiki.py` (classe TestPrivate)

**Interfaces:**
- Consumes: `md_convert`.
- Produces:
  - `extract_private(body: str) -> tuple[str, list, bool]` - remplace chaque bloc `%%...%%` (re.S) par un token `\x02PRIVn\x03` ; retourne (body_tokenise, blocs, unbalanced). Si nombre de `%%` impair : retour (body inchange, [], True).
  - `render_private(html: str, blocks: list, share: bool) -> str` - share=True : tokens -> "" ; sinon bloc SANS saut de ligne -> `<span class="prive">` + inline(bloc), bloc AVEC saut de ligne -> `<div class="prive">` + md_convert(bloc).
  - Marqueur hypothese dans `inline()` : `\{\?:\s*([^}]+)\}` -> `<span class="hyp"><span class="hyp-b">?</span> \1</span>`.
  - Directive : `{{fiche_technique}}` remplacee par le token `\x02TECH\x03` avant conversion ; substituee apres (Task 6 fournit le HTML).

- [ ] **Step 1: Tests qui echouent**

```python
from build_wiki import extract_private, render_private

class TestPrivate(unittest.TestCase):
    def test_inline_et_multiligne(self):
        body, blocks, bad = extract_private("A %%secret%% B\n\n%%multi\nlignes%%")
        self.assertFalse(bad); self.assertEqual(len(blocks), 2)
        self.assertNotIn("secret", body)
        h = render_private(md_convert(body), blocks, share=False)
        self.assertIn('<span class="prive">', h); self.assertIn('<div class="prive">', h)

    def test_partage_supprime(self):
        body, blocks, _ = extract_private("A %%secret%% B")
        h = render_private(md_convert(body), blocks, share=True)
        self.assertNotIn("secret", h); self.assertIn("A", h)

    def test_non_ferme(self):
        body, blocks, bad = extract_private("A %%oubli")
        self.assertTrue(bad); self.assertEqual(body, "A %%oubli")

    def test_marqueur_hypothese(self):
        self.assertIn('class="hyp"', md_convert("Elle serait {?: Axxel deguise}."))
```

- [ ] **Step 2: Verifier l'echec.** / **Step 3: Implementer.** / **Step 4: Pass.** / **Step 5: Commit** `"build_wiki: blocs prives + marqueur hypothese"`

### Task 6: Infobox, badges, fiche technique ZogZork

**Files:**
- Modify: `build_wiki.py`
- Test: `tests/test_build_wiki.py` (classes TestInfobox, TestFicheTechnique)

**Interfaces:**
- Consumes: fiche dict (Task 4), `tests/fixtures/mini_profile.json`.
- Produces:
  - `embed_img(path: Path) -> str` - data URI (mime par extension png/jpg/jpeg/gif/webp), "" si introuvable (+ warning dans le rapport).
  - `render_infobox(fiche, wiki_root: Path) -> str` - `<aside class="infobox">` : portrait (meta `portrait`, chemin relatif a `wiki/`), lignes cle/valeur mono : Type (libelle FR du TYPE_LABELS), Statut (si != confirme), Etat (affaires), Decouverte, Tags, puis les paires du map `infobox`. Retourne "" si rien a afficher.
  - `render_badges(meta) -> str` - `<span class="st st-hyp">? HYPOTHESE</span>`, `st-frag ~ FRAGMENT`, `st-encours EN COURS`, `st-resolu RESOLU`, `st-ferme FERME`.
  - `render_fusion_warning(meta, resolver) -> str` - si `ne-pas-fusionner` : `<div class="warn-fusion">Ne pas fusionner avec X, Y sans preuve en seance.</div>` (X, Y en wikilinks resolus).
  - `render_fiche_technique(profile: dict, wiki_root: Path) -> str` - depuis `profile["sheet"]` : identite (nom/niveau/race/classe/alignement), table attributs `valeur (Dvaleur) bonus`, vitaux PV/PF, degats (`XdY+Z label`), RD : liste entrees (marquer `(conditionnel)`) + ligne totale `RD max N (base M)` avec N = somme de tout, M = somme des non-conditionnels ; table competences (name/attr/bonus) ; bonus de race et capacites inseres SANS echappement (HTML de confiance : `<strong>` issus de l'outil de Benoit) ; descriptions Physique/Histoire en paragraphes ; notes en bloc pre-wrap.
  - `TYPE_LABELS = {"personnages": "Personnage", "lieux": "Lieu", "factions": "Faction", "affaires": "Affaire", "objets": "Objet", "creatures": "Creature", "concepts": "Concept", "sessions": "Session", "systeme/races": "Race", "systeme/classes": "Classe", "": "Page"}`

- [ ] **Step 1: Tests qui echouent**

```python
import json
from build_wiki import render_infobox, render_badges, render_fiche_technique, TYPE_LABELS

class TestInfobox(unittest.TestCase):
    def test_infobox_map(self):
        fiches = load_fiches(FIX)
        simpol = next(f for f in fiches if f["slug"] == "simpol")
        h = render_infobox(simpol, FIX)
        self.assertIn("Dirigeant", h); self.assertIn("M. LeMaire", h); self.assertIn("Lieu", h)

    def test_badges(self):
        self.assertIn("EN COURS", render_badges({"etat": "en-cours"}))
        self.assertIn("HYPOTHESE", render_badges({"statut": "hypothese"}))
        self.assertEqual(render_badges({"statut": "confirme"}), "")

class TestFicheTechnique(unittest.TestCase):
    def test_rendu(self):
        prof = json.loads((Path(__file__).resolve().parent / "fixtures" / "mini_profile.json").read_text())
        h = render_fiche_technique(prof, FIX)
        self.assertIn("ZogZork", h); self.assertIn("12 (D12) +4", h)
        self.assertIn("RD max 32 (base 18)", h)
        self.assertIn("<strong>Paume de Boudh'Orc", h)   # HTML passe tel quel
        self.assertIn("Bagarre", h)
```

- [ ] **Step 2: Echec.** / **Step 3: Implementer.** / **Step 4: Pass.** / **Step 5: Commit** `"build_wiki: infobox + badges + fiche technique"`

### Task 7: Assemblage single-file (template, nav, index, accueil, recherche)

**Files:**
- Modify: `build_wiki.py` (constante TEMPLATE + fonctions d'assemblage)
- Test: `tests/test_build_wiki.py` (classe TestAssembly)

**Interfaces:**
- Consumes: tout ce qui precede.
- Produces: `build_html(fiches, resolver, conflicts, wiki_root, share: bool, profile: dict|None) -> tuple[str, dict]` - (HTML complet, rapport partiel). Le rapport accumule : counts par type, dead, conflicts, orphans, unbalanced, images manquantes.
- TEMPLATE : head avec les 3 fonts Google CDN (copier les `<link>` de board.html), le CSS du board colle tel quel, PLUS le CSS additionnel ci-dessous. Placeholders `__TITLE__ __TIMESTAMP__ __NAV__ __SECTIONS__`.
- Chaque fiche = `<section class="page" id="p-SLUG" data-title data-alias data-resume data-tags data-type>` : `<h1>` + badges, infobox, warn-fusion, corps, backlinks (`<div class="backlinks">Mentionne dans : liens`).
- Pages speciales generees : `accueil` (affaires en-cours depuis les meta ; contenu de questions.md ; derniere session (slug session-NN max) ; "Fiches a creer" = liens morts groupes par nom avec sources ; "Recemment modifiees" = top 10 mtime), `index-personnages`, `index-lieux`, etc. (table Nom/Resume/Badges/Tags), `chronologie` (chronologie.md + liste des sessions), `systeme` (portails races/classes avec portraits + liens competences/avantages).
- Nav sticky : ACCUEIL CHRONOLOGIE PERSONNAGES LIEUX FACTIONS AFFAIRES OBJETS CREATURES CONCEPTS SESSIONS SYSTEME + bouton recherche. Brand : `GAIA 2 - ARCHIVES DE ZOGZORK` (`GAIA 2 - ARCHIVES` en partage... non : meme brand, voir Task 8).
- JS (~50 lignes vanilla, dans TEMPLATE) : `show(id)` (masque .page, affiche `#p-`+id, nav active, scroll top), routing `location.hash` + hashchange + defaut `accueil` ; recherche : overlay Ctrl+K/Cmd+K/bouton, filtre sur un array construit au chargement depuis les data-attributs (title/alias/resume/tags), fleches+Entree naviguent, Esc ferme.

CSS additionnel (a coller dans TEMPLATE apres le CSS du board) :

```css
.page{display:none}.page.active{display:block;animation:fade .18s ease}
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
@media(max-width:680px){.home-cols{grid-template-columns:1fr}.infobox{float:none;width:auto;margin:0 0 18px}}
```

- [ ] **Step 1: Tests qui echouent**

```python
from build_wiki import build_html

class TestAssembly(unittest.TestCase):
    def setUp(self):
        fiches = load_fiches(FIX)
        resolver, conflicts = build_resolver(fiches)
        self.html, self.report = build_html(fiches, resolver, conflicts, FIX, share=False, profile=None)

    def test_sections_et_nav(self):
        for pid in ("p-accueil", "p-neros", "p-index-personnages", "p-chronologie"):
            self.assertIn(f'id="{pid}"', self.html)
        self.assertIn("ARCHIVES DE ZOGZORK", self.html)

    def test_accueil(self):
        self.assertIn("La Fleche", self.html)          # affaire en cours
        self.assertIn("Fiches a creer", self.html)
        self.assertIn("Kretel", self.html)             # lien mort liste

    def test_recherche_data(self):
        self.assertIn('data-alias="l&#x27;Archimage"', self.html) or self.assertIn("data-alias", self.html)

    def test_backlinks_affiches(self):
        self.assertIn("Mentionne dans", self.html)
```

(Pour `test_recherche_data`, asserter simplement `'data-alias'` present ET `'Archimage'` present dans la section neros.)

- [ ] **Step 2: Echec.** / **Step 3: Implementer.** / **Step 4: Pass.** / **Step 5: Commit** `"build_wiki: assemblage single-file + accueil + recherche"`

### Task 8: Double sortie, filtrage partage, rapport, CLI

**Files:**
- Modify: `build_wiki.py` (main)
- Test: `tests/test_build_wiki.py` (classe TestShareBuild)

**Interfaces:**
- Produces: `main(argv) -> int` : lit `wiki/` + `data/zogzork_profile.json` (si present), ecrit `wiki.html` ET `wiki_partage.html`, imprime le rapport, retourne 0 (1 si zero fiche). Invocation : `python3 build_wiki.py` depuis Gaia2/.
- Regles partage (share=True) : fiches `prive: true` exclues des sections/index/recherche/backlinks/accueil ; blocs `%%` supprimes ; un wikilink vers une fiche privee est APLATI en `<span>label</span>` (pas deadlink) ; les backlinks utilisent `collect_links(include_private=False)`.
- Rapport stdout : `N fiches (X personnages, ...)`, liens morts (`source -> nom`), conflits d'alias, orphelines (fiches campagne sans backlink, types personnages/lieux/factions/affaires/objets/creatures/concepts uniquement), `%%` non fermes, images manquantes, duree.

- [ ] **Step 1: Tests qui echouent**

```python
class TestShareBuild(unittest.TestCase):
    def setUp(self):
        fiches = load_fiches(FIX)
        resolver, conflicts = build_resolver(fiches)
        self.full, _ = build_html(fiches, resolver, conflicts, FIX, share=False, profile=None)
        self.share, _ = build_html(fiches, resolver, conflicts, FIX, share=True, profile=None)

    def test_fiche_privee_absente(self):
        self.assertIn("Contact Secret", self.full)
        self.assertNotIn("Contact Secret", self.share)
        self.assertNotIn("p-secret", self.share)

    def test_blocs_prives_absents(self):
        self.assertIn("une biere", self.full)
        self.assertNotIn("une biere", self.share)

    def test_lien_vers_prive_aplati(self):
        # ajouter dans la fixture simpol.md une ligne : "Contact : [[Contact Secret]]" (Task 1 bis si oublie)
        self.assertIn('href="#p-secret"', self.full.replace("#secret", "#p-secret")) or True
        self.assertNotIn('href="#secret"', self.share)

    def test_backlinks_partage(self):
        # la section neros du partage ne mentionne pas la fiche privee
        neros_share = self.share.split('id="p-neros"')[1].split("</section>")[0]
        self.assertNotIn("Contact Secret", neros_share)
```

(Precision liens : les href internes sont `#SLUG` et les ids `p-SLUG` ; le JS mappe hash -> id. Ecrire les asserts en consequence : `href="#secret"` present dans full, absent dans share.)

- [ ] **Step 2: Echec.** / **Step 3: Implementer** (ajouter la ligne `[[Contact Secret]]` dans la fixture simpol.md si necessaire). / **Step 4: Pass.** / **Step 5: Commit** `"build_wiki: double sortie + filtrage prive + rapport"`

### Task 9: Integration complete + perf

- [ ] **Step 1: Test d'integration** - via `subprocess` : copier la fixture dans un tmpdir avec `data/` + mini_profile.json renomme zogzork_profile.json + une fiche `personnages/zogzork.md` contenant `{{fiche_technique}}`, executer `python3 build_wiki.py`, asserter : exit 0, les 2 fichiers existent, `wiki.html` contient `RD max 32`, duree < 2 s.
- [ ] **Step 2: Echec.** / **Step 3: Implementer** (main : accepter `--root DIR` optionnel pour les tests). / **Step 4: Pass + suite complete verte.** / **Step 5: Commit** `"build_wiki: CLI + integration"`

# PHASE 2 - IMPORT INITIAL (parallelisable par type, fichiers disjoints)

Conventions communes a toutes les tasks de contenu (LIRE la spec sections 4-9 d'abord) :
- Nom de fichier = slugify(titre H1). `resume:` OBLIGATOIRE (une ligne). Lier GENEREUSEMENT avec `[[...]]`, y compris vers des fiches d'autres types pas encore creees (liens morts OK, resolus en Task 15).
- Fidelite absolue aux PDFs sources : `/mnt/c/Users/benoi/OneDrive/Bureau/Dev/Character_Sheet/Gaia_2_Dossier_detaille_ZogZork_2026-07-10.pdf` (principal, 12 p.) + `Recap_Gaia_2_ZogZork_2026-07-10_v3.pdf` (croisement). Statuts/hypotheses/fragments repris tels quels. Pas d'em-dash.
- Corps type : intro 1-3 phrases, puis sections `## Ce qu'on sait`, `## Relations` (si utile), `## Zones d'ombre` (si utile). Court = OK ; une fiche fragment peut faire 3 lignes.

### Task 10: Extraction systeme (script + execution)

**Files:** Create `scripts/extract_systeme.py` ; Create `wiki/systeme/races/*.md` (20), `wiki/systeme/classes/*.md` (13), `wiki/systeme/competences.md`, `wiki/systeme/avantages.md`, `wiki/img/races/*` (20), `wiki/img/classes/*` (13).

- [ ] Extraire `const characterData = {...}` de `/mnt/c/Users/benoi/OneDrive/Bureau/Dev/WeakAuction/project_cursor/Projet_Weak_Auctions/JDR/index.html` (~ligne 3780) : localiser par regex `const characterData\s*=\s*`, matcher les accolades equilibrees, `json.loads` (fallback : retirer virgules trainantes). VERIFIER : 20 races, 13 classes, 52 competences, 15 avantagesGeneraux.
- [ ] Generer les fiches. Race : frontmatter `resume` + `tags: [race]` + `portrait: img/races/<id>.png`, corps = description + `## Bonus` (les 2 bonus + le neutre) + `## Malus`. Classe : `portrait: img/classes/<id>.png`, corps = description + `## Avantages de classe` (les 10, `**Nom** - effet`). `competences.md` : table Nom | Attribut (52 lignes). `avantages.md` : les 15 en `**Nom** - effet` + la table levelUps en fin (`## Montee de niveau`).
- [ ] Copier les images vers `wiki/img/{races,classes}/`, redimensionnees a max 512px de large (Pillow si dispo, sinon ImageMagick `convert -resize 512x>`) ; renommer `avanturier.png -> aventurier.png` (et pointer la fiche dessus), garder `centaure.jpg`. Verifier 33 fichiers presents.
- [ ] `python3 build_wiki.py` passe ; commit `"import: section systeme (20 races, 13 classes, competences, avantages)"`.

### Task 11: ZogZork (donnees + narratif)

**Files:** Create `data/zogzork_profile.json`, `wiki/img/zogzork.jpg`, `wiki/personnages/zogzork.md`.

- [ ] Copier `/mnt/c/Users/benoi/OneDrive/Bureau/Dev/Character_Sheet/ZogZork_profile_level3_Juillet.json` -> `data/zogzork_profile.json` ; extraire `sheet.avatar` (base64) -> `wiki/img/zogzork.jpg` redimensionne max 512px ; remplacer le champ `avatar` par `""` dans la copie.
- [ ] Rediger `zogzork.md` : frontmatter (`resume`, `tags: [pj, groupe]`, `portrait: img/zogzork.jpg`, `infobox:` Race/Classe/Niveau en liens), narratif depuis `descriptions` du JSON + section 8 du dossier PDF (parcours, relations dont Nemesis `[[Prevot Bertrand]]` et `[[Wolframe]]`, style d'action), puis `{{fiche_technique}}` en fin sous `## Fiche technique`.
- [ ] Build OK, la fiche affiche `61` PV et `RD max 32` ; commit `"import: ZogZork (profil + narratif)"`.

### Task 12: Fiches campagne - personnages, lieux, factions

**Files:** Create `wiki/personnages/*.md` (~30), `wiki/lieux/*.md` (~10), `wiki/factions/*.md` (~8).

Listes attendues (issues du dossier ; l'implementeur lit les PDFs et peut en decouvrir d'autres) :
- Personnages : Axxel, Axelle, l'Empereur de PaxAlpha, M. LeMaire, Dr Van Richten, Neros, Kretel, Ambroise, Yannick, Kathlyn, Telem, Turdan, Gerwin, Gueule de Figue, La Flechec (NON : La Fleche est une AFFAIRE ; creer aussi une fiche personnage "La Fleche (identite inconnue)" statut hypothese SEULEMENT si le dossier la traite comme personne - sinon laisser en affaire seule), l'enqueteur infiltre du sauna (titre : "Enqueteur du sauna", statut hypothese), Prevot Bertrand, Wolframe, le haut grade kidnappe ("Haut grade imperial", statut confirme mais anonyme) + PJ : ZogZork (Task 11), Petit Panda, Bebou (-> creatures, PAS ici), Sidonie, Bluno, Bill + fragments (statut: fragment) : Tel, Knitt, Casper, Corien, Mick, Matt. Gretel = PAS de fiche : `alias: [Gretel]` sur Kretel + une ligne "Zone d'ombre : un doute de lecture Gretel/Kretel subsiste".
- Lieux : Simpol, Muscerie, Prison des Mondes, Taverne Sauna et Bains d'Ambroise, Foret des Elfes du Vent, Chapiteau de Neros, Camps des Refugies, Temple de la secte, Entrepot des quais, Quais de Simpol.
- Factions : Empire PaxAlpha, La Garde, Les Sauvages, Les Refugies, Secte des Refugies, Reseau de contrebande, Mairie de Simpol, Guilde des monteurs de meubles.
- PJ : `tags: [pj, groupe]` + mention du role de pont (Bill -> La Garde, Sidonie -> Refugies, ZogZork/Petit Panda -> Sauvages).

- [ ] Rediger les fiches (conventions communes). / - [ ] Build OK. / - [ ] Commit `"import: personnages + lieux + factions"`.

### Task 13: Fiches campagne - affaires, objets, creatures, concepts

**Files:** Create `wiki/affaires/*.md` (~6), `wiki/objets/*.md` (~9), `wiki/creatures/*.md` (~9), `wiki/concepts/*.md` (~10).

- Affaires (avec `etat:`) : Vol des recherches de Neros (resolu), Crise du Canas (resolu), Fausse epidemie (resolu), Passage d'Ambroise (ferme), Navire marchand (resolu), La Fleche (en-cours, `ne-pas-fusionner` selon dossier section 10.3 : Canas / Baies de loyaute / Drogues de contrebande portent les separations - les poser sur les fiches concernees comme le dossier le fait).
- Objets : Carnet de recherches de Neros, Baies de loyaute, La fleur des baies, Canas (+antidote, meme fiche), Laissez-passer de Gerwin, Enchantement druidique, Message de La Fleche, Weed (fragment), Pendentif carre (fragment).
- Creatures : Mere des Monstres, Bebou, Serpent enorme, Ours (meme fiche que serpent si le dossier les traite ensemble : "Serpent et ours du kidnapping"), Dynastie ogre (fragment, ou concept selon le texte). NOTE : les RACES jouables restent dans systeme/ ; creatures/ = etres et especes non-systeme.
- Concepts : Loi beaute-moralite d'Axxel, Technomagie, Systeme de classes impose, Dissociation corps-esprit (Canas), Forme astrale, Guerre sur deux plans, Regime de loi martiale, Castes des Hauts-Nains, Contrebande, Enfant poisson (fragment ou zone d'ombre de Yannick selon le texte).

- [ ] Rediger. / - [ ] Build OK. / - [ ] Commit `"import: affaires + objets + creatures + concepts"`.

### Task 14: Chronologie, questions, template session

**Files:** Create `wiki/chronologie.md`, `wiki/questions.md`, `wiki/sessions/_template.md`.

- [ ] `chronologie.md` : les 13 periodes de la section 9 du dossier, en `## Periode` + texte + wikilinks, dans l'ordre causal, avec l'avertissement du dossier (ordre approximatif, causalite d'abord) en intro.
- [ ] `questions.md` : `## Questions ouvertes` (les ~11-13 questions de la section 10.2, en liste, wikilinks) + `## A surveiller a la prochaine partie` (section 8 du recap). Inclure les separations 10.3 en rappel.
- [ ] `sessions/_template.md` : structure de la section 12 du dossier (date reelle, numero, presents, evenements, nouveaux personnages/lieux, indices, quetes ouvertes/fermees, consequences pour ZogZork, questions au MJ). Le fichier commence par `_` -> le build DOIT l'ignorer (ajouter si absent : skip des fichiers commencant par `_` dans load_fiches + test).
- [ ] Build OK. / - [ ] Commit `"import: chronologie + questions + template session"`.

### Task 15: Passe de coherence et maillage

- [ ] `python3 build_wiki.py` ; examiner le rapport : (a) conflits d'alias -> corriger ; (b) liens morts -> pour chaque nom, SOIT creer la micro-fiche manquante (souvent un fragment), SOIT corriger la typo vers la fiche existante ; garder morts uniquement les liens deliberement futurs ; (c) orphelines -> ajouter les wikilinks manquants dans les fiches qui devraient les citer (verifier via les 15 relations listees dans la spec section 13 / le dossier).
- [ ] Verifier la densite : chaque fiche campagne non-fragment cite au moins 2 autres fiches.
- [ ] Verifier les 3 affaires a separation (`ne-pas-fusionner`) affichent leur avertissement.
- [ ] Commit `"import: passe de coherence (liens, alias, orphelines)"`.

# PHASE 3 - VERIFICATION ET LIVRAISON

### Task 16: Acceptation (spec section 16) + revue + livraison

- [ ] Derouler les criteres : build < 2 s (chronometrer), double-clic file:// OK, liens morts tous listes sur l'accueil, backlinks exacts sur 3 fiches tirees au hasard (verifier a la main contre grep), `wiki_partage.html` sans aucun contenu prive (grep des resumes prives et de "%%"), fiche ZogZork fidele au PDF (PV 61, PF 59, RD 32/18, 8 competences), look board (verification par Benoit).
- [ ] Revue de code adversariale de build_wiki.py (correctness/securite d'echappement/perf) + application des fixes confirmes.
- [ ] Mettre a jour `Gaia2.md` (statut : prod v1 livree, en attente relecture Benoit) ; commit final.
- [ ] Message a Benoit : quoi relire, comment rebuilder, comment se passe la prochaine session en mode dictee.

## Self-review du plan (faite le 2026-07-11)

- Couverture spec : sections 3-12 -> Tasks 1-9 ; section 13 -> Tasks 10-14 ; section 5 (ZogZork JSON) -> Tasks 6+11 ; section 16 -> Task 16 ; workflow post-session (14) = usage, rien a construire ; v2 (15) = hors scope, OK.
- Coherence des noms : `md_convert/load_fiches/build_resolver/collect_links/extract_private/render_private/render_infobox/render_badges/render_fusion_warning/render_fiche_technique/build_html/main` utilises de maniere uniforme entre tasks.
- Ids/href : convention unique `id="p-SLUG"` pour les sections, `href="#SLUG"` pour les liens, mapping fait par le JS (Task 7, repris Task 8).
- `_template.md` ignore par le build : exige en Task 14 avec test.
