"""O Codex do cliente, a letra: recompensas, numeracao, custo em kills (ordem 11, 21/09/2026).

O `ac.json` dizia «a recompensa esta no ecra do Codex». Nao esta: **calcula-se no proprio
cliente, de forma deterministica**, a partir do id da missao (bundle `index-DnzxFejS.js`,
bytes ~2 222 780-2 256 600: `$5e`, `Iq`, `O5e`, `qX`, `H5e`, `F5e`, `K5e`, `Wr`, `MX`, `t4e`,
`S_`/`_D`). O servidor so pode alterar o gold dos degraus (`codexconfig` -> `stepGold`).
Confirmado no ecra do Andre a 21/09/2026: «Dominio: Livraria FIRE I — Dano de magia +0,654%»
(#130) e o II (#131) «+0,654% · Ataque +0,233%», com o x5 na lista e os 50 M do degrau II.

Tudo aqui e puro: catalogo -> numeros. Nada le a BD nem a rede.
"""
from . import formulas as F

# --- constantes do cliente (nome do cliente ao lado) ---------------------------------------------
FNV_OFFSET, FNV_PRIME = 2166136261, 16777619            # $5e: FNV-1a de 32 bits
ELEMENTS = ("physical", "energy", "earth", "fire", "ice", "holy", "death")   # ID
OFFENSIVE_MIN_LEVEL = 150                                # R5e: hunts com minLevel >= 150 levam triplos ofensivos
STEP_GOLD = (0, 5e7, 5e8, 1e9)                           # SX.stepGold (omissao do cliente; `codexconfig` pode mudar)
STEP_MULT = ((" I", 1), (" II", 5), (" III", 15))         # j5e: o degrau II pede 5x a lista, o III 15x
GEAR_TIERS = (1, 1.5, 2, 3)                              # G5e
GEAR_ARMOR_FACTOR, GEAR_WEAPON_FACTOR, GEAR_SPELL_FACTOR = 0.175, 0.35, 0.5   # V5e, U5e, Q5e
RARITY = ("Comum", "Incomum", "Raro", "Épico")           # _n[0..3] = Y5e (o «tier» dos sets e a raridade da forja)
CATEGORIES = ("hunt", "boss", "gear")                    # u7
CATEGORY_LABEL = {"hunt": "Hunts", "boss": "Bosses", "gear": "Equipamento"}   # Gf


def _dt(key, el=None):
    return {"id": "%s.%s" % (key, el) if el else key, "key": key, "el": el}


# N5e: 4 triplos utilitarios (hunts com minLevel < 150)
UTILITY_TRIPLES = (
    (_dt("manaPct"), _dt("manaLeech"), _dt("spellHealPct")),
    (_dt("moveSpeed"), _dt("lifeLeech"), _dt("hpPct")),
    (_dt("lifeLeech"), _dt("manaPct"), _dt("defFlat")),
    (_dt("manaLeech"), _dt("moveSpeed"), _dt("armorFlat")),
)
# _5e: 6 triplos ofensivos (hunts com minLevel >= 150)
OFFENSIVE_TRIPLES = (
    (_dt("atkPct"), _dt("spellDmgPct"), _dt("spellHealPct")),
    (_dt("critChance"), _dt("critDmg"), _dt("onslaught")),
    (_dt("spellDmgPct"), _dt("atkPct"), _dt("manaPct")),
    (_dt("critDmg"), _dt("critChance"), _dt("lifeLeech")),
    (_dt("atkPct"), _dt("critDmg"), _dt("hpPct")),
    (_dt("spellDmgPct"), _dt("critChance"), _dt("spellHealPct")),
)
# ND: 4 triplos dos bosses sem elemento
BOSS_TRIPLES = (
    (_dt("hpPct"), _dt("armorFlat"), _dt("atkPct")),
    (_dt("armorFlat"), _dt("defFlat"), _dt("critDmg")),
    (_dt("hpPct"), _dt("defFlat"), _dt("spellDmgPct")),
    (_dt("absorbPct", "holy"), _dt("elementDmgPct", "holy"), _dt("critDmg")),
)


