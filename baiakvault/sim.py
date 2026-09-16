"""O simulador de combate: personagem + alvo de referencia -> DPS, HPS, EHP, mana.

Deterministico, em valores esperados (sem sorteios): a media de cada golpe, a
chance de critico como multiplicador, a chance de uma habilidade do monstro
como fraccao do dano. Dado um `Profile` (vocacao, nivel, skills, arvore
comprada, equipamento) e um `Target` (a hunt de referencia), corre 60 s de
combate na grelha de 1 s — todos os cooldowns do cliente sao multiplos de
1 s; o ataque automatico, que nao e, entra como taxa continua — respeitando o
cooldown de grupo de ataque (2 s, cliente), o grupo de cura (1 s, guia), o
cooldown proprio de cada feitico, o custo de mana, o leech e as pocoes com o
exhaust de 1 s.

Cada numero que sai daqui tem uma fonte em `formulas.py`. O que la esta como
`convencao` (o golpe da arma, o intervalo do ataque automatico, quantos
bichos uma area apanha, a regen base desconhecida) e o que torna estes
numeros uma estimativa e nao uma medicao — a pagina diz isso.
"""
from . import formulas as F

ELEMENTS = F.ELEMENTS
MAIN_SKILL = {"knight": "melee", "monk": "fist", "paladin": "distance", "sorcerer": "magic", "druid": "magic"}
MAGES = ("sorcerer", "druid")
AVATAR_SECONDS = F._c("avatar_seconds", 15, F.SOURCE_CLIENT,
                      F.BUNDLE + " — desc dos nos Avatar: «entrar na forma avatar por 15s (crita sempre e -3% de dano recebido)»")
# Magic level tipico das vocacoes fisicas (o guia so da o dos mages) — CONVENCAO,
# marcada assim na pagina; o ML real dele substitui isto (16/09/2026).
ML_AT_LEVEL_PHYSICAL = {"knight": (8, 0.02), "monk": (8, 0.02), "paladin": (12, 0.05)}
F._c("ml_at_level_physical", ML_AT_LEVEL_PHYSICAL, F.SOURCE_CONVENTION,
     "magic level tipico de knight/monk (8 + 0,02/nivel) e paladin (12 + 0,05/nivel); o guia nao da",
     "so pesa na cura propria e nas runas destas vocacoes")


def empty_bonuses():
    b = {k: 0.0 for k in ("atkPct", "defFlat", "armorFlat", "critChance", "critDmg", "lifeLeech",
                          "manaLeech", "hpPct", "manaPct", "expPct", "lootPct", "spellDmgPct",
                          "attackSpeedPct", "spellHealPct", "hpRegenPct", "mpRegenPct", "hpRegenFlat",
                          "mpRegenFlat", "moveSpeed", "reflect", "execute")}
    b["absorbPct"] = {e: 0.0 for e in ELEMENTS}
    b["elementDmgPct"] = {e: 0.0 for e in ELEMENTS}
    return b


def add_bonus(bon, per, times=1):
    """Soma um `efeito_por_rank` x times. Cliente `KN`: numeros somam; absorcoes
    empilham com `ds`; o resto dos dicionarios soma."""
    if not per:
        return
    for key, val in per.items():
        if val is None:
            continue
        if isinstance(val, (int, float)):
            bon[key] = bon.get(key, 0.0) + val * times
        elif key == "absorbPct":
            if isinstance(val, dict) and "$expr" in val:
                # `yo(x)` do cliente: x em todos os elementos
                x = float(val["$expr"][3:-1])
                val = {e: x for e in ELEMENTS}
            for el, v in val.items():
                if isinstance(v, (int, float)):
                    bon["absorbPct"][el] = F.ds(bon["absorbPct"][el], v * times)
        elif isinstance(val, dict):
            target = bon.setdefault(key, {e: 0.0 for e in ELEMENTS})
            for el, v in val.items():
                if isinstance(v, (int, float)):
                    target[el] = target.get(el, 0.0) + v * times


