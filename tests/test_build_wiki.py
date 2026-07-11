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
