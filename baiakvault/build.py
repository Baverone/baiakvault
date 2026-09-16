"""O gerador: catalogo + vault.db -> `docs/` (ou `--out`).

Uma funcao por pagina, todas puras a menos da escrita final. O `build()`
devolve o que escreveu e quanto tempo levou, para o `check` e os testes
provarem o efeito (ficheiros no disco, tamanho, tempo) em vez de confiarem no
«ok».

O que a fonte nao tem sai «?» (ver `html.fmt`). As contas que aqui se fazem
sao as do proprio jogo (gold esperado de um drop) ou nenhuma — XP/h e gold/h
nao existem em fonte nenhuma e nao se inventam.
"""
import time
from datetime import datetime
from pathlib import Path

from . import advisor
from . import builds as builds_module
from . import catalog as catalog_module
from . import db as db_module
from . import formulas as F
from . import html as h
from . import notes
from . import pages_builds

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "docs"
# A validacao cruzada e escrita a mao (com o que `scripts/validar_guia.py` mede) e vive no repo;
# o build copia-a para `docs/builds/` e gera a versao HTML.
VALIDATION_MD = DEFAULT_OUT / "builds" / "validacao.md"

VOCATION_LABEL = {"knight": "Knight (EK)", "monk": "Monk", "paladin": "Paladin (RP)",
                  "sorcerer": "Sorcerer (MS)", "druid": "Druid (ED)"}
GOAL_LABEL = {"damage": "dano", "tank": "tank (sobreviver)", "heal": "cura", "support": "support"}
KIND_LABEL = {"offensive": "ofensivo", "defensive": "defensivo", "passive": "passivo"}
ELEMENT_LABEL = {"physical": "fisico", "fire": "fogo", "earth": "terra", "ice": "gelo",
                 "energy": "energia", "death": "morte", "holy": "sagrado"}
INDEX_WARNING = ("Os indices de XP e de loot sao a conta que o proprio jogo faz para ordenar "
                 "as hunts: <b>XP por ponto de vida a abater — eficiencia, nao XP/h</b>. Uma hunt "
                 "de bichos gordos rende pouco no indice e muito por kill. XP/h e gold/h "
                 "absolutos nao existem em fonte nenhuma; so medindo na conta.")


def gold_expected(drop):
    """Gold medio por kill de uma linha de loot, pela conta do proprio jogo:
    `chance/100000 x (1+max)/2 x preco do NPC`. `None` sem preco ou chance."""
    if not drop:
        return None
    chance, price = drop.get("chance_por_100k"), drop.get("preco_npc")
    maximum = drop.get("max") or 1
    if chance is None or price is None:
        return None
    return chance / 100000.0 * (1 + maximum) / 2.0 * price


def _hunt_href(root, hunt_id):
    return "%shunts/%s.html" % (root, hunt_id)


def _hunt_link(root, cat, hunt_id):
    hunt = cat.hunt_by_id.get(hunt_id)
    if not hunt:
        return h.esc(hunt_id)
    return '<a href="%s">%s</a>' % (_hunt_href(root, hunt_id), h.esc(hunt["nome"]))


