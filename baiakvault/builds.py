"""O optimizador: para (vocacao, objectivo, nivel) devolve a build — arvore por
ordem de compra, equipamento BiS por slot com alternativas, rotacao para o
Helper, numeros e fontes. Tudo pelo simulador (`sim.py`) e pelas formulas
(`formulas.py`); nada aqui e opiniao, e o que o canal diz entra a parte,
citado, na pagina.

As oito builds (pedido do Andre, 16/09/2026): knight tank/damage, druid
heal/damage, sorcerer damage, paladin damage, monk support/damage.

Metricas por objectivo (decisao de 16/09/2026, registada no CLAUDE.md):

- ``damage``  — DPS efectivo num ciclo de hunt (57 normais com as areas a
  apanhar o pack + o boss da wave 10 com x3 HP, so alvo unico).
- ``tank``    — tempo ate morrer com o pack inteiro em cima (HP / pressao
  mitigada menos o leech) x DPS^0,3: matar mais depressa tambem e sobreviver,
  mas um no de ataque so ganha a um de defesa se render ~3x mais em %.
- ``heal`` / ``support`` — cura por segundo sustentavel em 60 s (a melhor
  cura propria que a mana aguenta, mais a cura aliada se existir) x DPS^0,3.

Algoritmo da arvore: guloso preguicoso por ganho marginal por ponto, com
«lookahead» nos pre-requisitos (um no fechado e avaliado com o caminho mais
barato ate ele, um rank em cada no intermedio). A ordem sai como caminho de
subida: o passo k avalia-se ao nivel que k pontos gastos pressupoem, com o
equipamento e a rotacao desse nivel. Limitacoes: guloso nao e optimo (nao
troca compras feitas), os «notables» caros so entram quando o ganho/ponto os
justifica, e a metrica depende das convencoes de `formulas.py`.
"""
import heapq
import itertools
import math
import time

from . import formulas as F
from . import sim

# A build «melhor» por vocacao (pedido do Andre, 16/09/2026 12:20) vem primeiro e e a
# omissao; as oito anteriores ficam disponiveis.
BUILDS = (("knight", "best"), ("druid", "best"), ("sorcerer", "best"), ("paladin", "best"), ("monk", "best"),
          ("knight", "tank"), ("knight", "damage"), ("druid", "heal"), ("druid", "damage"),
          ("sorcerer", "damage"), ("paladin", "damage"), ("monk", "support"), ("monk", "damage"))
LEVELS = (50, 100, 200, 300, 500, 800, 1200, 1500)
GOAL_LABEL = {"best": "melhor", "damage": "dano", "tank": "tank", "heal": "cura", "support": "support"}
GOAL_ASKED = {("knight", "tank"): "Sobreviver", ("knight", "damage"): "Dar dano",
              ("druid", "heal"): "Curar bastante", ("druid", "damage"): "Dar dano",
              ("sorcerer", "damage"): "Dar dano", ("paladin", "damage"): "Dar dano",
              ("monk", "support"): "Curar (support)", ("monk", "damage"): "Dar dano",
              ("knight", "best"): "A melhor possivel", ("druid", "best"): "A melhor possivel",
              ("sorcerer", "best"): "A melhor possivel", ("paladin", "best"): "A melhor possivel",
              ("monk", "best"): "A melhor possivel"}
SLOTS = ("weapon", "shield", "helmet", "armor", "legs", "boots", "amulet", "ring")
SECONDARY_DPS_EXPONENT = 0.3
TTD_CAP = 600.0
CANDIDATES_PER_SLOT = 20
EQUIPMENT_PASSES = 1
ROTATION_POOL = 5
MIN_LEVEL = 8
USELESS_IMBUEMENTS = ("increase speed",)  # nao entra em metrica nenhuma
# «best»: DPS do ciclo sujeito a aguentar o pack e o boss e a sustentar a mana (e, no
# druid, a curar o knight). Cada condicao falhada corta a metrica pela fraccao em que
# falha, elevada a BEST_PENALTY_POWER — uma penalizacao e nao um corte seco, para o
# guloso ter por onde subir a partir da arvore vazia (16/09/2026, ordem 6).
BEST_PENALTY_POWER = 2.0
# Poupar para um no caro: o caminho so espera `wait` niveis sem comprar nada quando o
# pacote rende pelo menos (1 + SAVE_MARGIN) x o que os mesmos pontos rendem nos outros
# nos, os dois medidos no simulador ao nivel em que se chega la. Pacotes que esperam
# ate SAVE_CHECK_MIN_WAIT niveis (ranks de small) nao passam pelo teste. Recusado, o
# no so se reconsidera quando os pequenos ja renderem SAVE_RETRY_DROP menos por ponto
# do que a alternativa rendia (limita o numero de testes). Decisao de 16/09/2026
# (ordem 6): a regra «espera <= 15 % do nivel ou <= 60 niveis» proposta na supervisao
# proibiria para sempre qualquer notable acima de 60 pontos (o caminho nunca tem pontos
# por gastar), por isso compara-se o integral no tempo, que e o que ela queria aproximar.
SAVE_CHECK_MIN_WAIT = 20
SAVE_MARGIN = 0.10
SAVE_RETRY_DROP = 0.20
SAVE_RETRY_SHARE = 0.25   # so se volta a testar depois de gastar 25 % do custo do no desde a recusa


# --- alvo de referencia ---------------------------------------------------------------------
def reference_hunt(cat, level):
    """A hunt que o jogo recomenda ao nivel: a de `nivel_minimo` mais alto que
    ainda cabe; empate pelo indice de XP do jogo."""
    best = None
    for h in cat.hunts:
        lv = h.get("nivel_minimo") or 0
        if lv > level:
            continue
        key = (lv, h.get("indice_xp") or 0)
        if best is None or key > best[0]:
            best = (key, h["id"])
    return best[1] if best else cat.hunts[0]["id"]


# --- metrica ---------------------------------------------------------------------------
def rotation_slots(profile, target, spells):
    """Slots por prioridade (dano por lancamento decrescente) com o minimo de
    bichos das areas: a area so compensa a partir de N alvos quando N x dano por
    alvo ultrapassa o melhor golpe de alvo unico."""
    strikes = [s for s in spells if s["tipo"] != "area"]
    best_single = max([sim.spell_damage(profile, s, target, True) for s in strikes] or [0.0])
    slots = []
    for s in spells:
        min_mobs = 1
        if s["tipo"] == "area" and best_single > 0:
            per_target = sim.spell_damage(profile, s, target, True)
            if per_target > 0:
                min_mobs = max(1, min(target.pack, int(math.ceil(best_single / per_target))))
        slots.append(sim.RotationSlot(s, min_mobs))
    slots.sort(key=lambda sl: -sim.spell_damage(profile, sl.spell, target, False))
    return slots


