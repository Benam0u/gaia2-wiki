import json, os, shutil, subprocess, sys, tempfile, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from build_wiki import (parse_frontmatter, slugify, norm_key, md_convert,
                        load_fiches, build_resolver, collect_links,
                        extract_private, render_private, inline, split_row,
                        render_infobox, render_badges, render_fiche_technique,
                        TYPE_LABELS, build_html, _js_json)

FIX = Path(__file__).resolve().parent / "fixtures" / "mini_wiki"

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

    def test_split_row_pipe_interne(self):
        self.assertEqual(split_row("| [[Kretel|le marchand]] | victime |"),
                         ["[[Kretel|le marchand]]", "victime"])
        self.assertEqual(split_row("| `a|b` | code |"), ["`a|b`", "code"])

    def test_url_pas_double_echappee(self):
        h = inline("[doc](https://x.test/?a=1&b=2)")
        self.assertIn("a=1&amp;b=2", h)
        self.assertNotIn("&amp;amp;", h)

    def test_wikilink_esperluette(self):
        fiches = [{"slug": "ol", "title": "Ombre & Lumiere", "meta": {}}]
        resolver, _ = build_resolver(fiches)
        h = md_convert("Voir [[Ombre & Lumiere]].", resolver=resolver)
        self.assertIn('href="#ol"', h)
        self.assertNotIn("deadlink", h)

    def test_tasklist_markup_valide(self):
        h = md_convert("- [x] fait")
        self.assertIn('<div class="txt">fait</div>', h)
        self.assertNotIn("</span></div>", h)

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

    def test_titre_bat_alias(self):
        # Un titre H1 exact l'emporte sur l'alias d'une autre fiche (spec §6).
        fiches = [
            {"slug": "autre", "title": "Autre", "meta": {"alias": ["Axelle"]}},
            {"slug": "axelle", "title": "Axelle", "meta": {}},
        ]
        resolver, conflicts = build_resolver(fiches)
        self.assertEqual(resolver[norm_key("Axelle")], "axelle")
        self.assertIn((norm_key("Axelle"), "axelle", "autre"), conflicts)

    def test_liens_dans_code_ignores(self):
        fiches = [
            {"slug": "a", "title": "A", "meta": {},
             "body": "```\nvoir [[B]]\n```\net `[[B]]` inline.",
             "reldir": "concepts", "mtime": 0},
            {"slug": "b", "title": "B", "meta": {}, "body": "# B",
             "reldir": "concepts", "mtime": 0},
        ]
        resolver, _ = build_resolver(fiches)
        _, back, dead = collect_links(fiches, resolver, include_private=True)
        self.assertNotIn("a", back["b"])
        self.assertEqual(dead, [])

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

    def test_private_ignore_code(self):
        body, blocks, bad = extract_private(
            "```\nexemple %%cache%% ici\n```\n\n%%vrai secret%%")
        self.assertFalse(bad)
        self.assertEqual(blocks, ["vrai secret"])
        self.assertIn("%%cache%%", body)   # le code reste litteral

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

    def test_badge_pj_pnj(self):
        self.assertIn(">PJ<", render_badges({"tags": ["pj", "groupe"]}))
        self.assertIn(">PNJ<", render_badges({"tags": ["pnj"]}))
        self.assertEqual(render_badges({"tags": ["lieu"]}), "")

