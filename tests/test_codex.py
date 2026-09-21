"""O Codex do cliente a letra (ordem 11, 21/09/2026): o hash, os bonus digito a digito (os que o
supervisor fez a mao e os dois que o Andre confirmou no ecra), a soma = B5e, a numeracao, o custo em
kills, e a tabela `codex_progress` (v7) pelo Vault."""
import unittest

from baiakvault import codex, db
from tests import helpers


class Hash(unittest.TestCase):
    def test_fnv1a_lands_on_the_supervisor_triples(self):
        # `hunt:livrariafire-cave` cai em _5e[2], cobra em [3], gazer em [4], trueazura em [1]
        self.assertEqual(codex.fnv1a("hunt:livrariafire-cave") % 6, 2)
        self.assertEqual(codex.fnv1a("hunt:cobra-cave") % 6, 3)
        self.assertEqual(codex.fnv1a("hunt:gazer-lair") % 6, 4)
        self.assertEqual(codex.fnv1a("hunt:trueazura-cave") % 6, 1)
        self.assertEqual(codex.fnv1a(""), 2166136261)   # o offset: string vazia nao mexe

    def test_triples(self):
        self.assertEqual([s["id"] for s in codex.triple_for("hunt:livrariafire-cave", None, 500)],
                         ["spellDmgPct", "atkPct", "manaPct"])
        self.assertEqual([s["id"] for s in codex.triple_for("boss:alptramun", "ice", 0)],
                         ["absorbPct.ice", "elementDmgPct.ice", "critDmg"])
        # abaixo de 150 a tabela e a utilitaria (4 triplos)
        self.assertIn(codex.triple_for("hunt:troll-cave", None, 1), codex.UTILITY_TRIPLES)


