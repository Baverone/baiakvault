"""O motor dos charms por hunt (`charms.py`): regras do jogo cumpridas,
determinismo, «?» onde falta dado, e as paginas sem None/nan."""
import copy
import re
import unittest

import helpers
from baiakvault import charms as C
from baiakvault import pages_charms

FORBIDDEN = re.compile(r"\b(None|nan|NaN|undefined|null)\b")


def _owner(**kw):
    base = dict(level=300, vip=1, hp_max=5000.0, mana_max=3000.0, crit_chance=8.0, life_leech=3.0, mana_leech=0.0,
                mana_shield=False, bestiary={}, stats_source="teste", hp_source="teste")
    base.update(kw)
    return C.owner(**base)


class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = helpers.real_catalog()

    def test_never_a_charm_he_does_not_have(self):
        own = _owner(charms=[{"charm_key": "enflame", "tier": 2, "assigned_creature_key": None},
                             {"charm_key": "gut", "tier": 1, "assigned_creature_key": None}])
        rec = C.recommend(self.cat, own, "cobra-cave")
        placed = {a["charm_key"] for a in rec["assignments"]} | {x["charm_key"] for x in rec["left_out"]}
        self.assertEqual(placed, {"enflame", "gut"})
        self.assertEqual(rec["owned"], 2)
        # tier 0 / desconhecido nao conta como ter
        own["charms"].append({"charm_key": "zap", "tier": 0, "assigned_creature_key": None})
        rec = C.recommend(self.cat, own, "cobra-cave")
        self.assertNotIn("zap", {a["charm_key"] for a in rec["assignments"]} | {x["charm_key"] for x in rec["left_out"]})

    def test_one_major_and_one_minor_per_creature_and_one_creature_per_charm(self):
        own = _owner(charms=None, slot_limit=25)
        for hunt in self.cat.hunts:
            rec = C.recommend(self.cat, own, hunt["id"])
            pairs = [(a["creature_key"], a["category"]) for a in rec["assignments"]]
            self.assertEqual(len(pairs), len(set(pairs)), hunt["id"])
            keys = [a["charm_key"] for a in rec["assignments"]]
            self.assertEqual(len(keys), len(set(keys)), hunt["id"])
            n = len(hunt["monstros"])
            self.assertLessEqual(sum(1 for _, c in pairs if c == "major"), n)
            self.assertLessEqual(sum(1 for _, c in pairs if c == "minor"), n)

    def test_creature_limit_is_respected_and_explained(self):
        charms = [{"charm_key": k, "tier": 3, "assigned_creature_key": None}
                  for k in ("enflame", "freeze", "zap", "dodge", "gut", "scavenge")]
        own = _owner(charms=charms, vip=0, slot_limit=None)   # sem VIP: 2 criaturas
        rec = C.recommend(self.cat, own, "cobra-cave")        # 3 criaturas na hunt
        self.assertEqual(rec["limit"], 2)
        self.assertLessEqual(len(rec["used"]), 2)
        self.assertLessEqual(len({a["creature_key"] for a in rec["assignments"]}), 2)
        self.assertTrue(any("limite" in x["reason"] for x in rec["left_out"]), rec["left_out"])
        own = _owner(charms=charms, vip=1)
        self.assertEqual(C.recommend(self.cat, own, "cobra-cave")["limit"], 6)
        own = _owner(charms=charms, vip=None)
        rec = C.recommend(self.cat, own, "cobra-cave")
        self.assertEqual(rec["limit"], 2)
        self.assertIn("desconhecido", rec["limit_source"])
        own = _owner(charms=charms, slot_limit=25)
        self.assertEqual(C.recommend(self.cat, own, "cobra-cave")["limit"], 25)

    def test_low_blow_and_savage_blow_need_known_crit(self):
        charms = [{"charm_key": "low_blow", "tier": 1, "assigned_creature_key": None},
                  {"charm_key": "savage_blow", "tier": 1, "assigned_creature_key": None}]
        for crit, kind in ((None, "unknown"), (0.0, "useless")):
            rec = C.recommend(self.cat, _owner(charms=charms, crit_chance=crit), "cobra-cave")
            self.assertEqual(rec["assignments"], [])
            self.assertEqual({x["charm_key"] for x in rec["left_out"]}, {"low_blow", "savage_blow"})
            self.assertTrue(all(x["kind"] == kind and "critico" in x["reason"] for x in rec["left_out"]), rec["left_out"])
        rec = C.recommend(self.cat, _owner(charms=charms, crit_chance=5.0), "cobra-cave")
        self.assertEqual({a["charm_key"] for a in rec["assignments"]}, {"low_blow", "savage_blow"})

    def test_leech_and_mana_shield_requirements(self):
        charms = [{"charm_key": "vampiric_embrace", "tier": 1, "assigned_creature_key": None},
                  {"charm_key": "voids_call", "tier": 1, "assigned_creature_key": None},
                  {"charm_key": "void_inversion", "tier": 1, "assigned_creature_key": None}]
        rec = C.recommend(self.cat, _owner(charms=charms, life_leech=2.0, mana_leech=0.0, mana_shield=False), "cobra-cave")
        self.assertEqual({a["charm_key"] for a in rec["assignments"]}, {"vampiric_embrace"})
        self.assertEqual({x["charm_key"] for x in rec["left_out"]}, {"voids_call", "void_inversion"})
        rec = C.recommend(self.cat, _owner(charms=charms, life_leech=0.0, mana_leech=1.0, mana_shield=True), "cobra-cave")
        self.assertEqual({a["charm_key"] for a in rec["assignments"]}, {"voids_call", "void_inversion"})

    def test_elemental_goes_to_lowest_resistance(self):
        # Hydra: gelo 50 %, energia -10 %, fisico -5 % (bestiario). Bog Raider e a outra criatura da hunt.
        hunt = "hydra-cave"
        self.assertIn(hunt, self.cat.hunt_by_id)
        view = C.hunt_view(self.cat, hunt)
        by_key = {c["key"]: c for c in view["creatures"]}
        self.assertEqual(by_key["hydra"]["resist"]["ice"], 50)
        own = _owner(charms=[{"charm_key": "freeze", "tier": 3, "assigned_creature_key": None}], bestiary=None)
        rec = C.recommend(self.cat, own, hunt)
        self.assertEqual(len(rec["assignments"]), 1)
        a = rec["assignments"][0]
        self.assertIn("resistencia a gelo", a["why"])
        # a Hydra e gorda (64 % dos golpes) e por isso ganha apesar dos 50 %; com exposicao igual,
        # ganha quem tem menos resistencia (Bog Raider, -5 %)
        charm = self.cat.charm_by_key["freeze"]
        same = copy.deepcopy(view)
        for c in same["creatures"]:
            c["exposure_share"], c["hp"] = 0.5, 2000
        scores = {c["key"]: C.score_pair(charm, 3, own, same, c)[0] for c in same["creatures"]}
        self.assertGreater(scores["bog_raider"], scores["hydra"])
        # um alvo imune (100 %) nunca ganha: forcamos uma copia com todos imunes menos um
        view2 = copy.deepcopy(view)
        for c in view2["creatures"]:
            c["resist"] = dict(c["resist"] or {}, ice=100)
        view2["creatures"][0]["resist"]["ice"] = 0
        charm = self.cat.charm_by_key["freeze"]
        scores = [C.score_pair(charm, 3, own, view2, c)[0] for c in view2["creatures"]]
        self.assertGreater(scores[0], 0)
        self.assertTrue(all(s == 0 for s in scores[1:]))

    def test_missing_resistances_give_unknown_not_a_guess(self):
        view = C.hunt_view(self.cat, "cobra-cave")
        for c in view["creatures"]:
            c["resist"], c["resist_source"] = None, None
        own = _owner()
        charm = self.cat.charm_by_key["enflame"]
        for c in view["creatures"]:
            score, why, _ = C.score_pair(charm, 2, own, view, c)
            self.assertIsNone(score)
            self.assertIn("desconhecida", why)
        # sem HP do dono, Overpower nao pontua e diz porque
        score, why, _ = C.score_pair(self.cat.charm_by_key["overpower"], 1, _owner(hp_max=None), view, view["creatures"][0])
        self.assertIsNone(score)
        self.assertIn("HP maximo", why)

    def test_resistance_fallback_is_flagged(self):
        view = C.hunt_view(self.cat, "cobra-cave")
        self.assertTrue(all(c["resist_source"] == "tabela de combate ⚠" for c in view["creatures"]))
        self.assertTrue(any("2.a tabela" in n for n in view["notes"]))
        view = C.hunt_view(self.cat, "hydra-cave")
        self.assertEqual({c["key"]: c["resist_source"] for c in view["creatures"]}["hydra"], "bestiario")

    def test_major_needs_closed_bestiary_when_known(self):
        own = _owner(charms=[{"charm_key": "wound", "tier": 1, "assigned_creature_key": None}],
                     bestiary={"cobra_vizier": 100, "cobra_assassin": 2500, "cobra_scout": 2500})
        rec = C.recommend(self.cat, own, "cobra-cave")
        self.assertEqual(len(rec["assignments"]), 1)
        self.assertNotEqual(rec["assignments"][0]["creature_key"], "cobra_vizier")
        own["bestiary"] = {"cobra_vizier": 10, "cobra_assassin": 10, "cobra_scout": 10}
        rec = C.recommend(self.cat, own, "cobra-cave")
        self.assertEqual(rec["assignments"], [])
        self.assertIn("por fechar", rec["left_out"][0]["reason"])
        # menor nao exige bestiario fechado
        own["charms"] = [{"charm_key": "gut", "tier": 1, "assigned_creature_key": None}]
        self.assertEqual(len(C.recommend(self.cat, own, "cobra-cave")["assignments"]), 1)

    def test_dodge_goes_to_the_creature_that_hits_hardest(self):
        view = C.hunt_view(self.cat, "cobra-cave")
        hardest = max(c["taken"] for c in view["creatures"])
        own = _owner(charms=[{"charm_key": "dodge", "tier": 1, "assigned_creature_key": None}], bestiary=None)
        rec = C.recommend(self.cat, own, "cobra-cave")
        chosen = {c["key"]: c for c in view["creatures"]}[rec["assignments"][0]["creature_key"]]
        self.assertEqual(chosen["taken"], hardest)   # ha empate Vizier/Scout: qualquer dos dois

    def test_gut_and_scavenge_follow_loot(self):
        view = C.hunt_view(self.cat, "cobra-cave")
        best_items = max(view["creatures"], key=lambda c: c["loot_items"])
        best_coins = max(view["creatures"], key=lambda c: c["loot_coins"])
        own = _owner(charms=[{"charm_key": "gut", "tier": 1, "assigned_creature_key": None},
                             {"charm_key": "scavenge", "tier": 1, "assigned_creature_key": None}])
        rec = C.recommend(self.cat, own, "cobra-cave")
        got = {a["charm_key"]: a["creature_key"] for a in rec["assignments"]}
        self.assertEqual(len(got), 2)
        if best_items["key"] != best_coins["key"]:
            self.assertEqual(got, {"gut": best_items["key"], "scavenge": best_coins["key"]})

    def test_changes_and_costs(self):
        own = _owner(level=300, charms=[
            {"charm_key": "dodge", "tier": 1, "assigned_creature_key": "troll"},      # noutra hunt: mover
            {"charm_key": "gut", "tier": 1, "assigned_creature_key": None},          # livre: atribuir
        ])
        rec = C.recommend(self.cat, own, "cobra-cave")
        kinds = {c["charm_key"]: c["kind"] for c in rec["changes"]}
        self.assertEqual(kinds, {"dodge": "move", "gut": "assign"})
        move = [c for c in rec["changes"] if c["kind"] == "move"][0]
        self.assertEqual(move["gold"], 300 * 1000)
        self.assertEqual(move["from"], "Troll")
        self.assertTrue(any("mover um charm custa" in n for n in rec["notes"]))
        # ja esta onde deve: keep
        own["charms"][0]["assigned_creature_key"] = rec["assignments"][0]["creature_key"] if rec["assignments"][0]["charm_key"] == "dodge" else own["charms"][0]["assigned_creature_key"]
        rec2 = C.recommend(self.cat, own, "cobra-cave")
        self.assertIn("keep", {c["kind"] for c in rec2["changes"]})
        self.assertEqual(C.remove_cost(300, expansion=True), 225000)
        self.assertEqual(C.reset_cost(50), 1_000_000)
        self.assertEqual(C.reset_cost(200), 1_000_000 + 200 * 110_000)
        self.assertEqual([C.echoes_for_upgrade(t) for t in (0, 1, 2)], [50, 100, 200])

    def test_deterministic(self):
        own = _owner(charms=None)
        a = C.recommend(self.cat, own, "orclops-cave")
        b = C.recommend(self.cat, own, "orclops-cave")
        self.assertEqual([(x["charm_key"], x["creature_key"]) for x in a["assignments"]],
                         [(x["charm_key"], x["creature_key"]) for x in b["assignments"]])
        self.assertTrue(all(x["why"] for x in a["assignments"]))

    def test_every_hunt_ceiling_places_something(self):
        for hunt in self.cat.hunts:
            own = C.owner(level=hunt.get("nivel_minimo") or 8, charms=None)
            own["assume_requirements"] = True
            rec = C.recommend(self.cat, own, hunt["id"])
            self.assertTrue(rec["assignments"], hunt["id"])
            self.assertTrue(all(a["score"] is not None and a["score"] >= 0 for a in rec["assignments"]))

    def test_neighbour_hunts(self):
        ids = C.neighbour_hunts(self.cat, 312, "cobra-cave", 5)
        self.assertEqual(len(ids), 5)
        self.assertNotIn("cobra-cave", ids)
        self.assertTrue(all(abs((self.cat.hunt_by_id[i].get("nivel_minimo") or 0) - 312) <= 40 for i in ids), ids)