def evaluate(profile, target, rotation, boss_rotation=None, heal=None, attackers=None):
    """Corre o simulador nos dois cenarios e devolve as metricas da build."""
    heal = heal if heal is not None else default_heal(profile)
    pack = sim.simulate(profile, target, rotation, boss=False, heal=heal)
    boss = sim.simulate(profile, target, boss_rotation or rotation, boss=True, heal=heal)
    dps_cycle = sim.cycle_dps(pack.dps, boss.dps, target)
    n_att = attackers if attackers is not None else target.pack
    # o pack inteiro em cima, com as curas e as pocoes do Helper: e o «aguenta» da build
    # «best» (o `ttd_pack` analitico abaixo ignora curas e pocoes e fica na pagina)
    full = sim.simulate(profile, target, rotation, boss=False, heal=heal, attackers=n_att)
    pressure_pack, max_hit, _ = sim.pressure(profile, target, boss=False, attackers=n_att)
    _, boss_max_hit, _ = sim.pressure(profile, target, boss=True)
    # so o dano que rouba (ataque normal + strikes; `F.LEECH_SCOPE`), nao o DPS todo
    leech_hps = pack.leech_hps
    hps_self, heal_spell = sim.sustained_hps(profile)
    hps_friend, friend_spell = sim.sustained_hps(profile, friend=True)
    # tempo ate morrer, com tecto de 10 min: quando o leech cobre a pressao o
    # numero deixa de ter significado (e a pagina diz «> 10 min»)
    net = max(0.05, pressure_pack - leech_hps - profile.bonuses["hpRegenFlat"])
    ttd_pack = min(TTD_CAP, profile.hp_max / net)
    ttd_one = min(TTD_CAP, profile.hp_max / max(0.05, pack.pressure - leech_hps - profile.bonuses["hpRegenFlat"]))
    mit = sim.mitigation(profile, target)
    inc = target.incoming
    total_in = sum(inc.values()) or 1.0
    mitigated_share = sum(inc[el] * (1 - mit[el]) for el in F.ELEMENTS) / total_in
    ehp = profile.hp_max / max(0.05, 1 - mitigated_share)
    return {
        "dps_pack": pack.dps, "dps_boss": boss.dps, "dps_cycle": dps_cycle, "auto_dps": pack.auto_dps,
        "hps_self": hps_self, "hps_friend": hps_friend, "heal_spell": heal_spell, "friend_spell": friend_spell,
        "hps_sim": pack.hps, "leech_hps": leech_hps, "leech_dps": pack.leech_dps,
        "pressure_one": pack.pressure, "pressure_pack": pressure_pack, "max_hit": max_hit,
        "boss_max_hit": boss_max_hit, "ttd_pack": ttd_pack, "ttd_one": ttd_one, "ehp": ehp,
        "mitigated_share": mitigated_share, "hp_max": profile.hp_max, "mana_max": profile.mana_max,
        "hp_regen_flat": profile.bonuses["hpRegenFlat"], "armor": profile.armor, "defense": profile.defense,
        "mana_demand": pack.mana_demand, "mana_demand_attacks": pack.mana_demand_attacks,
        "mana_income": pack.mana_income, "mana_empty_at": pack.mana_empty_at,
        "mana_end": pack.mana_end, "boss_mana_empty_at": boss.mana_empty_at,
        "hp_potions": pack.hp_potions, "mana_potions": pack.mana_potions,
        "gold_per_hour": pack.gold_per_hour, "boss_gold_per_hour": boss.gold_per_hour,
        "hp_min": pack.hp_min, "death_at": pack.death_at, "boss_death_at": boss.death_at,
        "casts": pack.casts, "boss_casts": boss.casts,
        "uses_mana_potions": profile.uses_mana_potions,
        "survive_pack_s": sim.time_to_death(full, TTD_CAP), "survive_boss_s": sim.time_to_death(boss, TTD_CAP),
        "full_death_at": full.death_at, "full_hp_min": full.hp_min, "full_hp_potions": full.hp_potions,
        "full_mana_demand": full.mana_demand, "attackers_full": n_att,
        # a pressao do pack sobre o knight da party, quando o alvo a traz (druid «best»)
        "ally_pressure": getattr(target, "ally_pressure", None),
    }


def best_constraints(metrics):
    """As condicoes da build «melhor», cada uma como fraccao cumprida (1 = cumprida):
    aguentar o pack inteiro e o boss mais de 10 min (o simulador de 60 s com as
    curas e as pocoes do Helper, tendencia da vida extrapolada), mana sustentavel
    (knight/monk sem pocoes: o que o leech e os itens repoem cobre o que a rotacao
    gasta; mages/paladin com pocoes: a mana nao se esgota nos 60 s) e, quando o alvo
    traz `ally_pressure` (o druid a curar o knight da party), a cura aliada
    sustentavel cobre a pressao do pack sobre o knight."""
    out = {}
    out["survive_pack"] = max(0.01, min(1.0, metrics["survive_pack_s"] / TTD_CAP))
    out["survive_boss"] = max(0.01, min(1.0, metrics["survive_boss_s"] / TTD_CAP))
    if metrics.get("uses_mana_potions"):
        empty = metrics.get("mana_empty_at")
        out["mana"] = 1.0 if empty is None else max(0.01, empty / 60.0)
    else:
        demand = metrics.get("full_mana_demand", metrics["mana_demand"])   # com as curas do pack inteiro
        out["mana"] = 1.0 if demand <= 0 else min(1.0, metrics["mana_income"] / demand)
    ally = metrics.get("ally_pressure")
    if ally:
        out["heal_ally"] = min(1.0, metrics["hps_friend"] / ally)
    return out


def score_of(metrics, goal):
    dps = max(1e-6, metrics["dps_cycle"])
    if goal == "damage":
        return dps
    if goal == "best":
        factor = 1.0
        for frac in best_constraints(metrics).values():
            factor *= max(1e-3, frac) ** BEST_PENALTY_POWER
        return dps * factor
    if goal == "tank":
        # EHP (vida a dividir pelo que passa da mitigacao, com o pack em cima) x
        # sustain (o leech e a regen cobrem ate 100 % da pressao: no maximo
        # duplica) x DPS^0,3. Nao se usa o TTD directamente porque com leech a
        # cobrir a pressao ele fica infinito e deixava de distinguir builds.
        sustain = min(1.0, (metrics["leech_hps"] + metrics["hp_regen_flat"]) / max(1e-6, metrics["pressure_pack"]))
        return metrics["ehp"] * (1 + sustain) * dps ** SECONDARY_DPS_EXPONENT
    hps = metrics["hps_self"] + 0.5 * metrics["hps_friend"]
    return max(1e-6, hps) * dps ** SECONDARY_DPS_EXPONENT