def tree_bonuses(cat, vocation, ranks):
    """(bonuses, specials) de uma arvore comprada. Cliente `fq` e `d_`."""
    bon = empty_bonuses()
    specials = {}
    tree = cat.tree_by_vocation.get(vocation) or {}
    for node in tree.get("nos") or []:
        r = min(int(ranks.get(node["id"], 0) or 0), node.get("rank_maximo") or 1)
        if r <= 0:
            continue
        add_bonus(bon, node.get("efeito_por_rank"), r)
        sp = node.get("especial")
        if sp:
            specials[sp["key"]] = specials.get(sp["key"], 0) + sp["value"] * r
    return bon, specials


_ITEM_BONUS_FIELDS = (("crit_chance", "critChance"), ("crit_dano", "critDmg"),
                      ("life_leech", "lifeLeech"), ("mana_leech", "manaLeech"))


def item_bonuses(bon, skills, item, up_level=0, imbuements=(), cat=None):
    """Aplica um item equipado aos bonus e skills. Cliente `l5` (a letra: a
    arma melhorada da +1 % atk por nivel; um item com `def` melhorado da
    armorFlat += def x 0,005 x nivel), mais absorcoes, crit/leech, regen e skills."""
    if not item:
        return
    if item.get("slot") == "weapon":
        bon["atkPct"] += up_level * F.UPGRADE_WEAPON_ATK_PCT
    elif item.get("defesa"):
        bon["armorFlat"] += (item.get("defesa") or 0) * (up_level * F.UPGRADE_ARMOR_DEF_FACTOR)
    for el, v in (item.get("absorcao") or {}).items():
        if el in bon["absorbPct"]:
            bon["absorbPct"][el] = F.ds(bon["absorbPct"][el], v)
    for src, dst in _ITEM_BONUS_FIELDS:
        if item.get(src):
            bon[dst] += item[src]
    for sk, v in (item.get("skills") or {}).items():
        skills[sk] = skills.get(sk, 0.0) + v
    for el, v in (item.get("magic_por_elemento") or {}).items():
        # «{el} magic level {v}» (cliente cY): +v de ML so para esse elemento
        mel = bon.setdefault("magicEl", {})
        mel[el] = mel.get(el, 0.0) + v
    imb_list = ((cat.meta("itens").get("imbuements") or {}).get("lista") or []) if cat else []
    imb_by_key = {i["key"]: i for i in imb_list}
    for imb in imbuements or ():
        key, tier = (imb, 3) if isinstance(imb, str) else (imb[0], imb[1])
        info = imb_by_key.get(key)
        if not info:
            continue
        value = (info.get("values") or [0, 0, 0])[max(0, min(2, tier - 1))]
        kind = info.get("kind")
        if kind == "leech-life":
            bon["lifeLeech"] += value
        elif kind == "leech-mana":
            bon["manaLeech"] += value
        elif kind == "crit":
            bon["critDmg"] += value
            bon["critChance"] += F.IMBUEMENT_CRIT_CHANCE
        elif kind == "protect" and info.get("element"):
            bon["absorbPct"][info["element"]] = F.ds(bon["absorbPct"][info["element"]], value)
        elif kind == "skill" and info.get("skill"):
            skills[info["skill"]] = skills.get(info["skill"], 0.0) + value
        elif kind == "elemdmg" and info.get("element"):
            # «{n}% do dano vira {el}» (cliente W2): conversao, nao dano extra
            conv = bon.setdefault("convert", {})
            conv[info["element"]] = conv.get(info["element"], 0.0) + value


