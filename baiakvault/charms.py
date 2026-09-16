"""Charms por hunt: que charm por em que criatura. Puro — catalogo + estado do
dono + hunt entram; a atribuicao com pontuacao, justificacao e as mudancas
saem. Sem BD, sem simulador, sem rede.

O contrato e `docs/charms.md` (as regras do jogo lidas no cliente a 16/09/2026,
cada uma com fonte; o que la esta ⚠ trata-se aqui pelo lado conservador e
diz-se na pagina). Em resumo:

- um charm esta numa so criatura; uma criatura leva um maior e um menor, nunca
  dois da mesma categoria; ha um limite de criaturas com charm (2 / 6 VIP /
  25 com a Expansion); um maior exige o bestiario da criatura fechado;
- mover um charm custa 1 000 gold x nivel (x0,75 com a Expansion);
- os elementais fazem min(2 x nivel, 5 % do HP do alvo) e assume-se que
  respeitam a resistencia (⚠) -> criatura gorda, fraca ao elemento e muito
  batida; Carnage em packs densos; Overpower/Overflux pelo HP/mana dele;
  Dodge/Parry/Numb/Adrenaline/Cripple/Void Inversion na criatura que mais
  dano faz; Low Blow/Savage Blow/Vampiric/Void's Call so com o requisito do
  equipamento conhecido e > 0; Gut no melhor loot, Scavenge no mais ouro;
  Bless na criatura que aparece em mais hunts; Fatal Hold na mais batida.

Nunca se atribui um charm que ele nao tem; onde falta um dado a criatura nao
pontua e sai «?».
"""
from . import formulas as F
from . import sim

ELEMENTS = ("physical", "fire", "earth", "ice", "energy", "death", "holy")
ELEMENT_LABEL = {"physical": "fisico", "fire": "fogo", "earth": "terra", "ice": "gelo",
                 "energy": "energia", "death": "morte", "holy": "sagrado"}
COINS = ("gold coin", "platinum coin", "crystal coin")
MAX_TIER = 3
# limites de criaturas com charm (texto do cliente e da loja, 16/09/2026)
LIMIT_BASE, LIMIT_VIP, LIMIT_EXPANSION = 2, 6, 25
REMOVE_GOLD_PER_LEVEL = 1000          # cliente `Zbe`
EXPANSION_DISCOUNT = 0.75             # cliente `SK`
RESET_BASE_GOLD, RESET_PER_LEVEL_GOLD, RESET_LEVEL_FROM = 1_000_000, 110_000, 100  # cliente `e3e`
ECHOES_PER_TIER = (50, 100, 200)      # cliente `Jbe`: 25t^2+25t+50
PACK_NEIGHBOURS = 4                   # Carnage estoira nas 4 casas coladas

# a que se agarra cada charm (ver o docstring); «exposure» = HP abatido por ciclo
ELEMENT_OF = {"wound": "physical", "enflame": "fire", "poison": "earth", "freeze": "ice",
              "zap": "energy", "curse": "death", "divine_wrath": "holy"}
RULE_OF = {
    "carnage": "carnage", "overpower": "overpower", "overflux": "overflux",
    "dodge": "taken", "parry": "taken", "numb": "taken", "adrenaline_burst": "taken",
    "cripple": "taken", "void_inversion": "taken",
    "low_blow": "exposure", "savage_blow": "exposure", "fatal_hold": "exposure",
    "vampiric_embrace": "exposure", "voids_call": "exposure",
    "gut": "loot", "scavenge": "gold", "bless": "bless",
}
# o que o equipamento tem de dar para o charm valer (texto do cliente)
REQUIRES = {"low_blow": "crit_chance", "savage_blow": "crit_chance",
            "vampiric_embrace": "life_leech", "voids_call": "mana_leech",
            "void_inversion": "mana_shield"}
REQUIRE_LABEL = {"crit_chance": "critico", "life_leech": "roubo de vida", "mana_leech": "roubo de mana",
                 "mana_shield": "escudo de mana"}


class CharmsError(Exception):
    pass


