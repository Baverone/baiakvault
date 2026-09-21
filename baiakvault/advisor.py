"""O «proximo passo» de um personagem: funcoes puras (catalogo + estado do
personagem + o motor das builds entram; sugestoes com pontuacao e
justificacao saem). Sem BD, sem relogio, sem rede.

Regras (decisao de 16/09/2026, registada no CLAUDE.md):

- A referencia e a build que `builds.Planner.plan(vocacao, objectivo, nivel,
  hunt actual)` recomenda — nao se duplica logica, chama-se o motor.
- O ganho de cada accao mede-se no simulador **com o que ele tem** (a arvore
  dele, o equipamento dele, a hunt dele): e a diferenca entre a metrica do
  objectivo antes e depois da accao, em %.
- Ordem da lista: medido antes de nao medido; entre medidos, pelo ganho %;
  um respec vale metade (custa gold); charms e bestiario a seguir; o que
  falta preencher fecha a lista. No maximo 7 linhas.
- Desconhecido nao e zero: um slot nao registado nao entra na conta e a lista
  diz que falta preencher; um upgrade desconhecido conta a 0 e diz-se.
- Nunca se sugere o que ele ja tem, um no sem pre-requisitos (o caminho de
  desbloqueio vai na sugestao), nem um item fora do nivel/vocacao/slot.
"""
import math

from . import builds as B
from . import charms as charms_module
from . import db as db_module
from . import formulas as F
from . import sim
from . import treecode

METRIC_LABEL = {"best": "DPS do ciclo sustentavel (aguenta + mana; druid: cura o knight)",
                "damage": "DPS do ciclo (= XP/h; knight/monk: o que a mana sustenta) x nao morrer", "tank": "EHP x sustain x DPS^0,3",
                "heal": "cura/s sustentavel x DPS^0,3", "support": "cura/s sustentavel x DPS^0,3",
                # a «prioridades» mede-se como a «dano»; a ordem da arvore e que e outra (21/09/2026)
                "priority": "DPS do ciclo (= XP/h; knight/monk: o que a mana sustenta) x nao morrer — so informacao: a arvore segue as prioridades"}
SLOT_LABEL = {"weapon": "arma", "shield": "escudo", "helmet": "elmo", "armor": "armadura",
              "legs": "pernas", "boots": "botas", "amulet": "amuleto", "ring": "anel", "ammo": "municao",
              "backpack": "mochila"}
# «best» maximiza o DPS (as condicoes sao restricoes): pede charms ofensivos como «damage»
GOAL_CHARM_KIND = {"priority": "offensive", "best": "offensive", "damage": "offensive", "tank": "defensive",
                   "heal": "defensive", "support": "defensive"}
CHARM_KIND_LABEL = {"offensive": "ofensivo", "defensive": "defensivo", "passive": "passivo"}
# atributos da forja que o motor entende (somam-se aos do item, em %)
FORGE_ATTRIBUTES = ("crit_chance", "crit_dano", "life_leech", "mana_leech")
MIN_GAIN_PCT = 0.5           # abaixo disto e ruido do simulador, nao uma sugestao
RESPEC_MIN_GAIN_PCT = 5.0    # um respec custa gold: so se a arvore recomendada render bem mais
RESPEC_SCORE_FACTOR = 0.5
CHARM_SCORE = 0.5
BESTIARY_SCORE = 0.25
BESTIARY_NEAR_SHARE = 0.3    # «perto de fechar» = faltam <= 30 % da meta
MAX_SUGGESTIONS = 7
MAX_MISSING = 2

SOURCE_SIM = "formulas do cliente + simulador do BaiakVault"
SOURCE_CATALOG = "catalogo (bundle do cliente)"


def _suggestion(kind, action, why, cost, source, score, **extra):
    d = {"kind": kind, "action": action, "why": why, "cost": cost, "source": source, "score": score}
    d.update(extra)
    return d


def _missing(what, where, score=0.0):
    return _suggestion("missing", "Preencher: " + what, where, "—", "vault.db", score)