class TestFicheTechnique(unittest.TestCase):
    def test_rendu(self):
        prof = json.loads((Path(__file__).resolve().parent / "fixtures" / "mini_profile.json").read_text())
        h = render_fiche_technique(prof, FIX)
        self.assertIn("ZogZork", h)
        # Layout PDF : valeur, de en petit, bonus en accent
        self.assertIn('12 <span class="ft-die">(D12)</span> <span class="ft-bonus">+4</span>', h)
        self.assertIn("Dextérité", h)      # cles courtes dex/emp/sag/int du JSON reel
        self.assertIn("Intelligence", h)
        self.assertIn("RD 32 (18)", h)
        self.assertIn("(D12+4) + (D6)", h)
        self.assertIn("Notes - Quêtes - Équipements", h)
        self.assertIn("<strong>Paume de Boudh'Orc", h)   # HTML passe tel quel
        self.assertIn("Bagarre", h)

    def test_pas_de_descriptions(self):
        # Le narratif vit dans zogzork.md (spec §5) : la fiche technique ne le duplique pas.
        prof = json.loads((Path(__file__).resolve().parent / "fixtures" / "mini_profile.json").read_text())
        h = render_fiche_technique(prof, FIX)
        self.assertNotIn("Grand orc noueux", h)
        self.assertNotIn("Ne dans les plaines", h)

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
        neros = self.html.split('id="p-neros"')[1].split("</section>")[0]
        self.assertIn("data-alias", neros)
        self.assertIn("Archimage", neros)

    def test_backlinks_affiches(self):
        self.assertIn("Mentionne dans", self.html)

    def test_hovercard(self):
        self.assertIn('id="hovercard"', self.html)
        self.assertIn("var HMAP=", self.html)

    def test_data_portrait(self):
        import base64
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "w"
            shutil.copytree(FIX, d)
            (d / "img").mkdir()
            png = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
                   "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
            (d / "img" / "x.png").write_bytes(base64.b64decode(png))
            p = d / "personnages" / "neros.md"
            p.write_text(p.read_text(encoding="utf-8").replace(
                "tags: [magie]", "tags: [magie]\nportrait: img/x.png"), encoding="utf-8")
            fiches = load_fiches(d)
            resolver, conflicts = build_resolver(fiches)
            out, _ = build_html(fiches, resolver, conflicts, d, share=False, profile=None)
            self.assertIn('data-portrait="img/x.png"', out)

    def test_polices_embarquees(self):
        self.assertIn("@font-face", self.html)
        self.assertIn("data:font/woff2;base64,", self.html)
        self.assertNotIn("fonts.googleapis.com", self.html)
        # dedupliquees : un bloc par (famille, subset), pas par graisse
        self.assertLessEqual(self.html.count("data:font/woff2"), 6)

    def test_tables_index_mobile(self):
        # badges insecables + classe idx (colonne Tags masquable sur mobile)
        self.assertIn("white-space:nowrap", self.html.split(".st{")[1].split("}")[0])
        self.assertIn('<table class="idx">', self.html)
        self.assertIn("table.idx th:nth-child(4)", self.html)

    def test_recherche_fulltext(self):
        # Recherche insensible aux accents + indexation du corps des fiches.
        self.assertIn("function norm(", self.html)
        self.assertIn("\\u0300", self.html)
        self.assertIn("body:norm(p.textContent", self.html)

class TestShareBuild(unittest.TestCase):
    def setUp(self):
        fiches = load_fiches(FIX)
        resolver, conflicts = build_resolver(fiches)
        self.full, _ = build_html(fiches, resolver, conflicts, FIX, share=False, profile=None)
        self.share, _ = build_html(fiches, resolver, conflicts, FIX, share=True, profile=None)

    def test_fiche_privee_absente(self):
        # La fiche privee : pas de section, pas d'entree d'index/recherche/backlink.
        self.assertIn('id="p-secret"', self.full)
        self.assertNotIn('id="p-secret"', self.share)
        self.assertNotIn('href="#secret"', self.share)

    def test_blocs_prives_absents(self):
        self.assertIn("une biere", self.full)
        self.assertNotIn("une biere", self.share)

    def test_lien_vers_prive_aplati(self):
        # En partage, un [[lien]] vers une fiche privee est aplati en texte (spec §8) :
        # le nom reste, mais aucun lien ni ancre vers la fiche.
        self.assertIn('href="#secret"', self.full)
        self.assertNotIn('href="#secret"', self.share)
        self.assertIn('class="flat">Contact Secret</span>', self.share)

    def test_backlinks_partage(self):
        neros_share = self.share.split('id="p-neros"')[1].split("</section>")[0]
        self.assertNotIn("Contact Secret", neros_share)

class TestIntegration(unittest.TestCase):
    def test_cli_bout_en_bout(self):
        repo = Path(__file__).resolve().parent.parent
        script = repo / "build_wiki.py"
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            shutil.copytree(FIX, td / "wiki")
            (td / "data").mkdir()
            shutil.copy(FIX.parent / "mini_profile.json",
                        td / "data" / "zogzork_profile.json")
            (td / "wiki" / "personnages" / "zogzork.md").write_text(
                "---\nresume: PJ orc enqueteur\ntags: [pj]\n---\n\n# ZogZork\n\n"
                "Narratif court, lie a [[Neros]].\n\n## Fiche technique\n{{fiche_technique}}\n",
                encoding="utf-8")
            t0 = time.time()
            proc = subprocess.run([sys.executable, str(script), "--root", str(td)],
                                  capture_output=True, text=True)
            dt = time.time() - t0
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((td / "wiki.html").is_file())
            self.assertTrue((td / "wiki_partage.html").is_file())
            html = (td / "wiki.html").read_text(encoding="utf-8")
            self.assertIn("RD 32 (18)", html)
            self.assertLess(dt, 2.0)