# --- o dono -------------------------------------------------------------------------------
def owner(level, charms=None, vip=None, slot_limit=None, expansion=None, hp_max=None, mana_max=None,
          crit_chance=None, life_leech=None, mana_leech=None, mana_shield=None, bestiary=None,
          hp_source=None, stats_source=None, name=None):
    """O estado de quem usa os charms, tal como o motor o quer. `charms` e uma
    lista de {charm_key, tier, assigned_creature_key} (o que ele tem); `None`
    = todos os 24 ao tier 3 (o tecto de uma build generica). O que nao se sabe
    fica `None` e nunca vira zero."""
    return {"name": name, "level": level, "charms": charms, "vip": vip, "slot_limit": slot_limit,
            "expansion": expansion, "hp_max": hp_max, "mana_max": mana_max, "crit_chance": crit_chance,
            "life_leech": life_leech, "mana_leech": mana_leech, "mana_shield": mana_shield,
            "bestiary": bestiary, "hp_source": hp_source, "stats_source": stats_source}


def owner_from_state(state, profile=None, stats_known=False):
    """Do estado do `advisor` (e do `sim.Profile` ja construido com o que ele
    tem) para o dono. `stats_known` diz se ha equipamento registado: sem ele,
    critico e roubo sao «?» (nao se recomenda o que depende deles)."""
    points = state.get("charm_points") or {}
    bon = profile.bonuses if profile is not None else {}
    shield = None
    if profile is not None:
        shield = any(s.get("palavras") == "utamo vita" for s in profile.spells)
    return owner(
        name=state.get("name"), level=state.get("level"), charms=state.get("charms") or [],
        vip=state.get("vip"), slot_limit=points.get("slot_limit"), expansion=points.get("expansion"),
        hp_max=getattr(profile, "hp_max", None), mana_max=getattr(profile, "mana_max", None),
        hp_source="simulador (nivel + arvore registada)" if profile is not None else None,
        crit_chance=bon.get("critChance") if stats_known else None,
        life_leech=bon.get("lifeLeech") if stats_known else None,
        mana_leech=bon.get("manaLeech") if stats_known else None,
        mana_shield=shield, bestiary=state.get("bestiary") or {},
        stats_source="simulador com o equipamento registado" if stats_known else None)


def owner_from_plan(plan):
    """O tecto de uma build generica: todos os charms ao tier 3, estatisticas da
    build recomendada, bestiario desconhecido."""
    prof = plan["profile"]
    bon = prof.bonuses
    return owner(level=plan["level"], charms=None, vip=None, slot_limit=None,
                 hp_max=prof.hp_max, mana_max=prof.mana_max, hp_source="build recomendada",
                 crit_chance=bon.get("critChance"), life_leech=bon.get("lifeLeech"), mana_leech=bon.get("manaLeech"),
                 mana_shield=bool(plan.get("helper", {}).get("magic_shield")), bestiary=None,
                 stats_source="build recomendada")


def slot_limit(own):
    """(limite, como se chegou la). Registado > VIP > minimo — o conservador."""
    if own.get("slot_limit"):
        return int(own["slot_limit"]), "registado"
    if own.get("expansion"):
        return LIMIT_EXPANSION, "Charm Expansion registada"
    if own.get("vip"):
        return LIMIT_VIP, "VIP (6; se tiveres a Charm Expansion regista o limite)"
    if own.get("vip") is None:
        return LIMIT_BASE, "VIP desconhecido: assumido o minimo (2)"
    return LIMIT_BASE, "sem VIP (2)"


def remove_cost(level, expansion=False):
    """Gold para tirar um charm de uma criatura (cliente `Zbe`). `None` sem nivel."""
    if not level:
        return None
    gold = max(1, int(level)) * REMOVE_GOLD_PER_LEVEL
    return int(gold * EXPANSION_DISCOUNT) if expansion else gold


def reset_cost(level, expansion=False):
    if not level:
        return None
    lv = max(1, int(level))
    gold = RESET_BASE_GOLD + (lv * RESET_PER_LEVEL_GOLD if lv > RESET_LEVEL_FROM else 0)
    return int(gold * EXPANSION_DISCOUNT) if expansion else gold


def echoes_for_upgrade(current_tier):
    """Echoes «de troco» ao subir um maior do tier actual (cliente `Jbe`)."""
    t = max(0, min(MAX_TIER - 1, int(current_tier)))
    return ECHOES_PER_TIER[t]