# --- o estado, a partir das linhas da BD (puro: recebe listas, nao a BD) ------------------
def state_from_rows(character, tree_rows=(), equipment_rows=(), charm_rows=(), points_row=None,
                    bestiary_rows=()):
    """O dicionario de estado que `advise` consome. As linhas sao as que
    `db.Vault.*_of` devolvem; aqui nao se valida nada (a BD ja validou)."""
    return {
        "name": character.get("name"), "vocation": character.get("vocation"),
        "level": character.get("level"), "goal": character.get("goal"),
        "current_hunt": character.get("current_hunt"), "vip": character.get("vip"),
        # o que ele fixou (ordem 8): rotacao (lista de nomes) e arma (chave do item)
        "fixed_rotation": character.get("fixed_rotation"), "fixed_weapon": character.get("fixed_weapon"),
        "tree": {r["node_key"]: r["rank"] for r in tree_rows} if tree_rows else None,
        "equipment": {r["slot"]: {"item_key": r.get("item_key"), "upgrade_level": r.get("upgrade_level"),
                                  "imbuements": r.get("imbuements"), "attributes": r.get("attributes")}
                      for r in equipment_rows},
        "charms": [{"charm_key": r["charm_key"], "tier": r["tier"],
                    "assigned_creature_key": r.get("assigned_creature_key")} for r in charm_rows],
        "charm_points": ({"points_available": points_row.get("points_available"),
                          "points_spent": points_row.get("points_spent")} if points_row else None),
        "bestiary": {r["creature_key"]: r["kills"] for r in bestiary_rows},
    }


# --- equipamento dele -> o que o simulador entende ---------------------------------------------
def imbuement_index(cat):
    """{'vampirism' | 'Vampirism' | 'life leech' (categoria): entrada} — para ler o
    que ele escreve no formulario ou o que a captura le."""
    lista = (cat.meta("itens").get("imbuements") or {}).get("lista") or []
    idx = {}
    for imb in lista:
        for k in (imb.get("key"), imb.get("name"), imb.get("cat")):
            if k:
                idx[str(k).lower()] = imb
    return idx


def parse_imbuement(cat, text, index=None):
    """«vampirism», «Vampirism:2», «life leech 3» -> (chave, tier ou None). None se
    nao se reconhece."""
    index = index or imbuement_index(cat)
    raw = str(text or "").strip().lower()
    if not raw:
        return None
    tier = None
    for sep in (":", " "):
        head, _, tail = raw.rpartition(sep)
        if head and tail.isdigit() and 1 <= int(tail) <= 3:
            raw, tier = head.strip(), int(tail)
            break
    imb = index.get(raw)
    if not imb:
        return None
    return imb["key"], tier


def profile_equipment(cat, equipment, index=None):
    """`{slot: {"item", "up", "imbuements"}}` so com os slots conhecidos e com
    item, mais as notas do que ficou a contar a 0 (upgrade ou tier de
    imbuement desconhecidos)."""
    index = index or imbuement_index(cat)
    out = {}
    notes = []
    for slot, e in (equipment or {}).items():
        key = e.get("item_key")
        if not key or slot == "backpack":
            continue  # a mochila nao entra em conta nenhuma do simulador
        item = cat.item_by_key.get(str(key).lower())
        if not item:
            continue
        attrs = e.get("attributes") or {}
        if any(k in attrs for k in FORGE_ATTRIBUTES):
            item = dict(item)
            for k in FORGE_ATTRIBUTES:
                if isinstance(attrs.get(k), (int, float)):
                    item[k] = (item.get(k) or 0) + attrs[k]
        up = e.get("upgrade_level")
        if up is None:
            notes.append("upgrade de %s desconhecido (contado a 0)" % SLOT_LABEL.get(slot, slot))
            up = 0
        imbs = []
        for text in (e.get("imbuements") or []):
            parsed = parse_imbuement(cat, text, index)
            if not parsed:
                continue
            k, tier = parsed
            if tier is None:
                notes.append("tier do imbuement %s em %s desconhecido (contado ao minimo)" % (k, SLOT_LABEL.get(slot, slot)))
                tier = 1
            imbs.append((k, tier))
        out[slot] = {"item": item, "up": up, "imbuements": imbs}
    return out, notes