def boss_element_triple(el):
    """P5e: bosses com elemento."""
    return (_dt("absorbPct", el), _dt("elementDmgPct", el), _dt("critDmg"))


# B5e: o orcamento total por stat — o que o Codex INTEIRO da com tudo fechado
BUDGET = {"atkPct": 15, "spellDmgPct": 35, "critChance": 12.5, "critDmg": 75, "onslaught": 9, "hpPct": 50,
          "manaPct": 50, "armorFlat": 10, "defFlat": 10, "spellHealPct": 50, "lifeLeech": 8, "manaLeech": 8,
          "moveSpeed": 12}
for _el in ELEMENTS:
    BUDGET["elementDmgPct." + _el] = 15
    BUDGET["absorbPct." + _el] = 20

# W5e: os 42 sets (armaduras x V5e; armas «-w» x U5e; spellDmgPct ainda x Q5e)
GEAR_SETS = (
    ("leather", "Leather", ("leather helmet", "leather armor", "leather legs", "leather boots"), {"armorFlat": .2}),
    ("studded", "Studded", ("studded helmet", "studded armor", "studded legs", "leather boots"), {"armorFlat": .25}),
    ("chain", "Chain", ("chain helmet", "chain armor", "chain legs", "leather boots"), {"armorFlat": .3}),
    ("brass", "Brass", ("brass helmet", "brass armor", "brass legs", "leather boots"), {"armorFlat": .35}),
    ("plate", "Plate", ("steel helmet", "plate armor", "plate legs", "leather boots"), {"armorFlat": .5}),
    ("knight", "Knight", ("steel helmet", "knight armor", "knight legs", "steel boots"), {"armorFlat": .7, "hpPct": .2}),
    ("crown", "Crown", ("crown helmet", "crown armor", "crown legs", "steel boots"), {"armorFlat": 1, "hpPct": .3}),
    ("steel", "Steel", ("steel helmet", "plate armor", "plate legs", "steel boots"), {"armorFlat": .85}),
    ("terra", "Terra", ("terra hood", "terra mantle", "terra legs", "terra boots"), {"armorFlat": 1.05}),
    ("magma", "Magma", ("magma monocle", "magma coat", "magma legs", "magma boots"), {"armorFlat": 1.05}),
    ("glacier", "Glacier", ("glacier mask", "glacier robe", "glacier kilt", "glacier shoes"), {"armorFlat": 1.05}),
    ("lightning", "Lightning", ("lightning headband", "lightning robe", "lightning legs", "lightning boots"), {"armorFlat": 1.05}),
    ("zaoan", "Zaoan", ("zaoan helmet", "zaoan armor", "zaoan legs", "zaoan shoes"), {"armorFlat": 1.25}),
    ("depth", "Depth", ("depth galea", "depth lorica", "depth ocrea", "depth calcei"), {"armorFlat": 1.7}),
    ("gnome", "Gnome", ("gnome helmet", "gnome armor", "gnome legs", "gnomish footwraps"), {"armorFlat": 1.7}),
    ("stoiciks", "Stoic Iks", ("stoic iks headpiece", "stoic iks chestplate", "stoic iks culet", "stoic iks boots"), {"armorFlat": 2}),
    ("bone", "Bone", ("skull helmet", "skullcracker armor", "mutant bone kilt", "mutant bone boots"), {"armorFlat": 1.85}),
    ("eldritch", "Eldritch", ("eldritch cowl", "eldritch cuirass", "eldritch breeches", "eldritch monk boots"), {"armorFlat": 1.9}),
    ("norcferatu", "Norcferatu", ("norcferatu skullguard", "norcferatu tuskplate", "norcferatu thornwraps", "norcferatu goretrampers"), {"armorFlat": 2.45}),
    ("stag", "Stag", ("stag helmet", "stag plate", "stag legs", "stag boots"), {"armorFlat": 2.4}),
    ("dark", "Dark", ("dark helmet", "dark armor"), {"armorFlat": .5}),
    ("cobra", "Cobra", ("cobra hood", "cobra boots"), {"armorFlat": .7}),
    ("ornate", "Ornate", ("ornate chestplate", "ornate legs"), {"armorFlat": 1.15}),
    ("lion", "Lion", ("lion spangenhelm", "lion plate"), {"armorFlat": 1.35}),
    ("falcon", "Falcon", ("falcon coif", "falcon plate", "falcon greaves"), {"armorFlat": 2.15}),
    ("spiritthorn", "Spiritthorn", ("spiritthorn helmet", "spiritthorn armor"), {"armorFlat": 2.05}),
    ("falcon-w", "Falcon — Armas", ("falcon battleaxe", "falcon bow", "falcon longsword", "falcon mace", "falcon rod", "falcon sai", "falcon shield", "falcon wand"), {"atkPct": 1.75, "spellDmgPct": 1.75}),
    ("cobra-w", "Cobra — Armas", ("cobra axe", "cobra bo", "cobra club", "cobra crossbow", "cobra rod", "cobra sword", "cobra wand"), {"atkPct": 1.55, "spellDmgPct": 1.55}),
    ("eldritch-w", "Eldritch — Armas", ("eldritch bow", "eldritch claymore", "eldritch crescent moon spade", "eldritch folio", "eldritch greataxe", "eldritch quiver", "eldritch rod", "eldritch shield", "eldritch tome", "eldritch wand", "eldritch warmace"), {"atkPct": 2.4, "spellDmgPct": 2.4}),
    ("gildedeldritch-w", "Gilded Eldritch — Armas", ("gilded eldritch bow", "gilded eldritch claymore", "gilded eldritch crescent moon spade", "gilded eldritch greataxe", "gilded eldritch rod", "gilded eldritch wand", "gilded eldritch warmace"), {"atkPct": 1.55, "spellDmgPct": 1.55}),
    ("lion-w", "Lion — Armas", ("lion axe", "lion claws", "lion hammer", "lion longbow", "lion longsword", "lion rod", "lion shield", "lion spellbook", "lion wand"), {"atkPct": 1.95, "spellDmgPct": 1.95}),
    ("naga-w", "Naga — Armas", ("naga axe", "naga club", "naga crossbow", "naga katar", "naga quiver", "naga rod", "naga sword", "naga wand"), {"atkPct": 1.75, "spellDmgPct": 1.75}),
    ("amber-w", "Amber — Armas", ("amber axe", "amber bludgeon", "amber bow", "amber crossbow", "amber cudgel", "amber greataxe", "amber kusarigama", "amber rod", "amber sabre", "amber slayer", "amber wand"), {"atkPct": 2.4, "spellDmgPct": 2.4}),
    ("soul-w", "Soul — Armas", ("soulbastion", "soulbiter", "soulbleeder", "soulcrusher", "soulcutter", "souleater", "soulhexer", "soulkamas", "soulmaimer", "soulpiercer", "soulshredder", "soultainter"), {"atkPct": 3, "spellDmgPct": 3}),
    ("sanguine-w", "Sanguine — Armas", ("sanguine battleaxe", "sanguine blade", "sanguine bludgeon", "sanguine bow", "sanguine claws", "sanguine coil", "sanguine crossbow", "sanguine cudgel", "sanguine hatchet", "sanguine razor", "sanguine rod"), {"atkPct": 2.75, "spellDmgPct": 2.75}),
    ("inferniarch-w", "Inferniarch — Armas", ("inferniarch arbalest", "inferniarch battleaxe", "inferniarch blade", "inferniarch bow", "inferniarch claws", "inferniarch flail", "inferniarch greataxe", "inferniarch rod", "inferniarch slayer", "inferniarch wand", "inferniarch warhammer"), {"atkPct": 2.4, "spellDmgPct": 2.4}),
    ("jungle-w", "Jungle — Armas", ("jungle bow", "jungle flail", "jungle quiver", "jungle rod", "jungle wand"), {"atkPct": .95, "spellDmgPct": .95}),
    ("stag-w", "Stag — Armas", ("refined stag shield", "stag scrolls", "stag shield", "stag spellbook"), {"atkPct": 1, "spellDmgPct": 1}),
    ("primal-w", "Primal — Armas", ("alicorn quiver", "arboreal tome", "arcanomancer folio"), {"atkPct": .75, "spellDmgPct": .75}),
    ("depthornate-w", "Depth & Ornate — Armas", ("depth claws", "depth scutum", "ornate crossbow", "ornate mace", "ornate shield"), {"atkPct": .8, "spellDmgPct": .8}),
    ("glooth-w", "Glooth — Armas", ("glooth axe", "glooth blade", "glooth club", "glooth spear", "glooth whip"), {"atkPct": .8, "spellDmgPct": .8}),
)