# --- a hunt vista pelos charms -----------------------------------------------------------------
def _resistances(cat, creature):
    """(resistencias {el: %}, fonte) — bestiario primeiro; depois a tabela de
    combate do cliente (`bosses_de_sala`, marcada ⚠); senao (None, None)."""
    res = creature.get("resistencias")
    if res:
        return {el: (res.get(el) or 0) for el in ELEMENTS}, "bestiario"
    alt = _combat_table(cat).get((creature.get("nome") or "").lower())
    if alt and alt.get("resistencias") is not None:
        return {el: (alt["resistencias"].get(el) or 0) for el in ELEMENTS}, "tabela de combate ⚠"
    return None, None


_COMBAT_CACHE = {}


def _combat_table(cat):
    key = id(cat)
    if key not in _COMBAT_CACHE:
        _COMBAT_CACHE[key] = {b["nome"].lower(): b for b in cat.room_bosses if b.get("nome")}
    return _COMBAT_CACHE[key]


def _dps(creature):
    """Dano/s de um monstro pela conta do cliente (a mesma do simulador)."""
    inc, _ = sim.creature_pressure(creature)
    return sum(inc.values())


def _loot_value(creature):
    """(gold esperado por kill em itens, em moedas) pela conta do jogo."""
    items = coins = 0.0
    for d in creature.get("loot") or []:
        chance, price = d.get("chance_por_100k"), d.get("preco_npc")
        if chance is None or price is None:
            continue
        value = chance / 100000.0 * (1 + (d.get("max") or 1)) / 2.0 * price
        if d.get("item") in COINS:
            coins += value
        else:
            items += value
    return items, coins


def hunt_view(cat, hunt_id):
    """As criaturas da hunt com o que os charms precisam: peso, kills e HP
    abatido por ciclo (exposicao), dano que fazem, resistencias (com fonte),
    loot. Notas da hunt (pesos em falta, resistencias da 2.a tabela)."""
    hunt = cat.hunt_by_id.get(hunt_id)
    if not hunt:
        raise CharmsError("hunt desconhecida: %r" % hunt_id)
    monsters = hunt.get("monstros") or []
    weights_known = any(m.get("peso") is not None for m in monsters)
    weights = [(m.get("peso") if m.get("peso") is not None else 1.0) for m in monsters]
    total_w = sum(weights) or 1.0
    boss_key = (hunt.get("boss_da_wave_10") or {}).get("chave")
    notes = []
    if not weights_known:
        notes.append("pesos de spawn nao publicados: as criaturas contam por igual")
    creatures = []
    fallback = []
    for m, w in zip(monsters, weights):
        c = cat.creature_by_key.get(m["chave"])
        if not c:
            continue
        share = w / total_w
        kills = F.CYCLE_NORMAL_KILLS * share
        hp = c.get("hp")
        is_boss = c["chave"] == boss_key
        exposure = None
        if hp is not None:
            exposure = kills * hp + (F.BOSS_HP_MULT * hp if is_boss else 0.0)
        res, res_source = _resistances(cat, c)
        if res_source and res_source.startswith("tabela"):
            fallback.append(c["nome"])
        dps = _dps(c)
        taken = None
        if exposure is not None:
            # tempo a apanhar de cada uma ∝ HP dela a abater; o boss bate x1,5
            taken = kills * hp * dps + (F.BOSS_HP_MULT * hp * dps * F.BOSS_DMG_MULT if is_boss else 0.0)
        items, coins = _loot_value(c)
        creatures.append({
            "key": c["chave"], "name": c["nome"], "hp": hp, "exp": c.get("exp"), "weight": share,
            "kills": kills, "is_boss": is_boss, "exposure": exposure, "dps": dps, "taken": taken,
            "resist": res, "resist_source": res_source, "loot_items": items * kills, "loot_coins": coins * kills,
            "loot_known": c.get("loot") is not None,
            "meta_kills": c.get("meta_kills"), "hunts": len([hid for hid in (c.get("aparece_em") or []) if hid in cat.hunt_by_id]),
        })
    if fallback:
        notes.append("resistencias de %s vem da 2.a tabela de combate do cliente (o bestiario nao as declara) ⚠"
                     % ", ".join(fallback))
    total_exposure = sum(c["exposure"] or 0.0 for c in creatures) or 1.0
    total_taken = sum(c["taken"] or 0.0 for c in creatures) or 1.0
    for c in creatures:
        c["exposure_share"] = (c["exposure"] / total_exposure) if c["exposure"] is not None else None
        c["taken_share"] = (c["taken"] / total_taken) if c["taken"] is not None else None
    return {"hunt": hunt, "hunt_id": hunt_id, "creatures": creatures, "pack": int(hunt.get("max_vivos") or 1),
            "weights_known": weights_known, "notes": notes}


