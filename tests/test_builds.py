"""O simulador e o optimizador: propriedades que tem de valer sempre.

- mais nivel nunca da menos DPS com a mesma build;
- a arvore devolvida nunca viola pre-requisitos, orcamento nem rank maximo;
- a rotacao nunca viola cooldowns nem o cooldown de grupo, e a mana nunca fica
  negativa;
- o equipamento respeita nivel, vocacao e slot;
- as 8 builds x 8 niveis geram em menos de 10 s.
"""
import unittest

import helpers
from baiakvault import builds, formulas as F, sim

planner = helpers.planner


class Simulator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = helpers.real_catalog()

    def test_target_from_hunt(self):
        t = sim.Target(self.cat, "glooth-cave")
        self.assertEqual(t.pack, 4)
        # dois monstros sem pesos -> media simples dos HP: (2400 + 2600) / 2 = 2500
        self.assertAlmostEqual(t.hp, 2500.0)
        # glooth bandit: dano base [0, 280] -> 140 / 2 s = 70/s ; habilidade fisica 60..200 a 50 % a cada 2 s = 130 x 0.5 / 2 = 32.5/s
        inc, mx = sim.creature_pressure(self.cat.creature_by_key["glooth_bandit"])
        self.assertAlmostEqual(inc["physical"], 70.0 + 32.5)
        self.assertEqual(mx["physical"], 280.0)
        self.assertEqual(inc["fire"], 0.0)  # a cura do monstro nao e dano

    def test_more_level_never_less_dps(self):
        target = sim.Target(self.cat, "cobra-cave")
        for voc in ("knight", "sorcerer", "paladin", "druid", "monk"):
            last = None
            for level in (100, 200, 400, 800):
                p = sim.Profile(self.cat, voc, level)
                spells = sim.attack_spells(p)[:3]
                rot = [sim.RotationSlot(s) for s in spells]
                r = sim.simulate(p, target, rot, heal=sim.best_heal(p))
                if last is not None:
                    self.assertGreaterEqual(r.dps, last, (voc, level))
                last = r.dps

    def test_rotation_respects_cooldowns_gcd_and_mana(self):
        pl, plans = planner()
        for key, b in plans.items():
            for boss in (False, True):
                rot = b["boss_rotation"] if boss else b["rotation"]
                r = sim.simulate(b["profile"], b["target"], rot, boss=boss, heal=b["heal"])
                self.assertGreaterEqual(r.mana_min, 0.0, key)
                by_spell = {}
                last_attack = None
                cds = {sl.spell["palavras"]: sl.spell["cooldown_ms"] / 1000.0 for sl in rot}
                for t, words in r.cast_log:
                    if words in cds:
                        if last_attack is not None:
                            self.assertGreaterEqual(t - last_attack, F.ATTACK_GCD_MS / 1000.0, (key, words))
                        last_attack = t
                        if words in by_spell:
                            self.assertGreaterEqual(t - by_spell[words], cds[words], (key, words))
                        by_spell[words] = t

    def test_simulation_is_deterministic(self):
        p = sim.Profile(self.cat, "sorcerer", 300)
        t = sim.Target(self.cat, "naga-lair")
        rot = [sim.RotationSlot(s) for s in sim.attack_spells(p)[:4]]
        a = sim.simulate(p, t, rot, heal=sim.best_heal(p))
        b = sim.simulate(p, t, rot, heal=sim.best_heal(p))
        self.assertEqual(a.as_dict(), b.as_dict())