# `on`: os rotulos do cliente, na ordem dele (e a ordem do filtro por stat)
STAT_LABEL = {"atkPct": "Ataque", "armorFlat": "Armadura", "defFlat": "Defesa", "hpPct": "Vida", "manaPct": "Mana",
              "critChance": "Chance de crítico", "critDmg": "Dano crítico", "absorbPct": "Resistência elemental",
              "elementDmgPct": "Dano elemental", "lifeLeech": "Roubo de vida", "manaLeech": "Roubo de mana",
              "spellDmgPct": "Dano de magia", "spellHealPct": "Cura de magia", "attackSpeedPct": "Velocidade de ataque",
              "moveSpeed": "Velocidade de movimento", "onslaught": "Onslaught (fatal)"}
FLAT_STATS = frozenset(("armorFlat", "defFlat", "moveSpeed"))   # r4e: sem «%»

# Convencao ⚠ (calibrada com a captura do Andre de 21/09/2026): o numero de itens por drop e uniforme
# em 1..max, logo a media e (1+max)/2 — e a mesma conta do `gold_expected` do build. Com «1 por drop» os
# itens exclusivos da Livraria FIRE (talon, purple tome, burnt scroll, flask, soul orb) davam kills a
# divergir 3x entre si; com (1+max)/2 batem a +-10 %.
DROP_COUNT_MEAN = "(1+max)/2"