# --- pontuar um charm numa criatura ---------------------------------------------------------------
def _pct(x):
    return ("%.0f%%" % (x * 100.0)) if x is not None else "?"


def _n(x):
    return "{:,}".format(int(round(x))).replace(",", ".") if x is not None else "?"


def score_pair(charm, tier, own, view, c):
    """(pontuacao ou None, porque, avisos) de por `charm` (ao `tier`) em `c`.
    `None` = nao se sabe o suficiente para pontuar (sai «?»)."""
    key = charm["key"]
    level = own.get("level")
    chance = (charm.get("chance") or [0, 0, 0])[max(0, min(MAX_TIER, tier) - 1)]
    warns = []
    if key in ELEMENT_OF:
        el = ELEMENT_OF[key]
        if c["exposure_share"] is None or level is None:
            return None, "HP da criatura ou nivel desconhecidos", warns
        if c["resist"] is None:
            return None, "resistencia a %s desconhecida" % ELEMENT_LABEL[el], warns
        r = c["resist"].get(el, 0)
        cap_level, cap_hp = 2.0 * level, 0.05 * c["hp"]
        per_proc = min(cap_level, cap_hp) * F.resist_factor(r)
        if c["is_boss"]:
            # no boss (x3 HP) o tecto dos 5 % sobe; pesa pela parte do boss na exposicao
            boss_part = F.BOSS_HP_MULT * c["hp"] / c["exposure"]
            per_proc = per_proc * (1 - boss_part) + min(cap_level, 0.05 * F.BOSS_HP_MULT * c["hp"]) * F.resist_factor(r) * boss_part
        score = c["exposure_share"] * per_proc * chance / 100.0
        if c["resist_source"] and c["resist_source"].startswith("tabela"):
            warns.append("resistencia da 2.a tabela do cliente ⚠")
        why = "%s dos golpes da hunt; %s%% de resistencia a %s; dano por proc ~%s (tecto: 2x nivel = %s, 5%% do HP = %s)" % (
            _pct(c["exposure_share"]), r, ELEMENT_LABEL[el], _n(per_proc), _n(cap_level), _n(cap_hp))
        return score, why, warns
    rule = RULE_OF.get(key)
    if rule == "carnage":
        if c["hp"] is None or level is None:
            return None, "HP da criatura ou nivel desconhecidos", warns
        burst = min(0.15 * c["hp"], 6.0 * level)
        neighbours = min(PACK_NEIGHBOURS, max(0, view["pack"] - 1))
        score = c["kills"] * burst * neighbours * chance / 100.0
        why = "%s kills por ciclo; estoiro ~%s por kill (15%% do HP = %s, 6x nivel = %s) em ate %d vizinhos (pack de %d)" % (
            _n(c["kills"]), _n(burst), _n(0.15 * c["hp"]), _n(6.0 * level), neighbours, view["pack"])
        return score, why, warns
    if rule in ("overpower", "overflux"):
        mine = own.get("hp_max") if rule == "overpower" else own.get("mana_max")
        frac = 0.05 if rule == "overpower" else 0.025
        label = "HP" if rule == "overpower" else "mana"
        if c["exposure_share"] is None:
            return None, "HP da criatura desconhecido", warns
        if mine is None:
            return None, "%s maximo do dono desconhecido (na pagina do personagem usa-se o teu)" % label, warns
        per_proc = min(0.08 * c["hp"], frac * mine)
        score = c["exposure_share"] * per_proc * chance / 100.0
        why = "%s dos golpes; dano por proc ~%s (8%% do HP do alvo = %s, %s%% do teu %s = %s%s)" % (
            _pct(c["exposure_share"]), _n(per_proc), _n(0.08 * c["hp"]), ("%g" % (frac * 100)).replace(".", ","), label,
            _n(frac * mine), (", " + own["hp_source"]) if own.get("hp_source") else "")
        return score, why, warns
    if rule == "taken":
        if c["taken_share"] is None:
            return None, "dano da criatura desconhecido", warns
        score = c["taken_share"] * chance / 100.0
        why = "%s do dano que apanhas nesta hunt vem dela (%s/s por bicho%s)" % (
            _pct(c["taken_share"]), _n(c["dps"]), ", boss x1,5" if c["is_boss"] else "")
        if key == "adrenaline_burst":
            why += "; regra conservadora: acelerar quando o que mais bate te acerta"
        if key == "cripple":
            why += "; abrandar o que mais bate (regra conservadora, o cliente nao diz mais)"
        return score, why, warns
    if rule == "exposure":
        if c["exposure_share"] is None:
            return None, "HP da criatura desconhecido", warns
        score = c["exposure_share"] * chance / 100.0
        why = "%s do dano que fazes nesta hunt vai para ela" % _pct(c["exposure_share"])
        if key == "fatal_hold":
            why += " (o bonus so conta nos ultimos 25%% do HP: %s por bicho)" % _n(0.25 * (c["hp"] or 0))
        return score, why, warns
    if rule in ("loot", "gold") and not c.get("loot_known", True):
        return None, "tabela de loot desconhecida", warns
    if rule == "loot":
        score = c["loot_items"] * chance / 100.0
        why = "loot em itens ~%s gold por ciclo (%s kills), pela tabela de loot do cliente" % (_n(c["loot_items"]), _n(c["kills"]))
        return score, why, warns
    if rule == "gold":
        score = c["loot_coins"] * chance / 100.0
        why = "moedas ~%s gold por ciclo (%s kills), pela tabela de loot do cliente" % (_n(c["loot_coins"]), _n(c["kills"]))
        return score, why, warns
    if rule == "bless":
        score = c["hunts"] + c["weight"] / 10.0
        why = "aparece em %d hunt%s do jogo: e onde a multa se poupa mais vezes (regra conservadora)" % (c["hunts"], "" if c["hunts"] == 1 else "s")
        return score, why, warns
    return None, "sem regra para este charm", warns