# --- Inicio -------------------------------------------------------------------
def render_index(cat, characters, generated_at, advice_by_slug=None):
    advice_by_slug = advice_by_slug or {}
    parts = ["<h1>BaiakVault</h1>",
             '<p class="mudo">Os personagens do Andre no Baiak Idle, a build de cada um e o '
             "proximo passo. Nada aqui toca no jogo nem na conta.</p>"]
    parts.append("<h2>Personagens</h2>")
    if not characters:
        parts.append('<div class="cartao"><p>Ainda nao ha personagens.</p>'
                     "<p>Como adicionar: o modo de edicao local (<code>py -m baiakvault serve</code>, "
                     "porto 8774) chega na ordem 2; a leitura de capturas de ecra "
                     "(<code>capturas/</code>) chega na ordem 4. Ate la a BD esta vazia de "
                     "proposito — nao se inventam personagens.</p></div>")
    else:
        parts.append('<div class="grelha">')
        for c in characters:
            advice = advice_by_slug.get(c["slug"])
            first = (advice or {}).get("suggestions") or []
            parts.append(
                '<div class="cartao"><h3><a href="personagens/%s.html">%s</a></h3>%s</div>'
                % (h.esc(c["slug"]), h.esc(c["name"]), h.kv([
                    ("vocacao", h.esc(VOCATION_LABEL.get(c["vocation"], c["vocation"]))),
                    ("nivel", h.fmt(c["level"])),
                    ("hunt actual", _hunt_link("", cat, c["current_hunt"]) if c["current_hunt"] else h.UNKNOWN),
                    ("VIP", h.yes_no(c["vip"])),
                    ("objectivo", _goal_text(advice, c)),
                    ("proximo passo", ('<b>%s</b> <small class="mudo">%s</small>'
                                       % (h.esc(first[0]["action"]), h.esc(first[0]["why"])))
                     if first else '<span class="mudo">nada a sugerir</span>'),
                ])))
        parts.append("</div>")
    parts.append("<h2>Atalhos</h2>")
    parts.append('<ul><li><a href="builds/index.html">Builds</a> — as 8 builds (vocacao + objectivo) por nivel: '
                 "arvore por ordem de compra, equipamento BiS, rotacao do Helper e numeros do simulador; "
                 '<a href="builds/validacao.html">validacao cruzada</a> com o guia</li>'
                 '<li><a href="hunts/index.html">Hunts</a> — as %d hunts pelos indices do jogo</li>'
                 '<li><a href="charms/index.html">Charms</a> — o guia dos %d charms</li></ul>'
                 % (len(cat.hunts), len(cat.charms)))
    parts.append('<p class="mudo"><small>Catalogo do jogo visto a %s. Gerado a %s.</small></p>'
                 % (h.esc(cat.seen_at()), h.esc(generated_at)))
    return h.page("BaiakVault", "".join(parts), root="", here="inicio", generated_at=generated_at)


# --- Hunts ------------------------------------------------------------------------
def _hunts_sorted(cat):
    return sorted(cat.hunts, key=lambda x: (x.get("nivel_minimo") or 0, x["nome"].lower()))


def render_hunts_index(cat, generated_at):
    root = "../"
    rows = []
    for hunt in _hunts_sorted(cat):
        note = notes.for_hunt(hunt["id"])
        boss = hunt.get("boss_da_wave_10")
        rows.append([
            h.fmt(hunt.get("nivel_minimo")),
            h.fmt(hunt.get("nivel_estimado_pelo_jogo")),
            '<a href="%s.html">%s</a>' % (h.esc(hunt["id"]), h.esc(hunt["nome"])),
            h.esc(", ".join(m["nome"] for m in hunt.get("monstros") or [])),
            h.esc(boss["nome"]) if boss else '<span class="mudo">sem boss</span>',
            h.fmt(hunt.get("indice_xp"), 1),
            h.fmt(hunt.get("indice_loot"), 1),
            h.esc(hunt.get("tende_para")),
            ('%s <small class="mudo">[%s]</small>' % (h.esc(note["text"]), h.esc(note["video"])))
            if note else "",
        ])
    body = ["<h1>Hunts</h1>",
            '<p class="aviso">%s</p>' % INDEX_WARNING,
            '<p class="mudo">«Nivel» e o minimo sugerido pelo jogo; «estim.» e o nivel que a '
            "formula do proprio cliente estima pela dificuldade dos monstros. O minimo e "
            "orientacao, nao bloqueio. A coluna «canal» e opiniao do %s — nao foi medida.</p>"
            % h.esc(notes.CHANNEL),
            h.table(["nivel", "estim.", "hunt", "monstros", "boss (wave 10)", "ind. XP",
                     "ind. loot", "tende para", "canal"], rows, numeric=(0, 1, 5, 6)),
            h.source_line(cat.source_of("hunts"), cat.seen_at("hunts"))]
    return h.page("Hunts — BaiakVault", "".join(body), root=root, here="hunts",
                  generated_at=generated_at)