# --- o hash e o triplo -----------------------------------------------------------------------------
def fnv1a(text):
    """`$5e`: FNV-1a de 32 bits sobre os code units da string (`Math.imul`, `>>> 0`)."""
    t = FNV_OFFSET
    for ch in text:
        t ^= ord(ch)
        t = (t * FNV_PRIME) & 0xFFFFFFFF
    return t


def triple_for(key, el=None, min_level=0):
    """`Iq(key, el, minLevel)`: o triplo de stats de uma cadeia."""
    n = fnv1a(key)
    if key.startswith("boss:"):
        return boss_element_triple(el) if el else BOSS_TRIPLES[n % len(BOSS_TRIPLES)]
    table = OFFENSIVE_TRIPLES if min_level >= OFFENSIVE_MIN_LEVEL else UTILITY_TRIPLES
    return table[n % len(table)]


def hunt_lists(cat):
    """`TX`: a lista de itens de cada hunt (do `hunts.json`, `codex_da_hunt`), so as nao vazias."""
    return {h["id"]: list(h.get("codex_da_hunt") or []) for h in cat.hunts if h.get("codex_da_hunt")}


def entries(cat):
    """`O5e`: as entradas — um boss por monstro (peso 1, o primeiro `el` visto) e uma hunt por lista
    nao vazia (peso 1 + minLevel/100), com o triplo de cada. Devolve (lista, `Lq` {stat: factor})."""
    out = []
    seen = {}
    for m in cat.missions:
        if m.get("cat") == "boss" and m["monster"] not in seen:
            seen[m["monster"]] = m.get("el")
    for monster, el in seen.items():
        key = "boss:" + monster
        out.append({"key": key, "weight": 1.0, "tri": triple_for(key, el, 0)})
    lists = hunt_lists(cat)
    for h in cat.hunts:
        if h["id"] not in lists:
            continue
        key = "hunt:" + h["id"]
        min_level = h.get("nivel_minimo") or 0
        out.append({"key": key, "weight": 1 + min_level / 100.0, "tri": triple_for(key, None, min_level)})
    acc = {}
    for e in out:
        for i, st in enumerate(e["tri"]):
            acc[st["id"]] = acc.get(st["id"], 0.0) + e["weight"] * (3 - i)
    lq = {sid: (BUDGET.get(sid, 0) / v if v > 0 else 0.0) for sid, v in acc.items()}
    return out, lq