# --- de onde vem um item -----------------------------------------------------------------------
def item_sources(cat, item, limit=4):
    """Onde cai: monstros normais (com a hunt) e bosses da wave 10 (com a hunt),
    pelas tabelas de loot do cliente. Lista de dicionarios, a mais provavel primeiro."""
    out = []
    for d in (item.get("cai_de") or []):
        c = cat.creature_by_key.get(d.get("monstro"))
        out.append({"creature": c["nome"] if c else d.get("monstro"), "boss": False,
                    "hunts": [hid for hid in ((c or {}).get("aparece_em") or []) if hid in cat.hunt_by_id],
                    "chance_por_100k": d.get("chance_por_100k")})
    name = item["nome"].lower()
    for boss in cat.wave10_bosses:
        for d in boss.get("drops") or []:
            if str(d.get("item", "")).lower() == name:
                out.append({"creature": boss["nome"], "boss": True,
                            "hunts": [boss["hunt"]] if boss.get("hunt") in cat.hunt_by_id else [],
                            "chance_por_100k": d.get("chance_por_100k")})
    out.sort(key=lambda s: -(s["chance_por_100k"] or 0))
    return out[:limit]


def item_sources_text(cat, item):
    srcs = item_sources(cat, item)
    if not srcs:
        return "nao cai de monstro nenhum no catalogo (boss de sala, loja ou Codex — o cliente nao diz)"
    bits = []
    for s in srcs:
        chance = ("%.2f%%" % ((s["chance_por_100k"] or 0) / 1000.0)).replace(".", ",")
        hunts = ", ".join(cat.hunt_by_id[hid]["nome"] for hid in s["hunts"])
        bits.append("%s%s (%s%s)" % (s["creature"], " [boss wave 10]" if s["boss"] else "", chance,
                                     ", " + hunts if hunts else ""))
    return "cai de " + "; ".join(bits)


# --- a analise --------------------------------------------------------------------------------
def _score_of(cat, vocation, level, goal, tree, equipment, target, rotation):
    prof = sim.Profile(cat, vocation, level, tree, equipment)
    m = B.evaluate(prof, target, rotation)
    return B.score_of(m, goal), m


def _pct(a, b):
    return (a / b - 1.0) * 100.0 if b else 0.0


def _fmt_pct(x):
    return ("%+.1f%%" % x).replace(".", ",")


def _node_name(cat, nid):
    return (cat.node_by_id.get(nid) or {}).get("nome") or nid


def _tree_spent(cat, ranks):
    return sum(F.tree_total_cost(cat.node_by_id[k], v) for k, v in (ranks or {}).items() if k in cat.node_by_id)