def default_heal(profile):
    """A cura propria do Helper: a melhor sem runa (as runas custam gold por
    lancamento e ficam como alternativa na pagina)."""
    heals = [s for s in sim.heal_spells(profile) if not s.get("custo_gold")]
    if not heals:
        return sim.best_heal(profile)
    return max(heals, key=lambda s: profile.heal_amount(s))


# --- rotacao -------------------------------------------------------------------------------
def rotation_value(r, profile, goal):
    """O que uma rotacao vale: o DPS dos 60 s; na build «best» cortado pela
    fraccao da mana que nao se sustenta (knight/monk sem pocoes: o que o leech
    repoe contra o que se gasta; os outros: se a mana se esgota nos 60 s)."""
    if goal != "best":
        return r.dps
    if profile.uses_mana_potions:
        frac = 1.0 if r.mana_empty_at is None else max(0.01, r.mana_empty_at / 60.0)
    else:
        frac = 1.0 if r.mana_demand <= 0 else min(1.0, r.mana_income / r.mana_demand)
    return r.dps * max(1e-3, frac) ** BEST_PENALTY_POWER


def choose_rotation(profile, target, boss=False, runes=False, top=ROTATION_POOL, size=4, goal=None):
    """Escolhe ate 4 feiticos por forca bruta entre os `top` melhores por
    lancamento: o conjunto que o simulador diz render mais DPS (no cenario
    pedido; na «best», DPS sustentavel — `rotation_value`) e a ordem de
    prioridade = dano por lancamento decrescente."""
    spells = sim.attack_spells(profile, runes=runes)
    if not spells:
        return [], None
    spells.sort(key=lambda s: -sim.spell_damage(profile, s, target, boss))
    pool = spells[:top]
    heal = default_heal(profile)
    best = None
    for k in range(1, min(size, len(pool)) + 1):
        for combo in itertools.combinations(pool, k):
            slots = rotation_slots(profile, target, list(combo))
            r = sim.simulate(profile, target, slots, boss=boss, heal=heal)
            value = rotation_value(r, profile, goal)
            # empate (ate 0,5 %): mais feiticos no Helper e melhor, cobre mais situacoes
            if best is None or value > best[0] * 1.005:
                best = (value, slots, r)
    return best[1], best[2]


# --- equipamento ---------------------------------------------------------------------------
def _item_ok(item, vocation, level):
    if not item.get("slot"):
        return False
    if item.get("cargas") or item.get("duracao_s"):
        return False  # consumiveis de emergencia (SSA, Might Ring): nao sao BiS permanente
    if (item.get("nivel") or 0) > level:
        return False
    vocs = item.get("vocacoes")
    if vocs and vocation not in vocs:
        return False
    return True


def _static_rank(item, goal):
    """Pre-filtro barato para nao simular os 750 armas todas: nivel exigido e
    os numeros brutos do item. O simulador decide entre os que passam."""
    s = (item.get("nivel") or 0) * 2.0
    s += (item.get("ataque") or 0) + (item.get("ataque_elemental") or 0)
    s += ((item.get("wand_min") or 0) + (item.get("wand_max") or 0)) / 2.0
    s += (item.get("armadura") or 0) * 3 + (item.get("defesa") or 0) * 0.5
    s += sum((item.get("skills") or {}).values()) * 8
    s += (item.get("crit_chance") or 0) * 4 + (item.get("crit_dano") or 0) + (item.get("life_leech") or 0) * 3
    s += (item.get("mana_leech") or 0) * 3 + sum((item.get("absorcao") or {}).values()) * 0.5
    return s


def candidates(cat, vocation, level, slot, goal, limit=CANDIDATES_PER_SLOT):
    items = [i for i in cat.equippable if i["slot"] == slot and _item_ok(i, vocation, level)]
    if vocation in sim.MAGES and slot == "weapon":
        items = [i for i in items if i.get("tipo_de_arma") == "wand"]
    items.sort(key=lambda i: -_static_rank(i, goal))
    return items[:limit]


def best_ammo(cat, weapon, level):
    if not weapon or not weapon.get("municao"):
        return None
    kind = weapon["municao"]
    pool = [i for i in cat.items if i.get("municao") == kind and not i.get("slot")
            and (i.get("nivel") or 0) <= level]
    if not pool:
        return None
    return max(pool, key=lambda i: F.ammo_attack(i["nome"], i.get("ataque")))


def choose_imbuements(item, goal, target, vocation=None):
    """Que imbuement por em cada slot do item, pelo objectivo: dano -> Strike
    (critico), depois Vampirism; tank -> proteccao do elemento dominante da
    hunt, depois Vampirism; cura/support -> Void (mana leech), depois Vampirism;
    «best» como dano, mas no knight/monk (sem pocoes de mana) o Void primeiro:
    a mana e uma restricao e o leech so vale no ataque normal e nos strikes.
    So o que a categoria do item permite (cliente)."""
    cats = item.get("imbuement_categorias") or []
    n = item.get("imbuement_slots") or 0
    if not n:
        return []
    dominant = target.dominant_element()
    prot_name = "elemental protection " + dominant
    if goal == "best":
        goal = "damage" if (vocation is None or F.USES_MANA_POTIONS.get(vocation, True)) else "sustain"
    prefs = {
        "sustain": ["mana leech", "life leech", "critical hit", prot_name],
        "damage": ["critical hit", "life leech", "mana leech", prot_name],
        "tank": [prot_name, "life leech", "critical hit", "mana leech"],
        "heal": ["mana leech", "life leech", prot_name, "critical hit"],
        "support": ["mana leech", "life leech", prot_name, "critical hit"],
    }[goal]
    # skillboost da skill principal e sempre bom para dano
    chosen = []
    for pref in prefs + [c for c in cats if c.startswith("skillboost")] + cats:
        if len(chosen) >= n:
            break
        if pref in cats and pref not in chosen and pref not in USELESS_IMBUEMENTS:
            chosen.append(pref)
    return chosen[:n]


def _imb_keys(cat, categories):
    lista = (cat.meta("itens").get("imbuements") or {}).get("lista") or []
    keys = []
    for c in categories:
        for imb in lista:
            if imb.get("cat") == c:
                keys.append((imb["key"], 3))
                break
    return keys


