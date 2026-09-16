"""A validacao cruzada (`validation.py` + `pages_builds.validation_markdown`):
as contas a mao, feitas so com os JSON, batem com o simulador no perfil de
referencia; e a pagina gerada mostra as tres seccoes sem esconder diferencas."""
import re
import unittest
from pathlib import Path

import helpers
from baiakvault import pages_builds, validation

FORBIDDEN = re.compile(r"\b(None|nan|NaN|undefined|null)\b")


class HandVsEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = helpers.real_catalog()
        cls.rows = pages_builds.validation_rows(cls.cat)

    def test_hand_calculation_is_independent_of_the_engine(self):
        # a garantia de independencia: o modulo nao importa formulas.py nem sim.py nem builds.py
        src = (Path(validation.__file__)).read_text(encoding="utf-8")
        for name in ("formulas", "sim", "builds", "pages_builds"):
            self.assertNotRegex(src, r"^\s*(from \. import %s\b|import baiakvault\.%s\b|from \.%s\b)" % (name, name, name))

    def test_every_number_within_tolerance(self):
        self.assertEqual(len(self.rows), len(validation.LABELS))
        for key, label, hand, engine, diff, ok in self.rows:
            self.assertIsNotNone(hand, key)
            self.assertIsNotNone(engine, key)
            self.assertTrue(ok, "%s: a mao %s, simulador %s (%s %%)" % (label, hand, engine, diff))

    def test_hand_numbers_match_the_page_of_2026_09_16(self):
        # os numeros que builds/sorcerer-damage.html publicava ao nivel 50 a 16/09/2026
        hand = dict((k, a) for k, _, a, _, _, _ in self.rows)
        self.assertEqual(round(hand["heal_per_cast"]), 446)
        self.assertEqual(hand["tree_points"], 50)
        self.assertEqual(round(hand["hp_max"]), 350)
        self.assertEqual(round(hand["mana_max"]), 1622)
        self.assertEqual(round(hand["dps_pack"]), 487)
        self.assertEqual(round(hand["dps_boss"]), 168)
        self.assertEqual(round(hand["dps_cycle"]), 427)

    def test_compare_flags_a_difference_instead_of_hiding_it(self):
        hand = validation.hand_calculation(self.cat)
        wrong = dict(pages_builds.engine_numbers(self.cat))
        wrong["dps_cycle"] *= 1.05
        rows = validation.compare(hand, wrong)
        bad = [r for r in rows if not r[5]]
        self.assertEqual([r[0] for r in bad], ["dps_cycle"])
        md = pages_builds.validation_markdown(self.cat, {}, rows)
        self.assertIn("DIFERENTE", md)
        self.assertIn("fora da tolerancia", md)

    def test_markdown_has_the_three_sections_and_the_guide_curve(self):
        _, plans = helpers.planner()
        md = pages_builds.validation_markdown(self.cat, plans)
        self.assertIn("## 1. Contas a mao vs simulador", md)
        self.assertIn("## 2. A curva de DPS do guia", md)
        self.assertIn("## 3. Onde o guia e o cliente discordam", md)
        self.assertIn("Tudo dentro da tolerancia", md)
        self.assertNotIn("DIFERENTE", md)
        self.assertNotIn("por preencher", md)
        # uma linha por build e nivel, com a curva do guia ao lado
        self.assertEqual(md.count("| x"), 64)
        self.assertAlmostEqual(validation.guide_dps(100), 7.012 * 100 ** 0.948, places=6)
        self.assertIsNone(FORBIDDEN.search(md))
        html = pages_builds.render_validation(md, "2026-09-16 12:00:00")
        self.assertIn("<table>", html)
        self.assertIsNone(FORBIDDEN.search(html))


if __name__ == "__main__":
    unittest.main()
