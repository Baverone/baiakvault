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
            "mana_demand": mana_s, "magic_level": magic}


LABELS = [("heal_per_cast", "cura por lancamento (exura vita)"), ("tree_points", "custo da arvore (pontos)"),
          ("hp_max", "HP maximo"), ("mana_max", "mana maxima"), ("magic_level", "magic level (guia + itens)"),
          ("dps_pack", "DPS contra o pack"), ("dps_boss", "DPS contra o boss (x3 HP)"),
          ("dps_cycle", "DPS do ciclo"), ("auto_dps", "dano/s do ataque automatico"),
          ("mana_demand", "mana/s gasta pela rotacao")]


def compare(hand, engine, tolerance_pct=TOLERANCE_PCT):
    """[(chave, rotulo, a mao, motor, diferenca %, ok)] — `engine` vem do simulador (build.py)."""
    rows = []
    for key, label in LABELS:
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
