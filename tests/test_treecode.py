"""O codigo de build do cliente (`treecode.py`, ordem 8): os 5 codigos do supervisor
sao fixtures (`encode(alloc) == codigo` e `decode(codigo) == alloc`), ida-e-volta em
arvores aleatorias validas, codigo invalido -> None, e as regras da arvore (MK/LK/
O3e/yD/Ik/z3e/Up/F3e/j3e/fD) contra casos feitos a mao."""
import json
import random
import unittest

import helpers
from baiakvault import catalog, formulas as F, treecode

FIXTURE = helpers.FIXTURES / "codigos.json"


class Codes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = helpers.real_catalog()
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_the_five_supervisor_codes_round_trip(self):
        self.assertEqual(len(self.fixture["builds"]), 5)
        for b in self.fixture["builds"]:
            self.assertEqual(treecode.encode(self.cat, b["voc"], b["nivel"], b["alloc"]), b["codigo"], b["voc"])
            voc, level, ranks = treecode.decode(self.cat, b["codigo"])
            self.assertEqual((voc, level, ranks), (b["voc"], b["nivel"], b["alloc"]), b["voc"])
            self.assertEqual(treecode.points_spent(self.cat, voc, ranks), b["pontos"])
            self.assertTrue(treecode.is_connected(self.cat, voc, ranks), b["voc"])

    def test_random_valid_trees_round_trip(self):
        rng = random.Random(8)
        for voc in catalog.VOCATIONS:
            nodes = self.cat.tree_by_vocation[voc]["nos"]
            for _ in range(30):
                ranks = {n["id"]: rng.randint(1, n.get("rank_maximo") or 1) for n in nodes if rng.random() < 0.4}
                level = rng.choice([None, 1, 57, 1500, 9999999])
                code = treecode.encode(self.cat, voc, level, ranks)
                self.assertRegex(code, r"^BT1-[KPSDM](F|\d{1,7})-[0-9A-F]*$")
                dec = treecode.decode(self.cat, code)
                self.assertIsNotNone(dec, code)
                self.assertEqual(dec, (voc, level, ranks), code)

    def test_encode_follows_the_client_to_the_letter(self):
        # nivel nulo -> «F»; abaixo de 1 -> 1; fraccao -> floor; ranks acima do maximo cortados; negativos a 0
        self.assertTrue(treecode.encode(self.cat, "knight", None, {}).startswith("BT1-KF-"))
        self.assertTrue(treecode.encode(self.cat, "knight", 0, {}).startswith("BT1-K1-"))
        self.assertTrue(treecode.encode(self.cat, "monk", 57.9, {}).startswith("BT1-M57-"))
        self.assertEqual(treecode.encode(self.cat, "knight", 10, {}), "BT1-K10-")   # tudo a zero: sem digitos
        first = treecode.ordered_nodes(self.cat, "knight")[0]
        too_much = treecode.encode(self.cat, "knight", 10, {first["id"]: 99})
        self.assertEqual(too_much, "BT1-K10-" + format(first["rank_maximo"], "X"))
        self.assertEqual(treecode.encode(self.cat, "knight", 10, {first["id"]: -3}), "BT1-K10-")
        # a ordem dos nos e a ordenacao por id (ordem de string do JS)
        ids = [n["id"] for n in treecode.ordered_nodes(self.cat, "sorcerer")]
        self.assertEqual(ids, sorted(ids))

    def test_decode_rejects_bad_codes_and_tolerates_extra_or_missing_digits(self):
        for bad in ("", "BT2-K10-1", "BT1-X10-1", "BT1-K-1", "BT1-K12345678-1", "BT1-K10-1G", "bt1", None, "BT1-K10"):
            self.assertIsNone(treecode.decode(self.cat, bad), bad)
        # minusculas e espacos a volta aceitam-se (trim + upper), nivel 0 -> None (|| null)
        first = treecode.ordered_nodes(self.cat, "knight")[0]
        self.assertEqual(treecode.decode(self.cat, "  bt1-k10-1 "), ("knight", 10, {first["id"]: 1}))
        self.assertEqual(treecode.decode(self.cat, "BT1-K0-1")[1], None)
        # digitos a mais ignoram-se; a menos valem 0; um digito acima do maximo fica no maximo
        n = len(treecode.ordered_nodes(self.cat, "knight"))
        self.assertEqual(treecode.decode(self.cat, "BT1-K10-" + "0" * n + "FFFF"), ("knight", 10, {}))
        self.assertEqual(treecode.decode(self.cat, "BT1-K10-F")[2], {first["id"]: first["rank_maximo"]})


