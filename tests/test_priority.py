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
        """(a) A conta e a do arvore.json; o motor tem de dar o mesmo nivel de alcance."""
        for voc, level in LEVELS.items():
            reach, avatar_id = cheapest_avatar_level(voc)
            b = self.plans[voc]
            info = b["priority"]
            self.assertEqual(info["avatar_level"], reach, voc)
            fits = reach <= level
            self.assertEqual(info["avatar"], fits, (voc, level, reach))
            self.assertEqual(b["tree"].get(avatar_id, 0) == 1, fits, voc)
            if fits:
                self.assertIsNone(b.get("avatar_plan"))
                # o caminho do Avatar custa exactamente o que a conta diz
                self.assertEqual(info["stage_points"]["avatar"], reach, voc)
            else:
                ap = b["avatar_plan"]
                self.assertIsNotNone(ap, voc)
                self.assertEqual(ap["level"], reach)
                self.assertTrue(ap["priority"]["avatar"])
                self.assertEqual(ap["tree"].get(avatar_id), 1)
        # os que ele deu: knight, druid e sorcerer tem o Avatar; o paladin nao (284 < caminho + 300)
        for voc in ("knight", "druid", "sorcerer"):
            self.assertTrue(self.plans[voc]["priority"]["avatar"], voc)
        self.assertFalse(self.plans["paladin"]["priority"]["avatar"])

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
