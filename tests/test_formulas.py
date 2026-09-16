"""As contas feitas a mao, ao lado da funcao. E o que o Andre pediu com «facas
bem as contas»: cada formula do cliente tem aqui pelo menos um valor calculado
por fora (a conta esta no comentario) e comparado com o que a funcao da."""
import unittest

import helpers
from baiakvault import formulas as F


class SpellFormulas(unittest.TestCase):
    def test_light_healing(self):
        # (e,t)=>[e*.2+t*1.4+8, e*.2+t*1.795+11]  nivel 100, ML 30
        # min = 20 + 42 + 8 = 70 ; max = 20 + 53.85 + 11 = 84.85
        f = F.compile_formula("(e,t)=>[e*.2+t*1.4+8,e*.2+t*1.795+11]")
        self.assertEqual(f.params, ("e", "t"))
        self.assertEqual(f.kind, "magic")
        lo, hi = f(100, 30)
        self.assertAlmostEqual(lo, 70.0)
        self.assertAlmostEqual(hi, 84.85)

    def test_wound_cleansing(self):
        # (e,t)=>[(e*.2+t*4+25)*1.05, (e*.2+t*7.95+51)*1.26]  nivel 300, ML 10
        # min = (60 + 40 + 25) x 1.05 = 125 x 1.05 = 131.25
        # max = (60 + 79.5 + 51) x 1.26 = 190.5 x 1.26 = 240.03
        f = F.compile_formula("(e,t)=>[(e*.2+t*4+25)*1.05,(e*.2+t*7.95+51)*1.26]")
        lo, hi = f(300, 10)
        self.assertAlmostEqual(lo, 131.25)
        self.assertAlmostEqual(hi, 240.03)

    def test_energy_strike(self):
        # (e,t)=>[e/5+t*1.403+8, e/5+t*2.203+13]  nivel 100, ML 25
        # min = 20 + 35.075 + 8 = 63.075 ; max = 20 + 55.075 + 13 = 88.075
        f = F.compile_formula("(e,t)=>[e/5+t*1.403+8,e/5+t*2.203+13]")
        lo, hi = f(100, 25)
        self.assertAlmostEqual(lo, 63.075)
        self.assertAlmostEqual(hi, 88.075)
        self.assertAlmostEqual(f.average(100, 25), (63.075 + 88.075) / 2)

    def test_brutal_strike_flat_branch(self):
        # (e,t,a,n)=>xp([(a*n*.02+4+e/5)*1.28,(a*n*.04+9+e/5)*1.28],[e/5+(a+n)*.9,e/5+(a+n)*1.8])
        # nivel 100, ML 10, skill 60, ataque 50:
        #   ramo arma: min = (60x50x0.02 + 4 + 20) x 1.28 = 84 x 1.28 = 107.52
        #              max = (60x50x0.04 + 9 + 20) x 1.28 = 149 x 1.28 = 190.72
        #   ramo fixo: min = 20 + 110 x 0.9 = 119 ; max = 20 + 110 x 1.8 = 218
        #   xp = maximo dos dois -> [119, 218]
        f = F.compile_formula("(e,t,a,n)=>xp([(a*n*.02+4+e/5)*1.28,(a*n*.04+9+e/5)*1.28],[e/5+(a+n)*.9,e/5+(a+n)*1.8])")
        self.assertEqual(f.kind, "physical")
        self.assertEqual(f(100, 10, 60, 50), (119.0, 218.0))

    def test_brutal_strike_weapon_branch(self):
        # mesma formula, skill 100, ataque 120:
        #   ramo arma: min = (240 + 4 + 20) x 1.28 = 337.92 ; max = (480 + 9 + 20) x 1.28 = 651.52
        #   ramo fixo: min = 20 + 220 x 0.9 = 218 ; max = 20 + 220 x 1.8 = 416  -> perde
        f = F.compile_formula("(e,t,a,n)=>xp([(a*n*.02+4+e/5)*1.28,(a*n*.04+9+e/5)*1.28],[e/5+(a+n)*.9,e/5+(a+n)*1.8])")
        lo, hi = f(100, 10, 100, 120)
        self.assertAlmostEqual(lo, 337.92)
        self.assertAlmostEqual(hi, 651.52)

    def test_fierce_berserk_block_body(self):
        # (e,t,a,n)=>{const o=(e/3+(a+2*n)*5)*1.5;return[o*.75,o]}  nivel 90, skill 50, ataque 40
        # o = (30 + (50 + 80) x 5) x 1.5 = (30 + 650) x 1.5 = 1020 -> [765, 1020]
        f = F.compile_formula("(e,t,a,n)=>{const o=(e/3+(a+2*n)*5)*1.5;return[o*.75,o]}")
        lo, hi = f(90, 0, 50, 40)
        self.assertAlmostEqual(lo, 765.0)
        self.assertAlmostEqual(hi, 1020.0)

    def test_groundshaker_DO(self):
        # (e,t,a,n)=>DO(e,a,n) com DO=(e,t,a)=>{n=(e/3+(t+a)*3.5)*1.5;[n*.75,n]}
        # nivel 33, skill 40, ataque 30: n = (11 + 70 x 3.5) x 1.5 = 256 x 1.5 = 384 -> [288, 384]
        f = F.compile_formula("(e,t,a,n)=>DO(e,a,n)")
        lo, hi = f(33, 0, 40, 30)
        self.assertAlmostEqual(lo, 288.0)
        self.assertAlmostEqual(hi, 384.0)

    def test_ethereal_spear_distance(self):
        # (e,t,a)=>[e*.2+a*2.3+7, e*.2+a*4.3+13]  nivel 100, skill 60
        # min = 20 + 138 + 7 = 165 ; max = 20 + 258 + 13 = 291
        f = F.compile_formula("(e,t,a)=>[e*.2+a*2.3+7,e*.2+a*4.3+13]")
        self.assertEqual(f.kind, "distance")
        self.assertEqual(f(100, 0, 60), (165.0, 291.0))

    def test_shield_bash_six_params(self):
        # (e,t,a,n,o=0,i=0)=>xp([(e/5+55+i*1.5+o*.6*2)*2.32,(e/5+55+i*2.5+o*1*2)*2.32],[e/5+(a+n)*.9,e/5+(a+n)*1.8])
        # nivel 100, ML 10, skill 60, ataque 50, o (def do escudo) 30, i (shielding) 60:
        #   min = (20 + 55 + 90 + 36) x 2.32 = 201 x 2.32 = 466.32
        #   max = (20 + 55 + 150 + 60) x 2.32 = 285 x 2.32 = 661.2   (ramo fixo [119, 218] perde)
        f = F.compile_formula("(e,t,a,n,o=0,i=0)=>xp([(e/5+55+i*1.5+o*.6*2)*2.32,(e/5+55+i*2.5+o*1*2)*2.32],[e/5+(a+n)*.9,e/5+(a+n)*1.8])")
        self.assertEqual(f.kind, "shield")
        lo, hi = f(100, 10, 60, 50, 30, 60)
        self.assertAlmostEqual(lo, 466.32)
        self.assertAlmostEqual(hi, 661.2)

    def test_explosion_and_sudden_death_and_caldera(self):
        # Explosion (e,t)=>[1,e/5+t*4.8] nivel 100 ML 25 -> [1, 20 + 120 = 140]
        self.assertEqual(F.compile_formula("(e,t)=>[1,e/5+t*4.8]")(100, 25), (1.0, 140.0))
        # Sudden Death (e,t)=>[e/3.5+t*6,e/3.5+t*9] nivel 350 ML 60 -> [100 + 360, 100 + 540]
        self.assertEqual(F.compile_formula("(e,t)=>[e/3.5+t*6,e/3.5+t*9]")(350, 60), (460.0, 640.0))
        # Divine Caldera [(e/2+t*10)*1.5,(e/2+t*12)*1.5] nivel 100 ML 20 -> [250 x 1.5, 290 x 1.5]
        self.assertEqual(F.compile_formula("(e,t)=>[(e/2+t*10)*1.5,(e/2+t*12)*1.5]")(100, 20), (375.0, 435.0))

    def test_every_catalog_formula_compiles_and_is_ordered(self):
        cat = helpers.real_catalog()
        n = 0
        for v in cat.vocations:
            for s in v["feiticos"]:
                for key in ("formula_dano", "formula_cura"):
                    js = s.get(key)
                    if not js:
                        continue
                    f = F.compile_formula(js)
                    lo, hi = f(200, 40, 80, 60, 30, 70)
                    self.assertLessEqual(lo, hi, s["nome"])
                    self.assertGreater(hi, 0, s["nome"])
                    n += 1
        self.assertEqual(n, 187)

    def test_rejects_anything_that_is_not_arithmetic(self):
        with self.assertRaises(ValueError):
            F.compile_formula("(e,t)=>[__import__('os'),1]")
        with self.assertRaises(ValueError):
            F.compile_formula("(e,t)=>[e.real,1]")
        with self.assertRaises(ValueError):
            F.compile_formula("(e,t,z)=>[e,z]")

    def test_spell_element_from_words(self):
        self.assertEqual(F.spell_element("exori vis"), "energy")
        self.assertEqual(F.spell_element("exevo gran mas tera"), "earth")
        self.assertEqual(F.spell_element("exori ico"), "physical")
        self.assertEqual(F.spell_element("utori pox"), "earth")
        self.assertEqual(F.spell_element("exevo mas san"), "holy")
        self.assertEqual(F.spell_element("adori gran mort"), "death")
        self.assertEqual(F.spell_element("exori gran frigo"), "ice")
        self.assertEqual(F.spell_element("exevo gran flam hur"), "fire")