def render_hunt(cat, hunt, generated_at):
    root = "../"
    parts = ["<h1>%s</h1>" % h.esc(hunt["nome"])]
    note = notes.for_hunt(hunt["id"])
    parts.append('<div class="cartao">' + h.kv([
        ("nivel minimo", h.fmt(hunt.get("nivel_minimo"))),
        ("nivel estimado pelo jogo", h.fmt(hunt.get("nivel_estimado_pelo_jogo"))),
        ("indice XP", h.fmt(hunt.get("indice_xp"), 1)),
        ("indice loot", h.fmt(hunt.get("indice_loot"), 1)),
        ("tende para", h.esc(hunt.get("tende_para"))),
        ("XP por kill (media)", h.fmt(hunt.get("exp_por_kill"), 1)),
        ("gold por kill (media)", h.fmt(hunt.get("gold_por_kill"), 1)),
        ("dificuldade (ecr)", h.fmt(hunt.get("dificuldade_ecr"), 1)),
        ("XP/h", h.UNKNOWN + ' <small class="mudo">so medindo na conta</small>'),
        ("gold/h", h.UNKNOWN + ' <small class="mudo">so medindo na conta</small>'),
    ]) + "</div>")
    parts.append('<p class="aviso">%s</p>' % INDEX_WARNING)
    if note:
        parts.append('<div class="cartao"><b>O canal diz:</b> %s<br><small class="mudo">fonte: %s '
                     "— opiniao em directo, nao medida</small></div>"
                     % (h.esc(note["text"]), h.esc(note["source"])))

    monsters = hunt.get("monstros") or []
    parts.append("<h2>Monstros</h2>")
    has_weights = any(m.get("peso") is not None for m in monsters)
    headers = ["monstro", "XP", "HP", "meta do bestiario"]
    numeric = (1, 2, 3)
    if has_weights:
        headers.append("peso")
        numeric = (1, 2, 3, 4)
    rows = []
    for m in monsters:
        row = [h.esc(m["nome"]), h.fmt(m.get("exp")), h.fmt(m.get("hp")),
               h.fmt(m.get("meta_kills_bestiario"))]
        if has_weights:
            row.append(h.fmt(m.get("peso")))
        rows.append(row)
    parts.append(h.table(headers, rows, numeric=numeric))
    if not has_weights:
        parts.append('<p class="mudo"><small>Pesos de spawn: o cliente nao os publica para esta '
                     "hunt (fica «?», nao se assume igual).</small></p>")
    parts.append('<p class="mudo"><small>Pack maximo: %s vivos; spawn a cada %s ms.</small></p>'
                 % (h.fmt(hunt.get("max_vivos")), h.fmt(hunt.get("spawn_ms"))))

    boss = hunt.get("boss_da_wave_10")
    parts.append("<h2>Boss da wave 10</h2>")
    if not boss:
        parts.append('<p class="mudo">Esta hunt nao tem boss de wave 10 no catalogo.</p>')
    else:
        parts.append("<p><b>%s</b> — XP base %s. Multiplicadores da wave 10 (do guia, nao do "
                     "cliente): x3 HP, x1,5 dano, x2,5 XP.</p>"
                     % (h.esc(boss["nome"]), h.fmt(boss.get("exp"))))
        wave = cat.wave10_by_hunt.get(hunt["id"])
        drops = []
        for d in (wave or {}).get("drops") or []:
            drops.append((gold_expected(d), d))
        drops.sort(key=lambda x: -(x[0] if x[0] is not None else -1))
        if drops:
            parts.append(h.table(
                ["drop", "chance", "max", "preco NPC", "gold esperado/kill"],
                [[h.esc(d["item"]), h.pct_of_100k(d.get("chance_por_100k")), h.fmt(d.get("max")),
                  h.fmt(d.get("preco_npc")), h.fmt(g, 1)] for g, d in drops[:12]],
                numeric=(1, 2, 3, 4)))
        else:
            parts.append('<p class="mudo">Loot do boss: nao esta no catalogo.</p>')

    parts.append("<h2>Drops que mais valem</h2>")
    best = hunt.get("drops_que_mais_valem") or []
    if best:
        parts.append(h.table(["item", "gold esperado por kill"],
                             [[h.esc(d["item"]), h.fmt(d.get("gold_esperado_por_kill"), 1)]
                              for d in best], numeric=(1,)))
        parts.append('<p class="mudo"><small>Gold esperado = chance/100 000 x (1+max)/2 x preco '
                     "do NPC, media ponderada pelos monstros da hunt — a conta do proprio "
                     "jogo.</small></p>")
    else:
        parts.append('<p class="mudo">Sem tabela de drops no catalogo.</p>')

    parts.append("<h2>Lista do Codex desta hunt</h2>")
    codex = hunt.get("codex_da_hunt") or []
    if codex:
        parts.append(h.table(["item", "quantidade"],
                             [[h.esc(c["item"]), h.fmt(c.get("qty"))] for c in codex], numeric=(1,)))
        parts.append('<p class="mudo"><small>E o que o Auto Collect vai apanhar nesta hunt; a '
                     "recompensa por fechar a lista nao esta no cliente.</small></p>")
    else:
        parts.append('<p class="mudo">Esta hunt nao tem lista de Codex.</p>')

    parts.append(h.source_line(hunt.get("fonte") or cat.source_of("hunts"), hunt.get("visto_em")))
    parts.append('<p><a href="index.html">&larr; todas as hunts</a></p>')
    return h.page("%s — Hunts — BaiakVault" % hunt["nome"], "".join(parts), root=root,
                  here="hunts", generated_at=generated_at)


