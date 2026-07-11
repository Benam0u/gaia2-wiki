import json, shutil, subprocess, sys, tempfile, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from build_wiki import (parse_frontmatter, slugify, norm_key, md_convert,
                        load_fiches, build_resolver, collect_links,
                        extract_private, render_private,
                        render_infobox, render_badges, render_fiche_technique,
                        TYPE_LABELS, build_html)

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
        self.assertIn('href="#secret"', self.full)
        self.assertNotIn('href="#secret"', self.share)

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
            self.assertIn("RD max 32", html)
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


if __name__ == "__main__":
    unittest.main()
