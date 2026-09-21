"""Ordem 9 (21/09/2026): a build «prioridades do Andre» — Avatar > Exp > Loot > Crit >
Ataque > Dano critico > Elemento > o resto, cada etapa esgotada antes da seguinte.

(a) aos niveis que ele deu (Knight 548, Monk 336, Paladin 284, Druid 498, Sorcerer 481) o
    Avatar entra quando o caminho ligado mais barato + 300 cabe — o custo do caminho
    conta-se aqui SO com o `arvore.json` (Dijkstra proprio, sem o motor);
(b) propriedade: nenhum ponto de uma categoria mais baixa esta gasto enquanto uma acima
    ainda tiver um rank compravel com esses pontos (excepto «so ligacao»);
(c) `tree_check` e ordem clicavel; (d) os codigos BT1 de ida e volta;
(e) migracao v6; a omissao e «priority» em todas as vocacoes.
"""
import heapq
import json
import sqlite3
import time
import types
import unittest

import helpers
from baiakvault import builds, db, formulas as F, treecode

# os niveis que o Andre deu a 21/09/2026 (os mesmos da vault.db); a hunt e a de referencia
LEVELS = {"knight": 548, "monk": 336, "paladin": 284, "druid": 498, "sorcerer": 481}
AVATAR_COST = 300


def cheapest_avatar_level(vocation):
    """So com o `arvore.json`: o caminho mais barato (um rank por no) de um no de tier 0 ate um
    vizinho do Avatar, mais os 300 do Avatar. Um no e vizinho de outro quando um `requer` o
    outro (o cliente liga nos dois sentidos, MK)."""
    raw = json.loads((helpers.ROOT / "data" / "catalogo" / "arvore.json").read_text(encoding="utf-8"))
    tree = next(t for t in raw["arvores"] if t["vocacao"] == vocation)
    nodes = {n["id"]: n for n in tree["nos"]}
    adj = {nid: set() for nid in nodes}
    for n in tree["nos"]:
        for req in n.get("requer") or []:
            adj[n["id"]].add(req)
            adj[req].add(n["id"])
    avatar = next(n for n in tree["nos"] if n["tier"] == 11)
    assert avatar["custo_por_rank"] == AVATAR_COST

    def rank1_cost(n):
        return n["custo_por_rank"]   # rank 1 de um small custa custo x 1; um notable custa o custo

    dist = {}
    heap = []
    for nid, n in nodes.items():
        if n["tier"] == 0:
            dist[nid] = rank1_cost(n)
            heapq.heappush(heap, (dist[nid], nid))
    best = None
    while heap:
        d, nid = heapq.heappop(heap)
        if d > dist.get(nid, float("inf")):
            continue
        if avatar["id"] in adj[nid]:
            best = d if best is None else min(best, d)
            continue
        for v in adj[nid]:
            if v == avatar["id"]:
                continue
            nd = d + rank1_cost(nodes[v])
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return best + AVATAR_COST, avatar["id"]