# --- Charms ---------------------------------------------------------------------------
def _pct(value):
    """5 -> «5%», 1.6 -> «1,6%», None -> «?»."""
    if value is None:
        return h.UNKNOWN
    decimals = 1 if float(value) != int(float(value)) else 0
    return h.fmt(value, decimals, "%")


def _charm_rows(charms):
    rows = []
    for c in charms:
        chance = c.get("chance") or [None, None, None]
        points = c.get("points") or [None, None, None]
        element = c.get("element")
        rows.append([
            "<b>%s</b>" % h.esc(c.get("name")),
            h.esc(KIND_LABEL.get(c.get("kind"), c.get("kind"))),
            h.esc(ELEMENT_LABEL.get(element, element)) if element else '<span class="mudo">&mdash;</span>',
            " / ".join(_pct(x) for x in chance),
            " / ".join(h.fmt(x) for x in points),
            h.esc(c.get("desc")),
        ])
    return rows


def render_charms(cat, generated_at):
    root = "../"
    major = [c for c in cat.charms if c.get("category") == "major"]
    minor = [c for c in cat.charms if c.get("category") == "minor"]
    headers = ["charm", "tipo", "elemento", "chance T1 / T2 / T3", "pontos T1 / T2 / T3", "o que faz"]
    parts = ["<h1>Charms</h1>",
             '<p class="mudo">Os %d charms tal como estao no cliente do jogo: categoria, tipo, '
             "elemento, chance e custo em pontos por tier, e a descricao a letra. Cada charm "
             "prende-se a uma criatura do bestiario.</p>" % len(cat.charms),
             '<h2>Maiores <span class="marca major">%d</span></h2>' % len(major),
             h.table(headers, _charm_rows(major), numeric=(3, 4)),
             '<h2>Menores <span class="marca minor">%d</span></h2>' % len(minor),
             h.table(headers, _charm_rows(minor), numeric=(3, 4)),
             "<h2>Os charms dele</h2>",
             '<div class="cartao"><p class="mudo">Que charm por em que criatura para cada hunt, a '
             "partir dos charms que ele tem — chega na ordem 3. Ate la, os charms de cada "
             "personagem aparecem na pagina do personagem.</p></div>",
             '<p class="aviso">Os charm points que cada entrada do bestiario da <b>nao estao no '
             "cliente</b> (e o servidor que calcula); le-se no ecra dos Charms. Aqui fica «?» "
             "ate haver leitura.</p>",
             h.source_line(cat.source_of("bestiario"), cat.seen_at("bestiario"))]
    return h.page("Charms — BaiakVault", "".join(parts), root=root, here="charms",
                  generated_at=generated_at)