class Codex:
    """As tabelas do cliente calculadas uma vez sobre o catalogo."""

    def __init__(self, cat):
        self.cat = cat
        self.entries, self.lq = entries(cat)
        self.by_key = {e["key"]: e for e in self.entries}
        self._missions = None
        self._by_id = None

    def bonus(self, key, step):
        """`qX(key, step)`: o bonus da missao — para i de 0 ate min(step, 2), o stat i do triplo vale
        round(Lq x peso x 1000)/1000. (O degrau II repete o stat do I: fechar I+II+III da tri[0] x3 +
        tri[1] x2 + tri[2] x1, coerente com o peso x (3 - i) da normalizacao.)"""
        e = self.by_key.get(key) or {"tri": triple_for(key, None, 0), "weight": 1.0}
        out = {}
        for i in range(min(step, 2) + 1):
            st = e["tri"][i]
            v = round(self.lq.get(st["id"], 0.0) * e["weight"] * 1000) / 1000.0
            if v <= 0:
                continue
            if st["el"]:
                d = out.setdefault(st["key"], {})
                d[st["el"]] = d.get(st["el"], 0.0) + v
            else:
                out[st["key"]] = out.get(st["key"], 0.0) + v
        return out

    def missions(self):
        """`Wr()` = `[...H5e(), ...AX.map(F5e), ...K5e()]`, cada uma com `number` = `MX(id)` (posicao,
        a comecar em 1). Hunts na ordem do `hunts.json` (`ca`), 3 degraus por hunt; depois os bosses na
        ordem do `ac.json` (`AX`); depois os sets x 4 raridades."""
        if self._missions is not None:
            return self._missions
        out = []
        lists = hunt_lists(self.cat)
        for h in self.cat.hunts:                                   # H5e
            items = lists.get(h["id"])
            if not items:
                continue
            for step, (suffix, mult) in enumerate(STEP_MULT):
                mid = "hunt-%s" % h["id"] if step == 0 else "hunt-%s-%d" % (h["id"], step + 1)
                out.append({"id": mid, "cat": "hunt", "name": "Domínio: %s%s" % (h["nome"], suffix),
                            "chain": "hunt:" + h["id"], "step": step, "hunt_id": h["id"],
                            "min_level": h.get("nivel_minimo"),
                            "req": [{"item": it["item"], "qty": it["qty"] * mult} for it in items],
                            "bonus": self.bonus("hunt:" + h["id"], step), "unlock_gold": STEP_GOLD[step]})
        for m in self.cat.missions:                                # AX.map(F5e)
            if m.get("cat") != "boss":
                continue
            creature = self.cat.creature_by_key.get(m["monster"])
            name = creature["nome"] if creature else m.get("mname")
            step = m["step"]
            out.append({"id": m["id"], "cat": "boss", "name": "Troféu de %s%s" % (name, STEP_MULT[step][0]),
                        "chain": "boss:" + m["monster"], "step": step, "monster": m["monster"], "el": m.get("el"),
                        "req": [dict(r) for r in m["req"]], "bonus": self.bonus("boss:" + m["monster"], step),
                        "unlock_gold": STEP_GOLD[step]})
        for sid, sname, pieces, base in GEAR_SETS:                  # K5e
            factor = GEAR_WEAPON_FACTOR if sid.endswith("-w") else GEAR_ARMOR_FACTOR
            for tier, mult in enumerate(GEAR_TIERS):
                bonus = {}
                for stat, v in base.items():
                    f = factor * GEAR_SPELL_FACTOR if stat == "spellDmgPct" else factor
                    bonus[stat] = round(v * mult * f * 1000) / 1000.0
                out.append({"id": "set-%s-%d" % (sid, tier), "cat": "gear", "name": "Set %s (%s)" % (sname, RARITY[tier]),
                            "chain": "gear:" + sid, "step": tier, "set_id": sid,
                            "req": [{"item": p, "qty": 1, "tier": tier} for p in pieces],
                            "bonus": bonus, "unlock_gold": STEP_GOLD[tier]})
        for i, m in enumerate(out):
            m["number"] = i + 1                                    # MX
        self._missions = out
        self._by_id = {m["id"]: m for m in out}
        return out

    def mission(self, mission_id):
        """`Kg(id)`: a missao pelo id, ou `None`."""
        self.missions()
        return self._by_id.get(mission_id)

    def total_budget(self, cats=("hunt", "boss")):
        """A soma dos bonus de todas as missoes de hunt e de boss por stat: tem de dar `B5e` a menos
        do arredondamento (os sets ficam fora da normalizacao `Lq` e somam por cima)."""
        total = {}
        for m in self.missions():
            if m["cat"] not in cats:
                continue
            for k, v in m["bonus"].items():
                if isinstance(v, dict):
                    for el, x in v.items():
                        total["%s.%s" % (k, el)] = total.get("%s.%s" % (k, el), 0.0) + x
                else:
                    total[k] = total.get(k, 0.0) + v
        return total

    # --- custo em kills -----------------------------------------------------------------------------
    def drop_rate(self, hunt_id, item):
        """Itens esperados por kill na hunt: a quota de cada monstro no pack (`peso`; uniforme quando
        e null) x chance/100 000 x (1+max)/2. `None` quando nenhum monstro da hunt o larga (o loot
        desse item e desconhecido: nunca zero)."""
        hunt = self.cat.hunt_by_id[hunt_id]
        monsters = hunt.get("monstros") or []
        weights = [(m.get("peso") if m.get("peso") is not None else 1.0) for m in monsters]
        total = sum(weights) or 1.0
        rate, known = 0.0, False
        for m, w in zip(monsters, weights):
            c = self.cat.creature_by_key.get(m["chave"])
            for d in (c or {}).get("loot") or []:
                if d.get("item") == item and d.get("chance_por_100k") is not None:
                    known = True
                    rate += (w / total) * d["chance_por_100k"] / 100000.0 * (1 + (d.get("max") or 1)) / 2.0
        return rate if known else None

    def kills_needed(self, hunt_id, step, progress=None):
        """Kills na hunt para fechar o «Dominio» do degrau (0, 1, 2): por item, qty / taxa por kill;
        o gargalo e o item que precisa de mais kills. `progress` (contagens por item, na ordem do
        `req`) desconta o que ja esta entregue. Itens sem drop conhecido ficam «?» (`unknown`) e nao
        entram no gargalo — o total e o maximo dos conhecidos e a pagina diz o que ficou de fora
        (desconhecido nao e zero, mas tambem nao pode ser infinito)."""
        m = self.mission("hunt-%s" % hunt_id if step == 0 else "hunt-%s-%d" % (hunt_id, step + 1))
        if m is None:
            return None
        rows, unknown = [], []
        for i, r in enumerate(m["req"]):
            done = 0
            if progress and i < len(progress) and progress[i] is not None:
                done = min(r["qty"], int(progress[i]))
            missing = r["qty"] - done
            rate = self.drop_rate(hunt_id, r["item"])
            if rate is None:
                unknown.append(r["item"])
                rows.append({"item": r["item"], "qty": r["qty"], "done": done, "missing": missing, "rate": None, "kills": None})
                continue
            kills = (missing / rate) if rate > 0 else None
            rows.append({"item": r["item"], "qty": r["qty"], "done": done, "missing": missing, "rate": rate, "kills": kills})
        known = [r for r in rows if r["kills"] is not None]
        worst = max(known, key=lambda r: r["kills"]) if known else None
        return {"mission_id": m["id"], "hunt_id": hunt_id, "step": step, "rows": rows, "unknown": unknown,
                "kills": worst["kills"] if worst else None, "bottleneck": worst["item"] if worst else None,
                "complete": all(r["missing"] <= 0 for r in rows)}