def optimize_equipment(cat, vocation, level, goal, tree, target, rotation=None, passes=EQUIPMENT_PASSES):
    """BiS por slot: para cada slot, o candidato que mais sobe a metrica com o
    resto do equipamento fixo; duas passagens para as dependencias (arma <->
    escudo, skills). Devolve (equipamento, alternativas por slot, metricas)."""
    equipment = {}
    alternatives = {}
    prof = sim.Profile(cat, vocation, level, tree, equipment)
    rot = rotation or choose_rotation(prof, target, goal=goal)[0]

    def metric_for(eq):
        # a metrica do objectivo, com empates (ate 0,5 %) decididos pela
        # sobrevivencia: entre duas armas iguais em DPS fica a que da mais EHP
        p = sim.Profile(cat, vocation, level, tree, eq)
        r = rot if rot else choose_rotation(p, target, goal=goal)[0]
        m = evaluate(p, target, r)
        s = score_of(m, goal)
        return (round(math.log(max(1e-9, s)) / 0.005), m["ehp"] * m["ttd_pack"]), m

    base_score, _ = metric_for(equipment)
    slots = list(SLOTS)
    if vocation != "knight":
        # so o knight usa escudo (vocacoes.json); o paladin poe o quiver ai, mages/monk nada
        slots.remove("shield")
    for _ in range(passes):
        for slot in slots:
            weapon = (equipment.get("weapon") or {}).get("item")
            if slot == "shield" and weapon and weapon.get("duas_maos"):
                equipment.pop("shield", None)
                continue
            scored = []
            for item in candidates(cat, vocation, level, slot, goal):
                if slot == "weapon" and vocation == "knight" and item.get("duas_maos") and equipment.get("shield"):
                    trial = {k: v for k, v in equipment.items() if k != "shield"}
                else:
                    trial = dict(equipment)
                imbs = choose_imbuements(item, goal, target, vocation)
                trial[slot] = {"item": item, "up": 0, "imbuements": _imb_keys(cat, imbs), "imbuement_cats": imbs}
                if slot == "weapon" and vocation == "paladin":
                    ammo = best_ammo(cat, item, level)
                    trial["ammo"] = {"item": ammo} if ammo else None
                    if trial["ammo"] is None:
                        trial.pop("ammo")
                s, m = metric_for(trial)
                scored.append((s, item["nome"], trial, m))
            if not scored:
                continue
            scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
            best_s, _, best_trial, _ = scored[0]
            if best_s >= base_score:
                equipment = best_trial
                base_score = best_s
            alternatives[slot] = [{"equip": t[slot], "metrics": m, "score": score_of(m, goal)}
                                  for s, _, t, m in scored[:4]]
    prof = sim.Profile(cat, vocation, level, tree, equipment)
    return equipment, alternatives, prof


# --- arvore -------------------------------------------------------------------------------
def _adjacency(cat, vocation):
    tree = cat.tree_by_vocation[vocation]
    adj = {n["id"]: set() for n in tree["nos"]}
    for n in tree["nos"]:
        for req in n.get("requer") or []:
            adj[n["id"]].add(req)
            adj[req].add(n["id"])
    return adj


def can_buy(node, ranks, adj):
    """Regra do cliente (yD): rank < maximo e (tier 0 ou um vizinho com rank >= 1)."""
    if ranks.get(node["id"], 0) >= (node.get("rank_maximo") or 1):
        return False
    if node.get("tier", 0) == 0:
        return True
    return any(ranks.get(v, 0) >= 1 for v in adj[node["id"]])


def unlock_path(node, ranks, adj, node_by_id):
    """O caminho mais barato (um rank por no intermedio) do que ja esta comprado
    ate `node`. Dijkstra na adjacencia. Devolve lista de ids a comprar antes."""
    if can_buy(node, ranks, adj):
        return []
    bought = {k for k, v in ranks.items() if v >= 1}
    # fontes: nos comprados, e os de tier 0 (comprar rank 1 custa o seu custo)
    dist = {}
    heap = []
    for nid, n in node_by_id.items():
        if nid in bought:
            dist[nid] = (0, [])
            heapq.heappush(heap, (0, nid, []))
        elif n.get("tier", 0) == 0:
            c = F.tree_rank_cost(n, 0)
            dist[nid] = (c, [nid])
            heapq.heappush(heap, (c, nid, [nid]))
    target = node["id"]
    while heap:
        d, nid, path = heapq.heappop(heap)
        if dist.get(nid, (math.inf, None))[0] < d:
            continue
        if target in adj[nid]:
            return path
        for v in adj[nid]:
            if v == target or v in bought:
                continue
            n = node_by_id[v]
            c = d + F.tree_rank_cost(n, ranks.get(v, 0))
            if c < dist.get(v, (math.inf, None))[0]:
                dist[v] = (c, path + [v])
                heapq.heappush(heap, (c, v, path + [v]))
    return None


class TreeStep:
    __slots__ = ("node_id", "rank", "cost", "cumulative", "level", "score", "gain_per_point", "saving")

    def __init__(self, node_id, rank, cost, cumulative, level, score, gain_per_point, saving=None):
        self.node_id, self.rank, self.cost = node_id, rank, cost
        self.cumulative, self.level, self.score, self.gain_per_point = cumulative, level, score, gain_per_point
        # so no passo que fecha uma poupanca longa: {"wait", "from_level", "gain_pct",
        # "alt_gain_pct", "alt"} — o que a espera rende face a gastar os mesmos pontos
        # nos outros nos (ver SAVE_*)
        self.saving = saving