def tree_suggestions(cat, state, goal, target, equipment, rotation, plan, current_score, metric):
    voc, level = state["vocation"], state["level"]
    ranks = state["tree"]
    out = []
    if ranks is None:
        return [_missing("a arvore (nenhum no registado)",
                         "sem a arvore nao se sabe que no comprar a seguir — modo de edicao, seccao Arvore")]
    spent = _tree_spent(cat, ranks)
    budget = F.tree_budget(level)
    left = budget - spent
    if left < 0:
        return [_missing("a arvore esta errada: os ranks registados custam %d pontos e o nivel %d so da %d"
                         % (spent, level, budget), "algum rank esta a mais — modo de edicao, seccao Arvore")]
    if goal == B.PRIORITY_GOAL:
        out += priority_tree_suggestions(cat, state, target, equipment, rotation, plan, current_score, metric, left)
    elif left > 0:
        top, _, _ = B.next_purchase(cat, voc, goal, level, ranks, equipment, target, rotation=rotation, top=3)
        for opt in top[:2]:
            if opt["gain_pct"] < MIN_GAIN_PCT:
                continue
            via = " (antes: %s)" % " → ".join("%s 1" % _node_name(cat, v) for v in opt["via"]) if opt["via"] else ""
            out.append(_suggestion(
                "tree", "Comprar na arvore: %s rank %d%s" % (opt["name"], opt["rank"], via),
                "%s na metrica «%s» com o teu equipamento em %s; tens %d ponto%s por gastar"
                % (_fmt_pct(opt["gain_pct"]), metric, cat.hunt_by_id[target.hunt_id]["nome"], left, "" if left == 1 else "s"),
                "%d ponto%s" % (opt["cost"], "" if opt["cost"] == 1 else "s"), SOURCE_SIM, opt["gain_pct"],
                node=opt["node"], rank=opt["rank"], via=opt["via"], points_left=left))
    else:
        # sem pontos livres: o que comprar quando o proximo nivel der o ponto
        top, _, _ = B.next_purchase(cat, voc, goal, level + 1, ranks, equipment, target, rotation=rotation, top=1)
        if top and top[0]["gain_pct"] >= MIN_GAIN_PCT:
            opt = top[0]
            out.append(_suggestion(
                "tree", "No nivel %d comprar: %s rank %d" % (level + 1, opt["name"], opt["rank"]),
                "%s na metrica «%s»; a arvore esta toda gasta (%d/%d), o proximo ponto vem com o nivel"
                % (_fmt_pct(opt["gain_pct"]), metric, spent, budget),
                "1 ponto (ao subir de nivel)", SOURCE_SIM, opt["gain_pct"] * 0.5,
                node=opt["node"], rank=opt["rank"], via=opt["via"], points_left=0))
    # a arvore recomendada com o equipamento dele: se render bem mais, vale um respec
    plan_score, _ = _score_of(cat, voc, level, goal, plan["tree"], equipment, target, rotation)
    gain = _pct(plan_score, current_score)
    diff_points = sum(max(0, F.tree_total_cost(cat.node_by_id[k], r) - F.tree_total_cost(cat.node_by_id[k], ranks.get(k, 0)))
                      for k, r in plan["tree"].items())
    if gain >= RESPEC_MIN_GAIN_PCT and diff_points > 0 and left <= budget * 0.1:
        # com pontos por gastar o respec nao faz sentido: primeiro gastam-se. O custo e o de
        # importar o codigo da recomendada (cliente fD, o mesmo do Reset All); o codigo esta na pagina
        out.append(_suggestion(
            "respec", "Importar o codigo da arvore recomendada (%s %s, nivel %d)" % (voc, goal, level),
            "%s na metrica «%s» com o teu equipamento; %d pontos da recomendada nao estao na tua — "
            "na arvore do personagem: Colar codigo para importar… → Carregar"
            % (_fmt_pct(gain), metric, diff_points),
            "%s gold (cliente fD: 1000 + 200 x %d pontos gastos agora)" % (_thousands(treecode.import_cost(spent)), spent),
            SOURCE_SIM, gain * RESPEC_SCORE_FACTOR, gain_pct=gain))
    return out