class Profile:
    """Quem se simula. `equipment` e {slot: {"item": item do catalogo, "up": n,
    "imbuements": [chave ou (chave, tier)]}}; `tree` e {no: rank}; `skills`
    e {"melee"/"fist"/"distance"/"magic"/"shielding": valor} — o que faltar
    vem do skill tipico do guia (marcado)."""

    def __init__(self, cat, vocation, level, tree=None, equipment=None, skills=None,
                 heal_at_pct=85, potion_hp_pct=85, potion_mana_pct=25):
        self.cat = cat
        self.vocation = vocation
        self.level = int(level)
        self.tree = dict(tree or {})
        self.equipment = dict(equipment or {})
        self.skills_given = dict(skills or {})
        self.heal_at_pct = heal_at_pct
        self.potion_hp_pct = potion_hp_pct
        self.potion_mana_pct = potion_mana_pct
        self.assumed_skill = False
        self._build()

    def _build(self):
        cat, voc, level = self.cat, self.vocation, self.level
        bon, specials = tree_bonuses(cat, voc, self.tree)
        weapon = (self.equipment.get("weapon") or {}).get("item")
        self.weapon = weapon
        self.weapon_type = (weapon or {}).get("tipo_de_arma") or ("wand" if voc in MAGES else "fist")
        skills = {}
        for slot, eq in self.equipment.items():
            if not eq or not eq.get("item"):
                continue
            item_bonuses(bon, skills, eq["item"], eq.get("up", 0) or 0, eq.get("imbuements") or (), cat)
        # as skills `sword`/`axe`/`club` dos itens so contam com a arma desse tipo (cliente $1e: os tres sao `melee`)
        for wt in ("sword", "axe", "club"):
            v = skills.pop(wt, 0.0)
            if v and wt == self.weapon_type:
                skills["melee"] = skills.get("melee", 0.0) + v
        main = MAIN_SKILL[voc]
        base = dict(self.skills_given)
        if main not in base:
            base[main] = F.typical_skill(voc, level)
            self.assumed_skill = True
        if "magic" not in base:
            if voc in MAGES:
                base["magic"] = base[main]
            else:
                a, b = ML_AT_LEVEL_PHYSICAL[voc]
                base["magic"] = a + b * level
        if "shielding" not in base:
            base["shielding"] = base[main] if voc == "knight" else 0.0
        for k, v in skills.items():
            base[k] = base.get(k, 0.0) + v
        self.skills = base
        self.bonuses = bon
        self.specials = specials

        shield = (self.equipment.get("shield") or {}).get("item")
        ammo = (self.equipment.get("ammo") or {}).get("item")
        self.two_handed = bool((weapon or {}).get("duas_maos"))
        self.has_shield = bool(shield) and not self.two_handed
        self.shield_def = (shield or {}).get("defesa") or 0
        up = (self.equipment.get("weapon") or {}).get("up", 0) or 0
        atk = (weapon or {}).get("ataque") or 0
        elem_atk = (weapon or {}).get("ataque_elemental") or 0
        if voc == "paladin" and ammo and (weapon or {}).get("municao") == ammo.get("municao"):
            atk += F.ammo_attack(ammo.get("nome"), ammo.get("ataque"))
        # ataque total = fisico + elemental (o cliente mostra «Atk N (+E el)»); a parte
        # elemental do golpe da arma sai nesse elemento
        self.attack = F.weapon_attack(atk + elem_atk, up, bon["atkPct"])
        self.attack_element_share = (elem_atk / float(atk + elem_atk)) if (atk + elem_atk) > 0 and elem_atk else 0.0
        self.wand = None
        if self.weapon_type == "wand" and weapon and weapon.get("wand_min") is not None:
            self.wand = {"min": weapon["wand_min"], "max": weapon["wand_max"],
                         "element": weapon.get("elemento") or "energy",
                         "mana_shot": weapon.get("mana_por_tiro") or 0}
        self.weapon_element = (weapon or {}).get("elemento") if self.weapon_type != "wand" else None

        armor = sum((eq.get("item") or {}).get("armadura") or 0 for eq in self.equipment.values() if eq)
        self.armor = armor + bon["armorFlat"]
        self.defense = self.shield_def + bon["defFlat"]  # Battle Instinct entra em `mitigation`, depende do pack
        self.hp_max = F.max_hp(voc, level, bon["hpPct"])
        self.mana_max = F.max_mana(voc, level, bon["manaPct"])
        self.uses_mana_potions = F.USES_MANA_POTIONS[voc]
        self.hp_potion = F.best_potion(F.HEALTH_POTIONS, voc, level)
        self.mana_potion = F.best_potion(F.MANA_POTIONS, voc, level) if self.uses_mana_potions else None
        self.spells = [s for s in (cat.vocation_by_name[voc].get("feiticos") or [])
                       if s["nivel"] <= level and (not s.get("promocao") or level >= 300)]

    # --- dano de um golpe/feitico contra um alvo (media esperada) -------------------------
    def avatar_uptime(self):
        """Fraccao do tempo na forma avatar: p % por golpe que acerta, 15 s
        (cliente, desc do no). Golpes/s = ataque automatico + um feitico por
        cooldown de grupo — CONVENCAO para a taxa de golpes."""
        p = self.specials.get("avatar", 0) / 100.0
        if p <= 0:
            return 0.0
        interval = F.AUTO_ATTACK_INTERVAL_MS / 1000.0 / (1 + self.bonuses["attackSpeedPct"] / 100.0)
        hits_per_s = 1.0 / interval + 1000.0 / F.ATTACK_GCD_MS
        wait = 1.0 / (hits_per_s * p)
        return AVATAR_SECONDS / (AVATAR_SECONDS + wait)

    def crit(self):
        chance = self.bonuses["critChance"]
        u = self.avatar_uptime()
        if u:
            chance = u * 100.0 + (1 - u) * chance  # em avatar «crita sempre»
        return F.crit_multiplier(chance, self.bonuses["critDmg"])

    def _element_mult(self, element, resist, pierce=0.0):
        bon = self.bonuses
        return (1 + bon["elementDmgPct"].get(element, 0.0) / 100.0) * F.resist_factor(resist.get(element, 0), pierce)

    def hit_vs(self, base, element, resist, is_spell):
        """Dano medio de um golpe `base` do elemento contra `resist` {el: %}."""
        bon = self.bonuses
        pierce = self.specials.get("element_pierce", 0.0)
        mult = self.crit()
        if is_spell:
            mult *= 1 + bon["spellDmgPct"] / 100.0
        if self.specials.get("execute"):
            mult *= 1 + self.specials["execute"] / 100.0 * F.EXECUTE_TIME_SHARE
        if not is_spell and element == "physical":
            # golpe da arma: parte elemental da arma + conversao dos imbuements
            conv = dict(bon.get("convert") or {})
            if self.attack_element_share and self.weapon_element:
                share = self.attack_element_share * 100.0
                conv[self.weapon_element] = conv.get(self.weapon_element, 0.0) + share
            if conv:
                total_conv = min(100.0, sum(conv.values()))
                dmg = base * (1 - total_conv / 100.0) * self._element_mult("physical", resist, pierce)
                for el, pct in conv.items():
                    dmg += base * pct / 100.0 * self._element_mult(el, resist, pierce)
                return dmg * mult
        return base * self._element_mult(element, resist, pierce) * mult

    def auto_attack(self):
        """(dano medio por golpe, elemento, intervalo s, mana por tiro). CONVENCAO para o golpe da arma."""
        bon = self.bonuses
        interval = F.AUTO_ATTACK_INTERVAL_MS / 1000.0 / (1 + bon["attackSpeedPct"] / 100.0)
        if self.wand:
            avg = (self.wand["min"] + self.wand["max"]) / 2.0
            return avg, self.wand["element"], interval, self.wand["mana_shot"]
        skill = self.skills.get(MAIN_SKILL[self.vocation], 0.0)
        lo, hi = F.auto_attack_range(self.level, skill, self.attack)
        avg = (lo + hi) / 2.0
        if self.vocation == "paladin":
            avg *= F.DISTANCE_HIT_CHANCE
        # Double Shot / Twin Palms: p % de um segundo golpe completo (cliente, desc)
        avg *= 1 + self.specials.get("precision", 0) / 100.0
        return avg, "physical", interval, 0

    def spell_base(self, spell):
        f = F.compile_formula(spell["formula_dano"] or spell["formula_cura"])
        sk = self.skills
        main = sk.get(MAIN_SKILL[self.vocation], 0.0)
        ml = sk.get("magic", 0.0)
        if spell.get("formula_dano"):
            ml += (self.bonuses.get("magicEl") or {}).get(F.spell_element(spell["palavras"]), 0.0)
        else:
            ml += (self.bonuses.get("magicEl") or {}).get("healing", 0.0)
        return f.average(self.level, ml, main, self.attack, self.shield_def, sk.get("shielding", 0.0))

    def heal_amount(self, spell):
        return self.spell_base(spell) * (1 + self.bonuses["spellHealPct"] / 100.0)


