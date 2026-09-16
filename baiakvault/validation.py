"""Validacao cruzada das contas das builds (pedido do Andre, 16/09/2026: «quero
que isto seja sempre validado»).

Duas partes, as duas escritas em `docs/builds/validacao.md` pelo build e
provadas pelos testes:

1. **Contas a mao** — um perfil fixo (sorcerer nivel 50 em Crawler, com a
   arvore e o equipamento que a pagina publicou a 16/09/2026) recalculado
   AQUI so a partir dos JSON do catalogo e de aritmetica simples: **este
   modulo nao importa `formulas.py` nem `sim.py`** de proposito. O build
   compara com o que o simulador da para o mesmo perfil; uma diferenca acima
   da tolerancia e um erro de gravidade alta (o teste chumba).
2. **A curva do guia** — `guiabaiakidle.com` publica no seu planner uma curva
   de DPS de referencia por nivel (`7.012 x nivel^0.948`, sem factores). Para
   cada build e nivel mostra-se o DPS do ciclo do simulador ao lado dela e a
   razao. Nao sao a mesma coisa (a curva do guia nao sabe de vocacao, hunt nem
   equipamento), por isso nao ha tolerancia: e para se VER a diferenca, nao
   para a esconder.

Mais as constantes em que o guia e o cliente do jogo discordam, com os dois
valores e qual se segue.
"""

# --- 1. contas a mao ------------------------------------------------------------------------------
# O perfil de referencia: o que builds/sorcerer-damage.html mostrava ao nivel 50 a 16/09/2026.
REFERENCE = {
    "vocation": "sorcerer", "level": 50, "hunt": "crawler-cave",
    "tree": {"s_arcane": 4, "s_wildfire": 4, "s_fire": 2, "s_ignite": 2, "s_inferno": 2, "s_archmage": 1,
             "s_crit": 1, "s_deathchill": 1, "s_deepwell": 1, "s_drain": 1, "s_energy": 1, "s_reaper": 1,
             "s_scholar": 1, "s_scorch": 1, "s_stormcall": 1, "s_ward": 1},
    "equipment": {"weapon": "void wand", "helmet": "cobra crown", "armor": "void robe", "legs": "void legs",
                  "boots": "void galoshes", "amulet": "amulet of earth", "ring": "ring of earth"},
    # (chave do imbuement, tier) por slot, como a pagina os poe
    "imbuements": {"weapon": [("strike", 3), ("vampirism", 3)], "armor": [("vampirism", 3)]},
    "rotation": ["Great Fire Wave", "Great Energy Beam"],
    "heal": "Ultimate Healing",
}
# As constantes que a conta a mao usa, com a fonte (as mesmas que a pagina cita; nao se le formulas.py)
HAND_CONSTANTS = {
    "hp_base": (100, "guia: 100 + hpPerLevel x nivel"), "mana_base": (90, "guia: 90 + manaPerLevel x nivel"),
    "hp_per_level": (5, "cliente j0.sorcerer"), "mana_per_level": (30, "cliente j0.sorcerer"),
    "skill_base": (15, "guia: magic level = 15 + 0,1 x nivel"), "skill_per_level": (0.1, "guia"),
    "gcd_s": (2, "cliente QO=2e3"), "auto_interval_s": (2, "convencao ⚠ (o mesmo intervalo dos monstros)"),
    "crit_base": (50, "guia: critico = 1 + chance x (50 + critDmg)/10000"),
    "imbuement_crit_chance": (5, "cliente FY=5"), "area_targets_radius_2": (5, "convencao ⚠, limitado ao pack"),
    "cycle_kills": (57, "guia L=57"), "boss_hp_mult": (3, "guia te=3"),
    # a IA de combate (cliente u4e): chance de decisao perfeita = 0,5 + 0,025 x qp, qp = min(10, 0,5 x floor(nivel/100)) + min(10, ranks)
    "tactics_aim_base": (0.5, "cliente u4e: aimChance = min(1, 0,5 + 0,025 x qp)"),
    "tactics_aim_per_qp": (0.025, "cliente u4e"),
    "tactics_imperfect": (0.6, "convencao ⚠: uma decisao imperfeita rende 60 % de uma perfeita"),
}
TOLERANCE_PCT = 1.0


def _js_range(formula, e, t):
    """As formulas do cliente sao `(e,t)=>[lo,hi]` com aritmetica simples e `Math.max`."""
    body = formula.split("=>", 1)[1].strip().replace("Math.max", "max")
    return eval(body, {"__builtins__": {}, "max": max, "e": e, "t": t})  # noqa: S307 - catalogo local