class TestUnderscore(unittest.TestCase):
    def test_fichiers_underscore_ignores(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "w"
            shutil.copytree(FIX, d)
            (d / "sessions" / "_template.md").write_text(
                "---\nresume: gabarit\n---\n\n# Template\n", encoding="utf-8")
            slugs = {f["slug"] for f in load_fiches(d)}
            self.assertNotIn("_template", slugs)
            self.assertIn("session-21", slugs)


class TestImages(unittest.TestCase):
    PNG_1PX = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
               "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")

    def test_registre_dedup(self):
        import base64
        import build_wiki as bw
        bw.IMG_REGISTRY.clear()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "img").mkdir()
            (root / "img" / "x.png").write_bytes(base64.b64decode(self.PNG_1PX))
            t1 = bw.img_ref(root, "img/x.png", alt="a")
            t2 = bw.img_ref(root, "img/x.png", alt="b")
            self.assertIn('data-img="img/x.png"', t1)
            self.assertNotIn("base64", t1 + t2)        # pas de data URI inline
            self.assertEqual(len(bw.IMG_REGISTRY), 1)  # une seule copie embarquee
            self.assertEqual(bw.img_ref(root, "img/absente.png"), "")

    def test_imgdata_injecte(self):
        fiches = load_fiches(FIX)
        resolver, conflicts = build_resolver(fiches)
        out, _ = build_html(fiches, resolver, conflicts, FIX, share=False, profile=None)
        self.assertIn("var IMGS=", out)
        self.assertNotIn("__IMGDATA__", out)