class Target:
    """A hunt de referencia: mistura ponderada dos monstros (pesos do cliente;
    sem pesos, iguais) e o boss da wave 10 com x3 HP e x1,5 dano (guia)."""

    def __init__(self, cat, hunt_id):
        hunt = cat.hunt_by_id[hunt_id]
        self.hunt = hunt
        self.hunt_id = hunt_id
        self.name = hunt["nome"]
        self.pack = int(hunt.get("max_vivos") or 1)
        self.spawn_ms = hunt.get("spawn_ms")
        monsters = hunt.get("monstros") or []
        weights = [(m.get("peso") if m.get("peso") is not None else 1.0) for m in monsters]
        total = sum(weights) or 1.0
        self.members = []
        for m, w in zip(monsters, weights):
            c = cat.creature_by_key.get(m["chave"])
            if c:
                self.members.append((c, w / total))
        self.hp = sum(c["hp"] * w for c, w in self.members)
        self.exp = sum((c.get("exp") or 0) * w for c, w in self.members)
        self.armor = sum((c.get("armadura") or 0) * w for c, w in self.members)
        self.resist = {el: sum(((c.get("resistencias") or {}).get(el, 0) or 0) * w for c, w in self.members)
                       for el in ELEMENTS}
        self.incoming = {el: 0.0 for el in ELEMENTS}   # dano/s por elemento, um monstro
        self.max_hit = {el: 0.0 for el in ELEMENTS}
        for c, w in self.members:
            inc, mx = creature_pressure(c)
            for el in ELEMENTS:
                self.incoming[el] += inc[el] * w
                self.max_hit[el] = max(self.max_hit[el], mx[el])
        boss = hunt.get("boss_da_wave_10")
        self.boss = cat.creature_by_key.get(boss["chave"]) if boss else None
        if self.boss:
            self.boss_hp = self.boss["hp"] * F.BOSS_HP_MULT
            self.boss_resist = {el: (self.boss.get("resistencias") or {}).get(el, 0) or 0 for el in ELEMENTS}
            inc, mx = creature_pressure(self.boss)
            self.boss_incoming = {el: inc[el] * F.BOSS_DMG_MULT for el in ELEMENTS}
            self.boss_max_hit = {el: mx[el] * F.BOSS_DMG_MULT for el in ELEMENTS}
        else:
            self.boss_hp = 0.0
            self.boss_resist = dict(self.resist)
            self.boss_incoming = dict(self.incoming)
            self.boss_max_hit = dict(self.max_hit)

    def dominant_element(self):
        return max(ELEMENTS, key=lambda el: self.incoming[el])