# --- Personagem -------------------------------------------------------------------------
def _goal_text(advice, character):
    goal = (advice or {}).get("goal") or character.get("goal")
    if not goal:
        return h.UNKNOWN
    text = h.esc(GOAL_LABEL.get(goal, goal))
    if (advice or {}).get("goal_defaulted"):
        text += ' <small class="mudo">(por omissao da vocacao; muda no modo de edicao)</small>'
    return text


def _suggestion_li(sug):
    cls = ' class="mudo"' if sug["kind"] == "missing" else ""
    return ('<li%s><b>%s</b><br>%s<br><small>custo: %s · fonte: %s</small></li>'
            % (cls, h.esc(sug["action"]), h.esc(sug["why"]), h.esc(sug.get("cost") or "—"), h.esc(sug["source"])))


def render_next_step(root, cat, advice):
    out = ["<h2>Proximo passo</h2>"]
    sugs = advice.get("suggestions") or []
    if not sugs:
        out.append('<div class="cartao"><p class="mudo">Nada a sugerir com o que esta registado.</p></div>')
        return "".join(out)
    out.append('<ol class="passos">%s</ol>' % "".join(_suggestion_li(sg) for sg in sugs))
    plan = advice.get("plan")
    if plan:
        cur, rec = advice["current"], plan["metrics"]
        out.append('<div class="cartao"><p class="mudo">Ganhos medidos no simulador com a tua arvore e o teu equipamento '
                   "registados, na hunt %s, na metrica «%s». A referencia e a "
                   '<a href="%sbuilds/%s.html">build %s %s</a> ao teu nivel exacto.%s%s</p>'
                   % (_hunt_link(root, cat, advice["hunt"]), h.esc(advice["metric"]), root,
                      pages_builds.slug(plan["vocation"], plan["goal"]), h.esc(VOCATION_LABEL[plan["vocation"]]),
                      h.esc(GOAL_LABEL[plan["goal"]]),
                      (" Notas: %s." % h.esc("; ".join(advice["notes"]))) if advice.get("notes") else "",
                      " Skill assumido pelo guia (o teu real substitui quando o registares)." if advice.get("assumed_skill") else ""))
        out.append(h.table(["", "a tua build", "a recomendada"], [
            ["metrica do objectivo", h.fmt(advice["current_score"], 1), h.fmt(advice["plan_score"], 1)],
            ["DPS do ciclo", h.fmt(cur["dps_cycle"]), h.fmt(rec["dps_cycle"])],
            ["EHP", h.fmt(cur["ehp"]), h.fmt(rec["ehp"])],
            ["cura/s sustentavel", h.fmt(cur["hps_self"]), h.fmt(rec["hps_self"])],
            ["aguenta o pack", pages_builds._seconds(cur["ttd_pack"]), pages_builds._seconds(rec["ttd_pack"])],
        ], numeric=(1, 2)) + "</div>")
    return "".join(out)