# --- a atribuicao ----------------------------------------------------------------------------------
def _owned(cat, own):
    """{charm_key: (tier, criatura actual ou None)} — todos ao tier 3 quando `charms` e None."""
    if own.get("charms") is None:
        return {c["key"]: (MAX_TIER, None) for c in cat.charms}
    out = {}
    for c in own["charms"]:
        tier = c.get("tier") or 0
        if tier >= 1 and cat.has_charm(c["charm_key"]):
            out[c["charm_key"]] = (min(MAX_TIER, tier), c.get("assigned_creature_key"))
    return out


def _requirement(own, key):
    """(ok, texto) para os charms que so valem com algo no equipamento.
    `ok` e None quando nao se sabe."""
    req = REQUIRES.get(key)
    if not req:
        return True, None
    value = own.get(req)
    label = REQUIRE_LABEL[req]
    if own.get("assume_requirements"):
        return True, "tecto: assume %s no equipamento" % label
    if value is None:
        return None, "so vale com %s no equipamento e nao esta registado (%s)" % (label, "regista o equipamento")
    if not value:
        return False, "so vale com %s no equipamento e o teu nao da (%s)" % (label, own.get("stats_source") or "registado")
    if req == "mana_shield":
        return True, "tens utamo vita"
    return True, "%s %s%% (%s)" % (label, ("%g" % value).replace(".", ","), own.get("stats_source") or "registado")


def _bestiary_ok(own, c, category="major"):
    """Um maior exige o bestiario fechado; um menor basta ter matado 1 (cliente
    `d3e`). (ok, nota): None = nao registado."""
    best = own.get("bestiary")
    if best is None:
        return None, None   # tecto de uma build: nao ha bestiario de ninguem para exigir
    if c["key"] not in best:
        if category != "major":
            return None, None   # kills nao registados: 1 kill e o normal numa hunt, nao vale aviso
        return None, "exige o bestiario de %s fechado (%s kills) — kills nao registados ⚠" % (c["name"], _n(c["meta_kills"]))
    kills = best[c["key"]]
    if category != "major":
        if kills < 1:
            return False, "0 kills registados de %s: um menor exige ter matado pelo menos 1" % c["name"]
        return True, None
    if c["meta_kills"] is not None and kills < c["meta_kills"]:
        return False, "bestiario de %s por fechar (%s/%s): um maior nao se atribui" % (c["name"], _n(kills), _n(c["meta_kills"]))
    return True, None