def optimize_tree(cat, vocation, goal, budget, equipment_at, rotation_at, target_at, start_ranks=None,
                  level_of=None, exclude=(), check_saving=True):
    """Caminho guloso de compra ate `budget` pontos. `equipment_at(level)`,
    `rotation_at(level, profile)` e `target_at(level)` dao o contexto do nivel
    em que cada ponto se gasta (level = pontos gastos, minimo 8, ou `level_of`).
    `exclude` sao nos que nao se compram; `check_saving` liga o teste da
    poupanca (SAVE_*), que se desliga na chamada aninhada que calcula a alternativa."""
    tree = cat.tree_by_vocation[vocation]
    node_by_id = {n["id"]: n for n in tree["nos"]}
    adj = _adjacency(cat, vocation)
    ranks = dict(start_ranks or {})
    spent = sum(F.tree_total_cost(node_by_id[k], v) for k, v in ranks.items() if k in node_by_id)
    steps = []

    contexts = {}
    baselines = {}

    def level_for(points):
        # o nivel em que se tem `points` pontos: o proprio numero (1 ponto por nivel)
        if level_of:
            return level_of(points)
        return max(MIN_LEVEL, points)

    def context(level):
        # equipamento/rotacao/alvo do nivel (mudam so nos checkpoints, ver Planner)
        if level not in contexts:
            eq = equipment_at(level, ranks)
            prof = sim.Profile(cat, vocation, level, ranks, eq)
            contexts[level] = (eq, target_at(level), rotation_at(level, prof))
        return contexts[level]

    def score_with(level, trial_ranks):
        eq, target, rot = context(level)
        p = sim.Profile(cat, vocation, level, trial_ranks, eq)
        return score_of(evaluate(p, target, rot), goal)

    def baseline(level):
        if level not in baselines:
            baselines[level] = score_with(level, ranks)
        return baselines[level]

    def package(node):
        """(ganho por ponto, custo, compras, score, nivel) de comprar um rank de
        `node` com o caminho de desbloqueio se preciso. O pacote avalia-se ao
        nivel em que se pode pagar (pontos gastos + custo), contra a base desse
        mesmo nivel — so assim um notable de 100 pontos e um small de 1 ponto
        sao comparaveis."""
        path = unlock_path(node, ranks, adj, node_by_id)
        if path is None:
            return None
        trial = dict(ranks)
        cost = 0
        purchases = []
        for nid in path + [node["id"]]:
            n = node_by_id[nid]
            cost += F.tree_rank_cost(n, trial.get(nid, 0))
            trial[nid] = trial.get(nid, 0) + 1
            purchases.append((nid, trial[nid]))
        if spent + cost > budget:
            return None
        level = level_for(spent + cost)
        s = score_with(level, trial)
        # ganho RELATIVO por ponto: em absoluto um notable avaliado a nivel 157
        # ganharia sempre a um small avaliado a nivel 8
        gain = (s / max(1e-9, baseline(level)) - 1.0) / cost
        return gain, cost, purchases, s, level

    def saving_verdict(nid, cost, s, level):
        """Poupar `cost` pontos para este pacote (chega-se la ao `level`) contra
        gastar os mesmos pontos nos outros nos, avaliados os dois no mesmo
        nivel e contexto. Devolve (poupa?, ganho %, ganho % da alternativa,
        alternativa). Decisao de 16/09/2026 (ordem 6), ver SAVE_MARGIN."""
        alt_ranks, alt_steps = optimize_tree(
            cat, vocation, goal, spent + cost, equipment_at, rotation_at, target_at, start_ranks=ranks,
            level_of=lambda pts: level, exclude=set(exclude) | {nid}, check_saving=False)
        base = max(1e-9, baseline(level))
        gain_pct = (s / base - 1.0) * 100.0
        alt_pct = (score_with(level, alt_ranks) / base - 1.0) * 100.0 if alt_steps else 0.0
        alt = [(st.node_id, st.rank) for st in alt_steps]
        return gain_pct >= alt_pct * (1.0 + SAVE_MARGIN), gain_pct, alt_pct, alt

    # Guloso preguicoso: a fila guarda o ultimo ganho/ponto conhecido de cada no.
    # Tira-se o topo; se o valor e velho, re-avalia-se e reinsere-se; se ja e
    # fresco (calculado neste estado) compra-se. Cada estado re-avalia no
    # maximo N nos, por isso termina.
    heap = [(-math.inf, nid) for nid in node_by_id if nid not in exclude]
    heapq.heapify(heap)
    fresh = {}
    parked = {}     # no -> ganho/ponto da alternativa: poupanca recusada neste estado, fora da fila ate se comprar algo
    no_test = set()  # nos que voltam a fila sem mais nada compravel: entram sem o teste (a alternativa e nada)
    last_rejected = {}   # no -> pontos gastos quando a poupanca foi recusada
    while heap or parked:
        if not heap:
            for pid, alt_pp in parked.items():
                heapq.heappush(heap, (-alt_pp, pid))
                no_test.add(pid)
            parked = {}
        neg_gain, nid = heapq.heappop(heap)
        node = node_by_id[nid]
        if ranks.get(nid, 0) >= (node.get("rank_maximo") or 1):
            continue
        if nid in fresh:
            gain, cost, purchases, s, level = fresh[nid]
        else:
            pkg = package(node)
            if pkg is None:
                continue  # nao cabe no orcamento: sai da fila
            gain, cost, purchases, s, level = pkg
            fresh[nid] = pkg
            if heap and gain < -heap[0][0]:
                heapq.heappush(heap, (-gain, nid))
                continue
        saving = None
        wait = level - level_for(spent)
        if check_saving and node.get("tipo") != "small" and wait > SAVE_CHECK_MIN_WAIT and nid not in no_test:
            # poupar N niveis sem comprar nada so quando rende mais do que os
            # pequenos pelos mesmos pontos; senao o no sai da fila ate se comprar
            # outra coisa (senao ficava a ocupar o topo) e so se volta a testar
            # quando o melhor dos outros tiver caido SAVE_RETRY_DROP e ja se
            # gastaram SAVE_RETRY_SHARE do custo dele desde a recusa
            best_other = -heap[0][0] if heap else gain
            if spent - last_rejected.get(nid, -math.inf) < cost * SAVE_RETRY_SHARE:
                fresh.pop(nid, None)
                parked[nid] = min(gain, best_other) * (1.0 - SAVE_RETRY_DROP)
                continue
            ok, gain_pct, alt_pct, alt = saving_verdict(nid, cost, s, level)
            if not ok:
                fresh.pop(nid, None)
                last_rejected[nid] = spent
                parked[nid] = min(gain, best_other) * (1.0 - SAVE_RETRY_DROP)
                continue
            saving = {"wait": wait, "from_level": level_for(spent), "gain_pct": gain_pct,
                      "alt_gain_pct": alt_pct, "alt": alt}
        for pid, r in purchases:
            c = F.tree_rank_cost(node_by_id[pid], r - 1)
            spent += c
            ranks[pid] = r
            steps.append(TreeStep(pid, r, c, spent, level_for(spent), s, gain,
                                  saving if pid == nid else None))
        fresh = {}
        baselines = {}
        contexts = {}
        no_test = set()
        # os que esperavam por outro estado voltam a fila com a chave da alternativa
        for pid, alt_pp in parked.items():
            heapq.heappush(heap, (-alt_pp, pid))
        parked = {}
        heapq.heappush(heap, (-gain, nid))
    return ranks, steps