def render_tree_section(cat, character, tree, plan):
    out = ["<h3>Arvore</h3>"]
    level = character.get("level")
    if not tree:
        out.append('<p class="mudo">Sem nos registados — nao se sabe o que ja comprou.</p>')
        return "".join(out)
    rows = []
    spent = 0
    plan_tree = (plan or {}).get("tree") or {}
    his = {t["node_key"]: t["rank"] for t in tree}
    for t in sorted(tree, key=lambda x: (-(x["rank"] or 0), x["node_key"])):
        node = cat.node_by_id.get(t["node_key"]) or {}
        cost = F.tree_total_cost(node, t["rank"]) if node else None
        spent += cost or 0
        rec = plan_tree.get(t["node_key"])
        rows.append([h.esc(node.get("nome") or t["node_key"]),
                     "%s / %s" % (h.fmt(t["rank"]), h.fmt(node.get("rank_maximo"))),
                     "%s / %s" % (h.fmt(cost), h.fmt(node.get("custo_do_zero_ao_maximo"))),
                     h.fmt(rec) if rec else '<span class="mudo">—</span>',
                     h.esc(t["source"]), h.esc(t["seen_at"])])
    out.append(h.table(["no", "rank", "pontos gastos / ate ao maximo", "rank na recomendada", "fonte", "visto a"],
                       rows, numeric=(1, 2, 3)))
    budget = F.tree_budget(level) if level else None
    out.append('<p class="mudo"><small>%d nos registados, %s pontos gastos de %s que o nivel da. Os nos que nao '
               "estao aqui sao desconhecidos, nao zero.</small></p>" % (len(tree), h.fmt(spent), h.fmt(budget)))
    missing = sorted((k, r) for k, r in plan_tree.items() if r > his.get(k, 0))
    if missing:
        out.append('<p class="mudo"><small>A recomendada tem ainda: %s.</small></p>' % h.esc(", ".join(
            "%s %d" % ((cat.node_by_id.get(k) or {}).get("nome") or k, r) for k, r in missing)))
    return "".join(out)


def render_equipment_section(cat, equipment, plan):
    out = ["<h3>Equipamento</h3>"]
    if not equipment:
        out.append('<p class="mudo">Sem equipamento registado.</p>')
        return "".join(out)
    rows = []
    plan_eq = (plan or {}).get("equipment") or {}
    for e in equipment:
        item = cat.item_by_key.get(e["item_key"] or "") or {}
        imb = e["imbuements"]
        attrs = e.get("attributes")
        rec = plan_eq.get(e["slot"])
        rows.append([
            h.esc(advisor.SLOT_LABEL.get(e["slot"], e["slot"])),
            h.esc(e["item_name"] or e["item_key"]) if (e["item_name"] or e["item_key"]) else h.UNKNOWN,
            h.fmt(item.get("nivel")),
            h.fmt(e["upgrade_level"]),
            (h.esc(", ".join(str(x) for x in imb)) if imb else '<span class="mudo">nenhum</span>')
            if imb is not None else h.UNKNOWN,
            (h.esc(", ".join("%s %s" % (k, v) for k, v in attrs.items())) if attrs else '<span class="mudo">nenhum</span>')
            if attrs is not None else h.UNKNOWN,
            h.esc(rec["item"]["nome"]) if rec else '<span class="mudo">—</span>',
            h.esc(e["source"]),
        ])
    out.append(h.table(["slot", "item", "nivel do item", "upgrade", "imbuements", "atributos", "na recomendada", "fonte"],
                       rows, numeric=(2, 3)))
    return "".join(out)