def recommend(cat, own, hunt_id):
    """A atribuicao recomendada para esta hunt com os charms que ele tem.

    Devolve `{"hunt_id", "limit", "limit_source", "assignments", "left_out",
    "changes", "notes", "creatures", "used"}`. `assignments` vem por ordem de
    categoria (maiores primeiro) e depois de pontuacao relativa."""
    view = hunt_view(cat, hunt_id)
    owned = _owned(cat, own)
    limit, limit_source = slot_limit(own)
    notes = list(view["notes"])
    if own.get("charms") is None:
        notes.append("tecto: todos os 24 charms ao tier 3, sem limite de criaturas — e o maximo, nao o que alguem tem")
        limit = None

    # 1) pontuar cada charm em cada criatura
    table = {}
    left_out = []
    for key, (tier, current) in owned.items():
        charm = cat.charm_by_key[key]
        ok, req_text = _requirement(own, key)
        if ok is None:
            left_out.append({"charm_key": key, "name": charm["name"], "tier": tier, "reason": req_text, "kind": "unknown"})
            continue
        if ok is False:
            left_out.append({"charm_key": key, "name": charm["name"], "tier": tier, "reason": req_text, "kind": "useless"})
            continue
        options = []
        unknown_pairs = []
        useless_pairs = []
        for c in view["creatures"]:
            score, why, warns = score_pair(charm, tier, own, view, c)
            if score is None:
                unknown_pairs.append((c["name"], why))
                continue
            if score <= 0:
                # pontua zero (ex.: Poison numa criatura imune a terra): nao e uma
                # opcao — se entrasse, o arrependimento «1 - 0» punha-o a decidir
                # primeiro e a ocupar a melhor criatura sem fazer nada (16/09/2026)
                useless_pairs.append((c["name"], why))
                continue
            b_ok, b_note = _bestiary_ok(own, c, charm["category"])
            if b_ok is False:
                unknown_pairs.append((None, b_note))
                continue
            if b_note:
                warns = warns + [b_note]
            if req_text:
                why = why + "; " + req_text
            options.append({"creature": c, "score": score, "why": why, "warns": warns})
        # a mesma falta em todas as criaturas diz-se uma vez, sem os nomes
        reasons = {why for _, why in unknown_pairs}
        if len(reasons) == 1 and len(unknown_pairs) == len(view["creatures"]):
            unknown_reasons = list(reasons)
        else:
            unknown_reasons = [("%s: %s" % (name, why)) if name else why for name, why in unknown_pairs]
        if not options:
            if useless_pairs and not unknown_pairs:
                left_out.append({"charm_key": key, "name": charm["name"], "tier": tier, "kind": "useless",
                                 "reason": "nao faz nada nesta hunt: " + "; ".join(
                                     "%s (%s)" % (name, why) for name, why in useless_pairs[:3])})
            else:
                left_out.append({"charm_key": key, "name": charm["name"], "tier": tier, "kind": "unknown",
                                 "reason": "sem criatura pontuavel: " + "; ".join(unknown_reasons[:3])})
            continue
        options.sort(key=lambda o: (-o["score"], o["creature"]["name"]))
        best = options[0]["score"]
        for o in options:
            o["rel"] = o["score"] / best
        table[key] = {"charm": charm, "tier": tier, "current": current, "options": options,
                      "unknown": unknown_reasons}

    # 2) guloso pelo arrependimento: quem mais perde se nao levar a 1.a escolha decide primeiro
    def regret(entry):
        opts = entry["options"]
        if len(opts) == 1:
            return 1.0
        return 1.0 - opts[1]["rel"]

    order = sorted(table.values(), key=lambda e: (e["charm"]["category"] != "major", -regret(e), e["charm"]["key"]))
    used_by_category = {}   # (creature_key, category) -> charm_key
    used_creatures = []
    assignments = []
    cat_label = {"major": "maior", "minor": "menor"}
    for entry in order:
        charm = entry["charm"]
        placed = False
        blocked = []
        for o in entry["options"]:
            ck = o["creature"]["key"]
            taken_by = used_by_category.get((ck, charm["category"]))
            if taken_by:
                blocked.append("%s ja leva %s (um %s por criatura)" % (
                    o["creature"]["name"], cat.charm_by_key[taken_by]["name"], cat_label[charm["category"]]))
                continue
            if limit is not None and ck not in used_creatures and len(used_creatures) >= limit:
                blocked.append("%s ficaria fora do limite de %d criaturas com charm (%s)" % (o["creature"]["name"], limit, limit_source))
                continue
            used_by_category[(ck, charm["category"])] = charm["key"]
            if ck not in used_creatures:
                used_creatures.append(ck)
            why = o["why"]
            if o is not entry["options"][0]:
                why += "; %s seria melhor mas ja leva outro %s" % (
                    entry["options"][0]["creature"]["name"], "maior" if charm["category"] == "major" else "menor")
            assignments.append({
                "charm_key": charm["key"], "name": charm["name"], "category": charm["category"], "kind": charm["kind"],
                "tier": entry["tier"], "chance": (charm.get("chance") or [None] * 3)[entry["tier"] - 1],
                "creature_key": ck, "creature_name": o["creature"]["name"], "score": o["score"], "rel": o["rel"],
                "why": why, "warns": o["warns"], "current_creature_key": entry["current"],
            })
            placed = True
            break
        if not placed:
            if len(blocked) == len(view["creatures"]) and all("ja leva" in b for b in blocked) and not entry["unknown"]:
                reason = "sem criatura livre: as %d criaturas da hunt ja levam um %s cada" % (
                    len(view["creatures"]), cat_label[charm["category"]])
            else:
                reason = "sem criatura livre: " + "; ".join(blocked + entry["unknown"])
            left_out.append({"charm_key": charm["key"], "name": charm["name"], "tier": entry["tier"], "kind": "no_room",
                             "reason": reason})
    assignments.sort(key=lambda a: (a["category"] != "major", -a["rel"], a["name"]))

    # 3) mudancas face ao que ele tem hoje
    changes = []
    if own.get("charms") is not None:
        cost = remove_cost(own.get("level"), bool(own.get("expansion")))
        for a in assignments:
            cur = a["current_creature_key"]
            if cur == a["creature_key"]:
                changes.append({"kind": "keep", "charm_key": a["charm_key"], "name": a["name"], "to": a["creature_name"], "gold": 0})
            elif cur is None:
                changes.append({"kind": "assign", "charm_key": a["charm_key"], "name": a["name"], "to": a["creature_name"], "gold": 0})
            else:
                from_c = cat.creature_by_key.get(cur) or {}
                changes.append({"kind": "move", "charm_key": a["charm_key"], "name": a["name"],
                                "from": from_c.get("nome") or cur, "to": a["creature_name"], "gold": cost})
        placed_keys = {a["charm_key"] for a in assignments}
        for key, (tier, current) in owned.items():
            if key in placed_keys or current is None:
                continue
            cur_c = cat.creature_by_key.get(current) or {}
            in_hunt = any(c["key"] == current for c in view["creatures"])
            changes.append({"kind": "leave", "charm_key": key, "name": cat.charm_by_key[key]["name"],
                            "from": cur_c.get("nome") or current, "in_hunt": in_hunt, "gold": 0})
        changes.sort(key=lambda ch: ({"move": 0, "assign": 1, "keep": 2, "leave": 3}[ch["kind"]], ch["name"]))
        if any(ch["kind"] == "move" for ch in changes):
            notes.append("mover um charm custa %s gold cada (1 000 x nivel%s; o cliente usa o nivel do main da conta ⚠)"
                         % (_n(cost), ", x0,75 com a Expansion" if own.get("expansion") else ""))
    return {"hunt_id": hunt_id, "hunt_name": view["hunt"]["nome"], "limit": limit, "limit_source": limit_source,
            "assignments": assignments, "left_out": left_out, "changes": changes, "notes": notes,
            "creatures": view["creatures"], "used": used_creatures, "owned": len(owned)}


def neighbour_hunts(cat, level, current_hunt=None, count=5):
    """As `count` hunts mais proximas do nivel (pelo nivel minimo), sem a actual."""
    ranked = sorted((abs((hh.get("nivel_minimo") or 0) - (level or 0)), hh.get("nivel_minimo") or 0, hh["id"])
                    for hh in cat.hunts if hh["id"] != current_hunt)
    return [hid for _, _, hid in ranked[:count]]