class Bonuses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cx = codex.Codex(helpers.real_catalog())

    def test_entries_and_weights(self):
        self.assertEqual(len(self.cx.entries), 174)   # 95 bosses + 79 hunts
        lq = self.cx.lq
        for key, value in {"atkPct": 0.039, "spellDmgPct": 0.109, "critChance": 0.026, "critDmg": 0.137, "hpPct": 0.643,
                           "manaPct": 0.503, "elementDmgPct.ice": 1.25, "absorbPct.ice": 1.111, "elementDmgPct.energy": 0.5,
                           "elementDmgPct.physical": 0.417, "elementDmgPct.holy": 0.625}.items():
            self.assertAlmostEqual(lq[key], value, places=3, msg=key)

    def test_bonuses_digit_by_digit(self):
        m = self.cx.mission
        # confirmados no ecra do Andre (21/09/2026): #130 e #131
        self.assertEqual(m("hunt-livrariafire-cave")["number"], 130)
        self.assertEqual(m("hunt-livrariafire-cave-2")["number"], 131)
        self.assertEqual(codex.format_bonus_line(m("hunt-livrariafire-cave")["bonus"]), "Dano de magia +0,654%")
        self.assertEqual(codex.format_bonus_line(m("hunt-livrariafire-cave-2")["bonus"]), "Dano de magia +0,654% · Ataque +0,233%")
        self.assertEqual(m("hunt-livrariafire-cave-3")["bonus"], {"spellDmgPct": 0.654, "atkPct": 0.233, "manaPct": 3.017})
        self.assertEqual(m("hunt-cobra-cave")["bonus"], {"critDmg": 0.397})
        self.assertEqual(m("hunt-gazer-lair-2")["bonus"], {"atkPct": 0.175, "critDmg": 0.616})
        self.assertEqual(m("hunt-livraria-cave-3")["bonus"], {"atkPct": 0.233, "critDmg": 0.822, "hpPct": 3.858})
        self.assertEqual(m("hunt-livrariaice-cave-3")["bonus"], {"critChance": 0.157, "critDmg": 0.822, "onslaught": 0.53})
        self.assertEqual(m("boss-alptramun-3")["bonus"], {"absorbPct": {"ice": 1.111}, "elementDmgPct": {"ice": 1.25}, "critDmg": 0.137})
        self.assertEqual(m("boss-ahau-3")["bonus"], {"absorbPct": {"energy": 0.444}, "elementDmgPct": {"energy": 0.5}, "critDmg": 0.137})
        self.assertEqual(codex.format_bonus_line(m("boss-alptramun-2")["bonus"]),
                         "Resistência elemental ice +1,111% · Dano elemental ice +1,250%")
        # o II pede 5x e o III 15x a lista (1.400 -> 7.000, 100 -> 500 no ecra dele)
        self.assertEqual(m("hunt-livrariafire-cave-2")["req"][0], {"item": "orb", "qty": 7000})
        self.assertEqual(m("hunt-livrariafire-cave-2")["req"][-1], {"item": "piece of hellfire armor", "qty": 500})
        self.assertEqual(m("hunt-livrariafire-cave-3")["req"][0]["qty"], 21000)
        # o gold dos degraus: o II confirmado pelo Andre (50 M)
        self.assertEqual([m("hunt-livrariafire-cave" + s)["unlock_gold"] for s in ("", "-2", "-3")], [0, 5e7, 5e8])
        self.assertEqual(m("set-soul-w-3")["unlock_gold"], 1e9)
        # sets: base x G5e[tier] x U5e (armas), spellDmgPct ainda x Q5e; armaduras x V5e
        self.assertEqual(m("set-soul-w-3")["bonus"], {"atkPct": 3.15, "spellDmgPct": 1.575})
        self.assertEqual(m("set-leather-0")["bonus"], {"armorFlat": 0.035})
        self.assertEqual(m("set-knight-1")["req"][0], {"item": "steel helmet", "qty": 1, "tier": 1})
        self.assertEqual(m("set-knight-2")["name"], "Set Knight (Raro)")

    def test_sum_is_the_budget(self):
        total = self.cx.total_budget()
        for key, value in codex.BUDGET.items():
            self.assertAlmostEqual(total.get(key, 0.0), value, delta=0.05, msg=key)

    def test_counts_and_numbering(self):
        ms = self.cx.missions()
        n_sets = len(codex.GEAR_SETS)
        self.assertEqual(n_sets, 41)
        self.assertEqual(len(ms), 79 * 3 + 95 * 3 + n_sets * 4)
        self.assertEqual([m["number"] for m in ms], list(range(1, len(ms) + 1)))
        self.assertEqual(len({m["id"] for m in ms}), len(ms))
        self.assertEqual(ms[0]["id"], "hunt-troll-cave")
        self.assertEqual(ms[79 * 3]["id"], "boss-ahau-1")
        self.assertEqual(ms[-1]["id"], "set-glooth-w-3")

    def test_item_matches_t4e(self):
        req = {"item": "orb", "qty": 1}
        self.assertTrue(codex.item_matches(req, "orb"))
        self.assertFalse(codex.item_matches(req, "orb", item_tier=1))   # forjado nunca serve uma hunt
        self.assertFalse(codex.item_matches(req, "purple tome"))
        self.assertTrue(codex.item_matches({"item": "steel helmet", "qty": 1, "tier": 1}, "steel helmet", 1))
        self.assertFalse(codex.item_matches({"item": "steel helmet", "qty": 1, "tier": 1}, "steel helmet", 0))
        self.assertTrue(codex.item_matches({"item": "x", "anyOf": ["a", "b"], "anyTier": True}, "b", 3))
        self.assertFalse(codex.item_matches({"item": "x", "anyOf": ["a", "b"], "anyTier": True}, "b", 4))
        self.assertFalse(codex.item_matches({"item": "x", "minUp": 5}, "x", 0, 4))

    def test_kills_needed(self):
        kn = self.cx.kills_needed("livrariafire-cave", 0)
        self.assertEqual(kn["bottleneck"], "purple tome")
        self.assertAlmostEqual(kn["kills"], 44213, delta=1)
        self.assertEqual(kn["unknown"], [])
        # com o progresso da captura dele (FIRE II): faltam ~2.900 purple tomes -> ~183 k kills
        progress = [7000, 3500, 3059, 3500, 852, 599, 956, 1375, 901, 840, 627, 1375, 579, 573, 178]
        kn2 = self.cx.kills_needed("livrariafire-cave", 1, progress)
        self.assertEqual(kn2["bottleneck"], "purple tome")
        self.assertAlmostEqual(kn2["kills"], 183231, delta=1)
        self.assertFalse(kn2["complete"])
        self.assertTrue(self.cx.kills_needed("livrariafire-cave", 1, [r["qty"] for r in self.cx.mission("hunt-livrariafire-cave-2")["req"]])["complete"])
        self.assertIsNone(self.cx.kills_needed("nao-existe", 0))

    def test_kills_needed_unknown_drop_is_not_zero(self):
        # um catalogo de teste: uma hunt com dois monstros, um item sem drop conhecido
        class Cat:
            hunts = [{"id": "h", "nome": "H", "nivel_minimo": 200, "monstros": [{"chave": "a", "peso": 3}, {"chave": "b", "peso": 1}],
                      "codex_da_hunt": [{"item": "x", "qty": 100}, {"item": "y", "qty": 10}]}]
            hunt_by_id = {"h": hunts[0]}
            creature_by_key = {"a": {"nome": "A", "loot": [{"item": "x", "chance_por_100k": 10000, "max": 3}]},
                               "b": {"nome": "B", "loot": [{"item": "x", "chance_por_100k": 20000, "max": 1}]}}
            missions = []
        cx = codex.Codex(Cat())
        # taxa = 0,75 x 0,1 x 2 + 0,25 x 0,2 x 1 = 0,2 por kill -> 500 kills para 100
        self.assertAlmostEqual(cx.drop_rate("h", "x"), 0.2)
        kn = cx.kills_needed("h", 0)
        self.assertAlmostEqual(kn["kills"], 500)
        self.assertEqual(kn["unknown"], ["y"])
        self.assertIsNone(kn["rows"][1]["kills"])
        self.assertEqual(kn["mission_id"], "hunt-h")