def priority_tree_suggestions(cat, state, target, equipment, rotation, plan, current_score, metric, left):
    """No objectivo «prioridades» (21/09/2026) o proximo no e o proximo da ordem de compra
    por etapas da build recomendada que ele ainda nao tem (nao o de maior ganho medido);
    o ganho medido no simulador com o que ele tem vai ao lado, como informacao. Se o
    Avatar nao cabe ao nivel dele, diz-se a que nivel cabe e que o passo la e importar a
    build desse nivel (respec pelo `fD`; o gold nao conta — decisao dele de 16/09)."""
    voc, level = state["vocation"], state["level"]
    ranks = state["tree"] or {}
    out = []
    order = plan.get("order") or []
    node_by_id = {n["id"]: n for n in cat.tree_by_vocation[voc]["nos"]}
    adj = B._adjacency(cat, voc)
    nxt = next((st for st in order if (ranks.get(st.node_id, 0) or 0) < st.rank), None)
    if nxt is not None:
        node = node_by_id[nxt.node_id]
        rank = (ranks.get(nxt.node_id, 0) or 0) + 1
        path = B.unlock_path(node, ranks, adj, node_by_id) or []
        trial = dict(ranks)
        cost = 0
        for pid in path + [nxt.node_id]:
            cost += F.tree_rank_cost(node_by_id[pid], trial.get(pid, 0))
            trial[pid] = trial.get(pid, 0) + 1
        s, _ = _score_of(cat, voc, level, "damage", trial, equipment, target, rotation)
        gain = _pct(s, current_score)
        stage = B.PRIORITY_LABEL.get(nxt.stage, nxt.stage or "?")
        via = " (antes: %s)" % " → ".join("%s 1" % _node_name(cat, v) for v in path) if path else ""
        fits = cost <= left
        out.append(_suggestion(
            "tree", ("Comprar na arvore: %s rank %d%s" if fits else "Juntar pontos para a arvore: %s rank %d%s")
            % (node["nome"], rank, via),
            "etapa «%s» das tuas prioridades (a proxima da ordem de compra); no simulador com o teu equipamento "
            "em %s: %s no DPS (informacao, nao e o criterio); tens %d ponto%s por gastar"
            % (stage, cat.hunt_by_id[target.hunt_id]["nome"], _fmt_pct(gain), left, "" if left == 1 else "s"),
            "%d ponto%s" % (cost, "" if cost == 1 else "s"), SOURCE_SIM, max(MIN_GAIN_PCT, gain) if fits else MIN_GAIN_PCT,
            node=nxt.node_id, rank=rank, via=path, points_left=left, stage=nxt.stage))
    info = plan.get("priority") or {}
    avatar_plan = plan.get("avatar_plan")
    if not info.get("avatar") and avatar_plan is not None:
        lv = avatar_plan["level"]
        spent_now = _tree_spent(cat, ranks)
        code = treecode.encode(cat, voc, lv, avatar_plan["tree"])
        out.append(_suggestion(
            "respec", "No nivel %d: importar a build com o %s (respec)" % (lv, _node_name(cat, B.AVATAR_NODE[voc])),
            "o Avatar e a 1.a prioridade mas o caminho mais barato + 300 pontos so cabe ao nivel %d (tens %d); "
            "ate la as outras prioridades seguem, e no nivel %d importa-se o codigo da build desse nivel — nao se "
            "deixam pontos por gastar a poupar (o gold do respec nao conta, decisao de 16/09/2026)"
            % (lv, level, lv),
            "%s gold ao importar (cliente fD: 1000 + 200 x pontos gastos nessa altura; com os %d de agora seriam %s)"
            % (_thousands(treecode.import_cost(lv)), spent_now, _thousands(treecode.import_cost(spent_now))),
            SOURCE_SIM, MIN_GAIN_PCT * 0.5, level_at=lv, code=code))
    return out


def _thousands(n):
    return "{:,}".format(int(round(n))).replace(",", ".")


def tree_diff(cat, vocation, level, his_tree, plan_tree):
    """A diferenca entre a arvore dele (importada pelo codigo, ou registada) e a
    recomendada: nos a subir e a tirar, em pontos, e o gold que importar a
    recomendada custa AGORA (cliente `fD`: 1000 + 200 x pontos gastos, 0 sem
    pontos). `None` sem arvore dele. O codigo da recomendada vai sempre."""
    code = treecode.encode(cat, vocation, level, plan_tree)
    plan_spent = _tree_spent(cat, plan_tree)
    if his_tree is None:
        return {"known": False, "code": code, "plan_spent": plan_spent, "gold": None, "same": False,
                "add": [], "remove": [], "points_add": 0, "points_remove": 0, "his_spent": None}
    add, remove = [], []
    points_add = points_remove = 0
    for nid in sorted(set(his_tree) | set(plan_tree)):
        a, b = his_tree.get(nid, 0) or 0, plan_tree.get(nid, 0) or 0
        node = cat.node_by_id.get(nid)
        if not node or a == b:
            continue
        delta = F.tree_total_cost(node, b) - F.tree_total_cost(node, a)
        if b > a:
            add.append((nid, node["nome"], a, b, delta))
            points_add += delta
        else:
            remove.append((nid, node["nome"], a, b, -delta))
            points_remove += -delta
    his_spent = _tree_spent(cat, his_tree)
    return {"known": True, "code": code, "plan_spent": plan_spent, "his_spent": his_spent,
            "gold": treecode.import_cost(his_spent), "same": not add and not remove,
            "add": add, "remove": remove, "points_add": points_add, "points_remove": points_remove}