def creature_pressure(creature):
    """Dano/s e maior golpe por elemento de UM monstro, pela conta do cliente
    (K0e): dano base medio / 2 s + habilidades media x chance / intervalo."""
    inc = {el: 0.0 for el in ELEMENTS}
    mx = {el: 0.0 for el in ELEMENTS}
    lo, hi = creature.get("dano_base") or [0, 0]
    inc["physical"] += (lo + hi) / 2.0 / (F.ATTACK_GCD_MS / 1000.0)
    mx["physical"] = max(mx["physical"], float(hi or 0))
    for ab in creature.get("habilidades") or []:
        el = ab.get("element")
        if el not in inc:
            continue  # "healing" e o que o monstro se cura; nao e dano
        avg = ((ab.get("min") or 0) + (ab.get("max") or 0)) / 2.0
        chance = min(100.0, max(0.0, float(ab.get("chance") if ab.get("chance") is not None else 100))) / 100.0
        interval = max(250.0, float(ab.get("interval") or 2000))
        inc[el] += avg * chance * 1000.0 / interval
        mx[el] = max(mx[el], float(ab.get("max") or 0))
    return inc, mx


# --- mitigacao -------------------------------------------------------------------------
def mitigation(profile, target, boss=False):
    """{el: fraccao do dano que passa} para o personagem contra este alvo."""
    bon = profile.bonuses
    armor_pct = F.armor_reduction_pct(profile.armor)
    defense = profile.defense + profile.specials.get("battle_instinct", 0) * min(target.pack, 3)
    block = F.block_pct(defense, profile.skills.get("shielding", 0.0), profile.has_shield)
    dodge = profile.specials.get("dodge", 0)
    avatar = 3.0 * profile.avatar_uptime()  # «-3% de dano recebido» enquanto em avatar
    out = {}
    for el in ELEMENTS:
        parts = [bon["absorbPct"].get(el, 0.0)]
        if el == "physical":
            parts += [armor_pct, block]
        if dodge:
            parts.append(dodge)
        if avatar:
            parts.append(avatar)
        out[el] = 1 - F.stack_pct(parts) / 100.0
    return out