def render_character(cat, vault, character, generated_at, advice=None):
    root = "../"
    cid = character["id"]
    advice = advice or {"suggestions": [], "goal": character.get("goal"), "goal_defaulted": False}
    parts = ["<h1>%s</h1>" % h.esc(character["name"])]
    parts.append('<div class="cartao">' + h.kv([
        ("vocacao", h.esc(VOCATION_LABEL.get(character["vocation"], character["vocation"]))),
        ("nivel", h.fmt(character["level"])),
        ("hunt actual", _hunt_link(root, cat, character["current_hunt"]) if character["current_hunt"] else h.UNKNOWN),
        ("VIP", h.yes_no(character["vip"])),
        ("objectivo", _goal_text(advice, character)),
        ("notas", h.esc(character["notes"]) if character["notes"] else '<span class="mudo">—</span>'),
        ("fonte", h.esc(character["source"])),
        ("visto a", h.esc(character["seen_at"])),
        ("actualizado a", h.esc(character["updated_at"])),
    ]) + "</div>")
    parts.append(render_next_step(root, cat, advice))

    parts.append("<h2>Build actual</h2>")
    parts.append(render_tree_section(cat, character, vault.tree_of(cid), advice.get("plan")))
    parts.append(render_equipment_section(cat, vault.equipment_of(cid), advice.get("plan")))

    parts.append("<h3>Charms</h3>")
    points = vault.charm_points_of(cid)
    parts.append(h.kv([
        ("pontos disponiveis", h.fmt(points["points_available"]) if points else h.UNKNOWN),
        ("pontos gastos", h.fmt(points["points_spent"]) if points else h.UNKNOWN),
    ]))
    charms = vault.charms_of(cid)
    if charms:
        rows = []
        for c in charms:
            charm = cat.charm_by_key.get(c["charm_key"]) or {}
            creature = cat.creature_by_key.get(c["assigned_creature_key"] or "")
            rows.append([h.esc(charm.get("name") or c["charm_key"]),
                         h.fmt(c["tier"]),
                         h.esc(creature["nome"]) if creature else '<span class="mudo">sem criatura</span>',
                         h.esc(c["source"])])
        parts.append(h.table(["charm", "tier", "criatura", "fonte"], rows, numeric=(1,)))
    else:
        parts.append('<p class="mudo">Sem charms registados.</p>')

    parts.append("<h3>Bestiario</h3>")
    bestiary = vault.bestiary_of(cid)
    if bestiary:
        rows = []
        for b in sorted(bestiary, key=lambda x: -x["kills"]):
            creature = cat.creature_by_key.get(b["creature_key"]) or {}
            goal = creature.get("meta_kills")
            rows.append([h.esc(creature.get("nome") or b["creature_key"]),
                         h.fmt(b["kills"]), h.fmt(goal),
                         h.fmt(max(0, goal - b["kills"])) if goal is not None else h.UNKNOWN])
        parts.append(h.table(["criatura", "kills", "meta", "faltam"], rows, numeric=(1, 2, 3)))
    else:
        parts.append('<p class="mudo">Sem kills registados.</p>')

    parts.append("<h2>Leituras</h2>")
    readings = vault.readings_of(cid, limit=20)
    if readings:
        parts.append(h.table(
            ["quando", "nivel", "XP", "gold", "stamina (min)", "hunt", "fonte"],
            [[h.esc(r["at"]), h.fmt(r["level"]), h.fmt(r["xp"]), h.fmt(r["gold"]),
              h.fmt(r["stamina"]), _hunt_link(root, cat, r["hunt"]) if r["hunt"] else h.UNKNOWN,
              h.esc(r["source"])] for r in readings], numeric=(1, 2, 3, 4)))
    else:
        parts.append('<p class="mudo">Sem leituras de estado. Sem duas leituras nao ha XP/h.</p>')
    parts.append('<p class="mudo"><small>Para corrigir ou completar: <code>py -m baiakvault serve</code> e abrir '
                 "<code>http://127.0.0.1:8774/editar/%s</code> no PC.</small></p>" % h.esc(character["slug"]))
    return h.page("%s — BaiakVault" % character["name"], "".join(parts), root=root,
                  generated_at=generated_at)