class CharacterFormulas(unittest.TestCase):
    def test_hp_and_mana(self):
        # knight nivel 100: 100 + 15 x 100 = 1600 ; sorcerer mana nivel 100: 90 + 30 x 100 = 3090
        self.assertAlmostEqual(F.max_hp("knight", 100), 1600.0)
        self.assertAlmostEqual(F.max_mana("sorcerer", 100), 3090.0)
        # +10 % de hpPct: 1600 x 1.1 = 1760
        self.assertAlmostEqual(F.max_hp("knight", 100, hp_pct=10), 1760.0)
        # monk segue o cliente (13/8), nao o guia (12/10): nivel 10 -> 100 + 130 = 230
        self.assertAlmostEqual(F.max_hp("monk", 10), 230.0)
        self.assertAlmostEqual(F.max_mana("monk", 10), 170.0)

    def test_typical_skill(self):
        # knight 42 + 0.15 x 200 = 72 ; mages ML 15 + 0.1 x 200 = 35
        self.assertAlmostEqual(F.typical_skill("knight", 200), 72.0)
        self.assertAlmostEqual(F.typical_skill("druid", 200), 35.0)

    def test_weapon_and_ammo_attack(self):
        # 6 de base + 10 da arma = 16 ; com upgrade 5 (+5 %) e atkPct 10: 16 x 1.15 = 18.4
        self.assertAlmostEqual(F.weapon_attack(10), 16.0)
        self.assertAlmostEqual(F.weapon_attack(10, up_level=5, atk_pct=10), 18.4)
        # municao x1.4: arrow 25 -> 35 ; diamond arrow x1.2: 37 -> 44.4 -> 44
        self.assertEqual(F.ammo_attack("arrow", 25), 35)
        self.assertEqual(F.ammo_attack("diamond arrow", 37), 44)

    def test_auto_attack_is_a_convention(self):
        # nivel 100, skill 60, ataque 50: min = 20 ; max = 20 + 0.085 x 50 x 60 = 275
        self.assertEqual(F.auto_attack_range(100, 60, 50), (20.0, 275.0))
        self.assertEqual(F.CONSTANTS["auto_attack_skill_factor"].source, F.SOURCE_CONVENTION)

    def test_absorb_stacking(self):
        # ds(20, 20) = 20 + 20 - 400/100 = 36 ; empilhar [20, 20, 10] = ds(36, 10) = 46 - 3.6 = 42.4
        self.assertAlmostEqual(F.ds(20, 20), 36.0)
        self.assertAlmostEqual(F.stack_pct([20, 20, 10]), 42.4)
        self.assertAlmostEqual(F.stack_pct([]), 0.0)

    def test_armor_and_block(self):
        # armadura 104: 104 / (104 + 520) x 100 = 16.667 % ; 1000: 65.8 % -> tecto 24
        self.assertAlmostEqual(F.armor_reduction_pct(104), 100 * 104 / 624.0)
        self.assertAlmostEqual(F.armor_reduction_pct(1000), 24.0)
        self.assertEqual(F.armor_reduction_pct(0), 0.0)
        # escudo def 65, shielding 90: 65/715 x 10 = 0.9091 ; 90/900 x 10 = 1.0 -> 1.9091
        self.assertAlmostEqual(F.block_pct(65, 90), 65 / 715.0 * 10 + 1.0)
        self.assertEqual(F.block_pct(65, 90, has_shield=False), 0.0)
        self.assertAlmostEqual(F.block_pct(100000, 100000), 18.0)

    def test_crit_and_resist(self):
        # chance 10 %, +20 % critDmg: 1 + 10 x (50 + 20) / 10000 = 1.07
        self.assertAlmostEqual(F.crit_multiplier(10, 20), 1.07)
        self.assertAlmostEqual(F.crit_multiplier(100, 0), 1.5)
        # resistencia 25 % -> passa 0.75 ; -12 % (fraqueza) -> 1.12 ; 100 % -> 0
        self.assertAlmostEqual(F.resist_factor(25), 0.75)
        self.assertAlmostEqual(F.resist_factor(-12), 1.12)
        self.assertEqual(F.resist_factor(100), 0.0)
        # Ballistic Mastery ignora 20 % da resistencia: 25 x 0.8 = 20 -> passa 0.8
        self.assertAlmostEqual(F.resist_factor(25, pierce_pct=20), 0.8)

    def test_prey(self):
        # cliente rye: dmg 2s+5, def 2s+10, xp/loot 3s+10 ; a 10 estrelas: 25 / 30 / 40
        self.assertEqual(F.prey_bonus_pct("dmg", 10), 25)
        self.assertEqual(F.prey_bonus_pct("def", 10), 30)
        self.assertEqual(F.prey_bonus_pct("xp", 10), 40)
        self.assertEqual(F.prey_bonus_pct("loot", 1), 13)

    def test_tree_costs_and_budget(self):
        small = {"tipo": "small", "custo_por_rank": 2, "rank_maximo": 10}
        notable = {"tipo": "notable", "custo_por_rank": 150, "rank_maximo": 1}
        # small custo 2: rank 1 custa 2, rank 4 custa 2 x 4 = 8, do zero ao 10: 2 x 10 x 11 / 2 = 110
        self.assertEqual(F.tree_rank_cost(small, 0), 2)
        self.assertEqual(F.tree_rank_cost(small, 3), 8)
        self.assertEqual(F.tree_total_cost(small, 10), 110)
        self.assertEqual(F.tree_total_cost(small, 3), 12)
        self.assertEqual(F.tree_rank_cost(notable, 0), 150)
        self.assertEqual(F.tree_total_cost(notable, 1), 150)
        self.assertEqual(F.tree_total_cost(notable, 0), 0)
        # 1 ponto por nivel ; respec com 100 gastos: 1000 + 200 x 100 = 21000
        self.assertEqual(F.tree_budget(300), 300)
        self.assertEqual(F.tree_respec_gold(100), 21000)

    def test_full_tree_costs_match_the_client(self):
        # duvidas.md: 4745 (knight), 4525 (paladin), 4425 (monk), 4370 (druid), 4315 (sorcerer)
        cat = helpers.real_catalog()
        expected = {"knight": 4745, "paladin": 4525, "monk": 4425, "druid": 4370, "sorcerer": 4315}
        for t in cat.trees:
            total = sum(F.tree_total_cost(n, n["rank_maximo"]) for n in t["nos"])
            self.assertEqual(total, expected[t["vocacao"]], t["vocacao"])

    def test_area_targets_convention(self):
        self.assertEqual(F.area_targets(None, 4), 3)
        self.assertEqual(F.area_targets(1, 4), 3)
        self.assertEqual(F.area_targets(2, 4), 4)
        self.assertEqual(F.area_targets(2, 9), 5)
        self.assertEqual(F.area_targets(3, 4), 4)
        self.assertEqual(F.area_targets(6, 9), 9)
        # o raio de procura da IA (castSearchRadius) soma-se ao raio: convencao
        self.assertEqual(F.area_targets(None, 9, 2), 5)
        self.assertEqual(F.area_targets(1, 9, 2), 5)
        self.assertEqual(F.area_targets(2, 9, 2), 9)
        self.assertEqual(F.area_targets(2, 9, 3), 9)
        self.assertEqual(F.area_targets(2, 4, 3), 4)

    def test_battle_tactics_is_the_client_u4e(self):
        """u4e(e,t): a=floor(e/100); tier=a+t; qp=min(10,a*.5)+min(10,t); aim=min(1,.5+.025*qp);
        castSearchRadius=min(1+floor(qp/7),3); repositionMinMs=max(4000,5000-50*qp); infiniteKite=tier>=3."""
        t = F.battle_tactics(50, 0)
        self.assertEqual((t["tier"], t["qp"], t["aim_chance"], t["cast_search_radius"], t["reposition_min_ms"], t["infinite_kite"]),
                         (0, 0, 0.5, 1, 5000, False))
        t = F.battle_tactics(527, 6)   # a=5: qp = 2,5 + 6 = 8,5; aim = 0,7125; raio 2; tier 11
        self.assertEqual(t["tier"], 11)
        self.assertAlmostEqual(t["qp"], 8.5)
        self.assertAlmostEqual(t["aim_chance"], 0.7125)
        self.assertEqual(t["cast_search_radius"], 2)
        self.assertAlmostEqual(t["reposition_min_ms"], 4575)
        self.assertTrue(t["infinite_kite"])
        t = F.battle_tactics(2500, 10)  # tectos: a*.5 = 12,5 -> 10; ranks 10; qp 20 -> aim 1, raio 3
        self.assertEqual((t["qp"], t["aim_chance"], t["cast_search_radius"], t["reposition_min_ms"]), (20, 1.0, 3, 4000))
        self.assertEqual(F.battle_tactics(300, 0)["infinite_kite"], True)    # tier 3 pelo nivel
        self.assertEqual(F.battle_tactics(200, 0)["infinite_kite"], False)
        # a convencao: perfeita rende 1, imperfeita 60 %; o recebido e o simetrico
        self.assertAlmostEqual(F.tactics_quality(1.0), 1.0)
        self.assertAlmostEqual(F.tactics_quality(0.5), 0.8)
        self.assertAlmostEqual(F.tactics_taken(0.5), 1.2)
        self.assertEqual(F.CONSTANTS["tactics_imperfect_factor"].source, F.SOURCE_CONVENTION)
        self.assertEqual(F.CONSTANTS["tactics_aim_base"].source, F.SOURCE_CLIENT)

    def test_best_potion(self):
        self.assertEqual(F.best_potion(F.HEALTH_POTIONS, "knight", 100)["name"], "great health potion")
        self.assertEqual(F.best_potion(F.HEALTH_POTIONS, "knight", 200)["name"], "supreme health potion")
        self.assertEqual(F.best_potion(F.HEALTH_POTIONS, "sorcerer", 100)["name"], "health potion")
        self.assertEqual(F.best_potion(F.MANA_POTIONS, "sorcerer", 130)["name"], "ultimate mana potion")
        self.assertEqual(F.best_potion(F.MANA_POTIONS, "paladin", 130)["name"], "ultimate spirit potion")

    def test_guide_dps_curve(self):
        # 7.012 x 100^0.948 = 7.012 x 78.71... -> ~551.9
        self.assertAlmostEqual(F.guide_reference_dps(100), 7.012 * 100 ** 0.948)

    def test_every_constant_has_a_source(self):
        for key, c in F.CONSTANTS.items():
            self.assertIn(c.source, (F.SOURCE_CLIENT, F.SOURCE_GUIDE, F.SOURCE_CHANNEL, F.SOURCE_CONVENTION), key)
            self.assertTrue(c.where, key)
        # o que nao vem do cliente tem de estar marcado como tal
        self.assertEqual(F.CONSTANTS["armor_denominator"].source, F.SOURCE_GUIDE)
        self.assertEqual(F.CONSTANTS["attack_gcd_ms"].source, F.SOURCE_CLIENT)
        self.assertEqual(F.CONSTANTS["mana_regen_base_per_s"].source, F.SOURCE_CONVENTION)
        self.assertIsNone(F.MANA_REGEN_BASE)


if __name__ == "__main__":
    unittest.main()