class Optimizer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = helpers.real_catalog()
        cls.pl, cls.plans = planner()

    def test_all_64_builds_in_under_ten_seconds(self):
        self.assertEqual(len(self.plans), 64)
        self.assertLess(helpers.PLAN_SECONDS, 10.0, "8 builds x 8 niveis levaram %.1f s" % helpers.PLAN_SECONDS)

    def test_tree_respects_budget_max_rank_prerequisites_and_vocation(self):
        for (voc, goal, level), b in self.plans.items():
            tree = b["tree"]
            spent = sum(F.tree_total_cost(self.cat.node_by_id[k], v) for k, v in tree.items())
            self.assertLessEqual(spent, F.tree_budget(level), (voc, goal, level))
            self.assertGreater(spent, 0, (voc, goal, level))
            adj = builds._adjacency(self.cat, voc)
            for nid, rank in tree.items():
                node = self.cat.node_by_id[nid]
                self.assertEqual(self.cat.node_vocation[nid], voc, (voc, goal, level, nid))
                self.assertGreaterEqual(rank, 1)
                self.assertLessEqual(rank, node["rank_maximo"], (voc, goal, level, nid))
                if node["tier"] > 0:
                    self.assertTrue(any(tree.get(v, 0) >= 1 for v in adj[nid]),
                                    "%s sem vizinho comprado em %s %s %d" % (nid, voc, goal, level))

    def test_path_is_a_valid_purchase_order(self):
        for voc, goal in builds.BUILDS:
            ranks, steps = self.pl.path(voc, goal)
            adj = builds._adjacency(self.cat, voc)
            state = {}
            spent = 0
            for st in steps:
                node = self.cat.node_by_id[st.node_id]
                self.assertTrue(builds.can_buy(node, state, adj), (voc, goal, st.node_id, st.rank))
                self.assertEqual(st.cost, F.tree_rank_cost(node, st.rank - 1))
                spent += st.cost
                self.assertEqual(st.cumulative, spent)
                state[st.node_id] = st.rank
            self.assertEqual(state, ranks)
            self.assertLessEqual(spent, F.tree_budget(max(builds.LEVELS)))

    def test_equipment_respects_level_vocation_and_slot(self):
        for (voc, goal, level), b in self.plans.items():
            for slot, eq in b["equipment"].items():
                if not eq:
                    continue
                item = eq["item"]
                if slot == "ammo":
                    self.assertEqual(voc, "paladin")
                    self.assertTrue(item.get("municao"))
                else:
                    self.assertEqual(item["slot"], slot, (voc, goal, level, slot))
                self.assertLessEqual(item.get("nivel") or 0, level, (voc, goal, level, item["nome"]))
                vocs = item.get("vocacoes")
                if vocs:
                    self.assertIn(voc, vocs, (voc, goal, level, item["nome"]))
                self.assertFalse(item.get("cargas") or item.get("duracao_s"), item["nome"])
            if voc != "knight":
                self.assertNotIn("shield", b["equipment"])
            weapon = (b["equipment"].get("weapon") or {}).get("item")
            if weapon and weapon.get("duas_maos"):
                self.assertNotIn("shield", b["equipment"])

    def test_rotation_has_at_most_four_spells_of_the_vocation_and_level(self):
        for (voc, goal, level), b in self.plans.items():
            for rot in (b["rotation"], b["boss_rotation"]):
                self.assertLessEqual(len(rot), 4)
                self.assertGreaterEqual(len(rot), 1, (voc, goal, level))
                for sl in rot:
                    self.assertEqual(sl.spell["vocacao"], voc)
                    self.assertLessEqual(sl.spell["nivel"], level)
                    self.assertFalse(sl.spell.get("custo_gold"), "runa na rotacao base")
            heal = b["heal"]
            self.assertIsNotNone(heal, (voc, goal, level))
            self.assertEqual(heal["tipo"], "heal")

    def test_metrics_are_finite_and_positive(self):
        for key, b in self.plans.items():
            m = b["metrics"]
            for k in ("dps_pack", "dps_boss", "dps_cycle", "hp_max", "mana_max", "ehp"):
                self.assertGreater(m[k], 0, (key, k))
                self.assertLess(m[k], 1e9, (key, k))
            self.assertLessEqual(m["ttd_pack"], builds.TTD_CAP)

    def test_goal_metric_beats_the_other_goal_of_the_same_vocation(self):
        """A build de tank do knight tem mais EHP do que a de dano; a de dano
        tem mais DPS do que a de tank. O mesmo para druid e monk."""
        for voc, a, b_goal in (("knight", "tank", "damage"), ("druid", "heal", "damage"), ("monk", "support", "damage")):
            for level in (300, 800):
                ma = self.plans[(voc, a, level)]["metrics"]
                mb = self.plans[(voc, b_goal, level)]["metrics"]
                self.assertGreaterEqual(mb["dps_cycle"], ma["dps_cycle"] * 0.999, (voc, level))
                if a == "tank":
                    self.assertGreater(ma["ehp"], mb["ehp"], (voc, level))
                else:
                    self.assertGreaterEqual(ma["hps_self"] + ma["hps_friend"], (mb["hps_self"] + mb["hps_friend"]) * 0.999, (voc, level))

    def test_next_purchase_from_a_real_state(self):
        b = self.plans[("knight", "damage", 100)]
        options, current, remaining = builds.next_purchase(
            self.cat, "knight", "damage", 120, b["tree"], b["equipment"], b["target"], b["rotation"])
        self.assertEqual(remaining, 120 - b["points_spent"])
        self.assertTrue(options)
        for o in options:
            self.assertLessEqual(o["cost"], remaining)
            self.assertGreaterEqual(o["gain_pct"], 0.0)

    def test_helper_config_uses_game_field_names(self):
        for key, b in self.plans.items():
            h = b["helper"]
            self.assertIn("heal_spell", h)
            self.assertIn("hunt_rotation", h)
            self.assertTrue(35 <= h["heal_at"] <= 85, key)
            self.assertTrue(h["hp_potion"], key)
            for name, words, min_mobs in h["hunt_rotation"]:
                self.assertTrue(words)
            self.assertIn(h["position"], ("Persegue o alvo e fica colado nele (corpo a corpo)",
                                          "Mantém essa distância do alvo"))


if __name__ == "__main__":
    unittest.main()