def _item_stats(item):
    bits = []
    if item.get("ataque"):
        bits.append("atk %s" % item["ataque"])
    if item.get("ataque_elemental"):
        bits.append("+%s %s" % (item["ataque_elemental"], item.get("elemento") or "?"))
    if item.get("wand_min") is not None:
        bits.append("%s-%s %s" % (item["wand_min"], item["wand_max"], item.get("elemento") or "?"))
    if item.get("armadura"):
        bits.append("arm %s" % item["armadura"])
    if item.get("defesa"):
        bits.append("def %s" % item["defesa"])
    for k, v in (item.get("skills") or {}).items():
        bits.append("%s +%s" % (k, v))
    for k, v in (item.get("absorcao") or {}).items():
        bits.append("%s %s%%" % (k, ("+%s" % v) if v > 0 else v))
    for src, label in (("crit_chance", "crit"), ("crit_dano", "crit dmg"), ("life_leech", "life leech"), ("mana_leech", "mana leech")):
        if item.get(src):
            bits.append("%s +%s%%" % (label, item[src]))
    return ", ".join(bits)


def equipment_suggestions(cat, state, goal, target, equipment, rotation, current_score, metric, index=None):
    voc, level = state["vocation"], state["level"]
    known = state["equipment"] or {}
    out = []
    missing_slots = []
    slots = list(B.SLOTS)
    if voc != "knight":
        slots.remove("shield")
    weapon = (equipment.get("weapon") or {}).get("item")
    for slot in slots:
        if slot == "shield" and weapon and weapon.get("duas_maos"):
            continue
        if slot == "weapon" and state.get("fixed_weapon"):
            continue   # a arma e decisao dele (ordem 8): nao se sugere trocar
        if slot not in known:
            missing_slots.append(SLOT_LABEL.get(slot, slot))
            continue
        his = known[slot]
        his_item = (equipment.get(slot) or {}).get("item")
        his_key = (his_item or {}).get("nome", "").lower() if his_item else None
        scored = []
        for item in B.candidates(cat, voc, level, slot, goal):
            trial = dict(equipment)
            if slot == "weapon" and voc == "knight" and item.get("duas_maos"):
                trial.pop("shield", None)
            imbs = B.choose_imbuements(item, goal, target, voc)
            trial[slot] = {"item": item, "up": 0, "imbuements": B._imb_keys(cat, imbs), "imbuement_cats": imbs}
            if slot == "weapon" and voc == "paladin":
                ammo = B.best_ammo(cat, item, level)
                if ammo:
                    trial["ammo"] = {"item": ammo}
                else:
                    trial.pop("ammo", None)
            s, m = _score_of(cat, voc, level, goal, state["tree"] or {}, trial, target, rotation)
            scored.append((s, item, imbs, trial))
        if not scored:
            continue
        scored.sort(key=lambda x: (x[0], x[1]["nome"]), reverse=True)
        best_s, best_item, best_imbs, _ = scored[0]
        gain = _pct(best_s, current_score)
        if best_item["nome"].lower() == his_key:
            # ja tem o melhor; so os imbuements podem estar por por
            if his.get("imbuements") is None and best_item.get("imbuement_slots"):
                missing_slots.append(SLOT_LABEL.get(slot, slot) + " (imbuements)")
            continue
        if gain < MIN_GAIN_PCT:
            continue
        why = "%s na metrica «%s» (%s)" % (_fmt_pct(gain), metric, _item_stats(best_item) or "sem numeros no catalogo")
        if his_item and his.get("upgrade_level") is None:
            why += "; o upgrade do que tens e desconhecido e contou a 0"
        imb_text = (" com " + ", ".join(best_imbs)) if best_imbs else ""
        out.append(_suggestion(
            "equipment", "Trocar %s: %s → %s%s" % (SLOT_LABEL.get(slot, slot),
                                                    his_item["nome"] if his_item else "(vazio)", best_item["nome"], imb_text),
            why, "%s; vende ao NPC por %s" % (item_sources_text(cat, best_item),
                                             _thousands(best_item["preco_npc"]) if best_item.get("preco_npc") else "?"),
            SOURCE_CATALOG + " + simulador", gain, slot=slot, item_key=best_item["nome"].lower(), gain_pct=gain,
            item_level=best_item.get("nivel")))
    if missing_slots:
        out.append(_missing("o equipamento em %s" % ", ".join(missing_slots),
                            "um slot nao registado nao entra na conta — modo de edicao, seccao Equipamento"))
    return out