class PriorityBuilds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = helpers.real_catalog()
        cls.planner, _ = helpers.planner()
        cls.plans = {voc: cls.planner.plan(voc, "priority", lv) for voc, lv in LEVELS.items()}

    def test_default_goal_is_priority_everywhere(self):
        self.assertEqual(builds.DEFAULT_GOAL, "priority")
        for voc, goals in db.GOALS_BY_VOCATION.items():
            self.assertEqual(goals[0], "priority", voc)
            self.assertEqual(db.default_goal(voc), "priority")
        self.assertIn("priority", db.GOALS)
        self.assertEqual(builds.BUILDS[0][1], "priority")
        self.assertEqual([v for v, g in builds.BUILDS if g == "priority"], ["knight", "druid", "sorcerer", "paladin", "monk"])

    def test_avatar_when_the_cheapest_path_plus_300_fits(self):
        """(a) A conta e a do arvore.json; o motor tem de dar o mesmo nivel de alcance da rota
        mais barata, e o Avatar entra quando ela cabe (a rota escolhida so pode ser mais cara
        se ainda couber — ordem 9b)."""
        for voc, level in LEVELS.items():
            reach, avatar_id = cheapest_avatar_level(voc)
            b = self.plans[voc]
            info = b["priority"]
            rt = info["route"]
            self.assertEqual(rt["cheapest_level"], reach, voc)
            self.assertEqual(info["avatar_level"], rt["cost"] + AVATAR_COST, voc)
            self.assertGreaterEqual(info["avatar_level"], reach, voc)
            fits = reach <= level
            self.assertEqual(info["avatar"], fits, (voc, level, reach))
            self.assertEqual(b["tree"].get(avatar_id, 0) == 1, fits, voc)
            if fits:
                self.assertIsNone(b.get("avatar_plan"))
                self.assertLessEqual(info["avatar_level"], level, voc)
                # a rota do Avatar custa exactamente o que o motor diz que custa
                self.assertEqual(info["stage_points"]["avatar"], info["avatar_level"], voc)
            else:
                ap = b["avatar_plan"]
                self.assertIsNotNone(ap, voc)
                self.assertLessEqual(info["avatar_level"], reach + builds.PRIORITY_ROUTE_MAX_DELAY, voc)
                self.assertEqual(ap["level"], info["avatar_level"])
                self.assertTrue(ap["priority"]["avatar"])
                self.assertEqual(ap["tree"].get(avatar_id), 1)
                # a build do nivel X leva a MESMA rota que se escolheu abaixo dele
                self.assertTrue(ap["priority"]["route"]["forced"])
                self.assertEqual(ap["priority"]["avatar_path"], info["avatar_path"])
                # e a rota ja esta comprada agora (plano B), a rank >= 1
                self.assertEqual(info["stage_points"]["avatar"], rt["cost"], voc)
                for nid in info["avatar_path"]:
                    self.assertGreaterEqual(b["tree"].get(nid, 0), 1, (voc, nid))
        # os que ele deu: knight, druid e sorcerer tem o Avatar; o paladin nao (284 < caminho + 300)
        for voc in ("knight", "druid", "sorcerer"):
            self.assertTrue(self.plans[voc]["priority"]["avatar"], voc)
        self.assertFalse(self.plans["paladin"]["priority"]["avatar"])

    def test_route_is_at_least_as_good_as_the_cheapest(self):
        """Ordem 9b (a): nos 5 ao nivel dele, a rota escolhida e pelo menos tao boa quanto a
        mais barata no vector lexicografico das prioridades; a mais barata e a do arvore.json."""
        for voc, level in LEVELS.items():
            info = self.plans[voc]["priority"]
            rt = info["route"]
            reach, _ = cheapest_avatar_level(voc)
            self.assertEqual(rt["cheapest_cost"] + AVATAR_COST, reach, voc)
            self.assertIsNotNone(rt["vector"], voc)
            self.assertIsNotNone(rt["cheapest_vector"], voc)
            self.assertGreaterEqual(tuple(rt["vector"]), tuple(rt["cheapest_vector"]), (voc, rt["route"], rt["cheapest_route"]))
            self.assertEqual(rt["vector"][0], 1, voc)   # avaliada com o Avatar
            self.assertGreaterEqual(rt["cost"], rt["cheapest_cost"], voc)
            self.assertFalse(rt["forced"], voc)
            # a rota so sobe e comeca no tier 0
            node_by_id = {n["id"]: n for n in self.cat.tree_by_vocation[voc]["nos"]}
            self.assertEqual(node_by_id[rt["route"][0]]["tier"], 0, voc)
            for a, b in zip(rt["route"], rt["route"][1:]):
                self.assertIn(a, node_by_id[b].get("requer") or [], (voc, a, b))
            self.assertIn(rt["route"][-1], node_by_id[builds.AVATAR_NODE[voc]]["requer"], voc)
            # a rota sozinha e clicavel a partir do tier 0 e ligada
            steps = [(nid, 1) for nid in rt["route"]]
            self.assertIsNone(treecode.purchase_order_is_clickable(self.cat, voc, steps), voc)
            self.assertTrue(treecode.is_connected(self.cat, voc, {nid: 1 for nid in rt["route"]}), voc)
            # e a ordem de compra da build comeca pela rota, na etapa «avatar»
            order = self.plans[voc]["order"]
            self.assertEqual([st.node_id for st in order[:len(rt["route"])]], rt["route"], voc)
            self.assertTrue(all(st.stage == "avatar" for st in order[:len(rt["route"])]), voc)

    def test_routes_enumeration_count_and_time(self):
        """Ordem 9b (c): as rotas por vocacao enumeram-se (centenas, abaixo do tecto de poda) em
        bem menos de 2 s, e a escolha inteira por stat tambem; a contagem bate na conta a mao."""
        from baiakvault import validation
        by_hand = validation.avatar_routes_by_hand(json.loads(
            (helpers.ROOT / "data" / "catalogo" / "arvore.json").read_text(encoding="utf-8")))
        for voc in LEVELS:
            t0 = time.perf_counter()
            routes = builds.avatar_routes(self.cat, voc)
            dt = time.perf_counter() - t0
            self.assertLess(dt, 2.0, (voc, dt))
            self.assertGreater(len(routes), 1, voc)
            self.assertLessEqual(len(routes), builds.PRIORITY_ROUTE_MAX_ENUM, voc)
            self.assertEqual((len(routes), min(c for c, _ in routes)), by_hand[voc], voc)
            self.assertEqual(len({tuple(r) for _, r in routes}), len(routes), voc)   # sem repetidas
            t0 = time.perf_counter()
            ch = builds.choose_avatar_route(self.cat, voc, LEVELS[voc], frozenset({"physical"}))
            dt = time.perf_counter() - t0
            self.assertLess(dt, 2.0, (voc, dt))
            self.assertEqual(ch["routes_total"], len(routes))
            self.assertEqual(ch["routes_pruned"], 0)

    def test_paladin_below_avatar_has_level_x_and_both_plans(self):
        """Ordem 9b (B): o paladin 284 tem o nivel X, a rota com os ranks do nivel X e os planos
        A e B com numeros; a build do plano B ao nivel X tem o Avatar e passa no tree_check."""
        b = self.plans["paladin"]
        info = b["priority"]
        self.assertFalse(info["avatar"])
        plans = b["avatar_plans"]
        self.assertIsNotNone(plans)
        lx = plans["level"]
        self.assertEqual(lx, info["avatar_level"])
        self.assertEqual(lx, plans["route_cost"] + AVATAR_COST)
        self.assertGreaterEqual(lx, 319)   # a mais barata: 19 + 300
        self.assertLessEqual(lx, 319 + builds.PRIORITY_ROUTE_MAX_DELAY)
        self.assertEqual(plans["route"], info["avatar_path"])
        ap = b["avatar_plan"]
        self.assertEqual(ap["level"], lx)
        self.assertEqual(ap["tree"].get("p_avatar_light"), 1)
        self.assertTrue(builds.tree_check(self.cat, "paladin", lx, ap["tree"])["ok"])
        for nid in plans["route"]:
            self.assertEqual(plans["route_ranks"][nid], ap["tree"].get(nid, 0))
            self.assertGreaterEqual(plans["route_ranks"][nid], 1)
        # plano A: so a rota, sem gold, com (nivel - R) pontos parados; DPS medido e abaixo do B
        a, pb = plans["a"], plans["b"]
        self.assertEqual(a["gold"], 0)
        self.assertEqual(a["unspent"], 284 - plans["route_cost"])
        self.assertEqual(a["tree"], {nid: 1 for nid in plans["route"]})
        self.assertGreater(a["dps"], 0)
        self.assertGreater(pb["dps"], a["dps"])
        self.assertEqual(pb["dps"], b["metrics"]["dps_cycle"])
        self.assertEqual(pb["gold"], treecode.import_cost(lx))
        self.assertEqual(pb["unspent"], 0)
        self.assertEqual(plans["recommended"], "B")
        # os dois codigos: o de agora e o do nivel X, os dois com a rota
        now_code = treecode.encode(self.cat, "paladin", 284, b["tree"])
        x_code = treecode.encode(self.cat, "paladin", lx, ap["tree"])
        self.assertTrue(now_code.startswith("BT1-P284-"))
        self.assertTrue(x_code.startswith("BT1-P%d-" % lx))
        self.assertEqual(treecode.decode(self.cat, x_code), ("paladin", lx, ap["tree"]))
        # os que chegam nao tem planos
        for voc in ("knight", "druid", "sorcerer"):
            self.assertIsNone(self.plans[voc]["avatar_plans"], voc)

    def test_higher_categories_are_exhausted_before_lower_ones(self):
        """(b) Para cada categoria, no estado da arvore no fim da etapa dela: nenhum rank
        compravel (com o caminho que faltar) cabe nos pontos que as etapas abaixo gastaram
        (ligacoes incluidas: sao pontos que ficaram livres) + os por gastar."""
        order = builds.PRIORITY_ORDER
        for voc, b in self.plans.items():
            info = b["priority"]
            cat_of = info["category"]
            node_by_id = {n["id"]: n for n in self.cat.tree_by_vocation[voc]["nos"]}
            adj = builds._adjacency(self.cat, voc)
            unspent = F.tree_budget(b["level"]) - b["points_spent"]
            for i, stage in enumerate(order[:-1]):
                if stage == "avatar":
                    continue   # o Avatar e um pacote: coberto pelo teste (a)
                # a arvore como estava no fim desta etapa: so os passos das etapas ate ela
                tree_c = {}
                lower = unspent
                for st in b["order"]:
                    if order.index(st.stage) <= i:
                        tree_c[st.node_id] = max(tree_c.get(st.node_id, 0), st.rank)
                    else:
                        lower += st.cost
                for nid, node in node_by_id.items():
                    if cat_of[nid] != stage or tree_c.get(nid, 0) >= (node.get("rank_maximo") or 1):
                        continue
                    path = builds.unlock_path(node, tree_c, adj, node_by_id)
                    if path is None:
                        continue
                    cost = sum(F.tree_rank_cost(node_by_id[p], tree_c.get(p, 0)) for p in path)
                    cost += F.tree_rank_cost(node, tree_c.get(nid, 0))
                    self.assertGreater(cost, lower, (voc, stage, node["nome"], tree_c.get(nid, 0), cost, lower))

    def test_client_rules_and_clickable_order_and_codes(self):
        """(c) e (d), nas 5 builds e na do nivel do Avatar do paladin."""
        plans = list(self.plans.values()) + [p["avatar_plan"] for p in self.plans.values() if p.get("avatar_plan")]
        for b in plans:
            voc, level = b["vocation"], b["level"]
            chk = builds.tree_check(self.cat, voc, level, b["tree"])
            self.assertTrue(chk["ok"], (voc, level, chk))
            self.assertEqual(chk["spent"], b["points_spent"])
            steps = [(st.node_id, st.rank) for st in b["order"]]
            self.assertIsNone(treecode.purchase_order_is_clickable(self.cat, voc, steps), (voc, level))
            # a ordem cobre a arvore toda, e por etapas na ordem das prioridades
            self.assertEqual({n: r for n, r in steps if r == b["tree"][n]}, b["tree"])
            stages = [builds.PRIORITY_ORDER.index(st.stage) for st in b["order"]]
            self.assertEqual(stages, sorted(stages), (voc, level))
            code = treecode.encode(self.cat, voc, level, b["tree"])
            self.assertTrue(code.startswith("BT1-%s%d-" % (treecode.VOCATION_LETTER[voc], level)))
            self.assertEqual(treecode.decode(self.cat, code), (voc, level, b["tree"]))

    def test_priority_is_measured_like_damage_and_compared(self):
        for voc, b in self.plans.items():
            self.assertEqual(b["goal"], "priority")
            self.assertEqual(builds.metric_goal("priority"), "damage")
            d = b["damage_plan"]
            self.assertEqual((d["goal"], d["level"], d["hunt"]), ("damage", b["level"], b["hunt"]))
            self.assertGreater(b["metrics"]["dps_cycle"], 0)
            self.assertGreater(d["metrics"]["dps_cycle"], 0)
            tot = b["priority"]["totals"]
            for k in ("expPct", "lootPct", "critChance", "atkPct", "spellDmgPct", "critDmg"):
                self.assertGreaterEqual(tot[k], 0.0)

    def test_categories_follow_the_rules_of_the_order(self):
        """Berserk Mastery -> attack; Lord of Destruction -> crit; Guiding Presence -> exp;
        Twin Bursts -> element (com gelo) ou rest (sem); Hell's Core -> attack."""
        el = frozenset({"ice", "physical"})
        by_name = {n["nome"]: n for t in self.cat.tree_by_vocation.values() for n in t["nos"]}
        self.assertEqual(builds.priority_category(by_name["Berserk Mastery"], el), "attack")
        self.assertEqual(builds.priority_category(by_name["Lord of Destruction"], el), "crit")
        self.assertEqual(builds.priority_category(by_name["Guiding Presence"], el), "exp")
        self.assertEqual(builds.priority_category(by_name["Twin Bursts"], el), "element")
        self.assertEqual(builds.priority_category(by_name["Twin Bursts"], frozenset({"physical"})), "rest")
        self.assertEqual(builds.priority_category(by_name["Hell's Core"], el), "attack")
        self.assertEqual(builds.priority_category(by_name["Battle Tactics"], el), "rest")
        self.assertEqual(builds.priority_category(by_name["Avatar of Steel"], el, "knight"), "avatar")
        # o knight nao tem Exp nem Loot; o sorcerer nao tem Loot
        knight = {builds.priority_category(n, el) for n in self.cat.tree_by_vocation["knight"]["nos"]}
        self.assertNotIn("exp", knight)
        self.assertNotIn("loot", knight)
        sorc = {builds.priority_category(n, el) for n in self.cat.tree_by_vocation["sorcerer"]["nos"]}
        self.assertNotIn("loot", sorc)
        self.assertIn("exp", sorc)