class Progress(unittest.TestCase):
    def test_v7_and_set_codex_progress(self):
        conn, vault, _ = helpers.temp_vault()
        self.assertEqual(db.schema_version(conn), 7)
        with self.assertRaises(db.VaultError):
            vault.set_codex_progress("hunt-nao-existe", done=1)
        vault.set_codex_progress("hunt-livrariafire-cave", done=1, source="captura", seen_at="2026-09-21")
        progress = [7000, 3500, 3059, 3500, 852, 599, 956, 1375, 901, 840, 627, 1375, 579, 573, 178]
        vault.set_codex_progress("hunt-livrariafire-cave-2", progress=progress, source="captura", seen_at="2026-09-21")
        rows = vault.codex_progress()
        self.assertEqual(rows["hunt-livrariafire-cave"]["done"], 1)
        self.assertEqual(rows["hunt-livrariafire-cave"]["progress"][0], 1400)   # concluida sem contagens = as pedidas
        self.assertEqual(rows["hunt-livrariafire-cave-2"]["done"], 0)
        self.assertEqual(rows["hunt-livrariafire-cave-2"]["progress"], progress)
        # um campo a None nao apaga; done sobe quando as contagens fecham
        vault.set_codex_progress("hunt-livrariafire-cave-2", seen_at="2026-09-22")
        self.assertEqual(vault.codex_progress()["hunt-livrariafire-cave-2"]["progress"], progress)
        with self.assertRaises(db.VaultError):
            vault.set_codex_progress("hunt-livrariafire-cave-2", progress=[8000])   # mais do que pede
        with self.assertRaises(db.VaultError):
            vault.set_codex_progress("hunt-livrariafire-cave-2", progress=[1] * 16)
        with self.assertRaises(db.VaultError):
            vault.set_codex_progress("hunt-livrariafire-cave-2", done=2)
        self.assertEqual(db.check(conn, helpers.real_catalog()), [])
        vault.forget_codex_progress("hunt-livrariafire-cave-2")
        self.assertNotIn("hunt-livrariafire-cave-2", vault.codex_progress())
        conn.close()