def next_purchase(cat, vocation, goal, level, ranks, equipment, target, rotation=None, top=3):
    """O proximo passo a partir de um estado real: as `top` compras com mais
    ganho por ponto que cabem no orcamento do nivel. Para a ordem 3."""
    tree = cat.tree_by_vocation[vocation]
    node_by_id = {n["id"]: n for n in tree["nos"]}
    adj = _adjacency(cat, vocation)
    spent = sum(F.tree_total_cost(node_by_id[k], v) for k, v in ranks.items() if k in node_by_id)
    budget = F.tree_budget(level)
    prof = sim.Profile(cat, vocation, level, ranks, equipment)
    rot = rotation or choose_rotation(prof, target, goal=goal)[0]
    current = score_of(evaluate(prof, target, rot), goal)
    out = []
    for nid, node in node_by_id.items():
        if ranks.get(nid, 0) >= (node.get("rank_maximo") or 1):
            continue
        path = unlock_path(node, ranks, adj, node_by_id)
        if path is None:
            continue
        trial = dict(ranks)
        cost = 0
        for pid in path + [nid]:
            cost += F.tree_rank_cost(node_by_id[pid], trial.get(pid, 0))
            trial[pid] = trial.get(pid, 0) + 1
        if spent + cost > budget:
            continue
        s = score_of(evaluate(sim.Profile(cat, vocation, level, trial, equipment), target, rot), goal)
        out.append({"node": nid, "name": node["nome"], "rank": trial[nid], "cost": cost,
                    "via": path, "score": s, "gain_pct": (s / current - 1) * 100 if current else 0.0})
    out.sort(key=lambda x: -(x["score"] - current) / max(1, x["cost"]))
    return out[:top], current, budget - spent


# --- a build inteira -----------------------------------------------------------------------
class Planner:
    """Calcula e guarda as builds: um caminho de arvore por (vocacao,
    objectivo), equipamento e rotacao nos niveis representativos, e a build
    completa por nivel. `plan(vocation, goal, level)` responde a qualquer nivel."""

    def __init__(self, cat, levels=LEVELS, hunt_by_level=None):
        self.cat = cat
        self.levels = tuple(levels)
        self.hunt_by_level = hunt_by_level or {}
        self._targets = {}
        self._equipment = {}   # (voc, goal, checkpoint) -> equipment
        self._rotation = {}    # (voc, goal, checkpoint) -> (hunt rotation, boss rotation)
        self._paths = {}       # (voc, goal, hunt ou None) -> (ranks, steps)
        self._ally = {}        # (hunt, checkpoint) -> pressao do pack sobre o knight «best»
        self.timings = {}

    # contexto por nivel: usa o checkpoint (nivel representativo) mais alto <= nivel
    def checkpoint(self, level):
        below = [lv for lv in self.levels if lv <= level]
        return max(below) if below else self.levels[0]

    def target(self, level, hunt_id=None, strict=False):
        """A hunt de referencia do nivel; com `hunt_id` (a hunt dele), essa — mas
        so a partir do nivel minimo dela (salvo `strict`): abaixo, o caminho segue
        as hunts que o jogo recomenda (senao a arvore de um nivel 8 optimizava-se
        para uma hunt de 500 em que morre ao segundo, e comprava so sobrevivencia)."""
        hunt = hunt_id
        if hunt and not strict and (self.cat.hunt_by_id[hunt].get("nivel_minimo") or 0) > level:
            hunt = None
        hunt = hunt or self.hunt_by_level.get(level) or reference_hunt(self.cat, level)
        if hunt not in self._targets:
            self._targets[hunt] = sim.Target(self.cat, hunt)
        return self._targets[hunt]

    def target_for(self, vocation, goal, level, hunt_id=None, strict=False):
        """O alvo de uma build: a hunt de referencia do nivel (ou `hunt_id`, a hunt
        dele; `strict` = mesmo abaixo do nivel minimo dela) e, no druid «best», a
        pressao do pack sobre o knight «best» da mesma party (mesmo nivel
        representativo e hunt) — e o que a cura aliada tem de cobrir."""
        target = self.target(level, hunt_id, strict)
        if vocation == "druid" and goal == "best":
            return sim.with_ally(target, self.ally_pressure(target.hunt_id, level))
        return target

    def ally_pressure(self, hunt_id, level):
        """A pressao do pack sobre o knight «best» ao nivel representativo: na hunt
        de referencia do nivel (o knight «best» generico desse checkpoint — um
        proxy, nao se calcula um knight por cada hunt de referencia) ou, se a hunt
        e a dele, nessa."""
        cp = self.checkpoint(level)
        reference = hunt_id == self.target(level).hunt_id
        key = (None if reference else hunt_id, cp)
        if key not in self._ally:
            self._ally[key] = None   # guarda contra recursao (o knight nao precisa do druid)
            knight = self.plan("knight", "best", cp, hunt_id=key[0])
            self._ally[key] = knight["metrics"]["pressure_pack"]
        return self._ally[key]

    def _tree_prefix(self, vocation, goal, budget, hunt_id=None):
        ranks, steps = self._paths.get((vocation, goal, hunt_id), ({}, []))
        out = {}
        for st in steps:
            if st.cumulative > budget:
                break
            out[st.node_id] = st.rank
        return out

    def equipment_at(self, vocation, goal, level, ranks=None, hunt_id=None):
        """O equipamento do checkpoint (nivel representativo) <= nivel. Calcula-se
        uma vez, com a arvore que o caminho tem ao chegar la, e serve o caminho
        e as paginas — e o que torna as builds todas possiveis em segundos."""
        cp = self.checkpoint(level)
        key = (vocation, goal, cp, hunt_id)
        if key not in self._equipment:
            tree = dict(ranks) if ranks is not None else self._tree_prefix(vocation, goal, F.tree_budget(cp), hunt_id)
            target = self.target_for(vocation, goal, cp, hunt_id)
            eq, alts, _ = optimize_equipment(self.cat, vocation, cp, goal, tree, target)
            self._equipment[key] = (eq, alts)
        return self._equipment[key][0]

    def rotation_at(self, vocation, goal, level, profile, hunt_id=None):
        cp = self.checkpoint(level)
        key = (vocation, goal, cp, hunt_id)
        if key not in self._rotation:
            target = self.target_for(vocation, goal, cp, hunt_id)
            hunt_rot, _ = choose_rotation(profile, target, boss=False, goal=goal)
            boss_rot, _ = choose_rotation(profile, target, boss=True, goal=goal)
            self._rotation[key] = (hunt_rot, boss_rot)
        return self._rotation[key][0]

    def path(self, vocation, goal, budget=None, hunt_id=None):
        """O caminho de compra de (vocacao, objectivo): pela hunt de referencia de
        cada nivel, ou, com `hunt_id`, pela hunt dele a todos os niveis — a arvore
        acompanha o elemento da hunt (na Livraria FIRE o sorcerer nao compra
        nos de fogo), decisao de 16/09/2026 (ordem 6)."""
        key = (vocation, goal, hunt_id)
        if key not in self._paths:
            t0 = time.perf_counter()
            budget = budget or F.tree_budget(max(self.levels))
            self._paths[key] = ({}, [])
            ranks, steps = optimize_tree(
                self.cat, vocation, goal, budget,
                equipment_at=lambda lv, ranks: self.equipment_at(vocation, goal, lv, ranks, hunt_id),
                rotation_at=lambda lv, prof: self.rotation_at(vocation, goal, lv, prof, hunt_id),
                target_at=lambda lv: self.target_for(vocation, goal, lv, hunt_id),
                level_of=lambda points: max(MIN_LEVEL, min(max(self.levels), points)))
            self._paths[key] = (ranks, steps)
            self.timings[key] = time.perf_counter() - t0
        return self._paths[key]

    def plan(self, vocation, goal, level, hunt_id=None):
        """A build completa a um nivel (na hunt de referencia do nivel, ou na
        `hunt_id` dele — caminho, equipamento e rotacao todos por essa hunt).
        Dicionario pronto para a pagina."""
        cat = self.cat
        self.path(vocation, goal, hunt_id=hunt_id)
        budget = F.tree_budget(level)
        tree = self._tree_prefix(vocation, goal, budget, hunt_id)
        target = self.target_for(vocation, goal, level, hunt_id, strict=True)   # a hunt dele, mesmo abaixo do minimo
        steps = [st for st in self._paths[(vocation, goal, hunt_id)][1] if st.cumulative <= budget]
        key = (vocation, goal, level, hunt_id)
        if key in self._equipment and self.target(level, hunt_id).hunt_id == target.hunt_id:
            eq, alts = self._equipment[key]
        else:
            eq, alts, _ = optimize_equipment(cat, vocation, level, goal, tree, target)
        prof = sim.Profile(cat, vocation, level, tree, eq)
        hunt_rot, _ = choose_rotation(prof, target, boss=False, goal=goal)
        boss_rot, _ = choose_rotation(prof, target, boss=True, goal=goal)
        heal = default_heal(prof)
        # o que o caminho deixa por gastar (a poupar para um notable) gasta-se
        # agora ao nivel da pagina, e depois uma melhoria local: se desviar os
        # ultimos pontos render mais com este equipamento, desvia-se
        tree, fill_steps = fill_tree(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal)
        tree, improved = local_improve(cat, vocation, goal, level, tree, steps + fill_steps, eq, target,
                                       hunt_rot, boss_rot, heal)
        prof = sim.Profile(cat, vocation, level, tree, eq)
        hunt_rot, hunt_sim = choose_rotation(prof, target, boss=False, goal=goal)
        boss_rot, boss_sim = choose_rotation(prof, target, boss=True, goal=goal)
        boss_rot_runes, boss_sim_runes = choose_rotation(prof, target, boss=True, runes=True, goal=goal)
        heal = default_heal(prof)
        metrics = evaluate(prof, target, hunt_rot, boss_rot, heal)
        alternatives = tree_alternatives(cat, vocation, goal, level, tree, steps + fill_steps, eq, target,
                                         hunt_rot, boss_rot, heal)
        spent = sum(F.tree_total_cost(cat.node_by_id[k], v) for k, v in tree.items())
        next_step = None
        path_steps = self._paths[(vocation, goal, hunt_id)][1]
        for st in path_steps:
            if st.cumulative > budget:
                next_step = st
                break
        return {
            "vocation": vocation, "goal": goal, "level": level, "hunt": target.hunt_id, "target": target,
            "profile": prof, "tree": tree, "steps": steps, "fill_steps": fill_steps, "improved": improved,
            "next_step": next_step, "points_spent": spent, "points_budget": budget,
            "equipment": eq, "equipment_alternatives": alts,
            "rotation": hunt_rot, "boss_rotation": boss_rot, "boss_rotation_runes": boss_rot_runes,
            "hunt_sim": hunt_sim, "boss_sim": boss_sim, "boss_sim_runes": boss_sim_runes,
            "heal": heal, "metrics": metrics, "score": score_of(metrics, goal),
            "tree_alternatives": alternatives, "helper": helper_config(prof, target, hunt_rot, boss_rot, heal, metrics),
        }