def charm_suggestions(cat, state, goal):
    """O proximo charm a subir. Os maiores pagam-se em Charm Points e os menores
    em Minor Charm Echoes (cliente `OVe`, ver docs/charms.md) — sao dois saldos;
    aqui so os maiores, que sao os que o objectivo pede (os menores so valem
    com echoes, que vem de subir maiores)."""
    points = state.get("charm_points") or {}
    available = points.get("points_available")
    have = {c["charm_key"]: c for c in state.get("charms") or []}
    kind = GOAL_CHARM_KIND[goal]
    options = []
    for charm in cat.charms:
        if charm.get("category") != "major":
            continue
        key = charm["key"]
        tier = have.get(key, {}).get("tier", 0) or 0
        if tier >= 3:
            continue
        cost = (charm.get("points") or [None, None, None])[tier]
        chance = charm.get("chance") or [0, 0, 0]
        gain = chance[tier] - (chance[tier - 1] if tier > 0 else 0)
        if cost is None:
            continue
        options.append({"charm": charm, "tier": tier + 1, "cost": cost, "gain": gain,
                        "matches": charm.get("kind") == kind, "owned": tier > 0,
                        "creature": have.get(key, {}).get("assigned_creature_key")})
    if not options:
        return []
    # regra: o tipo do objectivo primeiro; subir um charm que ja usa antes de abrir outro; depois ganho por ponto
    options.sort(key=lambda o: (not o["matches"], not o["owned"], -(o["gain"] / max(1, o["cost"]))))
    if available is None:
        best = options[0]
        return [_missing("os charm points disponiveis",
                         "sem eles nao se sabe se %s tier %d (%d pontos) cabe — modo de edicao, seccao Charms"
                         % (best["charm"]["name"], best["tier"], best["cost"]))]
    affordable = [o for o in options if o["cost"] <= available]
    if affordable:
        o = affordable[0]
        verb = "Subir o charm" if o["owned"] else "Desbloquear o charm"
        return [_suggestion(
            "charm", "%s %s para tier %d" % (verb, o["charm"]["name"], o["tier"]),
            "%s %s: chance %s%% → %s%%; %s; da %d echoes de troco para os menores" % (
                CHARM_KIND_LABEL.get(o["charm"]["kind"], o["charm"]["kind"]),
                "e o tipo do objectivo" if o["matches"] else "(o objectivo pede %s, mas nao ha nenhum que caiba)" % CHARM_KIND_LABEL.get(kind, kind),
                (o["charm"]["chance"] or [0, 0, 0])[o["tier"] - 2] if o["tier"] > 1 else 0,
                (o["charm"]["chance"] or [0, 0, 0])[o["tier"] - 1],
                "esta na criatura %s" % cat.creature_by_key[o["creature"]]["nome"]
                if o["creature"] in cat.creature_by_key else "a criatura recomendada esta na seccao Charms desta pagina",
                charms_module.echoes_for_upgrade(o["tier"] - 1)),
            "%d de %d pontos disponiveis" % (o["cost"], available), SOURCE_CATALOG, CHARM_SCORE,
            charm_key=o["charm"]["key"], tier=o["tier"])]
    o = options[0]
    return [_suggestion(
        "charm", "Juntar pontos para %s tier %d" % (o["charm"]["name"], o["tier"]),
        "faltam %d pontos (tens %d); e o %s mais rentavel por ponto" % (
            o["cost"] - available, available, CHARM_KIND_LABEL.get(o["charm"]["kind"], o["charm"]["kind"])),
        "%d pontos" % o["cost"], SOURCE_CATALOG, CHARM_SCORE * 0.5, charm_key=o["charm"]["key"], tier=o["tier"])]


def bestiary_suggestions(cat, state):
    near = []
    for key, kills in (state.get("bestiary") or {}).items():
        c = cat.creature_by_key.get(key)
        meta = (c or {}).get("meta_kills")
        if not c or meta is None:
            continue
        remaining = meta - kills
        if 0 < remaining <= meta * BESTIARY_NEAR_SHARE:
            near.append((remaining, meta, c))
    if not near:
        return []
    remaining, meta, c = min(near, key=lambda x: x[0])
    hunts = ", ".join(cat.hunt_by_id[hid]["nome"] for hid in (c.get("aparece_em") or []) if hid in cat.hunt_by_id)
    return [_suggestion(
        "bestiary", "Fechar o bestiario de %s: faltam %s kills" % (c["nome"], _thousands(remaining)),
        "%s de %s; fecha a entrada e da charm points (quantos, o cliente nao diz)%s"
        % (_thousands(meta - remaining), _thousands(meta), " — em " + hunts if hunts else ""),
        "%s kills" % _thousands(remaining), SOURCE_CATALOG, BESTIARY_SCORE, creature_key=c["chave"])]


