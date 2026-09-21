"""Ordem 9 (21/09/2026): a build «prioridades do Andre»; desde a ordem 10b (21/09/2026 13:05,
«Avatar, Exp, Loot, e tu decides o resto») sao quatro etapas — Avatar (rota escolhida pelas
prioridades: exp, loot, DPS do modelo), Exp e Loot pelo efeito por ponto (esgotadas antes da
seguinte) e «damage» (tudo o que rende mais DPS no simulador, o mesmo stat pela conta por
ponto — a etapa 2 da ordem 10). A ordem da 9 (Avatar > Exp > Loot > Crit > Ataque > Dano
critico > Elemento > resto) fica em `PRIORITY_ORDER_ORDEM_9` e testa-se so a estrutura por
etapas.

(a) aos niveis que ele deu (Knight 548, Monk 336, Paladin 284, Druid 498, Sorcerer 481) o
    Avatar entra quando o caminho ligado mais barato + 300 cabe — o custo do caminho
    conta-se aqui SO com o `arvore.json` (Dijkstra proprio, sem o motor);
(b) propriedade (10b): nenhum ponto foi ao dano enquanto havia um rank de Exp ou de Loot
    compravel com o que sobrava (ligacao a parte), e dentro de Exp/Loot a regra da 9c (efeito
    por ponto com o caminho no custo);
(c) propriedade (ordem 10) na etapa «damage»: nenhum rank por comprar rende mais por ponto no
    modelo linear do que um rank comprado com os mesmos stats, e nenhum ponto foi a Exp/Loot
    excepto «so ligacao» ou «ponto que sobrou»;
(d) a rota escolhida tem exp/loot >= a de maior DPS e, a exp/loot iguais, DPS >=; e DPS >= a
    mais barata quando esta tem o mesmo exp/loot; (e) o bloco «o que rende mais» tem as tres
    linhas > 0 e o veredicto comeca pelo stat de maior ganho por ponto;
(f) `tree_check`, ordem clicavel, codigos BT1 de ida e volta; migracao v6; a omissao e
    «priority» em todas as vocacoes.
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
# a ordem da 9 (para os testes da estrutura por etapas; a build usa builds.PRIORITY_ORDER = avatar, exp, loot, damage)
ORDER_9 = ("avatar", "exp", "loot", "crit", "attack", "critdmg", "element", "rest")
ORDER_10B = ("avatar", "exp", "loot", "damage")
STAT_STAGES_9 = ("crit", "attack", "critdmg", "element")


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


def same_stat_violations(cat, vocation, plan, stages=STAT_STAGES_9, value=None, any_signature=False):
    """Repete os passos da build e, a cada rank comprado nas `stages` (ordem 9c: crit/attack/
    critdmg/element; ordem 10: «damage»; 10b: exp/loot com `any_signature`, porque nessas etapas
    tudo se compara pelo efeito por ponto), procura um no com os mesmos stats (e, na 9c, da mesma
    categoria), ligado e a caber, cujo proximo rank rendesse mais por ponto (`value(node, stage)`
    / custo, caminho incluido; a omissao e o efeito da categoria). Os ranks de caminho somam-se
    ao custo do rank que os pediu. Lista de mensagens."""
    node_by_id = {n["id"]: n for n in cat.tree_by_vocation[vocation]["nos"]}
    adj = builds._adjacency(cat, vocation)
    info = plan["priority"]
    category, elements = info["category"], frozenset(info["elements"])
    budget = F.tree_budget(plan["level"])
    by_category = value is None
    value = value or (lambda node, stage: builds._effect_value(node, stage, elements))

    def signature(nid):
        return () if any_signature else builds._stat_signature(node_by_id[nid])

    def per_point(nid, ranks, stage):
        node = node_by_id[nid]
        if ranks.get(nid, 0) >= (node.get("rank_maximo") or 1):
            return None
        path = builds.unlock_path(node, ranks, adj, node_by_id)
        if path is None:
            return None
        c = sum(F.tree_rank_cost(node_by_id[p], ranks.get(p, 0)) for p in path) + F.tree_rank_cost(node, ranks.get(nid, 0))
        return value(node, stage) / c, c

    def is_path(st):
        # na 9c um rank de caminho e o de categoria diferente da etapa (ou marcado `link`); na
        # ordem 10 so o marcado `link` — um no sem valor no modelo comprado pelo simulador e uma compra
        if getattr(st, "link", False):
            return True
        return by_category and category.get(st.node_id) != st.stage

    slack = 1.0001
    out = []
    ranks = {}
    before_path, path_cost = None, 0    # o estado antes dos ranks de caminho da compra em curso
    for st in plan["steps"]:
        stage = st.stage
        if stage in stages and not is_path(st):
            start = before_path if before_path is not None else dict(ranks)
            cost = path_cost + st.cost
            spent = builds._spent(cat, start)
            value.spent = spent   # o `value` da ordem 10 escolhe por aqui o modelo em vigor
            mine = value(node_by_id[st.node_id], stage) / cost
            for nid in node_by_id:
                if mine <= 0 or (by_category and category[nid] != stage) or nid == st.node_id or signature(nid) != signature(st.node_id):
                    continue
                pp = per_point(nid, start, stage)
                if pp is None or spent + pp[1] > budget:
                    continue
                if pp[0] > mine * slack:
                    out.append("%s %d %s: %s rank %d (%d pts, %.4f/pt) com %s rank %d a %.4f/pt por %d pts" % (
                        vocation, plan["level"], stage, node_by_id[st.node_id]["nome"], st.rank, cost, mine,
                        node_by_id[nid]["nome"], start.get(nid, 0) + 1, pp[0], pp[1]))
                    break
            before_path, path_cost = None, 0
        elif stage in stages:
            # um rank de caminho: o custo e da compra seguinte
            if before_path is None:
                before_path = dict(ranks)
            path_cost += st.cost
        else:
            before_path, path_cost = None, 0
        ranks[st.node_id] = st.rank
    return out


def damage_stage_violations(cat, vocation, plan):
    """Ordem 10 (b): na etapa «damage», com o modelo linear medido no inicio da etapa
    (`priority.stat_model`), nenhum rank comprado rende menos por ponto do que outro rank com
    os mesmos stats que estava ligado e a caber. Os ranks de caminho e os que o modelo nao ve
    (valor 0: HP, notables especiais…) nao se comparam — sao do simulador."""
    history = plan["priority"].get("stat_models")
    if not history:
        return ["%s %d: sem modelo" % (vocation, plan["level"])]

    def value(node, stage):
        # o modelo em vigor na compra: o ultimo cujo «a partir de N pontos» <= pontos gastos antes dela
        spent = value.spent if value.spent is not None else 0
        model = max((m for m in history if m[0] <= spent), key=lambda m: m[0], default=history[0])[1]
        return builds.model_rank_value(node, model)
    value.spent = None
    return same_stat_violations(cat, vocation, plan, stages=("damage",), value=value)


def exp_loot_before_damage_violations(cat, vocation, plan):
    """Ordem 10b (b): repete os passos e, a cada rank da etapa «damage» (ligacao a parte), procura um
    rank de Exp ou de Loot (no de categoria exp/loot, abaixo do maximo) ligado e a caber — com o
    caminho de desbloqueio no custo — nos pontos que sobravam nesse momento. Um que houvesse era um
    ponto ido ao dano antes de a Exp/Loot se esgotar. E a etapa «exp» tem de vir antes da «loot» e
    as duas antes da «damage». Lista de mensagens."""
    node_by_id = {n["id"]: n for n in cat.tree_by_vocation[vocation]["nos"]}
    adj = builds._adjacency(cat, vocation)
    info = plan["priority"]
    category = info["category"]
    budget = F.tree_budget(plan["level"])
    out = []
    ranks = {}
    order = [st.stage for st in plan["steps"]]
    idx = [ORDER_10B.index(s) for s in order if s in ORDER_10B]
    if idx != sorted(idx):
        out.append("%s %d: etapas fora de ordem: %s" % (vocation, plan["level"], order))
    for st in plan["steps"]:
        if st.stage == "damage" and not getattr(st, "link", False):
            spent = builds._spent(cat, ranks)
            for nid, node in node_by_id.items():
                if category.get(nid) not in ("exp", "loot") or ranks.get(nid, 0) >= (node.get("rank_maximo") or 1):
                    continue
                path = builds.unlock_path(node, ranks, adj, node_by_id)
                if path is None:
                    continue
                c = sum(F.tree_rank_cost(node_by_id[p], ranks.get(p, 0)) for p in path) + F.tree_rank_cost(node, ranks.get(nid, 0))
                if spent + c <= budget:
                    out.append("%s %d: %s rank %d (dano) comprado com %s rank %d (%s, %d pts) compravel nos %d que sobravam"
                               % (vocation, plan["level"], node_by_id[st.node_id]["nome"], st.rank, node["nome"],
                                  ranks.get(nid, 0) + 1, category[nid], c, budget - spent))
                    break
        ranks[st.node_id] = st.rank
    return out


def exp_loot_violations(cat, vocation, plan):
    """Ordem 10 (b): nenhum ponto da etapa «damage» foi a um no de Exp/Loot, excepto como «so
    ligacao» (caminho) ou «ponto que sobrou» (o refill sem onde por um ponto: ganho medido 0 e
    nenhum passo com ganho > 0 depois dele)."""
    info = plan["priority"]
    steps = [st for st in plan["steps"] if st.stage == "damage"]
    last_positive = max((i for i, st in enumerate(steps) if st.gain_per_point > 0), default=-1)
    out = []
    for i, st in enumerate(steps):
        if info["category"].get(st.node_id) in ("exp", "loot") and not getattr(st, "link", False) and st.node_id not in info["link"]:
            if not (st.gain_per_point <= 0 and i > last_positive):
                out.append("%s %d: %s rank %d (%s) comprado na etapa damage sem ser ligacao nem ponto que sobrou"
                           % (vocation, plan["level"], st.node_id, st.rank, info["category"][st.node_id]))
    return out


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
        """Ordem 10b (d): nos 5 ao nivel dele, a rota escolhida tem (exp, loot) >= a de maior DPS
        no modelo e >= a mais barata; a exp/loot iguais, o DPS no simulador >= (a mais barata e
        a de maior DPS entram sempre na confirmacao); o modelo linear ordenou as rotas e a
        escolhida e uma das confirmadas. A mais barata e a do arvore.json."""
        for voc, level in LEVELS.items():
            info = self.plans[voc]["priority"]
            rt = info["route"]
            reach, _ = cheapest_avatar_level(voc)
            self.assertEqual(rt["cheapest_cost"] + AVATAR_COST, reach, voc)
            self.assertTrue(rt["by_model"], voc)
            self.assertIsNotNone(rt["sim_score"], voc)
            self.assertIsNotNone(rt["cheapest_sim"], voc)
            self.assertEqual(rt["priority_stages"], ("exp", "loot"), voc)
            v10b, cheap = rt["vector_10b"], rt["cheapest_vector_10b"]
            self.assertIsNotNone(v10b, voc)
            self.assertIsNotNone(cheap, voc)
            self.assertEqual(len(v10b), 4, voc)
            self.assertGreaterEqual(tuple(v10b[1:3]), tuple(cheap[1:3]), (voc, v10b, cheap))
            if tuple(v10b[1:3]) == tuple(cheap[1:3]):
                self.assertGreaterEqual(rt["sim_score"], rt["cheapest_sim"] * (1 - 1e-9), (voc, rt["route"], rt["cheapest_route"]))
            dps_best = rt["dps_best"]
            self.assertIsNotNone(dps_best, voc)
            self.assertGreaterEqual(tuple(v10b[1:3]), tuple(dps_best["vector"][1:3]), (voc, v10b, dps_best))
            self.assertEqual(dps_best["same_exp_loot"], tuple(v10b[1:3]) == tuple(dps_best["vector"][1:3]), voc)
            self.assertEqual(dps_best["same"], dps_best["route"] == rt["route"], voc)
            if dps_best["same_exp_loot"]:
                self.assertIsNotNone(dps_best["sim_score"], voc)
                self.assertGreaterEqual(rt["sim_score"], dps_best["sim_score"] * (1 - 1e-9), (voc, rt["route"], dps_best["route"]))
            else:
                # a rota de maior DPS no modelo tem menos exp/loot: a regra dele decide, e a pagina mostra-a
                self.assertGreaterEqual(dps_best["model_score"], rt["model_score"] * (1 - 1e-9), voc)
            self.assertIsNotNone(rt["model_best_route"], voc)
            self.assertIsNotNone(rt["sim_check"], voc)
            self.assertGreaterEqual(rt["sim_ties"], 1, voc)
            self.assertLessEqual(rt["sim_ties"], builds.PRIORITY_ROUTE_SIM_TIES + 1, voc)
            self.assertIsNotNone(rt["vector"], voc)
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

    def test_stage_structure_and_the_order_9_constant(self):
        """A estrutura por etapas ficou (ordem 10b): a ordem em vigor e Avatar > Exp > Loot > Dano, a
        ordem da 9 esta inteira em `PRIORITY_ORDER_ORDEM_9`, cada etapa tem rotulo e os pontos por
        etapa de cada build somam o que esta gasto."""
        self.assertEqual(builds.PRIORITY_ORDER, ORDER_10B)
        self.assertEqual(builds.PRIORITY_ORDER_ORDEM_9, ORDER_9)
        for stage in ORDER_9 + ("damage",):
            self.assertIn(stage, builds.PRIORITY_LABEL)
        self.assertIn("Avatar › Exp › Loot › dano", builds.PRIORITY_ASKED)
        self.assertEqual(builds.priority_stages_before_damage(), "Avatar, Exp e Loot")
        for voc, b in self.plans.items():
            info = b["priority"]
            self.assertEqual(tuple(info["stage_points"]), builds.PRIORITY_ORDER, voc)
            self.assertEqual(sum(info["stage_points"].values()), b["points_spent"], voc)
            self.assertTrue(all(st.stage in builds.PRIORITY_ORDER for st in b["order"]), voc)
            # a categoria de cada no continua a ser a da ordem 9 (o que o no e)
            self.assertTrue(set(info["category"].values()) <= set(ORDER_9), voc)

    def test_same_stat_ranks_are_bought_by_effect_per_point(self):
        """Ordem 10b (b) e (c): nas 5 ao nivel dele, nos 8 niveis representativos e na build do
        nivel do Avatar do paladin — (b) nenhum ponto foi ao dano enquanto havia um rank de Exp ou
        de Loot compravel com o que sobrava, e dentro de Exp/Loot nenhum passo compra um rank
        quando havia outro da etapa a render mais efeito por ponto (9c, caminho no custo); (c) na
        etapa «damage» nenhum passo compra um rank quando havia, ligado e a caber, um rank de
        OUTRO no com os mesmos stats a render mais por ponto no modelo linear (custo `custo x n`
        mais o caminho), e nenhum ponto foi a Exp/Loot excepto como ligacao ou ponto que sobrou."""
        _, all_plans = helpers.planner()
        plans = [(voc, b) for voc, b in self.plans.items()]
        plans += [(voc, b) for (voc, goal, _lv), b in all_plans.items() if goal == "priority"]
        plans += [(voc, b["avatar_plan"]) for voc, b in self.plans.items() if b.get("avatar_plan")]
        bad = []
        n_exp_loot = 0
        for voc, b in plans:
            bad.extend(exp_loot_before_damage_violations(self.cat, voc, b))
            bad.extend(same_stat_violations(self.cat, voc, b, stages=("exp", "loot"), any_signature=True))
            bad.extend(damage_stage_violations(self.cat, voc, b))
            bad.extend(exp_loot_violations(self.cat, voc, b))
            # a regra da 9c nas etapas por categoria continua a valer (vazia com a ordem 10b: sem essas etapas)
            bad.extend(same_stat_violations(self.cat, voc, b))
            n_exp_loot += sum(1 for st in b["steps"] if st.stage in ("exp", "loot"))
        self.assertEqual(bad, [], "\n".join(bad))
        self.assertGreater(n_exp_loot, 0)   # a propriedade testou-se em passos reais de Exp/Loot

    def test_what_pays_more_block_has_numbers_and_a_consistent_verdict(self):
        """Ordem 10b (e): o bloco «Depois do Avatar, Exp e Loot: o que rende mais» tem as tres
        linhas (Ataque, Chance de critico, Dano critico) com +1 % > 0 no simulador e o melhor rank
        compravel; o veredicto comeca pelo stat de maior ganho por ponto e explica o dano
        critico pela chance; os pontos por stat somam os da etapa «damage»; o bloco mediu-se
        sobre a arvore das etapas 1-3 (rota + Avatar + Exp + Loot), que tem os pontos dessas."""
        for voc, b in self.plans.items():
            rep = b["priority"]["stat_report"]
            self.assertIsNotNone(rep, voc)
            info = b["priority"]
            pre = info["pre_damage_tree"]
            self.assertIsNotNone(pre, voc)
            self.assertEqual(builds._spent(self.cat, pre), sum(info["stage_points"][s] for s in ("avatar", "exp", "loot")), voc)
            for nid, r in pre.items():
                self.assertGreaterEqual(b["tree"].get(nid, 0), r, (voc, nid))   # a poda nao tocou nas etapas 1-3
            self.assertGreaterEqual(info["stage_points"]["exp"], 0, voc)
            self.assertGreaterEqual(info["stage_points"]["loot"], 0, voc)
            self.assertEqual([r["key"] for r in rep["rows"]], ["attack", "critChance", "critDmg"], voc)
            for r in rep["rows"]:
                self.assertGreater(r["per_unit"], 0.0, (voc, r["label"]))
                self.assertGreater(r["dps_per_unit"], 0.0, (voc, r["label"]))
                self.assertIsNotNone(r["best"], (voc, r["label"]))
                self.assertGreater(r["best"]["gain_per_point"], 0.0, (voc, r["label"]))
                self.assertGreaterEqual(r["bought_pct"], 0.0)
            self.assertGreater(rep["dps_base"], 0.0, voc)
            ranked = sorted(rep["rows"], key=lambda r: -r["best"]["gain_per_point"])
            self.assertEqual(rep["ranked"][0], ranked[0]["key"], voc)
            verdict = rep["verdict"]
            self.assertTrue(verdict.startswith("depois do Avatar, Exp e Loot rende mais " + ranked[0]["label"].lower()), (voc, verdict))
            self.assertIn("dano critico so vale a chance", verdict, voc)
            pts = rep["points_by_stat"]
            # os pontos por stat sao os dos passos da etapa (a poda no fim pode tirar ranks: `pruned`)
            damage_steps = sum(st.cost for st in b["steps"] if st.stage == "damage")
            self.assertEqual(sum(pts.values()), damage_steps, voc)
            pruned_pts = sum(F.tree_total_cost(self.cat.node_by_id[n], a) - F.tree_total_cost(self.cat.node_by_id[n], c)
                             for n, a, c in b["priority"]["pruned"])
            self.assertEqual(damage_steps - pruned_pts, b["priority"]["stage_points"]["damage"], voc)
            self.assertEqual(sum(o["cost"] for o in rep["order"]), pts["attack"] + pts["critChance"] + pts["critDmg"] + pts["rest"] + pts["link"], voc)
            # o modelo e o do DPS: fraccoes pequenas (nao a metrica com a sobrevivencia)
            model = b["priority"]["stat_model"]
            for stat in ("atkPct", "spellDmgPct", "critChance", "critDmg", "attackSpeedPct"):
                self.assertLess(abs(model[stat]), 0.05, (voc, stat, model[stat]))
            # o sorcerer dele: a conta a mao do critico bate no simulador (§1e do validacao.md)
        from baiakvault import pages_builds
        rows, hand = pages_builds.crit_marginals_rows(self.cat, self.plans["sorcerer"])
        for label, by_hand, engine, diff, ok in rows:
            self.assertTrue(ok, (label, by_hand, engine, diff))

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

    def test_exp_and_loot_are_bought_where_the_tree_has_them(self):
        """Ordem 10b: ao nivel dele, quem tem nos de Exp/Loot compra-os todos antes do dano (druid e
        paladin os dois, sorcerer so Exp); o knight nao tem nenhum e diz-se; e a conta a mao do
        `validation.exp_loot_by_hand` (so arvore.json) bate nos totais e confirma que, antes do
        dano, nenhum rank de Exp/Loot cabia no que sobrava."""
        from baiakvault import validation
        raw = json.loads((helpers.ROOT / "data" / "catalogo" / "arvore.json").read_text(encoding="utf-8"))
        has = {"knight": (False, False), "druid": (True, True), "paladin": (True, True), "sorcerer": (True, False)}
        for voc, b in self.plans.items():
            info = b["priority"]
            tot = info["totals"]
            final = validation.exp_loot_by_hand(raw, voc, b["level"], b["tree"])
            before = validation.exp_loot_by_hand(raw, voc, b["level"], info["pre_damage_tree"])
            self.assertAlmostEqual(final["exp"]["pct"], tot["expPct"], places=6, msg=voc)
            self.assertAlmostEqual(final["loot"]["pct"], tot["lootPct"], places=6, msg=voc)
            self.assertTrue(before["exp"]["exhausted"], (voc, before))
            self.assertTrue(before["loot"]["exhausted"], (voc, before))
            if voc in has:
                exp, loot = has[voc]
                self.assertEqual(final["exp"]["has_nodes"], exp, voc)
                self.assertEqual(final["loot"]["has_nodes"], loot, voc)
                self.assertEqual(tot["expPct"] > 0, exp, voc)
                self.assertEqual(tot["lootPct"] > 0, loot, voc)
                self.assertEqual(info["stage_points"]["exp"] > 0, exp, voc)
                self.assertEqual(info["stage_points"]["loot"] > 0, loot, voc)

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

    def test_with_the_model_exp_beats_dps_and_without_exp_in_the_order_dps_wins(self):
        """Ordem 10b: com o modelo linear (a escolha da 10/10b), uma rota de tier 0 por nos de ataque
        que o modelo adora perde para a rota de Exp (Exp > DPS no vector); com a ordem da 10
        (Avatar, dano) a mesma escolha da a rota de ataque, e a de Exp fica em `dps_best`... ao
        contrario: a rota de maior DPS e a de ataque e a pagina mostra-a ao lado."""
        atk = [_node("k_atk0", "Atk 0", 0, {"atkPct": 5}), _node("k_atk1", "Atk 1", 1, {"atkPct": 5}, ["k_atk0"]),
               _node("k_atk2", "Atk 2", 2, {"atkPct": 5}, ["k_atk1"])]
        nodes = list(self.cat.tree_by_vocation["knight"]["nos"]) + atk
        nodes[-4]["requer"] = ["k_hp2", "k_exp2", "k_atk2"]   # o Avatar liga tambem a rota de ataque
        cat = types.SimpleNamespace(tree_by_vocation={"knight": {"vocacao": "knight", "nos": nodes}},
                                    node_by_id={n["id"]: n for n in nodes})
        model = {"_base": 100.0, "_dps": 100.0, "atkPct": 0.01, "spellDmgPct": 0.0, "critChance": 0.0, "critDmg": 0.0,
                 "attackSpeedPct": 0.0, "elementDmgPct": {}}
        # nivel 305: a rota de Exp (5) + Avatar gasta tudo (3 % exp); as outras deixam 2 pontos, que compram
        # Exp 0 rank 1 (1 % exp) — e a Exp que decide, nao os 15 % de ataque que o modelo adora
        ch = builds.choose_avatar_route(cat, "knight", 305, self.el, model=model)
        self.assertEqual(ch["route"], ["k_exp0", "k_exp1", "k_exp2"])
        self.assertEqual(ch["priority_stages"], ("exp", "loot"))
        self.assertEqual(tuple(ch["vector_10b"][:3]), (1, 3.0, 0.0))
        self.assertEqual(tuple(ch["cheapest_vector_10b"][:3]), (1, 1.0, 0.0))
        self.assertEqual(ch["dps_best"]["route"], ["k_atk0", "k_atk1", "k_atk2"])
        self.assertEqual(tuple(ch["dps_best"]["vector"][:3]), (1, 1.0, 0.0))
        self.assertFalse(ch["dps_best"]["same"])
        self.assertFalse(ch["dps_best"]["same_exp_loot"])
        self.assertGreater(ch["dps_best"]["model_score"], ch["model_score"])
        # a ordem da 10 (sem Exp/Loot): a rota de ataque ganha
        old = builds.PRIORITY_ORDER
        try:
            builds.PRIORITY_ORDER = ("avatar", "damage")
            ch10 = builds.choose_avatar_route(cat, "knight", 320, self.el, model=model)
        finally:
            builds.PRIORITY_ORDER = old
        self.assertEqual(ch10["route"], ["k_atk0", "k_atk1", "k_atk2"])
        self.assertEqual(ch10["priority_stages"], ())
        self.assertTrue(ch10["dps_best"]["same"])

    def test_dominance_pruning_drops_routes_that_only_add_rest_nodes(self):
        category = {"k_hp0": "rest", "k_hp1": "rest", "k_exp0": "exp"}
        keep, dropped = builds._dominated_routes([(2, ["k_hp0", "k_hp1"]), (1, ["k_hp0"]), (2, ["k_exp0", "k_hp1"])], category)
        self.assertEqual(dropped, 1)
        self.assertEqual(sorted(keep), [(1, ["k_hp0"]), (2, ["k_exp0", "k_hp1"])])


class SameStatOnAHandMadeTree(unittest.TestCase):
    """Ordem 9c: dois nos de tier 0 com o mesmo stat (atkPct 1,5/rank a custo 1 e 2,5/rank a custo
    3) — a etapa compra pela conta por stat (Barato 1, 2, 3, Caro 1 (0,83), Barato 4 (0,375),
    Caro 2 (0,417) antes de Barato 4...), mesmo com um simulador a dizer o contrario; um notable
    com outro stat (atkPct + armor) so entra quando o simulador o prefere a um pacote do
    mesmo tamanho de ranks baratos."""

    def setUp(self):
        self.cheap = _node("k_cheap", "Barato", 0, {"atkPct": 1.5}, custo=1)
        self.dear = _node("k_dear", "Caro", 0, {"atkPct": 2.5}, custo=3)
        self.notable = _node("k_big", "Notable", 1, {"atkPct": 8, "armorFlat": 8}, ["k_cheap"], custo=10, tipo="notable", rank_max=1)
        nodes = [self.cheap, self.dear, self.notable]
        self.node_by_id = {n["id"]: n for n in nodes}
        self.adj = {"k_cheap": {"k_big"}, "k_dear": set(), "k_big": {"k_cheap"}}
        self.category = {nid: "attack" for nid in self.node_by_id}
        self.steps = []

    def run_stage(self, budget, score_fn):
        tree = {}

        def buy(nid, is_link):
            tree[nid] = tree.get(nid, 0) + 1
            self.steps.append((nid, tree[nid], is_link))
        builds._stage_by_effect(self.node_by_id, self.adj, tree, budget, self.category, "attack", frozenset(), buy,
                                score_fn=score_fn)
        return tree

    def test_same_stat_by_effect_per_point_even_against_a_noisy_simulator(self):
        # o simulador «gosta» do Caro (ruido): nao pode contar, e o mesmo stat
        def noisy(tree):
            return 100.0 + tree.get("k_dear", 0) * 50.0 + tree.get("k_cheap", 0) * 0.1 - tree.get("k_big", 0) * 1000
        tree = self.run_stage(12, noisy)
        # 12 pontos: Barato 1 (1,5/pt), Caro 1 (0,83), Barato 2 (0,75), Barato 3 (0,5) = 9; Barato 4 (4) e Caro 2 (6) nao cabem
        # nos 3 que sobram; o Notable (11 com o caminho) cabia ao principio e o simulador recusou-o
        self.assertEqual(tree, {"k_cheap": 3, "k_dear": 1})
        self.assertEqual([s[:2] for s in self.steps], [("k_cheap", 1), ("k_dear", 1), ("k_cheap", 2), ("k_cheap", 3)])
        self.assertEqual(same_stat_order_ok(self.node_by_id, self.steps), [])

    def test_a_different_stat_is_decided_by_the_simulator_on_equal_packages(self):
        # o simulador vale a armadura: com 10 pontos o Notable (8 % + armor) bate 10 pontos de Barato/Caro
        def likes_armor(tree):
            return 100.0 + tree.get("k_cheap", 0) * 1.5 + tree.get("k_dear", 0) * 2.5 + tree.get("k_big", 0) * 30.0
        tree = self.run_stage(11, likes_armor)
        self.assertEqual(tree.get("k_big"), 1)
        self.assertIn(("k_cheap", 1, True), self.steps)   # o caminho para o Notable
        # e quando o simulador lhe da menos (6 % em 10 pontos contra 7 % em 9 de smalls), fica fora
        self.steps = []
        def by_stat(tree):
            return 100.0 + tree.get("k_cheap", 0) * 1.5 + tree.get("k_dear", 0) * 2.5 + tree.get("k_big", 0) * 6.0
        tree = self.run_stage(11, by_stat)
        self.assertEqual(tree.get("k_big", 0), 0)
        self.assertEqual(tree, {"k_cheap": 3, "k_dear": 1})   # 9 pontos; Barato 4 (4) e Caro 2 (6) nao cabem nos 2 que sobram


def same_stat_order_ok(node_by_id, steps):
    """Na arvore a mao: cada compra (nao caminho) rende por ponto pelo menos tanto como a seguinte do mesmo stat."""
    out = []
    per = []
    for nid, rank, is_link in steps:
        if is_link:
            continue
        node = node_by_id[nid]
        per.append((nid, rank, node["efeito_por_rank"]["atkPct"] / F.tree_rank_cost(node, rank - 1)))
    for a, b in zip(per, per[1:]):
        if b[2] > a[2] * 1.0001:
            out.append((a, b))
    return out


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