def pressure(profile, target, boss=False, attackers=1):
    """Dano/s que entra depois da mitigacao, e o maior golpe mitigado."""
    mit = mitigation(profile, target, boss)
    inc = target.boss_incoming if boss else target.incoming
    mx = target.boss_max_hit if boss else target.max_hit
    dps_in = sum(inc[el] * mit[el] for el in ELEMENTS) * attackers
    max_hit = max(mx[el] * mit[el] for el in ELEMENTS)
    return dps_in, max_hit, mit


# --- rotacao e simulacao ------------------------------------------------------------------
class RotationSlot:
    __slots__ = ("spell", "min_mobs")

    def __init__(self, spell, min_mobs=1):
        self.spell = spell
        self.min_mobs = min_mobs


def attack_spells(profile, runes=False):
    out = []
    for s in profile.spells:
        if s["tipo"] not in ("strike", "area") or not s.get("formula_dano"):
            continue
        if s.get("custo_gold") and not runes:
            continue
        out.append(s)
    return out


def heal_spells(profile, friend=False):
    return [s for s in profile.spells if s["tipo"] == "heal" and s.get("formula_cura")
            and (bool(s.get("alvo_da_cura")) == friend)]


def spell_targets(spell, pack, boss):
    if boss or spell["tipo"] != "area":
        return 1
    return F.area_targets(spell.get("raio"), pack)


def spell_damage(profile, spell, target, boss):
    """Dano medio de um lancamento contra a mistura da hunt (ou o boss), ja com
    o numero de alvos de uma area e a cadeia (chain) quando a ha."""
    base = profile.spell_base(spell)
    element = F.spell_element(spell["palavras"])
    resist = target.boss_resist if boss else target.resist
    one = profile.hit_vs(base, element, resist, is_spell=True)
    n = spell_targets(spell, target.pack, boss)
    chain = spell.get("cadeia")
    if chain and not boss:
        n = max(n, min(target.pack, int(chain.get("targets") or 1)))
    return one * n