class Pages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = helpers.real_catalog()

    def test_print_and_sections_without_none(self):
        own = _owner(charms=[{"charm_key": "wound", "tier": 2, "assigned_creature_key": "cobra_vizier"},
                             {"charm_key": "dodge", "tier": 1, "assigned_creature_key": None},
                             {"charm_key": "low_blow", "tier": 1, "assigned_creature_key": None}],
                     crit_chance=None, hp_max=None)
        rec = C.recommend(self.cat, own, "cobra-cave")
        character = {"name": "Teste", "slug": "teste", "level": 300, "current_hunt": "cobra-cave"}
        page = pages_charms.render_print(self.cat, character, rec, "2026-09-16 12:00:00")
        self.assertIsNone(FORBIDDEN.search(page), page)
        self.assertIn("width:390px", page)
        self.assertNotIn("nav", page)
        self.assertIn("Cobra", page)           # nomes do jogo
        self.assertIn("Low Blow", page)        # o que fica de fora tambem se explica
        section = pages_charms.render_character_section(self.cat, "../", character, rec, [], True)
        self.assertIsNone(FORBIDDEN.search(section), section)
        ceiling = C.recommend(self.cat, C.owner(level=190, charms=None), "cobra-cave")
        ceiling["_level"] = 190
        hunt_section = pages_charms.render_hunt_section(self.cat, "../", [(character, rec)], ceiling)
        self.assertIsNone(FORBIDDEN.search(hunt_section), hunt_section)
        self.assertIn("Tecto", hunt_section)

    def test_rules_page_renders_the_markdown(self):
        md = (helpers.ROOT / "docs" / "charms.md").read_text(encoding="utf-8")
        self.assertIn("⚠", md)
        page = pages_charms.render_rules(md, "2026-09-16 12:00:00")
        self.assertIn("Limite de criaturas", page)
        self.assertIsNone(FORBIDDEN.search(page))


if __name__ == "__main__":
    unittest.main()
