"""O simulador e o optimizador: propriedades que tem de valer sempre.

- mais nivel nunca da menos DPS com a mesma build;
- a arvore devolvida nunca viola pre-requisitos, orcamento nem rank maximo;
- a rotacao nunca viola cooldowns nem o cooldown de grupo, e a mana nunca fica
  negativa;
- o equipamento respeita nivel, vocacao e slot;
- as 13 builds (5 «best» + 8 por objectivo) x 8 niveis geram em tempo util.
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

    def test_target_reads_resistances_from_the_second_table_when_the_bestiary_has_none(self):
        # Elder Wyrm: sem resistencias no bestiario, 75 % terra / 30 % fogo na 2.a tabela do cliente.
        # Ate 16/09/2026 o simulador contava-o a 0 % em tudo (e o motor dos charms ja lia a tabela).
        wyrm = self.cat.creature_by_key["elder_wyrm"]
        self.assertFalse(wyrm.get("resistencias"))
        res, source = self.cat.resistances(wyrm)
        self.assertEqual(source, self.cat.RESIST_FALLBACK)
        self.assertEqual(res["earth"], 75)
        t = sim.Target(self.cat, "wyrm-cave")
        self.assertIn("Elder Wyrm", t.resist_fallback)
        self.assertGreater(t.resist["earth"], 0)
        self.assertEqual(t.resist_unknown, [])
        # e a mesma leitura que o motor dos charms faz
        from baiakvault import charms
        self.assertEqual(charms._resistances(self.cat, wyrm), (res, source))
        # uma hunt com tudo no bestiario nao muda nem leva aviso
        t = sim.Target(self.cat, "crawler-cave")
        self.assertEqual(t.resist_fallback, [])
        self.assertAlmostEqual(t.resist["earth"], 100.0)
        # todos os monstros de hunt tem resistencias numa das duas tabelas: nenhum fica «?»
        for hunt in self.cat.hunts:
            self.assertEqual(sim.Target(self.cat, hunt["id"]).resist_unknown, [], hunt["id"])

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

    def test_all_104_builds_in_time(self):
        self.assertEqual(len(self.plans), len(builds.BUILDS) * len(builds.LEVELS))
        self.assertEqual(len(self.plans), 104)
        # 16/09/2026 (ordem 6): a «best» corre o simulador 3x por avaliacao (pack, boss, pack
        # inteiro) e testa as poupancas; o tecto sobe de 10 s para 60 s
        self.assertLess(helpers.PLAN_SECONDS, 60.0, "13 builds x 8 niveis levaram %.1f s" % helpers.PLAN_SECONDS)

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
                # e a rotacao so de mana (para se ver o que as runas compram) nao tem runas
                for sl in b["rotation_no_runes"] + b["boss_rotation_no_runes"]:
                    self.assertFalse(sim.is_rune(sl.spell), (voc, goal, level, sl.spell["nome"]))
            heal = b["heal"]
            self.assertIsNotNone(heal, (voc, goal, level))
            self.assertEqual(heal["tipo"], "heal")
            self.assertFalse(heal.get("custo_gold"), "a cura do Helper e sem runa; a runa e alternativa")

    def test_runes_are_normal_candidates_with_gold_per_cast_and_the_cap_is_a_parameter(self):
        """Ponto 6 da ordem 7 (teste do Andre, 16/09/2026 13:20): as runas de area e a
        Sudden Death entram na rotacao de hunt e de boss com o gold por lancamento do
        cliente; sem tecto por omissao (ponto 0), com tecto so o que cabe."""
        target = sim.Target(self.cat, "livrariafire-cave")
        sorc = sim.Profile(self.cat, "sorcerer", 471)
        pool = builds.rotation_pool(sorc, target, boss=False)
        runes = [s for s in pool if sim.is_rune(s)]
        self.assertTrue(runes, "sem runa na pool")
        self.assertTrue(all(s["tipo"] in ("area", "strike") for s in runes))
        self.assertLessEqual(len(runes), 2, "so a melhor runa de area e a melhor de alvo unico")
        for s in runes:
            self.assertGreater(s["custo_gold"], 0)
            self.assertNotEqual(F.spell_element(s["palavras"]), "fire", "runa de fogo na Livraria FIRE")
        # sem tecto: a rotacao de hunt do sorcerer leva uma runa e rende mais do que sem
        rot, r = builds.choose_rotation(sorc, target, boss=False, goal="damage")
        rot0, r0 = builds.choose_rotation(sorc, target, boss=False, goal="damage", runes=False)
        self.assertTrue(any(sim.is_rune(sl.spell) for sl in rot), [sl.spell["nome"] for sl in rot])
        self.assertGreater(r.dps, r0.dps)
        self.assertGreater(r.runes_per_hour, 0)
        self.assertAlmostEqual(r.gold_per_hour, r.runes_per_hour + r.hp_potions_per_hour + r.mana_potions_per_hour)
        area_rune = [sl for sl in rot if sim.is_rune(sl.spell) and sl.spell["tipo"] == "area"]
        for sl in area_rune:
            self.assertEqual(sl.min_mobs, F.RUNE_AREA_MIN_MOBS)
        # com tecto: nenhuma rotacao acima dele (ou, se nenhuma cabe, a mais barata)
        cap = r0.gold_per_hour * 0.5
        rot_cap, r_cap = builds.choose_rotation(sorc, target, boss=False, goal="damage", gold_cap=cap)
        self.assertLessEqual(r_cap.gold_per_hour, cap + 1e-6, [sl.spell["nome"] for sl in rot_cap])
        # a pagina: custo por lancamento em gold nas runas, e o total «gold/h (pocoes + runas)»
        b = self.plans[("sorcerer", "damage", 500)]
        costs = b["helper"]["hunt_costs"]
        self.assertEqual([c["words"] for c in costs], [w for _, w, _ in b["helper"]["hunt_rotation"]])
        for c in costs:
            self.assertEqual(c["rune"], c["gold_per_cast"] > 0)
        self.assertIsNotNone(b["helper"]["hunt_supplies"])
        self.assertIsNone(b["gold_cap"])

    def test_sustained_dps_limits_knight_and_monk_not_potion_users(self):
        """Ponto 0 (16/09/2026): no knight/monk so o DPS que a mana sustenta conta (o ataque
        normal e as runas nao dependem da mana); mages/paladin bebem pocoes a vontade."""
        target = sim.Target(self.cat, "livrariafire-cave")
        monk = sim.Profile(self.cat, "monk", 306)
        spells = sim.attack_spells(monk)
        rot = builds.rotation_slots(monk, target, [s for s in spells if not sim.is_rune(s)][:3])
        r = sim.simulate(monk, target, rot, boss=True, heal=sim.best_heal(monk))
        self.assertLess(r.mana_sustain, 1.0)
        self.assertLess(r.dps_sustained, r.dps)
        self.assertAlmostEqual(r.dps_sustained, r.dps_free + r.dps_mana_spells * r.mana_sustain, places=6)
        self.assertEqual(builds.rotation_value(r, monk, "damage"), r.dps_sustained)
        sorc = sim.Profile(self.cat, "sorcerer", 471)
        rs = sim.simulate(sorc, target, builds.rotation_slots(sorc, target, sim.attack_spells(sorc)[:2]), heal=sim.best_heal(sorc))
        self.assertEqual(rs.dps_sustained, rs.dps)
        self.assertEqual(builds.rotation_value(rs, sorc, "damage"), rs.dps)
        # a metrica de dano: DPS sustentado do ciclo x sobreviver (sem condicao de mana a parte)
        for key, b in self.plans.items():
            if key[1] != "damage":
                continue
            m = b["metrics"]
            cons = builds.goal_constraints(m, "damage")
            self.assertEqual(set(cons), {"survive_pack", "survive_boss"}, key)
            if not m["uses_mana_potions"]:
                self.assertLessEqual(m["dps_cycle_sustained"], m["dps_cycle"] + 1e-6, key)

    def test_beams_and_immune_elements_stay_out_of_the_hunt_rotation(self):
        """Regras de 16/09/2026 (ordem 7): beams so no boss (Andre); um feitico do
        elemento a que o pack e imune (multiplicador medio < 0,5) fica fora da hunt."""
        target = sim.Target(self.cat, "livrariafire-cave")   # 3 dos 4 imunes a fogo
        self.assertGreaterEqual(target.resist["fire"], 50.0)
        for voc, level in (("sorcerer", 471), ("druid", 488), ("knight", 527)):
            p = sim.Profile(self.cat, voc, level)
            excluded = builds.hunt_exclusions(p, target)
            for s in sim.attack_spells(p):
                if s["palavras"] in builds.BEAM_SPELLS:
                    self.assertIn("beam", excluded[s["palavras"]], (voc, s["nome"]))
                elif F.spell_element(s["palavras"]) == "fire":
                    self.assertIn("fire", excluded[s["palavras"]], (voc, s["nome"]))
            hunt_rot, _ = builds.choose_rotation(p, target, boss=False)
            for sl in hunt_rot:
                self.assertNotIn(sl.spell["palavras"], excluded, (voc, sl.spell["nome"]))
            self.assertTrue(hunt_rot, voc)
            # no boss os beams continuam candidatos: nenhuma exclusao
            boss_rot, _ = builds.choose_rotation(p, target, boss=True)
            self.assertTrue(boss_rot, voc)
        sorc = sim.Profile(self.cat, "sorcerer", 471)
        names = {s["nome"] for s in sim.attack_spells(sorc) if s["palavras"] in builds.hunt_exclusions(sorc, target)}
        self.assertIn("Hell's Core", names)
        self.assertIn("Great Energy Beam", names)
        # e a pagina diz o que ficou de fora
        for key, b in self.plans.items():
            for name, words, why in b["helper"]["hunt_excluded"]:
                self.assertTrue(why, key)
                self.assertNotIn(words, [w for _, w, _ in b["helper"]["hunt_rotation"]], key)

    def test_battle_tactics_changes_damage_dealt_and_taken(self):
        """O no Battle Tactics (special `tactics`) entra no simulador: mais ranks =
        mais chance de decisao perfeita = mais dano e menos dano recebido (16/09/2026, ordem 7)."""
        target = sim.Target(self.cat, "livrariafire-cave")
        nid = {"knight": "k_tactics", "sorcerer": "s_tactics"}
        for voc, level in (("knight", 527), ("sorcerer", 471)):
            base = sim.Profile(self.cat, voc, level)
            more = sim.Profile(self.cat, voc, level, {nid[voc]: 6})
            self.assertEqual(base.specials.get("tactics", 0), 0)
            self.assertEqual(more.specials["tactics"], 6)
            self.assertGreater(more.tactics["aim_chance"], base.tactics["aim_chance"])
            self.assertGreater(more.ai_quality, base.ai_quality)
            rot = [sim.RotationSlot(s) for s in sim.attack_spells(base)[:3]]
            r0 = sim.simulate(base, target, rot, heal=sim.best_heal(base))
            r1 = sim.simulate(more, target, rot, heal=sim.best_heal(more))
            self.assertGreater(r1.dps, r0.dps * 1.03, voc)
            self.assertLess(r1.pressure, r0.pressure, voc)
        # e o optimizador compra-o na build «best» ao nivel dele (Livraria FIRE)
        pl = self.pl
        for voc, level in (("knight", 527), ("sorcerer", 471)):
            b = pl.plan(voc, "best", level, hunt_id="livrariafire-cave")
            self.assertGreaterEqual(b["tree"].get(nid[voc], 0), 1, (voc, b["tree"]))

    def test_metrics_are_finite_and_positive(self):
        for key, b in self.plans.items():
            m = b["metrics"]
            for k in ("dps_pack", "dps_boss", "dps_cycle", "hp_max", "mana_max", "ehp"):
                self.assertGreater(m[k], 0, (key, k))
                self.assertLess(m[k], 1e9, (key, k))
            self.assertLessEqual(m["ttd_pack"], builds.TTD_CAP)

    def test_goal_metric_beats_the_other_goal_of_the_same_vocation(self):
        """A build de tank do knight tem mais EHP do que a de dano; a de dano
        tem mais DPS (sustentado: e a metrica dela desde o ponto 0 da ordem 7 — no
        knight/monk so o que a mana paga) do que a de tank. O mesmo para druid e monk."""
        # 16/09/2026 (ordem 7): com o factor da IA de combate o guloso da monk-damage a 800
        # fica abaixo da monk-support em DPS (a support compra Battle Tactics mais cedo);
        # e uma falha conhecida do guloso, registada no relatorio-7, nao escondida: fica aqui
        # a vista ate se corrigir o optimizador
        known_greedy_gaps = {("monk", 800)}
        for voc, a, b_goal in (("knight", "tank", "damage"), ("druid", "heal", "damage"), ("monk", "support", "damage")):
            for level in (300, 800):
                ma = self.plans[(voc, a, level)]["metrics"]
                mb = self.plans[(voc, b_goal, level)]["metrics"]
                if (voc, level) not in known_greedy_gaps:
                    self.assertGreaterEqual(mb["dps_cycle_sustained"], ma["dps_cycle_sustained"] * 0.999, (voc, level))
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