def _node(nid, nome, tier, efeito, requer=None, custo=1, tipo="small", rank_max=10):
    return {"id": nid, "nome": nome, "tier": tier, "tipo": tipo, "custo_por_rank": custo, "rank_maximo": rank_max,
            "requer": requer or [], "efeito_por_rank": efeito}


class RouteChoiceOnAHandMadeTree(unittest.TestCase):
    """Ordem 9b (b): uma arvore feita a mao em que a rota mais barata passa por HP e uma rota
    2 pontos mais cara passa por Exp — o motor tem de escolher a segunda (e a mais barata
    quando o tecto de atraso nao a deixa)."""

    def setUp(self):
        # tier 0: HP (1) e Exp (1); tier 1: HP (1) e Exp (2); tier 2: HP (1) e Exp (2); tier 3: o Avatar (300)
        nodes = [_node("k_hp0", "HP 0", 0, {"hpPct": 1}), _node("k_exp0", "Exp 0", 0, {"expPct": 1}),
                 _node("k_hp1", "HP 1", 1, {"hpPct": 1}, ["k_hp0"]), _node("k_exp1", "Exp 1", 1, {"expPct": 1}, ["k_exp0"], custo=2),
                 _node("k_hp2", "HP 2", 2, {"hpPct": 1}, ["k_hp1"]), _node("k_exp2", "Exp 2", 2, {"expPct": 1}, ["k_exp1"], custo=2),
                 _node("k_avatar_steel", "Avatar of Steel", 3, {"atkPct": 10}, ["k_hp2", "k_exp2"], custo=300, tipo="notable", rank_max=1)]
        self.cat = types.SimpleNamespace(tree_by_vocation={"knight": {"vocacao": "knight", "nos": nodes}},
                                         node_by_id={n["id"]: n for n in nodes})
        self.el = frozenset({"physical"})

    def test_routes_and_costs(self):
        routes = builds.avatar_routes(self.cat, "knight")
        self.assertEqual(sorted(routes), [(3, ["k_hp0", "k_hp1", "k_hp2"]), (5, ["k_exp0", "k_exp1", "k_exp2"])])

    def test_the_useful_route_beats_the_cheapest_when_the_avatar_fits(self):
        ch = builds.choose_avatar_route(self.cat, "knight", 320, self.el)
        self.assertTrue(ch["fits"])
        self.assertEqual(ch["route"], ["k_exp0", "k_exp1", "k_exp2"])
        self.assertEqual((ch["cost"], ch["level"]), (5, 305))
        self.assertEqual((ch["cheapest_cost"], ch["cheapest_level"], ch["cheapest_route"]), (3, 303, ["k_hp0", "k_hp1", "k_hp2"]))
        self.assertGreater(tuple(ch["vector"]), tuple(ch["cheapest_vector"]))
        self.assertGreater(ch["vector"][1], ch["cheapest_vector"][1])   # mais exp
        self.assertEqual(ch["vector"][0], 1)

    def test_below_the_avatar_the_delay_cap_decides(self):
        ch = builds.choose_avatar_route(self.cat, "knight", 100, self.el)
        self.assertFalse(ch["fits"])
        self.assertEqual(ch["eval_level"], 303 + builds.PRIORITY_ROUTE_MAX_DELAY)
        self.assertEqual(ch["route"], ["k_exp0", "k_exp1", "k_exp2"])   # atrasa 2 niveis, dentro do tecto de 5
        self.assertEqual(ch["level"], 305)
        ch1 = builds.choose_avatar_route(self.cat, "knight", 100, self.el, max_delay=1)
        self.assertEqual(ch1["route"], ["k_hp0", "k_hp1", "k_hp2"])   # 2 > 1: fica a mais barata
        self.assertEqual(ch1["level"], 303)

    def test_a_forced_route_is_kept_and_marked(self):
        ch = builds.choose_avatar_route(self.cat, "knight", 320, self.el, forced=("k_hp0", "k_hp1", "k_hp2"))
        self.assertTrue(ch["forced"])
        self.assertEqual((ch["route"], ch["cost"], ch["level"]), (["k_hp0", "k_hp1", "k_hp2"], 3, 303))

    def test_dominance_pruning_drops_routes_that_only_add_rest_nodes(self):
        category = {"k_hp0": "rest", "k_hp1": "rest", "k_exp0": "exp"}
        keep, dropped = builds._dominated_routes([(2, ["k_hp0", "k_hp1"]), (1, ["k_hp0"]), (2, ["k_exp0", "k_hp1"])], category)
        self.assertEqual(dropped, 1)
        self.assertEqual(sorted(keep), [(1, ["k_hp0"]), (2, ["k_exp0", "k_hp1"])])