class Pages(unittest.TestCase):
    """O plano com a fixture (1 personagem): valor, horas, XP perdida, paginas dentro dos tectos e sem
    None/nan/undefined; o `serve` grava o progresso pelo numero do ecra."""

    @classmethod
    def setUpClass(cls):
        import time
        from baiakvault import build, pages_codex
        cls.conn, cls.vault, cls.db_path = helpers.temp_vault(with_fixture=True)
        cls.vault.set_codex_progress("hunt-livrariafire-cave", done=1, source="captura", seen_at="2026-09-21")
        cls.vault.set_codex_progress("hunt-livrariafire-cave-2", progress=[7000, 3500, 3059], source="captura", seen_at="2026-09-21")
        planner, _ = helpers.planner()
        cat = helpers.real_catalog()
        chars = cls.vault.characters()
        advice = {c["slug"]: build.character_advice(cat, cls.vault, c, planner) for c in chars}
        started = time.perf_counter()
        cls.report = pages_codex.compute(cat, planner, chars, advice, cls.vault.codex_progress(), None)
        cls.seconds = time.perf_counter() - started
        cls.pages = {"index": pages_codex.render_index(cat, cls.report, "2026-09-21 15:00:00"),
                     "missoes": pages_codex.render_missions(cat, cls.report, "2026-09-21 15:00:00"),
                     "print": pages_codex.render_print(cat, cls.report, "2026-09-21 15:00:00")}

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_values_and_costs(self):
        r = self.report
        self.assertEqual(len(r["chars"]), 1)
        self.assertLess(self.seconds, 20.0)   # 79 hunts x 2 simulacoes por personagem
        by = r["by_id"]
        fire1, fire2 = by["hunt-livrariafire-cave"], by["hunt-livrariafire-cave-2"]
        self.assertEqual(fire1["status"], "concluida")
        self.assertEqual(fire2["status"], "em curso")
        self.assertGreater(fire2["value_pct"], 0)             # +0,654 % magia e +0,233 % atk rendem dano em qualquer vocacao
        self.assertEqual(fire2["bottleneck"], "purple tome")
        # a hunt ao alcance do personagem da horas e XP perdida; a de nivel 610 «ainda nao»
        level = r["party_level"]
        reachable = [x for x in r["missions"] if x["mission"]["cat"] == "hunt" and x["hunt"]["min_level"] <= level]
        self.assertTrue(all(x["hours"] is not None or x["status"] == "concluida" or x["unknown"] for x in reachable))
        far = [x for x in r["missions"] if x["mission"]["cat"] == "hunt" and x["hunt"]["min_level"] > level
               and x["status"] not in ("concluida", "em curso")]
        self.assertTrue(far)
        self.assertTrue(all(x["hours"] is None and x["status"].startswith("ainda nao") for x in far))
        self.assertIsNotNone(r["best_xp"])
        best = by["hunt-" + r["best_xp"]["id"]]
        self.assertEqual(best["xp_lost"], 0.0)               # a melhor hunt de XP nao perde XP
        # um Trofeu I e so resistencia: valor 0 e utilidade a dizer
        alp1 = by["boss-alptramun-1"]
        self.assertEqual(alp1["value_pct"], 0.0)
        self.assertEqual([s for s, el, v in alp1["utility"]], ["absorbPct"])
        # a ordenacao geral e por valor por hora, decrescente
        vph = [x["value_per_hour"] for x in r["plan"]["ranked"]]
        self.assertEqual(vph, sorted(vph, reverse=True))
        self.assertTrue(r["plan"]["now"] and r["plan"]["now"][0]["mission"]["hunt_id"] == r["current_hunt"])

    def test_pages_clean_and_within_limits(self):
        import re
        forbidden = re.compile(r"\b(None|nan|NaN|undefined|null)\b")
        for name, html in self.pages.items():
            self.assertIsNone(forbidden.search(html), name)
            self.assertLess(len(html.encode("utf-8")), 320 * 1024, name)
        self.assertIn("Dano de magia +0,654%", self.pages["missoes"])
        self.assertIn('id="m130"', self.pages["missoes"])
        self.assertIn("Auto Collect", self.pages["index"])
        self.assertIn("codex/index.html", self.pages["index"])   # o menu tem a entrada Codex
        self.assertNotIn("estilo.css", self.pages["print"])

    def test_serve_codex_post(self):
        from baiakvault import serve
        _, msg = serve.apply_post(helpers.real_catalog(), self.vault, "/editar/codex",
                                  {"mission": ["#73"], "done": [""], "progress": ["12/700, 3\n4"], "seen_at": ["2026-09-21"]})
        self.assertIn("#73", msg)
        row = self.vault.codex_progress()["hunt-cobra-cave"]
        self.assertEqual(row["progress"], [12, 3, 4])
        self.assertEqual(row["done"], 0)
        with self.assertRaises(serve.FormError):
            serve.apply_post(helpers.real_catalog(), self.vault, "/editar/codex", {"mission": ["#99999"]})
        with self.assertRaises(serve.FormError):
            serve.apply_post(helpers.real_catalog(), self.vault, "/editar/codex", {"mission": ["#73"], "progress": ["abc"]})


if __name__ == "__main__":
    unittest.main()