class TestReviewFixes(unittest.TestCase):
    def setUp(self):
        self.fiches = load_fiches(FIX)
        self.resolver, self.conflicts = build_resolver(self.fiches)
        self.full, _ = build_html(self.fiches, self.resolver, self.conflicts,
                                  FIX, share=False, profile=None)
        self.share, _ = build_html(self.fiches, self.resolver, self.conflicts,
                                   FIX, share=True, profile=None)

    # Fix 1 : blocs %% de questions.md / chronologie.md passent le pipeline prive
    def test_pages_speciales_pipeline_prive(self):
        self.assertIn("Note MJ privee", self.full)        # accueil, complet
        self.assertIn("periode secrete", self.full)       # chronologie, complet
        self.assertNotIn("Note MJ privee", self.share)
        self.assertNotIn("periode secrete", self.share)
        self.assertNotIn("%%", self.share)

    # Fix 10 : plus de <p><div> parasite
    def test_pas_de_p_div(self):
        self.assertNotIn("<p><div", self.full)
        self.assertNotIn("<p><div", self.share)

    # Fix 9 : backlink vers un slug special resout vers sa page generee
    def test_backlink_special_slug(self):
        self.assertNotIn('href="#questions"', self.full)
        self.assertNotIn('href="#questions"', self.share)

    # Fix 12 : la recherche echappe title/type avant innerHTML
    def test_recherche_js_echappe(self):
        self.assertIn("function esc(", self.full)
        self.assertIn("esc(h.e.title)", self.full)

    # Fix 14 : un placeholder litteral dans un corps de fiche survit
    def test_placeholder_litteral_preserve(self):
        fiches = [{"slug": "doc", "title": "Doc", "meta": {"resume": "x"},
                   "body": "# Doc\n\nLe jeton __IMGDATA__ reste litteral.",
                   "reldir": "concepts", "mtime": 0}]
        resolver, conflicts = build_resolver(fiches)
        out, _ = build_html(fiches, resolver, conflicts, FIX, share=False, profile=None)
        self.assertIn("__IMGDATA__", out)

    # Fix 15 : _js_json neutralise </ pour ne pas casser le bloc <script>
    def test_js_json_echappe_slash(self):
        self.assertNotIn("</", _js_json({"img</script>/p.png": "data:image/png;base64,AAA"}))
        self.assertIn("<\\/", _js_json({"a</b": "x"}))

    # Fix 16 : nav mobile en une ligne scrollable
    def test_nav_mobile_scrollable(self):
        self.assertIn("flex-wrap:nowrap", self.full)

    # Fix 17 : un clic sur un resultat ferme l'overlay
    def test_recherche_clic_ferme(self):
        self.assertIn("sres.addEventListener('click'", self.full)

    # Fix 18 : le H1 d'ouverture du corps est retire (render_section porte le titre)
    def test_h1_unique_par_fiche(self):
        neros = self.full.split('id="p-neros"')[1].split("</section>")[0]
        self.assertEqual(neros.count("<h1"), 1)

    # Fix 18 : un H1 en milieu de corps reste rendu
    def test_h1_milieu_corps_conserve(self):
        fiches = [{"slug": "x", "title": "X", "meta": {"resume": "r"},
                   "body": "# X\n\nIntro.\n\n# Sous-titre\n\nTexte.",
                   "reldir": "concepts", "mtime": 0}]
        resolver, conflicts = build_resolver(fiches)
        out, _ = build_html(fiches, resolver, conflicts, FIX, share=False, profile=None)
        sec = out.split('id="p-x"')[1].split("</section>")[0]
        self.assertEqual(sec.count("<h1>X</h1>"), 1)     # titre non duplique
        self.assertIn("<h1>Sous-titre</h1>", sec)        # H1 en milieu conserve

    # Fix 2 : %% non ferme fait echouer le build, aucune sortie ecrite
    def test_pourcent_non_ferme_fail_closed(self):
        repo = Path(__file__).resolve().parent.parent
        script = repo / "build_wiki.py"
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            shutil.copytree(FIX, td / "wiki")
            (td / "wiki" / "affaires" / "oubli.md").write_text(
                "---\nresume: x\n---\n\n# Oubli\n\n%%secret non ferme\n", encoding="utf-8")
            sentinel = "SENTINEL-INTACT"
            (td / "wiki_partage.html").write_text(sentinel, encoding="utf-8")
            proc = subprocess.run([sys.executable, str(script), "--root", str(td)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertEqual((td / "wiki_partage.html").read_text(encoding="utf-8"), sentinel)
            self.assertFalse((td / "wiki.html").is_file())


class TestRelations(unittest.TestCase):
    def test_relations_typees(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "w"
            shutil.copytree(FIX, d)
            p = d / "personnages" / "neros.md"
            p.write_text(p.read_text(encoding="utf-8").replace(
                "tags: [magie]",
                'tags: [magie]\nrelations:\n  Conseiller de: "[[La Fleche]]"'),
                encoding="utf-8")
            fiches = load_fiches(d)
            resolver, conflicts = build_resolver(fiches)
            # La relation compte comme un lien (backlink + arete de Toile)
            _, back, _ = collect_links(fiches, resolver, include_private=True)
            self.assertIn("neros", back["la-fleche"])
            out, _ = build_html(fiches, resolver, conflicts, d, share=False, profile=None)
            neros = out.split('id="p-neros"')[1].split("</section>")[0]
            self.assertIn("Conseiller de", neros)          # ligne d'infobox cote source
            fleche = out.split('id="p-la-fleche"')[1].split("</section>")[0]
            self.assertIn("Relations :", fleche)           # bloc entrant cote cible
            self.assertIn("(Conseiller de)", fleche)
            # pas de doublon : Neros dans Relations, PAS dans Mentionne dans
            import re
            rel = re.search(r'class="relations-in">(.*?)</div>', fleche, re.S)
            self.assertIn('href="#neros"', rel.group(1))
            back = re.search(r'class="backlinks">(.*?)</div>', fleche, re.S)
            if back:
                self.assertNotIn('href="#neros"', back.group(1))

    def test_relations_source_privee_masquee_en_partage(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "w"
            shutil.copytree(FIX, d)
            p = d / "personnages" / "secret.md"
            p.write_text(p.read_text(encoding="utf-8").replace(
                "prive: true",
                'prive: true\nrelations:\n  Informateur de: "[[Neros]]"'),
                encoding="utf-8")
            fiches = load_fiches(d)
            resolver, conflicts = build_resolver(fiches)
            share, _ = build_html(fiches, resolver, conflicts, d, share=True, profile=None)
            neros = share.split('id="p-neros"')[1].split("</section>")[0]
            self.assertNotIn("Informateur de", neros)


class TestGuardPrive(unittest.TestCase):
    SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "guard_prive.sh"

    def _run(self, d):
        return subprocess.run(["bash", str(self.SCRIPT), str(d)],
                              capture_output=True, text=True)

    def test_refuse_prive_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "a.md").write_text("---\nresume: x\nprive: true\n---\n\n# A\n",
                                    encoding="utf-8")
            r = self._run(d)
            self.assertEqual(r.returncode, 1)
            self.assertIn("a.md", r.stderr)
            self.assertIn("PUBLIC", r.stderr)

    def test_refuse_bloc_pourcent(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "b.md").write_text("---\nresume: x\n---\n\n# B\n\n%%secret%%\n",
                                    encoding="utf-8")
            self.assertEqual(self._run(d).returncode, 1)

    def test_passe_sur_corpus_reel(self):
        r = self._run(Path(__file__).resolve().parent.parent / "wiki")
        self.assertEqual(r.returncode, 0, r.stderr)


class TestDatesGit(unittest.TestCase):
    def test_git_dates_repo(self):
        from build_wiki import git_dates
        repo = Path(__file__).resolve().parent.parent
        newest, oldest = git_dates(repo)
        self.assertTrue(newest)          # le repo a des commits
        k = next(iter(newest))
        self.assertLessEqual(oldest[k], newest[k])

    def test_git_dates_suit_les_renames(self):
        # Un fichier renomme garde la date de creation de son ancien nom.
        from build_wiki import git_dates
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                   "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                   "GIT_AUTHOR_DATE": "2026-01-01T00:00:00", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00",
                   "PATH": os.environ.get("PATH", "")}
            def git(*a, **kw):
                e = dict(env); e.update(kw.get("env_extra", {}))
                subprocess.run(["git", "-C", str(d)] + list(a), check=True,
                               capture_output=True, env=e)
            git("init", "-q")
            (d / "a.md").write_text("x", encoding="utf-8")
            git("add", "a.md"); git("commit", "-qm", "creation")
            git("mv", "a.md", "b.md")
            git("commit", "-qm", "rename",
                env_extra={"GIT_AUTHOR_DATE": "2026-06-01T00:00:00",
                           "GIT_COMMITTER_DATE": "2026-06-01T00:00:00"})
            newest, oldest = git_dates(d)
            self.assertIn("b.md", oldest)
            self.assertLess(oldest["b.md"], newest["b.md"])   # creation < rename

    def test_git_dates_sans_git(self):
        from build_wiki import git_dates
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(git_dates(Path(tmp)), ({}, {}))


class TestToile(unittest.TestCase):
    def test_graph_data(self):
        from build_wiki import graph_data
        fiches = [
            {"slug": "neros", "title": "Neros", "reldir": "personnages"},
            {"slug": "simpol", "title": "Simpol", "reldir": "lieux"},
            {"slug": "canas", "title": "Canas", "reldir": "objets"},
        ]
        links_out = {"neros": {"simpol"}, "simpol": {"neros"}, "canas": set()}
        g = graph_data(fiches, links_out)
        self.assertEqual(len(g["nodes"]), 3)
        self.assertEqual(g["links"], [(0, 1)])   # dedupliquee, non orientee
        self.assertEqual(g["nodes"][0]["g"], "personnages")
        self.assertIn("personnages", g["colors"])

    def test_toile_dans_la_page(self):
        fiches = load_fiches(FIX)
        resolver, conflicts = build_resolver(fiches)
        out, _ = build_html(fiches, resolver, conflicts, FIX, share=False, profile=None)
        self.assertIn('id="p-toile"', out)
        self.assertIn("var GRAPH=", out)
        self.assertIn('<canvas id="toile">', out)
        self.assertIn("tchip", out)
        self.assertNotIn("__GRAPHDATA__", out)


class TestH1Unique(unittest.TestCase):
    def test_h1_unique_et_h1_median_conserve(self):
        # Le H1 d'ouverture du corps ne doit pas doubler celui de render_section ;
        # un H1 en milieu de corps reste rendu.
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "w"
            shutil.copytree(FIX, d)
            p = d / "personnages" / "neros.md"
            p.write_text(p.read_text(encoding="utf-8")
                         + "\n# Chapitre tardif\n\nSuite.\n", encoding="utf-8")
            fiches = load_fiches(d)
            resolver, conflicts = build_resolver(fiches)
            out, _ = build_html(fiches, resolver, conflicts, d,
                                share=False, profile=None)
            sec = out.split('id="p-neros"')[1].split("</section>")[0]
            self.assertEqual(sec.count("<h1"), 2)
            self.assertIn("Chapitre tardif", sec)


if __name__ == "__main__":
    unittest.main()