def auto_damage(profile, target, boss):
    avg, element, interval, mana_shot = profile.auto_attack()
    resist = target.boss_resist if boss else target.resist
    one = profile.hit_vs(avg, element, resist, is_spell=False)
    n = 1.0
    if not boss:
        slash = profile.specials.get("slash", 0)
        if slash and profile.weapon_type in ("sword", "axe", "club", "fist"):
            n += slash / 100.0 * min(F.CLEAVE_ADJACENT, max(0, target.pack - 1))
        chain = profile.specials.get("chain", 0)
        if chain and profile.weapon_type == "wand":
            n += 0.6 * min(chain, max(0, target.pack - 1))
    return one * n, interval, mana_shot


class SimResult:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def as_dict(self):
        return dict(self.__dict__)


def simulate(profile, target, rotation, boss=False, seconds=60, heal=None, potions=True, attackers=1):
    """60 s de combate na grelha de 1 s. `rotation` e lista de RotationSlot por
    prioridade. Devolve DPS, casts, mana, cura, pocoes, gold — valores esperados."""
    cat_pack = target.pack
    dps_in, max_hit, _ = pressure(profile, target, boss, attackers)
    bon = profile.bonuses
    auto_dmg, auto_interval, mana_shot = auto_damage(profile, target, boss)
    auto_per_s = auto_dmg / auto_interval
    auto_mana_per_s = mana_shot / auto_interval
    hp = hp_max = profile.hp_max
    mana = mana_max = profile.mana_max
    casts = {}
    cooldown_until = {}
    gcd_attack = 0
    gcd_heal = 0
    potion_until = 0
    dealt = 0.0
    healed = 0.0
    hp_potions = mana_potions = 0
    gold = 0.0
    mana_spent = 0.0
    mana_min = mana
    hp_min = hp
    empty_at = None
    death_at = None
    slots = [(slot, spell_damage(profile, slot.spell, target, boss)) for slot in rotation
             if slot.spell.get("formula_dano")]
    heal_spell = heal
    heal_amount = profile.heal_amount(heal_spell) if heal_spell else 0.0
    life_leech = bon["lifeLeech"] / 100.0 * F.LEECH_EFFECTIVE_FACTOR
    mana_leech = bon["manaLeech"] / 100.0
    hp_regen = bon["hpRegenFlat"]
    mp_regen = bon["mpRegenFlat"]
    hp_pot = profile.hp_potion
    mana_pot = profile.mana_potion
    for t in range(int(seconds)):
        # o que entra e o que regenera neste segundo
        hp -= dps_in
        hp += hp_regen
        mana += mp_regen
        # ataque automatico (taxa continua)
        dealt_now = auto_per_s
        if mana_shot:
            if mana >= auto_mana_per_s:
                mana -= auto_mana_per_s
            else:
                dealt_now = 0.0
        # feiticos de ataque, por prioridade, um por cooldown de grupo
        if t >= gcd_attack:
            for slot, dmg in slots:
                sp = slot.spell
                if sp["tipo"] == "area" and not boss and cat_pack < slot.min_mobs:
                    continue
                if cooldown_until.get(sp["palavras"], 0) > t or mana < sp["mana"]:
                    continue
                mana -= sp["mana"]
                mana_spent += sp["mana"]
                cooldown_until[sp["palavras"]] = t + max(1, int(round(sp["cooldown_ms"] / 1000.0)))
                gcd_attack = t + int(round(F.ATTACK_GCD_MS / 1000.0))
                casts[sp["palavras"]] = casts.get(sp["palavras"], 0) + 1
                dealt_now += dmg
                if sp.get("custo_gold"):
                    gold += sp["custo_gold"]
                break
        dealt += dealt_now
        hp += dealt_now * life_leech
        mana += dealt_now * mana_leech
        # cura propria
        if heal_spell and t >= gcd_heal and hp < hp_max * profile.heal_at_pct / 100.0 \
                and cooldown_until.get(heal_spell["palavras"], 0) <= t and mana >= heal_spell["mana"]:
            mana -= heal_spell["mana"]
            mana_spent += heal_spell["mana"]
            cooldown_until[heal_spell["palavras"]] = t + max(1, int(round(heal_spell["cooldown_ms"] / 1000.0)))
            gcd_heal = t + int(round(F.HEAL_GCD_MS / 1000.0))
            casts[heal_spell["palavras"]] = casts.get(heal_spell["palavras"], 0) + 1
            gain = min(heal_amount, max(0.0, hp_max - hp))
            healed += gain
            hp += gain
        # pocoes (exhaust partilhado de 1 s)
        if potions and t >= potion_until:
            if hp_pot and hp < hp_max * profile.potion_hp_pct / 100.0:
                gain = min(hp_pot.get("heal") or 0, max(0.0, hp_max - hp))
                hp += gain
                healed += gain
                mana += hp_pot.get("mana") or 0
                gold += hp_pot["cost"]
                hp_potions += 1
                potion_until = t + 1
            elif mana_pot and mana < mana_max * profile.potion_mana_pct / 100.0:
                mana = min(mana_max, mana + (mana_pot.get("mana") or 0))
                gold += mana_pot["cost"]
                mana_potions += 1
                potion_until = t + 1
        hp = min(hp, hp_max)
        mana = min(mana, mana_max)
        mana_min = min(mana_min, mana)
        hp_min = min(hp_min, hp)
        if mana <= 0 and empty_at is None:
            empty_at = t
        if hp <= 0 and death_at is None:
            death_at = t
    income = mp_regen + (dealt / seconds) * mana_leech
    return SimResult(
        seconds=seconds, boss=boss, dps=dealt / seconds, dealt=dealt, casts=casts,
        healed=healed, hps=healed / seconds, hp_min=hp_min, hp_end=hp, hp_max=hp_max, death_at=death_at,
        mana_end=mana, mana_min=mana_min, mana_max=mana_max, mana_spent=mana_spent,
        mana_demand=mana_spent / seconds, mana_income=income, mana_empty_at=empty_at,
        hp_potions=hp_potions, mana_potions=mana_potions, gold=gold, gold_per_hour=gold * 3600.0 / seconds,
        pressure=dps_in, max_hit=max_hit, auto_dps=auto_per_s,
    )