def _spent(cat, tree):
    return sum(F.tree_total_cost(cat.node_by_id[k], v) for k, v in tree.items())


def fill_tree(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal):
    """Gasta os pontos que sobram do prefixo do caminho, ao nivel da pagina, com
    o mesmo guloso preguicoso de `optimize_tree` (nivel e contexto fixos)."""
    if _spent(cat, tree) >= F.tree_budget(level):
        return dict(tree), []
    return optimize_tree(cat, vocation, goal, F.tree_budget(level),
                         equipment_at=lambda lv, ranks: eq, rotation_at=lambda lv, p: hunt_rot,
                         target_at=lambda lv: target, start_ranks=tree, level_of=lambda pts: level)


def tree_alternatives(cat, vocation, goal, level, tree, steps, eq, target, hunt_rot, boss_rot, heal):
    """Os tres melhores nos em que os ultimos ~10 pontos poderiam ter ido: a
    metrica de cada um para se ver o que se perde (ou ganha) ao desviar."""
    node_by_id = {n["id"]: n for n in cat.tree_by_vocation[vocation]["nos"]}
    adj = _adjacency(cat, vocation)
    if not steps:
        return {"freed": 0, "removed": [], "base": dict(tree), "options": []}
    # tira os ultimos passos ate libertar >= 10 pontos (ou o ultimo notable)
    freed = 0
    base = dict(tree)
    removed = []
    for st in reversed(steps):
        if freed >= 10:
            break
        if base.get(st.node_id, 0) != st.rank:
            break  # o passo ja nao bate com a arvore (melhoria local mexeu aqui)
        base[st.node_id] = st.rank - 1
        if base[st.node_id] <= 0:
            base.pop(st.node_id)
        freed += st.cost
        removed.append(st.node_id)
    out = []
    for nid, node in node_by_id.items():
        if nid in removed:
            continue
        if base.get(nid, 0) >= (node.get("rank_maximo") or 1):
            continue
        path = unlock_path(node, base, adj, node_by_id)
        if path is None:
            continue
        trial = dict(base)
        cost = 0
        for pid in path + [nid]:
            cost += F.tree_rank_cost(node_by_id[pid], trial.get(pid, 0))
            trial[pid] = trial.get(pid, 0) + 1
        # gasta o que sobrou em mais ranks do mesmo no, se der
        while cost < freed and trial[nid] < (node.get("rank_maximo") or 1):
            c = F.tree_rank_cost(node, trial[nid])
            if cost + c > freed:
                break
            cost += c
            trial[nid] += 1
        if cost > freed:
            continue
        p = sim.Profile(cat, vocation, level, trial, eq)
        m = evaluate(p, target, hunt_rot, boss_rot, heal)
        out.append({"node": nid, "name": node["nome"], "rank": trial[nid], "metrics": m,
                    "score": score_of(m, goal), "tree": trial})
    out.sort(key=lambda x: -x["score"])
    return {"freed": freed, "removed": removed, "base": base, "options": out[:3]}