class SchemaV6(unittest.TestCase):
    def test_v5_to_v6_keeps_the_five_and_accepts_priority(self):
        path = helpers.temp_dir() / "v5.db"
        conn = sqlite3.connect(str(path))
        for script in db.MIGRATIONS[:5]:
            conn.executescript(script)
        conn.execute("PRAGMA user_version = 5")
        rows = [(1, "Knight", "knight", "knight", 548, "livrariafire-cave", None, '["Fierce Berserk", "Groundshaker"]', "soulmaimer"),
                (2, "Druid", "druid", "druid", 498, "livrariafire-cave", None, '["Eternal Winter", "Avalanche"]', None),
                (3, "Sorcerer", "sorcerer", "sorcerer", 481, "livrariafire-cave", "damage", None, None),
                (4, "Monk", "monk", "monk", 336, "livrariafire-cave", None, None, None),
                (5, "Paladin", "paladin", "paladin", 284, "livrariafire-cave", "best", None, None)]
        conn.executemany("INSERT INTO characters (id, name, slug, vocation, level, current_hunt, goal, fixed_rotation_json, "
                         "fixed_weapon, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'x')", rows)
        conn.execute("INSERT INTO character_tree (character_id, node_key, rank, source) VALUES (1, 'k_fury', 3, 'manual')")
        conn.execute("INSERT INTO readings (character_id, at, level) VALUES (1, '2026-09-21', 548)")
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO characters (name, slug, goal, updated_at) VALUES ('X', 'x', 'priority', 'x')")
        conn.commit()
        conn.close()
        conn = db.connect(path)
        try:
            self.assertEqual(db.schema_version(conn), 6)
            self.assertEqual(db.SCHEMA_VERSION, 6)
            vault = db.Vault(conn, helpers.real_catalog())
            got = [(c["id"], c["name"], c["slug"], c["vocation"], c["level"], c["current_hunt"], c["goal"],
                    c["fixed_rotation_json"], c["fixed_weapon"]) for c in vault.characters()]
            self.assertEqual(sorted(got), rows)
            self.assertEqual(vault.character("knight")["fixed_rotation"], ["Fierce Berserk", "Groundshaker"])
            self.assertEqual(conn.execute("SELECT count(*) FROM character_tree").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM readings").fetchone()[0], 1)
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            # «priority» passa a ser aceite, em todas as vocacoes; NULL continua a ser «a omissao»
            for slug in ("knight", "druid", "sorcerer", "monk", "paladin"):
                vault.upsert_character(vault.character(slug)["name"], goal="priority")
                self.assertEqual(vault.character(slug)["goal"], "priority")
            cid = vault.upsert_character("Novo", vocation="paladin", level=10)
            self.assertIsNone(vault.character(cid)["goal"])
            with self.assertRaises(db.VaultError):
                vault.upsert_character("Novo", goal="heal")
            self.assertEqual(db.check(conn, helpers.real_catalog()), [])
            # apagar continua a cascatear para os filhos
            vault.delete_character(1)
            self.assertEqual(conn.execute("SELECT count(*) FROM character_tree").fetchone()[0], 0)
        finally:
            conn.close()