def cycle_dps(dps_pack, dps_boss, target):
    """DPS efectivo num ciclo de 57 normais + 1 boss (x3 HP): HP total do ciclo
    a dividir pelo tempo que leva a limpa-lo com cada DPS."""
    normals = F.CYCLE_NORMAL_KILLS * target.hp
    if dps_pack <= 0:
        return 0.0
    time = normals / dps_pack
    if target.boss_hp > 0:
        if dps_boss <= 0:
            return 0.0
        time += target.boss_hp / dps_boss
    return (normals + target.boss_hp) / time if time > 0 else 0.0


def sustained_hps(profile, seconds=60, friend=False):
    """A melhor cura por segundo que a mana aguenta em 60 s (cooldown e mana
    limitam; regen base desconhecida conta a 0). Devolve (hps, feitico)."""
    best = (0.0, None)
    income = profile.bonuses["mpRegenFlat"] * seconds
    for s in heal_spells(profile, friend):
        amount = profile.heal_amount(s)
        cd = max(F.HEAL_GCD_MS, s["cooldown_ms"]) / 1000.0
        by_cd = seconds / cd
        by_mana = (profile.mana_max + income) / s["mana"] if s["mana"] > 0 else by_cd
        hps = min(by_cd, by_mana) * amount / seconds
        if hps > best[0]:
            best = (hps, s)
    return best


def best_heal(profile):
    """A cura propria mais forte por lancamento (o que o Helper deve ter seleccionado)."""
    heals = heal_spells(profile)
    if not heals:
        return None
    return max(heals, key=lambda s: profile.heal_amount(s))