class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = helpers.real_catalog()

    def test_adjacency_is_both_ways(self):
        adj = treecode.adjacency(self.cat, "knight")
        self.assertIn("k_fury", adj["k_haste"])
        self.assertIn("k_haste", adj["k_fury"])
        for n in self.cat.tree_by_vocation["knight"]["nos"]:
            for req in n.get("requer") or []:
                self.assertIn(n["id"], adj[req])

    def test_connected_and_can_add_rank(self):
        cat = self.cat
        self.assertTrue(treecode.is_connected(cat, "knight", {}))
        self.assertTrue(treecode.is_connected(cat, "knight", {"k_fury": 1, "k_haste": 2}))
        self.assertFalse(treecode.is_connected(cat, "knight", {"k_haste": 2}))          # tier 1 sem o tier 0
        self.assertEqual(treecode.connected(cat, "knight", {"k_haste": 2}), set())
        self.assertFalse(treecode.is_connected(cat, "knight", {"k_fury": 1, "k_warlord": 1}))   # salta o Battle Haste
        # yD: tier 0 sempre (se couber); tier > 0 so com vizinho >= 1; rank < max; Up + Ik <= nivel
        self.assertTrue(treecode.can_add_rank(cat, "knight", {}, "k_fury", 1))
        self.assertFalse(treecode.can_add_rank(cat, "knight", {}, "k_fury", 0))
        self.assertFalse(treecode.can_add_rank(cat, "knight", {}, "k_haste", 10))
        self.assertTrue(treecode.can_add_rank(cat, "knight", {"k_fury": 1}, "k_haste", 2))
        self.assertFalse(treecode.can_add_rank(cat, "knight", {"k_fury": 1}, "k_haste", 1))   # 1 gasto + 1 > 1
        self.assertFalse(treecode.can_add_rank(cat, "knight", {"k_fury": 10}, "k_fury", 999))  # no maximo
        # a ligacao vale nos dois sentidos: o filho comprado abre o pai (Vigor via Sharpened Steel)
        self.assertTrue(treecode.can_add_rank(cat, "knight", {"k_fury": 1, "k_sharp": 1}, "k_vigor", 10))

    def test_costs_match_the_client_and_formulas(self):
        cat = self.cat
        fury = cat.node_by_id["k_fury"]         # small, custo 1
        mastery = cat.node_by_id["k_combat_mastery"]   # notable, custo 50
        self.assertEqual([treecode.next_rank_cost(fury, r) for r in range(4)], [1, 2, 3, 4])
        self.assertEqual([treecode.node_cost(fury, r) for r in range(4)], [0, 1, 3, 6])
        self.assertEqual(treecode.node_cost(fury, 99), 55)   # cortado ao maximo
        self.assertEqual(treecode.next_rank_cost(mastery, 0), 50)
        self.assertEqual((treecode.node_cost(mastery, 0), treecode.node_cost(mastery, 1)), (0, 50))
        for n in cat.tree_by_vocation["druid"]["nos"]:
            for r in range(0, (n.get("rank_maximo") or 1) + 1):
                self.assertEqual(treecode.node_cost(n, r), F.tree_total_cost(n, r), (n["id"], r))
                if r < (n.get("rank_maximo") or 1):
                    self.assertEqual(treecode.next_rank_cost(n, r), F.tree_rank_cost(n, r), (n["id"], r))
        self.assertEqual(treecode.points_spent(cat, "knight", {"k_fury": 3, "k_combat_mastery": 1, "desconhecido": 5}), 56)
        # fD: 0 sem pontos, senao 1000 + 200 x pontos (o mesmo do Reset All); gD: 400 x pontos do rank
        self.assertEqual([treecode.import_cost(p) for p in (0, 1, 527)], [0, 1200, 1000 + 200 * 527])
        self.assertEqual(treecode.refund_cost(3), 1200)

    def test_refund_sanitize_and_validate_import(self):
        cat = self.cat
        tree = {"k_fury": 1, "k_haste": 1, "k_warlord": 2}
        self.assertIsNone(treecode.refund_rank_cost(cat, "knight", tree, "k_fury"))     # desligava o resto
        self.assertIsNone(treecode.refund_rank_cost(cat, "knight", tree, "k_vigor"))    # sem rank
        self.assertEqual(treecode.refund_rank_cost(cat, "knight", tree, "k_warlord"), 2)   # Ik(rank-1) = 1 x 2
        self.assertEqual(treecode.refund_rank_cost(cat, "knight", {"k_fury": 1, "k_haste": 1}, "k_haste"), 1)
        # j3e: nos desconhecidos, zero ou negativos caem; acima do maximo corta; desligados caem
        self.assertEqual(treecode.sanitize(cat, "knight", {"k_fury": 12, "k_haste": 0, "k_warlord": 3, "x": 2, "k_vigor": -1}),
                         {"k_fury": 10})
        # o handler de Carregar: codigo invalido, vocacao errada, nivel a menos
        with self.assertRaises(treecode.TreeCodeError):
            treecode.validate_import(cat, "knight", 100, "lixo")
        with self.assertRaises(treecode.TreeCodeError):
            treecode.validate_import(cat, "knight", 100, treecode.encode(cat, "druid", 100, {"d_nature": 1}))
        code = treecode.encode(cat, "knight", 100, {"k_fury": 10, "k_haste": 10})
        with self.assertRaises(treecode.TreeCodeError):
            treecode.validate_import(cat, "knight", 50, code)
        clean, level, dropped = treecode.validate_import(cat, "knight", 110, code)
        self.assertEqual((clean, level, dropped), ({"k_fury": 10, "k_haste": 10}, 100, []))
        # um no desligado no codigo cai em silencio (como no cliente) e vem na lista dos que cairam
        clean, _, dropped = treecode.validate_import(cat, "knight", 200, treecode.encode(cat, "knight", 200, {"k_fury": 1, "k_warlord": 1}))
        self.assertEqual((clean, dropped), ({"k_fury": 1}, ["k_warlord"]))
        # sem nivel na BD nao ha verificacao de orcamento
        self.assertEqual(treecode.validate_import(cat, "knight", None, code)[0], {"k_fury": 10, "k_haste": 10})

    def test_purchase_order_is_clickable_checker(self):
        cat = self.cat
        self.assertIsNone(treecode.purchase_order_is_clickable(cat, "knight", [("k_fury", 1), ("k_haste", 1), ("k_haste", 2)]))
        self.assertEqual(treecode.purchase_order_is_clickable(cat, "knight", [("k_haste", 1)]), ("k_haste", 1))
        self.assertEqual(treecode.purchase_order_is_clickable(cat, "knight", [("k_fury", 2)]), ("k_fury", 2))
        self.assertEqual(treecode.purchase_order_is_clickable(cat, "knight", [("k_fury", 1), ("k_haste", 1)], level=1), ("k_haste", 1))


if __name__ == "__main__":
    unittest.main()