def local_improve(cat, vocation, goal, level, tree, steps, eq, target, hunt_rot, boss_rot, heal, rounds=4):
    """Melhoria local: enquanto desviar os ultimos ~10 pontos para outro no render
    mais de 0,2 % com o equipamento deste nivel, adopta-se o desvio. Devolve a
    arvore e a lista dos desvios feitos."""
    improved = []
    steps = list(steps)
    for _ in range(rounds):
        prof = sim.Profile(cat, vocation, level, tree, eq)
        current = score_of(evaluate(prof, target, hunt_rot, boss_rot, heal), goal)
        alts = tree_alternatives(cat, vocation, goal, level, tree, steps, eq, target, hunt_rot, boss_rot, heal)
        if not alts["options"] or alts["options"][0]["score"] <= current * 1.002:
            break
        best = alts["options"][0]
        improved.append({"removed": list(alts["removed"]), "to": best["name"], "rank": best["rank"],
                         "gain_pct": (best["score"] / current - 1) * 100})
        before = alts["base"]
        tree = best["tree"]
        # os passos removidos saem; cada rank comprado no desvio entra como passo
        # proprio (com o seu custo real), senao o `freed` da ronda seguinte mente
        n_removed = len(alts["removed"])
        steps = steps[:-n_removed] if n_removed else steps
        steps.extend(_diff_steps(cat, before, tree, level, best["score"]))
        # o que sobrou do orcamento (se o desvio custou menos) preenche-se
        tree, extra = fill_tree(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal)
        steps.extend(extra)
    return tree, improved


def _diff_steps(cat, before, after, level, score):
    steps = []
    spent = _spent(cat, before)
    for nid, r_after in after.items():
        r_before = before.get(nid, 0)
        node = cat.node_by_id[nid]
        for r in range(r_before + 1, r_after + 1):
            c = F.tree_rank_cost(node, r - 1)
            spent += c
            steps.append(TreeStep(nid, r, c, spent, level, score, 0.0))
    return steps


# --- Helper --------------------------------------------------------------------------------
def potion_threshold(profile, target, rotation, heal):
    """O limiar de pocao mais baixo (35..85) com que o simulador nao deixa a
    vida cair abaixo de 2x o maior golpe do boss — a margem contra um pico."""
    _, boss_max_hit, _ = sim.pressure(profile, target, boss=True)
    for pct in (35, 45, 55, 65, 75, 85):
        old = profile.potion_hp_pct
        profile.potion_hp_pct = pct
        r = sim.simulate(profile, target, rotation, boss=True, heal=heal)
        profile.potion_hp_pct = old
        if r.hp_min >= 2 * boss_max_hit and r.death_at is None:
            return pct
    return 85


def helper_config(profile, target, hunt_rot, boss_rot, heal, metrics):
    """Os campos do Helper com os nomes do jogo (etiquetas do cliente)."""
    canal_85 = 85
    computed = potion_threshold(profile, target, boss_rot or hunt_rot, heal)
    heal_at = max(computed, min(canal_85, int(math.ceil(2 * metrics["boss_max_hit"] / max(1.0, profile.hp_max) * 100 / 5.0) * 5)))
    heal_at = max(35, min(85, heal_at))
    hp_pot = profile.hp_potion
    mana_pot = profile.mana_potion
    rune_heals = [s for s in sim.heal_spells(profile) if s.get("custo_gold")]
    rune_alt = max(rune_heals, key=lambda s: profile.heal_amount(s)) if rune_heals else None
    friend = [s for s in sim.heal_spells(profile, friend=True)]
    return {
        "heal_spell": heal["nome"] if heal else None,
        "heal_words": heal["palavras"] if heal else None,
        "heal_at": heal_at, "heal_at_computed": computed, "heal_at_canal": canal_85,
        "heal_rune_alternative": rune_alt,
        "hp_potion": hp_pot["name"] if hp_pot else None, "hp_below": max(computed, 35),
        "mana_potion": mana_pot["name"] if mana_pot else None, "mana_below": 25 if mana_pot else None,
        "friend_heal": friend[0]["nome"] if friend else None,
        "friend_heal_at": 85 if friend else None,
        "hunt_rotation": [(sl.spell["nome"], sl.spell["palavras"], sl.min_mobs if sl.spell["tipo"] == "area" else None) for sl in hunt_rot],
        "boss_rotation": [(sl.spell["nome"], sl.spell["palavras"], None) for sl in boss_rot],
        "position": _position(profile),
        "distance": _distance(profile),
        "magic_shield": profile.vocation in sim.MAGES,
        "emergency": _emergency(profile, target),
    }


def _position(profile):
    if profile.vocation == "knight":
        return "Persegue o alvo e fica colado nele (corpo a corpo)"
    if profile.vocation == "monk":
        return "Persegue o alvo e fica colado nele (corpo a corpo)"
    return "Mantém essa distância do alvo"


def _distance(profile):
    if profile.vocation in ("knight", "monk"):
        return 1
    return 3


def _emergency(profile, target):
    """Anel/amuleto de emergencia pela regra do canal (SSA, Might Ring) — e o
    amuleto elemental pelo dano dominante da hunt. Opiniao do canal, citada."""
    dominant = target.dominant_element()
    amulet = {"energy": "Light Pendant", "fire": "Magma Amulet", "earth": "Terra Amulet",
              "physical": "Protection Amulet"}.get(dominant, "Protection Amulet")
    return {"dominant_element": dominant, "amulet_standard": amulet, "amulet_emergency": "Stone Skin Amulet",
            "ring_emergency": "Might Ring", "source": "canal CharllonLobo (mSE11hHamRs, rP83AhzvK9M)"}