# --- o formato do cliente ---------------------------------------------------------------------------
def fmt_client(value):
    """`_D`: 3 casas decimais, virgula (pt-BR), sem separador de milhares."""
    return ("%.3f" % value).replace(".", ",")


def format_bonus(bonus):
    """`S_`: «Dano de magia +0,654%» · «Resistência elemental ice +1,111%» (os flat sem %)."""
    parts = []
    for k, v in bonus.items():
        label = STAT_LABEL.get(k, k)
        if isinstance(v, dict):
            for el, x in v.items():
                if x:
                    parts.append("%s %s +%s%%" % (label, el, fmt_client(x)))
        elif v:
            parts.append("%s +%s%s" % (label, fmt_client(v), "" if k in FLAT_STATS else "%"))
    return parts


def format_bonus_line(bonus):
    """`s4e`: as partes unidas por « · »."""
    return " · ".join(format_bonus(bonus))


def item_matches(req, item_name, item_tier=0, up_level=0):
    """`t4e(req, item)`: quando um item da bag serve um `req`. Nome igual (ou na lista `anyOf`);
    com `tier` a raridade tem de ser exactamente essa (os sets); com `anyTier` qualquer ate a maxima
    da forja (3, `qq()`); com `minTier` pelo menos essa; sem nada disto **so tier 0** — um item
    forjado (Incomum ou melhor) nunca serve uma hunt nem um boss. E `upLevel >= minUp` (omissao 0).
    Nao ha no bundle regra nenhuma sobre «of destruction»."""
    if req.get("anyOf"):
        if item_name not in req["anyOf"]:
            return False
    elif item_name != req.get("item"):
        return False
    tier = item_tier or 0
    if req.get("tier") is not None:
        if tier != req["tier"]:
            return False
    elif req.get("anyTier"):
        if tier > MAX_FORGE_TIER:
            return False
    elif req.get("minTier") is not None:
        if tier < req["minTier"]:
            return False
    elif tier != 0:
        return False
    return (up_level or 0) >= (req.get("minUp") or 0)


MAX_FORGE_TIER = 3   # qq(): o maior tier com custo definido em n5e (1: 2000, 2: 500, 3: 50)


def bonus_stats(bonus):
    """[(stat, elemento ou None, valor)] de um bonus, para as contas."""
    out = []
    for k, v in bonus.items():
        if isinstance(v, dict):
            out.extend((k, el, x) for el, x in v.items())
        else:
            out.append((k, None, v))
    return out


def kills_per_hour(dps_pack, dps_boss, target):
    """Kills/h de quem faz `dps_pack` no pack e `dps_boss` no boss, no ciclo do simulador (57 normais
    de HP medio + 1 boss x3): 58 kills por ciclo a dividir pelo tempo do ciclo. `None` sem DPS."""
    if not dps_pack or dps_pack <= 0:
        return None
    seconds = F.CYCLE_NORMAL_KILLS * target.hp / dps_pack
    if target.boss_hp > 0:
        if not dps_boss or dps_boss <= 0:
            return None
        seconds += target.boss_hp / dps_boss
    return (F.CYCLE_NORMAL_KILLS + (1 if target.boss_hp > 0 else 0)) * 3600.0 / seconds if seconds > 0 else None