# --- escrever ---------------------------------------------------------------------------
def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def build_plans(cat, planner=None):
    """As 8 builds x 8 niveis pelo `builds.Planner` (uns 8 s). `{(voc, goal, level): build}`."""
    planner = planner or builds_module.Planner(cat)
    plans = {}
    for voc, goal in builds_module.BUILDS:
        for level in builds_module.LEVELS:
            plans[(voc, goal, level)] = planner.plan(voc, goal, level)
    return plans


def character_advice(cat, vault, character, planner):
    """O estado do personagem lido pelo `Vault` e passado ao motor puro."""
    cid = character["id"]
    state = advisor.state_from_rows(character, vault.tree_of(cid), vault.equipment_of(cid), vault.charms_of(cid),
                                    vault.charm_points_of(cid), vault.bestiary_of(cid))
    return advisor.advise(cat, state, planner)


def build(out_dir=None, db_path=None, catalog_dir=None, now=None, plans=None, with_builds=True, planner=None,
          cat=None):
    """Gera o site inteiro. Devolve `{"files": [...], "seconds": float, "out": Path}`.
    `plans`/`planner` ja calculados poupam os ~8 s do optimizador (os testes e o
    `serve` passam-nos); `with_builds=False` salta as paginas das builds (o `serve`
    regenera so o resto a cada escrita)."""
    started = time.perf_counter()
    out = Path(out_dir or DEFAULT_OUT)
    cat = cat or catalog_module.load(catalog_dir)
    planner = planner or builds_module.Planner(cat)
    conn = db_module.connect(db_path)
    try:
        vault = db_module.Vault(conn, cat)
        generated_at = (now or datetime.now()).replace(microsecond=0).isoformat(sep=" ")
        characters = vault.characters()
        written = []
        written.append(_write(out / "estilo.css", h.CSS))
        written.append(_write(out / ".nojekyll", ""))
        advice_by_slug = {c["slug"]: character_advice(cat, vault, c, planner) for c in characters}
        written.append(_write(out / "index.html", render_index(cat, characters, generated_at, advice_by_slug)))
        written.append(_write(out / "hunts" / "index.html", render_hunts_index(cat, generated_at)))
        for hunt in cat.hunts:
            written.append(_write(out / "hunts" / (hunt["id"] + ".html"),
                                  render_hunt(cat, hunt, generated_at)))
        written.append(_write(out / "charms" / "index.html", render_charms(cat, generated_at)))
        for c in characters:
            written.append(_write(out / "personagens" / (c["slug"] + ".html"),
                                  render_character(cat, vault, c, generated_at, advice_by_slug[c["slug"]])))
        if with_builds:
            plans = plans or build_plans(cat, planner)
            written.append(_write(out / "builds" / "index.html", pages_builds.render_index(cat, plans, generated_at)))
            for voc, goal in builds_module.BUILDS:
                by_level = {lv: plans[(voc, goal, lv)] for lv in builds_module.LEVELS}
                written.append(_write(out / "builds" / (pages_builds.slug(voc, goal) + ".html"),
                                      pages_builds.render_build(cat, voc, goal, by_level, generated_at)))
                for lv in builds_module.LEVELS:
                    written.append(_write(out / "print" / ("helper-%s-%d.html" % (pages_builds.slug(voc, goal), lv)),
                                          pages_builds.render_print(cat, plans[(voc, goal, lv)], generated_at)))
            md = VALIDATION_MD if VALIDATION_MD.is_file() else (out / "builds" / "validacao.md")
            if md.is_file():
                text = md.read_text(encoding="utf-8")
                if md != out / "builds" / "validacao.md":
                    written.append(_write(out / "builds" / "validacao.md", text))
                written.append(_write(out / "builds" / "validacao.html",
                                      pages_builds.render_validation(text, generated_at)))
    finally:
        conn.close()
    return {"files": written, "seconds": time.perf_counter() - started, "out": out,
            "characters": len(characters), "hunts": len(cat.hunts)}
