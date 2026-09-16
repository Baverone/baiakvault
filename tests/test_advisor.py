"""O motor do «proximo passo»: com um personagem ficticio por vocacao
(`fixtures/personagens.json`) as sugestoes tem de ser coerentes —
o no sugerido tem os pre-requisitos satisfeitos e nao esta no maximo; o item
respeita nivel/vocacao/slot e e melhor que o actual; nunca se sugere o que ja
tem; com equipamento desconhecido diz-se que falta preencher."""
import json
import re
import unittest

import helpers
from baiakvault import advisor, builds, db, formulas as F

FORBIDDEN = re.compile(r"\b(None|nan|NaN|undefined|null)\b")


def _fixtures():
    return json.loads((helpers.FIXTURES / "personagens.json").read_text(encoding="utf-8"))["personagens"]


class Advisor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = helpers.real_catalog()
        cls.planner = helpers.planner()[0]
        conn, vault, _ = helpers.temp_vault()
        cls.states = {}
        cls.advice = {}
        for data in _fixtures():
            cid = helpers.load_fixture(vault, data)
            c = vault.character(cid)
            state = advisor.state_from_rows(c, vault.tree_of(cid), vault.equipment_of(cid), vault.charms_of(cid),
                                            vault.charm_points_of(cid), vault.bestiary_of(cid))
            cls.states[c["vocation"]] = state
            cls.advice[c["vocation"]] = advisor.advise(cls.cat, state, cls.planner)
        conn.close()

    def test_every_vocation_gets_a_short_clean_list(self):
        for voc, adv in self.advice.items():
            sugs = adv["suggestions"]
            self.assertTrue(sugs, voc)
            self.assertLessEqual(len(sugs), advisor.MAX_SUGGESTIONS)
            for s in sugs:
                for key in ("action", "why", "cost", "source"):
                    self.assertTrue(s.get(key), (voc, key, s))
                    self.assertIsNone(FORBIDDEN.search(str(s[key])), (voc, s))
            kinds = [s["kind"] for s in sugs]
            # o que falta preencher fecha a lista
            first_missing = kinds.index("missing") if "missing" in kinds else len(kinds)
            self.assertNotIn("missing", kinds[:first_missing])
            self.assertTrue(all(k == "missing" for k in kinds[first_missing:]))
            # medidos por ordem de ganho
            scores = [s["score"] for s in sugs if s["kind"] != "missing"]
            self.assertEqual(scores, sorted(scores, reverse=True))

    def test_tree_suggestions_respect_prerequisites_and_max(self):
        for voc, adv in self.advice.items():
            state = self.states[voc]
            ranks = dict(state["tree"] or {})
            adj = builds._adjacency(self.cat, voc)
            for s in adv["suggestions"]:
                if s["kind"] != "tree":
                    continue
                node = self.cat.node_by_id[s["node"]]
                self.assertLess(ranks.get(s["node"], 0), node.get("rank_maximo") or 1)
                self.assertEqual(s["rank"], ranks.get(s["node"], 0) + 1)
                trial = dict(ranks)
                for via in s["via"]:
                    self.assertTrue(builds.can_buy(self.cat.node_by_id[via], trial, adj), (voc, s))
                    trial[via] = trial.get(via, 0) + 1
                self.assertTrue(builds.can_buy(node, trial, adj), (voc, s))
                self.assertGreaterEqual(s["score"], 0)
                self.assertIn("ponto", s["cost"])

    def test_equipment_suggestions_respect_level_vocation_slot_and_are_better(self):
        for voc, adv in self.advice.items():
            state = self.states[voc]
            for s in adv["suggestions"]:
                if s["kind"] != "equipment":
                    continue
                item = self.cat.item_by_key[s["item_key"]]
                self.assertEqual(item["slot"], s["slot"])
                self.assertLessEqual(item.get("nivel") or 0, state["level"])
                self.assertTrue(not item.get("vocacoes") or voc in item["vocacoes"], (voc, s))
                current = (state["equipment"].get(s["slot"]) or {}).get("item_key")
                self.assertNotEqual((current or "").lower(), s["item_key"])
                self.assertGreater(s["gain_pct"], advisor.MIN_GAIN_PCT - 1e-9)
                self.assertTrue("cai de" in s["cost"] or "nao cai" in s["cost"], s["cost"])

    def test_never_suggests_what_he_has(self):
        for voc, adv in self.advice.items():
            state = self.states[voc]
            have_charms = {c["charm_key"]: c["tier"] for c in state["charms"]}
            for s in adv["suggestions"]:
                if s["kind"] == "charm":
                    self.assertGreater(s["tier"], have_charms.get(s["charm_key"], 0))

    def test_unknown_equipment_says_what_to_fill(self):
        sorcerer = self.advice["sorcerer"]
        missing = [s for s in sorcerer["suggestions"] if s["kind"] == "missing"]
        self.assertTrue(any("equipamento" in s["action"] for s in missing), missing)
        self.assertTrue(any("arma" in s["action"] for s in missing), missing)
        self.assertFalse([s for s in sorcerer["suggestions"] if s["kind"] == "equipment"])
        # hunt desconhecida: usou a de referencia e diz
        self.assertTrue(sorcerer["hunt_defaulted"])
        self.assertTrue(any("hunt actual" in s["action"] for s in missing), missing)

    def test_defaults_and_measured_gains(self):
        druid = self.advice["druid"]
        self.assertTrue(druid["goal_defaulted"])
        self.assertEqual(druid["goal"], "heal")
        self.assertTrue(any("upgrade de arma desconhecido" in n for n in druid["notes"]), druid["notes"])
        knight = self.advice["knight"]
        self.assertEqual(knight["goal"], "tank")
        self.assertFalse(knight["goal_defaulted"])
        kinds = {s["kind"] for s in knight["suggestions"]}
        self.assertIn("tree", kinds)       # tem pontos por gastar
        self.assertIn("equipment", kinds)  # «axe» ao nivel 150 tem melhor
        self.assertGreater(knight["plan_score"], 0)
        self.assertGreater(knight["current_score"], 0)

    def test_charm_points(self):
        paladin = self.advice["paladin"]
        charm = [s for s in paladin["suggestions"] if s["kind"] == "charm"]
        self.assertTrue(charm and charm[0]["action"].startswith("Juntar pontos"), charm)
        monk = self.advice["monk"]
        charm = [s for s in monk["suggestions"] if s["kind"] == "charm"]
        self.assertTrue(charm and charm[0]["action"].startswith("Desbloquear"), charm)
        self.assertEqual(self.cat.charm_by_key[charm[0]["charm_key"]]["kind"], advisor.GOAL_CHARM_KIND["support"])
        druid = self.advice["druid"]
        self.assertTrue(any("charm points" in s["action"] for s in druid["suggestions"] if s["kind"] == "missing"))

    def test_bestiary_near_close(self):
        state = dict(self.states["knight"])
        meta = self.cat.creature_by_key["cobra_scout"]["meta_kills"]
        state["bestiary"] = {"cobra_scout": meta - 10}
        sugs = advisor.bestiary_suggestions(self.cat, state)
        self.assertEqual(len(sugs), 1)
        self.assertIn("faltam 10 kills", sugs[0]["action"])
        state["bestiary"] = {"cobra_scout": meta}   # ja fechou: nada a dizer
        self.assertEqual(advisor.bestiary_suggestions(self.cat, state), [])
        state["bestiary"] = {"cobra_scout": 1}      # longe: nao e «perto de fechar»
        self.assertEqual(advisor.bestiary_suggestions(self.cat, state), [])

    def test_without_vocation_or_level_only_asks(self):
        adv = advisor.advise(self.cat, {"vocation": None, "level": 100}, self.planner)
        self.assertEqual([s["kind"] for s in adv["suggestions"]], ["missing"])
        self.assertIn("vocacao", adv["suggestions"][0]["action"])
        self.assertIsNone(adv["plan"])
        adv = advisor.advise(self.cat, {"vocation": "knight", "level": None}, self.planner)
        self.assertIn("nivel", adv["suggestions"][0]["action"])

    def test_tree_overspent_is_flagged_not_computed(self):
        state = dict(self.states["knight"])
        state["level"] = 10
        adv = advisor.advise(self.cat, state, self.planner)
        missing = [s for s in adv["suggestions"] if s["kind"] == "missing"]
        self.assertTrue(any("arvore esta errada" in s["action"] for s in missing), missing)
        self.assertFalse([s for s in adv["suggestions"] if s["kind"] == "tree"])

    def test_no_points_left_suggests_next_level(self):
        state = dict(self.states["knight"])
        plan = self.planner.plan("knight", "tank", 150, hunt_id="orclops-cave")
        state["tree"] = dict(plan["tree"])   # a recomendada, toda gasta
        self.assertEqual(advisor._tree_spent(self.cat, state["tree"]), F.tree_budget(150))
        adv = advisor.advise(self.cat, state, self.planner)
        tree = [s for s in adv["suggestions"] if s["kind"] == "tree"]
        for s in tree:
            self.assertIn("No nivel 151", s["action"])
        self.assertFalse([s for s in adv["suggestions"] if s["kind"] == "respec"])

    def test_pure_and_deterministic(self):
        a = advisor.advise(self.cat, self.states["monk"], self.planner)
        b = advisor.advise(self.cat, self.states["monk"], self.planner)
        self.assertEqual([(s["action"], round(s["score"], 6)) for s in a["suggestions"]],
                         [(s["action"], round(s["score"], 6)) for s in b["suggestions"]])

    def test_imbuement_parsing(self):
        cat = self.cat
        self.assertEqual(advisor.parse_imbuement(cat, "Vampirism:3"), ("vampirism", 3))
        self.assertEqual(advisor.parse_imbuement(cat, "vampirism"), ("vampirism", None))
        self.assertEqual(advisor.parse_imbuement(cat, "life leech 2"), ("vampirism", 2))
        self.assertIsNone(advisor.parse_imbuement(cat, "inexistente"))
        eq, notes = advisor.profile_equipment(cat, {"weapon": {"item_key": "axe", "upgrade_level": None, "imbuements": ["strike"],
                                                               "attributes": {"crit_chance": 5}},
                                                    "backpack": {"item_key": "ghost backpack", "upgrade_level": None}})
        self.assertEqual(eq["weapon"]["up"], 0)
        self.assertEqual(eq["weapon"]["imbuements"], [("strike", 1)])
        self.assertEqual(eq["weapon"]["item"]["crit_chance"], 5)
        self.assertNotIn("backpack", eq)
        self.assertEqual(len(notes), 2)

    def test_item_sources_use_client_loot_tables(self):
        srcs = advisor.item_sources(self.cat, self.cat.item_by_key["eldritch tome"])
        self.assertTrue(srcs)
        self.assertEqual(srcs[0]["creature"].lower(), "the brainstealer")
        text = advisor.item_sources_text(self.cat, self.cat.item_by_key["eldritch tome"])
        self.assertIn("cai de", text)


class Goals(unittest.TestCase):
    def test_default_goal_is_the_first_he_listed(self):
        self.assertEqual(db.default_goal("knight"), "tank")
        self.assertEqual(db.default_goal("druid"), "heal")
        self.assertEqual(db.default_goal("monk"), "support")
        self.assertEqual(db.default_goal("sorcerer"), "damage")
        self.assertEqual(db.default_goal("paladin"), "damage")
        self.assertIsNone(db.default_goal(None))

    def test_goal_must_belong_to_vocation(self):
        conn, vault, _ = helpers.temp_vault()
        try:
            with self.assertRaises(db.VaultError):
                vault.upsert_character("S", vocation="sorcerer", goal="tank")
            cid = vault.upsert_character("K", vocation="knight", goal="tank")
            with self.assertRaises(db.VaultError):
                vault.upsert_character("K", goal="heal")
            # muda de vocacao: o objectivo antigo deixa de valer e cai para o da nova
            vault.upsert_character("K", vocation="druid")
            self.assertEqual(vault.character(cid)["goal"], "heal")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
