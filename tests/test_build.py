import re
import unittest
from datetime import datetime

import helpers
from baiakvault import build, html

FORBIDDEN = re.compile(r"\b(None|nan|NaN|undefined|null)\b")
MAX_PAGE_BYTES = 200 * 1024
MAX_SECONDS = 5.0
NOW = datetime(2026, 9, 16, 12, 0, 0)


def _pages(result):
    return [p for p in result["files"] if p.suffix == ".html"]


def _local_links(text):
    return [m.split("#", 1)[0] for m in re.findall(r'href="([^"]+)"', text)
            if not m.startswith(("http://", "https://", "#"))]


class BuildEmptyVault(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = helpers.temp_dir() / "site"
        db_path = helpers.temp_dir() / "vault.db"
        cls.result = build.build(cls.out, db_path, helpers.ROOT / "data" / "catalogo", now=NOW,
                                 plans=helpers.planner()[1])

    def test_pages_exist(self):
        for rel in ("index.html", "hunts/index.html", "charms/index.html",
                    "hunts/cobra-cave.html", "estilo.css", ".nojekyll"):
            self.assertTrue((self.out / rel).is_file(), rel)
        self.assertEqual(len([p for p in self.result["files"] if p.parent.name == "hunts"]), 80)

    def test_every_page_has_a_title_and_the_stylesheet(self):
        for page in _pages(self.result):
            text = page.read_text(encoding="utf-8")
            self.assertRegex(text, r"<title>[^<]*BaiakVault</title>", page)
            self.assertIn('<meta name="viewport"', text, page)
            # os cartoes de print sao de proposito autonomos (fundo branco, 390 px, CSS embutido)
            if page.parent.name != "print":
                self.assertIn("estilo.css", text, page)

    def test_no_none_nan_undefined_anywhere(self):
        for page in _pages(self.result):
            text = page.read_text(encoding="utf-8")
            m = FORBIDDEN.search(text)
            self.assertIsNone(m, "%s: %r perto de %r" % (page, m and m.group(0),
                                                         m and text[max(0, m.start()-60):m.end()+20]))

    def test_pages_are_small_and_fast(self):
        for page in _pages(self.result):
            self.assertLess(page.stat().st_size, MAX_PAGE_BYTES, page)
        self.assertLess(self.result["seconds"], MAX_SECONDS)

    def test_empty_vault_says_so(self):
        text = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertIn("Ainda nao ha personagens", text)
        self.assertIn("2026-09-16 12:00:00", text)
        self.assertFalse((self.out / "personagens").exists())

    def test_hunts_index_warns_about_indices(self):
        text = (self.out / "hunts" / "index.html").read_text(encoding="utf-8")
        self.assertIn("eficiencia, nao XP/h", text)
        self.assertEqual(text.count('<a href="') - 4, 79)  # 4 do menu + 79 hunts

    def test_charms_page_has_all_24(self):
        text = (self.out / "charms" / "index.html").read_text(encoding="utf-8")
        for name in ("Wound", "Divine Wrath", "Cripple", "Void Inversion", "Savage Blow"):
            self.assertIn(name, text)
        self.assertIn("Os charms dele", text)

    def test_hunt_page_unknowns_are_question_marks(self):
        text = (self.out / "hunts" / "cobra-cave.html").read_text(encoding="utf-8")
        self.assertIn("XP/h", text)
        self.assertIn("so medindo na conta", text)
        self.assertIn("Cobra Vizier", text)
        self.assertIn("ICzhKPFcZWE", text)

    def test_local_links_resolve(self):
        for page in _pages(self.result):
            text = page.read_text(encoding="utf-8")
            for href in _local_links(text):
                target = (page.parent / href).resolve()
                self.assertTrue(target.is_file(), "%s -> %s" % (page, href))


class BuildWithCharacter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn, vault, db_path = helpers.temp_vault(with_fixture=True)
        conn.close()
        cls.out = helpers.temp_dir() / "site"
        cls.result = build.build(cls.out, db_path, helpers.ROOT / "data" / "catalogo", now=NOW,
                                 plans=helpers.planner()[1])

    def test_character_page_exists_and_index_links_to_it(self):
        page = self.out / "personagens" / "teste-knight.html"
        self.assertTrue(page.is_file())
        index = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertIn("personagens/teste-knight.html", index)
        self.assertIn("Teste Knight", index)
        self.assertNotIn("Ainda nao ha personagens", index)

    def test_character_page_shows_data_and_question_marks(self):
        text = (self.out / "personagens" / "teste-knight.html").read_text(encoding="utf-8")
        self.assertIn("Knight (EK)", text)
        self.assertIn("312", text)
        self.assertIn("Cobras", text)
        self.assertIn("Fury", text)
        self.assertIn("eldritch tome", text)
        self.assertIn("Wound", text)
        self.assertIn("Cobra Vizier", text)
        self.assertIn("500.000.000", text)
        # pontos gastos e desconhecido na fixture: sai «?», nao 0
        self.assertRegex(text, r"<dt>pontos gastos</dt><dd>\?</dd>")

    def test_no_none_anywhere(self):
        for page in _pages(self.result):
            text = page.read_text(encoding="utf-8")
            self.assertIsNone(FORBIDDEN.search(text), page)

    def test_local_links_resolve(self):
        for page in _pages(self.result):
            for href in _local_links(page.read_text(encoding="utf-8")):
                self.assertTrue((page.parent / href).resolve().is_file(), "%s -> %s" % (page, href))

    def test_size_and_time(self):
        for page in _pages(self.result):
            self.assertLess(page.stat().st_size, MAX_PAGE_BYTES, page)
        self.assertLess(self.result["seconds"], MAX_SECONDS)


class Formatting(unittest.TestCase):
    def test_none_is_question_mark(self):
        self.assertEqual(html.fmt(None), "?")
        self.assertEqual(html.esc(None), "?")
        self.assertEqual(html.kk(None), "?")
        self.assertEqual(html.yes_no(None), "?")
        self.assertEqual(html.pct_of_100k(None), "?")
        self.assertEqual(html.fmt(float("nan")), "?")

    def test_numbers_in_portuguese(self):
        self.assertEqual(html.fmt(1234567), "1.234.567")
        self.assertEqual(html.fmt(1234.5, 1), "1.234,5")
        self.assertEqual(html.kk(30_000_000), "30,00 kk")
        self.assertEqual(html.kk(1300), "1,3 k")
        self.assertEqual(html.pct_of_100k(4760), "4,76%")

    def test_escape(self):
        self.assertEqual(html.esc('<a href="x">&'), "&lt;a href=&quot;x&quot;&gt;&amp;")

    def test_gold_expected_is_the_games_formula(self):
        self.assertAlmostEqual(build.gold_expected({"chance_por_100k": 50000, "max": 3, "preco_npc": 100}), 100.0)
        self.assertIsNone(build.gold_expected({"chance_por_100k": 50000, "max": 3}))
        self.assertIsNone(build.gold_expected(None))


if __name__ == "__main__":
    unittest.main()