def _node_cost(node, rank):
    # cliente z3e: o rank k de um small custa custo x k, logo ate r e custo x r(r+1)/2; notable = custo
    if node["tipo"] == "small":
        return node["custo_por_rank"] * rank * (rank + 1) // 2
    return node["custo_por_rank"] if rank > 0 else 0


def hand_calculation(cat, ref=REFERENCE):
    """Os numeros do perfil de referencia a partir dos JSON, sem o simulador.
    Devolve {nome: valor} — e o texto do que se assumiu."""
    c = {k: v for k, (v, _) in HAND_CONSTANTS.items()}
    level = ref["level"]
    voc = cat.vocation_by_name[ref["vocation"]]
    spells = {s["nome"]: s for s in voc["feiticos"]}
    node_by_id = cat.node_by_id
    items = {slot: cat.item_by_key[name] for slot, name in ref["equipment"].items()}
    imb_by_key = {i["key"]: i for i in (cat.meta("itens").get("imbuements") or {}).get("lista") or []}
    hunt = cat.hunt_by_id[ref["hunt"]]

    # bonus da arvore
    spell_dmg = crit_chance = crit_dmg = mana_pct = hp_pct = 0.0
    element_dmg = {}
    for nid, rank in ref["tree"].items():
        for key, val in (node_by_id[nid].get("efeito_por_rank") or {}).items():
            if key == "spellDmgPct":
                spell_dmg += val * rank
            elif key == "critChance":
                crit_chance += val * rank
            elif key == "critDmg":
                crit_dmg += val * rank
            elif key == "manaPct":
                mana_pct += val * rank
            elif key == "hpPct":
                hp_pct += val * rank
            elif key == "elementDmgPct":
                for el, x in val.items():
                    element_dmg[el] = element_dmg.get(el, 0.0) + x * rank
    # itens: skill de magia, critico, imbuements
    magic = c["skill_base"] + c["skill_per_level"] * level
    for item in items.values():
        magic += (item.get("skills") or {}).get("magic", 0)
        crit_chance += item.get("crit_chance") or 0
        crit_dmg += item.get("crit_dano") or 0
    for slot, imbs in ref["imbuements"].items():
        for key, tier in imbs:
            info = imb_by_key[key]
            if info["kind"] == "crit":
                crit_dmg += info["values"][tier - 1]
                crit_chance += c["imbuement_crit_chance"]
    crit = 1 + crit_chance * (c["crit_base"] + crit_dmg) / 10000.0
    # a IA de combate: o perfil nao tem ranks de Battle Tactics; qp = min(10, 0,5 x floor(50/100)) + 0 = 0
    tactics_ranks = sum(r for nid, r in ref["tree"].items() if node_by_id[nid]["nome"] == "Battle Tactics")
    qp = min(10, 0.5 * (level // 100)) + min(10, tactics_ranks)
    aim = min(1.0, c["tactics_aim_base"] + c["tactics_aim_per_qp"] * qp)
    ai_quality = aim + (1 - aim) * c["tactics_imperfect"]
    crit *= ai_quality   # pesa em todo o dano que sai (nao na cura)
    hp = (c["hp_base"] + c["hp_per_level"] * level) * (1 + hp_pct / 100)
    mana = (c["mana_base"] + c["mana_per_level"] * level) * (1 + mana_pct / 100)

    tree_points = sum(_node_cost(node_by_id[nid], r) for nid, r in ref["tree"].items())
    lo, hi = _js_range(spells[ref["heal"]]["formula_cura"], level, magic)
    heal = (lo + hi) / 2

    members = [cat.creature_by_key[m["chave"]] for m in hunt["monstros"]]
    boss = cat.creature_by_key[hunt["boss_da_wave_10"]["chave"]]
    pack = hunt["max_vivos"]

    def resist(creatures, element):
        return sum(((x.get("resistencias") or {}).get(element) or 0) for x in creatures) / len(creatures)

    def spell_hit(spell, element, creatures):
        lo, hi = _js_range(spell["formula_dano"], level, magic)
        return ((lo + hi) / 2) * (1 + spell_dmg / 100) * (1 + element_dmg.get(element, 0.0) / 100) \
            * (1 - resist(creatures, element) / 100) * crit

    wand = items["weapon"]
    element_of = {"flam": "fire", "vis": "energy"}

    def dps(creatures, is_boss):
        targets = 1 if is_boss else min(pack, c["area_targets_radius_2"])
        casts_each = 60 // (2 * c["gcd_s"])   # os dois feiticos tem cooldown de 4 s e alternam no GCD de 2 s
        total = 0.0
        mana_s = 0.0
        for name in ref["rotation"]:
            sp = spells[name]
            el = next(v for k, v in element_of.items() if k in sp["palavras"].split())
            total += casts_each * spell_hit(sp, el, creatures) * targets
            mana_s += casts_each * sp["mana"] / 60.0
        auto = (wand["wand_min"] + wand["wand_max"]) / 2 * (1 + element_dmg.get(wand["elemento"], 0.0) / 100) \
            * (1 - resist(creatures, wand["elemento"]) / 100) * crit / c["auto_interval_s"]
        return total / 60.0 + auto, auto, mana_s

    dps_pack, auto, mana_s = dps(members, False)
    dps_boss, _, _ = dps([boss], True)
    hp_normals = c["cycle_kills"] * sum(x["hp"] for x in members) / len(members)
    hp_boss = c["boss_hp_mult"] * boss["hp"]
    dps_cycle = (hp_normals + hp_boss) / (hp_normals / dps_pack + hp_boss / dps_boss)
    return {"heal_per_cast": heal, "tree_points": tree_points, "hp_max": hp, "mana_max": mana,
            "dps_pack": dps_pack, "dps_boss": dps_boss, "dps_cycle": dps_cycle, "auto_dps": auto,
            "mana_demand": mana_s, "magic_level": magic, "ai_quality": ai_quality}


# --- 1b. contas a mao com uma runa e Battle Tactics (ordem 8, 16/09/2026) ------------------------
# Sorcerer 471 na Livraria FIRE com a rotacao que o Andre fixou (Rage of the Skies + Avalanche —
# a Avalanche e uma runa: 64 gold por lancamento, 5 de mana, cooldown 2 s), Battle Tactics 7 e o
# equipamento do perfil de referencia (nao e a build recomendada: e um perfil FIXO que a conta a
# mao cobre por inteiro). Sem cura e com pocoes: o que se valida e a rotacao (DPS, casts, mana/s),
# o gold/h das runas e o das pocoes de mana EM REGIME (deficit x preco por mana); as pocoes de vida
# dependem do ciclo de cura do simulador e nao se validam a mao (a pagina diz o total).
REFERENCE_RUNE = {
    "vocation": "sorcerer", "level": 471, "hunt": "livrariafire-cave",
    "tree": {"s_arcane": 10, "s_crit": 4, "s_energy": 5, "s_devastate": 2, "s_ignite": 1, "s_wildfire": 10,
             "s_conduit": 5, "s_focus_mastery": 1, "s_overchannel": 7, "s_necro": 1, "s_soulharvest": 1, "s_tactics": 7},
    "equipment": REFERENCE["equipment"], "imbuements": REFERENCE["imbuements"],
    "rotation": ["Rage of the Skies", "Avalanche"],
    "heal": None,
}
HAND_CONSTANTS_RUNE = dict(HAND_CONSTANTS, **{
    "rune_mana": (5, "cliente: `mana: 5` nas runas (bruto/feiticos.json)"),
    "rune_cd_s": (2, "cliente: `cd: 2000` nas runas"),
    "area_targets_radius_3plus": (9, "convencao ⚠ AREA_TARGETS: raio 3+ (com o raio de procura da IA somado) = 9, limitado ao pack"),
    "ultimate_mana_potion": ((800, 488), "cliente: ultimate mana potion, 800 de mana por 488 gold (sorcerer/druid, nivel 130+)"),
})


def _profile_numbers(cat, ref, c):
    """O que e comum as duas contas a mao: bonus da arvore, skill de magia, critico, IA."""
    level = ref["level"]
    node_by_id = cat.node_by_id
    items = {slot: cat.item_by_key[name] for slot, name in ref["equipment"].items()}
    imb_by_key = {i["key"]: i for i in (cat.meta("itens").get("imbuements") or {}).get("lista") or []}
    spell_dmg = crit_chance = crit_dmg = mana_pct = hp_pct = 0.0
    element_dmg = {}
    tactics_ranks = 0
    for nid, rank in ref["tree"].items():
        node = node_by_id[nid]
        if (node.get("especial") or {}).get("key") == "tactics":
            tactics_ranks += rank * node["especial"]["value"]
        for key, val in (node.get("efeito_por_rank") or {}).items():
            if key == "spellDmgPct":
                spell_dmg += val * rank
            elif key == "critChance":
                crit_chance += val * rank
            elif key == "critDmg":
                crit_dmg += val * rank
            elif key == "manaPct":
                mana_pct += val * rank
            elif key == "hpPct":
                hp_pct += val * rank
            elif key == "elementDmgPct":
                for el, x in val.items():
                    element_dmg[el] = element_dmg.get(el, 0.0) + x * rank
    magic = c["skill_base"] + c["skill_per_level"] * level
    for item in items.values():
        magic += (item.get("skills") or {}).get("magic", 0)
        crit_chance += item.get("crit_chance") or 0
        crit_dmg += item.get("crit_dano") or 0
    for slot, imbs in ref["imbuements"].items():
        for key, tier in imbs:
            info = imb_by_key[key]
            if info["kind"] == "crit":
                crit_dmg += info["values"][tier - 1]
                crit_chance += c["imbuement_crit_chance"]
    crit = 1 + crit_chance * (c["crit_base"] + crit_dmg) / 10000.0
    qp = min(10, 0.5 * (level // 100)) + min(10, tactics_ranks)
    aim = min(1.0, c["tactics_aim_base"] + c["tactics_aim_per_qp"] * qp)
    ai_quality = aim + (1 - aim) * c["tactics_imperfect"]
    tree_points = sum(_node_cost(node_by_id[nid], r) for nid, r in ref["tree"].items())
    return {"items": items, "spell_dmg": spell_dmg, "element_dmg": element_dmg, "magic": magic, "crit": crit,
            "ai_quality": ai_quality, "qp": qp, "hp_pct": hp_pct, "mana_pct": mana_pct, "tree_points": tree_points}


def hand_calculation_rune(cat, ref=REFERENCE_RUNE):
    """A conta a mao do perfil com runa e Battle Tactics. So JSON e aritmetica."""
    c = {k: v for k, (v, _) in HAND_CONSTANTS_RUNE.items()}
    level = ref["level"]
    voc = cat.vocation_by_name[ref["vocation"]]
    spells = {s["nome"]: s for s in voc["feiticos"]}
    p = _profile_numbers(cat, ref, c)
    hunt = cat.hunt_by_id[ref["hunt"]]
    pack = hunt["max_vivos"]
    members = [cat.creature_by_key[m["chave"]] for m in hunt["monstros"]]
    boss = cat.creature_by_key[hunt["boss_da_wave_10"]["chave"]]
    mult = p["crit"] * p["ai_quality"]

    def resist(creatures, element):
        # a mesma leitura do catalogo que o simulador faz (bestiario > 2.a tabela); todos conhecidos aqui
        return sum((cat.resistances(x)[0] or {}).get(element, 0) for x in creatures) / len(creatures)

    def spell_hit(spell, creatures):
        el = {"vis": "energy", "frigo": "ice", "flam": "fire", "tera": "earth", "mort": "death"}[
            next(w for w in spell["palavras"].split() if w in ("vis", "frigo", "flam", "tera", "mort"))]
        lo, hi = _js_range(spell["formula_dano"], level, p["magic"])
        return ((lo + hi) / 2) * (1 + p["spell_dmg"] / 100) * (1 + p["element_dmg"].get(el, 0.0) / 100) \
            * (1 - resist(creatures, el) / 100) * mult

    # a grelha de 2 s (cooldown de grupo): a magia com mais dano por lancamento primeiro — Rage of
    # the Skies (cooldown 10 s) cabe 6 vezes em 60 s; a runa (cooldown 2 s) apanha os outros 24 slots
    rage, rune = spells[ref["rotation"][0]], spells[ref["rotation"][1]]
    assert rune["custo_gold"] and rune["mana"] == c["rune_mana"] and rune["cooldown_ms"] == c["rune_cd_s"] * 1000
    slots_total = 60 // c["gcd_s"]
    casts_rage = 60 // (rage["cooldown_ms"] // 1000)
    casts_rune = slots_total - casts_rage
    targets = min(pack, c["area_targets_radius_3plus"])
    wand = p["items"]["weapon"]

    def dps(creatures, is_boss):
        n = 1 if is_boss else targets
        total = casts_rage * spell_hit(rage, creatures) * n + casts_rune * spell_hit(rune, creatures) * n
        auto = (wand["wand_min"] + wand["wand_max"]) / 2 * (1 + p["element_dmg"].get(wand["elemento"], 0.0) / 100) \
            * (1 - resist(creatures, wand["elemento"]) / 100) * mult / c["auto_interval_s"]
        return total / 60.0 + auto, auto

    dps_pack, auto = dps(members, False)
    dps_boss, _ = dps([boss], True)
    hp_normals = c["cycle_kills"] * sum(x["hp"] for x in members) / len(members)
    hp_boss = c["boss_hp_mult"] * boss["hp"]
    dps_cycle = (hp_normals + hp_boss) / (hp_normals / dps_pack + hp_boss / dps_boss)
    mana_s = (casts_rage * rage["mana"] + casts_rune * rune["mana"]) / 60.0
    runes_gold_h = casts_rune * rune["custo_gold"] * 60.0
    # pocoes de mana em regime: cada ponto de mana gasto que nada repoe (sem leech de mana nem regen
    # conhecida neste perfil) vem de uma pocao, ao preco por mana dela
    pot_mana, pot_cost = c["ultimate_mana_potion"]
    mana_potions_gold_h = mana_s * 3600.0 * pot_cost / pot_mana
    return {"tree_points": p["tree_points"], "ai_quality": p["ai_quality"], "magic_level": p["magic"],
            "dps_pack": dps_pack, "dps_boss": dps_boss, "dps_cycle": dps_cycle, "auto_dps": auto,
            "mana_demand": mana_s, "casts_first": casts_rage, "casts_rune": casts_rune,
            "runes_gold_per_hour": runes_gold_h, "mana_potions_gold_per_hour": mana_potions_gold_h,
            "hp_max": (c["hp_base"] + c["hp_per_level"] * level) * (1 + p["hp_pct"] / 100),
            "mana_max": (c["mana_base"] + c["mana_per_level"] * level) * (1 + p["mana_pct"] / 100)}


LABELS_RUNE = [("tree_points", "custo da arvore (pontos)"), ("ai_quality", "factor da IA de combate (Battle Tactics 7)"),
               ("magic_level", "magic level (guia + itens)"), ("hp_max", "HP maximo"), ("mana_max", "mana maxima"),
               ("casts_first", "lancamentos de Rage of the Skies em 60 s"), ("casts_rune", "lancamentos de Avalanche (runa) em 60 s"),
               ("dps_pack", "DPS contra o pack"), ("dps_boss", "DPS contra o boss (x3 HP)"), ("dps_cycle", "DPS do ciclo"),
               ("auto_dps", "dano/s do ataque automatico (wand)"), ("mana_demand", "mana/s gasta pela rotacao"),
               ("runes_gold_per_hour", "gold/h das runas"), ("mana_potions_gold_per_hour", "gold/h das pocoes de mana em regime")]

LABELS = [("heal_per_cast", "cura por lancamento (exura vita)"), ("tree_points", "custo da arvore (pontos)"),
          ("ai_quality", "factor da IA de combate (Battle Tactics)"),
          ("hp_max", "HP maximo"), ("mana_max", "mana maxima"), ("magic_level", "magic level (guia + itens)"),
          ("dps_pack", "DPS contra o pack"), ("dps_boss", "DPS contra o boss (x3 HP)"),
          ("dps_cycle", "DPS do ciclo"), ("auto_dps", "dano/s do ataque automatico"),
          ("mana_demand", "mana/s gasta pela rotacao")]


def compare(hand, engine, tolerance_pct=TOLERANCE_PCT, labels=None):
    """[(chave, rotulo, a mao, motor, diferenca %, ok)] — `engine` vem do simulador (build.py)."""
    rows = []
    for key, label in (labels or LABELS):
        a, b = hand.get(key), engine.get(key)
        if a is None or b is None:
            rows.append((key, label, a, b, None, False))
            continue
        diff = (b / a - 1.0) * 100.0 if a else (0.0 if b == 0 else float("inf"))
        rows.append((key, label, a, b, diff, abs(diff) <= tolerance_pct))
    return rows


# --- 2. a curva do guia --------------------------------------------------------------------------
GUIDE_CURVE = (7.012, 0.948, "guiabaiakidle.com/_astro/character-planner.D0n3Vxn3.js — `F=7.012,I=.948` (lido a 2026-09-16)")


def guide_dps(level):
    a, p, _ = GUIDE_CURVE
    return a * max(1, level) ** p


# Onde o guia e o cliente discordam: (o que, guia, cliente, o que se segue)
DISAGREEMENTS = [
    ("HP por nivel do monk", "12", "13 (`j0.monk.hpPerLevel`)", "cliente"),
    ("mana por nivel do monk", "10", "8 (`j0.monk.manaPerLevel`)", "cliente"),
    ("base de HP / mana ao nivel 0", "100 / 90", "nao esta no cliente", "guia (unica fonte)"),
    ("regeneracao base de HP/mana", "nao publica", "nao esta no cliente (e do servidor)", "nenhum: fica desconhecida e nao entra"),
    ("golpe do ataque automatico", "curva 7,012 x nivel^0,948 sem factores", "so a formula dos feiticos", "convencao ⚠ (formula do Tibia)"),
]
