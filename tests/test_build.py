import re
import unittest
from datetime import datetime

import helpers
from baiakvault import build, html

FORBIDDEN = re.compile(r"\b(None|nan|NaN|undefined|null)\b")
# 256 KiB desde a ordem 8 (16/09/2026): as paginas das builds passaram de ~187 para ~228 KB com o
# papel de cada no na ordem de compra, o codigo de build e a validacao do cliente nos 8 niveis
# 320 KiB desde a ordem 10 (21/09/2026): o bloco «Depois do Avatar: o que rende mais» em cada um
# dos 8 niveis pos a sorcerer-priority.html a 267 KB (era 256 KiB desde a 8b)
MAX_PAGE_BYTES = 320 * 1024
# 30 s desde a ordem 8 (16/09/2026): o plano do personagem avalia tambem o caminho da «best» na
# hunt dele, e um caminho a frio custa ate ~16 s (o «poupar para um notable»); com o Planner
# quente (o serve guarda-o em memoria) o mesmo build leva ~1,5 s — medido em _tempo_8b.py
MAX_SECONDS = 30.0
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
                                 planner=helpers.planner()[0], plans=helpers.planner()[1])

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
        # diz como adicionar hoje (modo de edicao e capturas), nao «chega na ordem N»
        self.assertNotIn("chega na ordem", text)
        self.assertIn("/editar", text)
        self.assertIn("baiakvault-leitura", text)

    def test_hunts_index_warns_about_indices(self):
        text = (self.out / "hunts" / "index.html").read_text(encoding="utf-8")
        self.assertIn("eficiencia, nao XP/h", text)
        self.assertEqual(text.count('<a href="') - 4, 79)  # 4 do menu + 79 hunts

    def test_charms_page_has_all_24(self):
        text = (self.out / "charms" / "index.html").read_text(encoding="utf-8")
        for name in ("Wound", "Divine Wrath", "Cripple", "Void Inversion", "Savage Blow"):
            self.assertIn(name, text)
        self.assertIn("Os teus charms", text)
        self.assertIn('href="regras.html"', text)
        self.assertTrue((self.out / "charms" / "regras.html").is_file())
        # a hunt sem personagens fica com o tecto (todos os charms) e a ligacao as regras
        hunt = (self.out / "hunts" / "cobra-cave.html").read_text(encoding="utf-8")
        self.assertIn("Charms para esta hunt", hunt)
        self.assertIn("Tecto", hunt)
        self.assertIn("Cobra Vizier", hunt)

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
                                 planner=helpers.planner()[0], plans=helpers.planner()[1])

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

    def test_charms_per_hunt_on_character_hunt_and_print(self):
        text = (self.out / "personagens" / "teste-knight.html").read_text(encoding="utf-8")
        self.assertIn("Charms por hunt", text)
        self.assertIn("Hunt actual: Cobras", text)
        self.assertIn("Hunts vizinhas em nivel", text)
        hunt = (self.out / "hunts" / "cobra-cave.html").read_text(encoding="utf-8")
        self.assertIn("Teste Knight", hunt)
        self.assertIn("O que mudar", hunt)
        # cartoes: a hunt actual + 5 vizinhas, e mais nenhum
        cards = sorted(p.name for p in (self.out / "print").glob("charms-teste-knight-*.html"))
        self.assertEqual(len(cards), 1 + build.PRINT_NEIGHBOURS, cards)
        self.assertIn("charms-teste-knight-cobra-cave.html", cards)
        card = (self.out / "print" / "charms-teste-knight-cobra-cave.html").read_text(encoding="utf-8")
        self.assertIn("width:390px", card)
        self.assertNotIn("<nav", card)
        self.assertIn("Dodge", card)
        # a pagina da build ganha os charms por nivel (tecto)
        text = (self.out / "builds" / "knight-tank.html").read_text(encoding="utf-8")
        self.assertIn("Charms recomendados em", text)

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


class PruneStalePages(unittest.TestCase):
    def test_deleted_character_pages_and_cards_leave_docs(self):
        conn, vault, db_path = helpers.temp_vault(with_fixture=True)
        out = helpers.temp_dir() / "site"
        planner, plans = helpers.planner()
        build.build(out, db_path, helpers.ROOT / "data" / "catalogo", now=NOW, planner=planner, plans=plans)
        page = out / "personagens" / "teste-knight.html"
        self.assertTrue(page.is_file())
        cards = list((out / "print").glob("charms-teste-knight-*.html"))
        self.assertTrue(cards)
        # um ficheiro que nao e do gerador (fora das pastas dele) fica em paz
        stranger = out / "notas.txt"
        stranger.write_text("do Andre", encoding="utf-8")
        vault.delete_character(vault.character("teste-knight")["id"])
        conn.close()
        result = build.build(out, db_path, helpers.ROOT / "data" / "catalogo", now=NOW, planner=planner,
                             plans=plans, with_builds=False)
        self.assertFalse(page.exists())
        self.assertEqual(list((out / "print").glob("charms-teste-knight-*.html")), [])
        # o cartao do Helper do personagem (ordem 8) e dele: vai com ele, mesmo sem as builds
        self.assertEqual(sorted(p.name for p in result["removed"]),
                         sorted(["teste-knight.html", "helper-personagem-teste-knight.html"] + [c.name for c in cards]))
        self.assertTrue(stranger.is_file())
        # sem as builds nao se mexe nas paginas das builds nem nos cartoes do Helper
        self.assertTrue((out / "builds" / "knight-tank.html").is_file())
        self.assertTrue(list((out / "print").glob("helper-*.html")))


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
