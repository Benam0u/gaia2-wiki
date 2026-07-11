import json, sys, unittest
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

if __name__ == "__main__":
    unittest.main()