def advise(cat, state, planner, max_items=MAX_SUGGESTIONS):
    """O proximo passo. Devolve um dicionario com `suggestions` (ordenadas, no
    maximo `max_items`), o objectivo e a hunt usados (e se foram por omissao),
    a build recomendada (`plan`) e as metricas actuais vs recomendadas."""
    voc, level = state.get("vocation"), state.get("level")
    missing = []
    if voc is None:
        missing.append(_missing("a vocacao", "sem vocacao nao ha arvore, feiticos nem itens — modo de edicao, seccao Personagem"))
    if level is None:
        missing.append(_missing("o nivel", "sem nivel nao ha orcamento da arvore nem itens equipaveis — modo de edicao, seccao Personagem"))
    if missing:
        return {"goal": state.get("goal"), "goal_defaulted": False, "hunt": None, "hunt_defaulted": False,
                "plan": None, "current": None, "notes": [], "suggestions": missing,
                "profile": None, "equipment_known": False}
    goal = state.get("goal")
    goal_defaulted = goal is None
    if goal_defaulted:
        goal = db_module.default_goal(voc)
    hunt = state.get("current_hunt")
    hunt_defaulted = hunt is None
    if hunt_defaulted:
        hunt = B.reference_hunt(cat, level)
    fixed_rotation, fixed_weapon = state.get("fixed_rotation"), state.get("fixed_weapon")
    plan = planner.plan(voc, goal, level, hunt_id=hunt, fixed_rotation=fixed_rotation, fixed_weapon=fixed_weapon)
    target = planner.target_for(voc, goal, level, hunt)   # no druid «best» traz a pressao sobre o knight
    index = imbuement_index(cat)
    equipment, notes = profile_equipment(cat, state.get("equipment"), index)
    tree = state.get("tree") or {}
    prof = sim.Profile(cat, voc, level, tree, equipment)
    # a rotacao dele: a que fixou (se o nivel a der), senao a que o optimizador escolhe com o que ele tem
    rotation, _ = planner.rotation(prof, target, False, goal, fixed=planner.fixed_key(fixed_rotation, fixed_weapon))
    current_metrics = B.evaluate(prof, target, rotation)
    current_score = B.score_of(current_metrics, goal)
    metric = METRIC_LABEL[goal]

    suggestions = []
    suggestions += tree_suggestions(cat, state, goal, target, equipment, rotation, plan, current_score, metric)
    diff = tree_diff(cat, voc, level, state.get("tree"), plan["tree"])
    suggestions += equipment_suggestions(cat, state, goal, target, equipment, rotation, current_score, metric, index)
    suggestions += charm_suggestions(cat, state, goal)
    suggestions += bestiary_suggestions(cat, state)
    if hunt_defaulted:
        suggestions.append(_missing("a hunt actual", "as contas usaram %s (a hunt que o jogo recomenda ao nivel %d)"
                                    % (cat.hunt_by_id[hunt]["nome"], level)))
    actions = sorted([s for s in suggestions if s["kind"] != "missing"], key=lambda s: -s["score"])
    missing = [s for s in suggestions if s["kind"] == "missing"][:MAX_MISSING]
    final = actions[:max(0, max_items - len(missing))] + missing
    return {"goal": goal, "goal_defaulted": goal_defaulted, "hunt": hunt, "hunt_defaulted": hunt_defaulted,
            "plan": plan, "current": current_metrics, "current_score": current_score,
            "plan_score": plan["score"], "metric": metric, "notes": notes, "suggestions": final,
            "assumed_skill": prof.assumed_skill, "tree_diff": diff, "rotation": rotation,
            "fixed_rotation": fixed_rotation, "fixed_weapon": fixed_weapon,
            # para o motor dos charms: as estatisticas dele (critico, roubo, HP) e se ha equipamento registado
            "profile": prof, "equipment_known": bool(equipment)}
