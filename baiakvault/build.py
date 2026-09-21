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
from . import charms as charms_module
from . import db as db_module
from . import formulas as F
from . import html as h
from . import notes
from . import pages_builds
from . import pages_charms

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "docs"
# A validacao cruzada (`docs/builds/validacao.md`) e gerada pelo build a partir de `validation.py`
# (contas a mao vs simulador, curva do guia, discordancias guia/cliente) — ate 16/09/2026 era um
# placeholder a apontar para um script que nunca existiu.
# As regras dos charms (lidas no cliente, com fonte) tambem sao escritas a mao e vivem no repo.
CHARMS_MD = DEFAULT_OUT / "charms.md"
# Cartoes de print dos charms: a hunt actual de cada personagem mais estas vizinhas em nivel
# (nao se geram 79 x N cartoes).
PRINT_NEIGHBOURS = 5

VOCATION_LABEL = {"knight": "Knight (EK)", "monk": "Monk", "paladin": "Paladin (RP)",
                  "sorcerer": "Sorcerer (MS)", "druid": "Druid (ED)"}
GOAL_LABEL = {"priority": builds_module.PRIORITY_ASKED,
              "best": "melhor (equilibrada: aguenta e sustenta a mana)", "damage": "dano (DPS do ciclo = XP/h; o custo nao conta)",
              "tank": "tank (sobreviver)", "heal": "cura", "support": "support"}
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
                     "<p>Como adicionar: no PC, <code>py -m baiakvault serve</code> e abrir "
                     "<code>http://127.0.0.1:8774/editar</code> (formulario); ou guardar um Win+Shift+S do "
                     "painel, da arvore, do equipamento ou do bestiario/charms em <code>capturas\\</code> — a "
                     "tarefa <code>baiakvault-leitura</code> le-o de 30 em 30 min. A BD esta vazia de "
                     "proposito: nao se inventam personagens.</p></div>")
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
    default_goal = builds_module.DEFAULT_GOAL
    links = " · ".join('<a href="builds/%s-%s.html">%s</a>' % (voc, default_goal, h.esc(VOCATION_LABEL[voc]))
                       for voc, goal in builds_module.BUILDS if goal == default_goal)
    parts.append('<ul><li><a href="builds/index.html">Builds</a> — a build das <b>prioridades do Andre</b> de cada '
                 "vocacao (%s): a arvore pela ordem estrita Avatar › Exp › Loot › Crit › Ataque › Dano critico › "
                 "Elemento › o que sobrar (decisao do Andre, 21/09/2026), com a build de <b>dano</b> (o maior DPS do "
                 "ciclo = XP/h, sem tecto de gold — decisao de 16/09/2026) ao lado em numero — por nivel: arvore por "
                 "ordem de compra e etapa, codigo para importar, equipamento BiS, rotacao do Helper com o gold/h e "
                 "numeros do simulador; a build «melhor» (equilibrada) e as builds por objectivo (tank, cura, "
                 'support) ficam la tambem; <a href="builds/validacao.html">validacao cruzada</a> com o guia</li>' % links)
    parts.append('<li><a href="hunts/index.html">Hunts</a> — as %d hunts pelos indices do jogo</li>'
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


def render_hunt(cat, hunt, generated_at, charm_section="", helper_plans=None):
    """`helper_plans` = [(personagem, plano do Planner nesta hunt)] — os personagens
    dele com esta hunt como actual (o plano ja vem do advisor, nao se recalcula)."""
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

    parts.append(charm_section)
    parts.append(pages_builds.render_hunt_helper(cat, hunt, helper_plans or [], "../"))

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
def render_charms(cat, generated_at, characters=(), states=None, advice_by_slug=None):
    """O guia dos 24 + «os teus charms» (ordem 3: `pages_charms`)."""
    return pages_charms.render_index(cat, list(characters), states or {}, advice_by_slug or {}, generated_at)


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


def _tree_diff_block(cat, character, plan, diff):
    """O codigo da arvore recomendada (com «Copiar» e o custo de importar pelos pontos que
    a BD diz que ele tem gastos) e a diferenca para a dele, em pontos e em gold."""
    if not plan or not diff:
        return ""
    out = [pages_builds.code_block(diff["code"], "codigo-%s" % character["slug"], spent_now=diff.get("his_spent"),
                                   spent_label=None if diff.get("his_spent") is not None else
                                   "cola o codigo Exportar da tua arvore em /editar e o custo aparece")]
    if not diff["known"]:
        return "".join(out)
    if diff["same"]:
        out.append('<p class="ok">A tua arvore ja e a recomendada.</p>')
        return "".join(out)
    rows = []
    for nid, name, a, b, pts in diff["add"]:
        rows.append([h.esc(name), "%d → %d" % (a, b), "+%d" % pts])
    for nid, name, a, b, pts in diff["remove"]:
        rows.append([h.esc(name), "%d → %d" % (a, b), "−%d" % pts])
    out.append('<p class="mudo">Da tua arvore para a recomendada: <b>%d pontos a subir</b> em %d nos e <b>%d a tirar</b> '
               "em %d nos; importar o codigo faz tudo de uma vez por <b>%s gold</b> (cliente fD, pelos %d pontos que "
               "tens gastos).</p>" % (diff["points_add"], len(diff["add"]), diff["points_remove"], len(diff["remove"]),
                                      h.kk(diff["gold"]), diff["his_spent"]))
    out.append(h.table(["no", "rank (tua → recomendada)", "pontos"], rows, numeric=(2,)))
    return "".join(out)


def _recommended_tree_block(cat, plan):
    """A arvore recomendada ao nivel exacto dele, na moldura das builds (ordem de compra por
    etapas, papeis, totais por categoria, Avatar, «contra a build de dano») — sem o codigo,
    que vai no bloco a seguir com o custo de importar pelos pontos que a BD diz que ele tem."""
    if not plan:
        return ""
    return ('<div class="cartao"><h4>A arvore recomendada ao teu nivel (%s, nivel %d, em %s)</h4>%s</div>'
            % (h.esc(GOAL_LABEL.get(plan["goal"], plan["goal"])), plan["level"], h.esc(cat.hunt_by_id[plan["hunt"]]["nome"]),
               pages_builds._tree_block(cat, plan, root="../", with_code=False)))


def render_tree_section(cat, character, tree, plan, diff=None):
    out = ["<h3>Arvore</h3>"]
    level = character.get("level")
    if not tree:
        out.append('<p class="mudo">Sem nos registados — nao se sabe o que ja comprou. A forma exacta de a registar: '
                   "na arvore do jogo, <b>Exportar</b> (copia um codigo) e colar em "
                   "<code>http://127.0.0.1:8774/editar/%s</code>, seccao Arvore.</p>" % h.esc(character["slug"]))
        out.append(_recommended_tree_block(cat, plan))
        out.append(_tree_diff_block(cat, character, plan, diff))
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
    if character.get("vocation") and level:
        chk = builds_module.tree_check(cat, character["vocation"], level, his)
        out.append('<p class="mudo"><small>A tua arvore pelas regras do cliente: %s; %s; %s de %s pontos%s.</small></p>' % (
            "ligada a partir do tier 0" if chk["connected"] else "<b>nao ligada ao tier 0</b> (falta registar um no do caminho?)",
            "ranks ≤ maximo" if chk["max_rank_ok"] else "<b>rank acima do maximo</b>",
            h.fmt(chk["spent"]), h.fmt(chk["budget"]), "" if chk["ok"] else " — ⚠"))
    out.append(_recommended_tree_block(cat, plan))
    out.append(_tree_diff_block(cat, character, plan, diff))
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
            # a linha existe sem item: ele disse que o slot esta vazio (nao e «nao sei»)
            h.esc(e["item_name"] or e["item_key"]) if (e["item_name"] or e["item_key"]) else '<span class="mudo">vazio</span>',
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


def render_character(cat, vault, character, generated_at, advice=None, charm_section=""):
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
    plan = advice.get("plan")
    if plan:
        parts.append(render_rotation_section(cat, root, character, plan))

    parts.append("<h2>Build actual</h2>")
    parts.append(render_tree_section(cat, character, vault.tree_of(cid), plan, advice.get("tree_diff")))
    parts.append(render_equipment_section(cat, vault.equipment_of(cid), plan))

    parts.append("<h3>Charms</h3>")
    points = vault.charm_points_of(cid) or {}
    parts.append(h.kv([
        ("pontos disponiveis", h.fmt(points.get("points_available"))),
        ("pontos gastos", h.fmt(points.get("points_spent"))),
        ("echoes (menores)", h.fmt(points.get("echoes"))),
        ("limite de criaturas com charm", h.fmt(points.get("slot_limit"))),
        ("Charm Expansion", h.yes_no(points.get("expansion"))),
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
    parts.append(charm_section)

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
    return h.page("%s — BaiakVault" % character["name"], "".join(parts) + pages_builds.CODE_JS, root=root,
                  generated_at=generated_at)


def print_card_name(slug):
    return "helper-personagem-%s.html" % slug


def render_rotation_section(cat, root, character, plan):
    """A rotacao do personagem: a fixada por ele (com a do optimizador ao lado, em
    numero) ou a do optimizador; e o cartao print do Helper dele."""
    out = ["<h2>Rotacao e Helper</h2>"]
    if plan.get("fixed_rotation"):
        out.append(pages_builds.fixed_rotation_note(plan))
    else:
        out.append('<p class="mudo">Sem rotacao fixada: a do Helper abaixo e a que o optimizador escolhe (fixa a tua em '
                   "<code>/editar/%s</code>, seccao Rotacao, e a arvore recomendada passa a ser para ela).</p>" % h.esc(character["slug"]))
    hc = plan["helper"]
    out.append(h.kv([
        ("hunt", h.esc(", ".join(n for n, w, mm in hc["hunt_rotation"]))),
        ("boss", h.esc(", ".join(n for n, w, mm in hc["boss_rotation"]))),
        ("gold/h (pocoes + runas)", "%s / %s" % (h.kk(plan["metrics"]["gold_per_hour"]), h.kk(plan["metrics"]["boss_gold_per_hour"]))),
    ]))
    out.append('<p><a href="%sprint/%s">cartao do Helper para copiar (390 px)</a> — com a rotacao fixada, se a fixaste.</p>'
               % (root, print_card_name(character["slug"])))
    return "".join(out)


# --- escrever ---------------------------------------------------------------------------
def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def build_plans(cat, planner=None):
    """As builds (5 «best» + 8 por objectivo) x 8 niveis pelo `builds.Planner`. `{(voc, goal, level): build}`."""
    planner = planner or builds_module.Planner(cat)
    plans = {}
    for voc, goal in builds_module.BUILDS:
        for level in builds_module.LEVELS:
            plans[(voc, goal, level)] = planner.plan(voc, goal, level)
    return plans


def character_state(cat, vault, character):
    """O estado do personagem lido pelo `Vault`, no formato do motor puro."""
    cid = character["id"]
    return advisor.state_from_rows(character, vault.tree_of(cid), vault.equipment_of(cid), vault.charms_of(cid),
                                   vault.charm_points_of(cid), vault.bestiary_of(cid))


def character_advice(cat, vault, character, planner):
    return advisor.advise(cat, character_state(cat, vault, character), planner)


def ceiling_owner(level):
    """O tecto de uma hunt: todos os charms ao tier 3, requisitos do equipamento
    assumidos; HP/mana do dono desconhecidos (Overpower/Overflux ficam «?»)."""
    own = charms_module.owner(level=level, charms=None)
    own["assume_requirements"] = True
    return own


def charm_recommendations(cat, characters, states, advice_by_slug):
    """Por personagem: {hunt_id: rec} para as 79 hunts, mais os cartoes a imprimir
    (hunt actual + vizinhas). Devolve `(recs_by_slug, print_keys)`."""
    recs = {}
    print_keys = set()
    for c in characters:
        slug = c["slug"]
        state = states[slug]
        advice = advice_by_slug.get(slug) or {}
        own = charms_module.owner_from_state(state, advice.get("profile"), advice.get("equipment_known", False))
        if state.get("level") is None:
            recs[slug] = {}
            continue
        recs[slug] = {hunt["id"]: charms_module.recommend(cat, own, hunt["id"]) for hunt in cat.hunts}
        wanted = charms_module.neighbour_hunts(cat, state["level"], state.get("current_hunt"), PRINT_NEIGHBOURS)
        if state.get("current_hunt"):
            wanted = [state["current_hunt"]] + wanted
        for hid in wanted:
            recs[slug][hid]["_print"] = True
            print_keys.add((slug, hid))
    return recs, print_keys


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
        states = {c["slug"]: character_state(cat, vault, c) for c in characters}
        advice_by_slug = {c["slug"]: advisor.advise(cat, states[c["slug"]], planner) for c in characters}
        recs, print_keys = charm_recommendations(cat, characters, states, advice_by_slug)
        written.append(_write(out / "index.html", render_index(cat, characters, generated_at, advice_by_slug)))
        written.append(_write(out / "hunts" / "index.html", render_hunts_index(cat, generated_at)))
        for hunt in cat.hunts:
            level = hunt.get("nivel_minimo") or builds_module.MIN_LEVEL
            ceiling = charms_module.recommend(cat, ceiling_owner(level), hunt["id"])
            ceiling["_level"] = level
            per_character = [(c, recs[c["slug"]][hunt["id"]]) for c in characters if hunt["id"] in recs[c["slug"]]]
            section = pages_charms.render_hunt_section(cat, "../", per_character, ceiling)
            helper_plans = [(c, advice_by_slug[c["slug"]]["plan"]) for c in characters
                            if c.get("current_hunt") == hunt["id"] and advice_by_slug[c["slug"]].get("plan")]
            written.append(_write(out / "hunts" / (hunt["id"] + ".html"),
                                  render_hunt(cat, hunt, generated_at, section, helper_plans)))
        written.append(_write(out / "charms" / "index.html", render_charms(cat, generated_at, characters, states, advice_by_slug)))
        md = CHARMS_MD if CHARMS_MD.is_file() else (out / "charms.md")
        if md.is_file():
            text = md.read_text(encoding="utf-8")
            if md != out / "charms.md":
                written.append(_write(out / "charms.md", text))
            written.append(_write(out / "charms" / "regras.html", pages_charms.render_rules(text, generated_at)))
        for c in characters:
            slug = c["slug"]
            by_hunt = recs[slug]
            current = by_hunt.get(c["current_hunt"]) if c.get("current_hunt") else None
            neighbours = [(cat.hunt_by_id[hid], by_hunt[hid]) for hid in
                          charms_module.neighbour_hunts(cat, c.get("level") or 0, c.get("current_hunt"), PRINT_NEIGHBOURS)
                          if hid in by_hunt]
            section = pages_charms.render_character_section(cat, "../", c, current, neighbours, bool(by_hunt))
            written.append(_write(out / "personagens" / (slug + ".html"),
                                  render_character(cat, vault, c, generated_at, advice_by_slug[slug], section)))
            if advice_by_slug[slug].get("plan"):
                # o cartao do Helper dele, com a rotacao que fixou (ordem 8)
                written.append(_write(out / "print" / print_card_name(slug),
                                      pages_builds.render_print(cat, advice_by_slug[slug]["plan"], generated_at, name=c["name"])))
            for hid in sorted(hid for s, hid in print_keys if s == slug):
                written.append(_write(out / "print" / ("charms-%s-%s.html" % (slug, hid)),
                                      pages_charms.render_print(cat, c, by_hunt[hid], generated_at)))
        if with_builds:
            plans = plans or build_plans(cat, planner)
            written.append(_write(out / "builds" / "index.html", pages_builds.render_index(cat, plans, generated_at)))
            for voc, goal in builds_module.BUILDS:
                by_level = {lv: plans[(voc, goal, lv)] for lv in builds_module.LEVELS}
                charm_blocks = {lv: pages_charms.render_build_charms(
                    cat, charms_module.recommend(cat, charms_module.owner_from_plan(b), b["hunt"]), "../")
                    for lv, b in by_level.items()}
                written.append(_write(out / "builds" / (pages_builds.slug(voc, goal) + ".html"),
                                      pages_builds.render_build(cat, voc, goal, by_level, generated_at, charm_blocks)))
                for lv in builds_module.LEVELS:
                    written.append(_write(out / "print" / ("helper-%s-%d.html" % (pages_builds.slug(voc, goal), lv)),
                                          pages_builds.render_print(cat, plans[(voc, goal, lv)], generated_at)))
            # §1e (ordem 10): o critico a mao contra o simulador no sorcerer dele (rotacao fixada)
            sorcerer = next((advice_by_slug[c["slug"]]["plan"] for c in characters
                             if c.get("vocation") == "sorcerer" and advice_by_slug[c["slug"]].get("plan")
                             and (advice_by_slug[c["slug"]]["plan"].get("priority") or {}).get("stat_report")), None)
            text = pages_builds.validation_markdown(cat, plans, sorcerer_plan=sorcerer)
            written.append(_write(out / "builds" / "validacao.md", text))
            written.append(_write(out / "builds" / "validacao.html",
                                  pages_builds.render_validation(text, generated_at)))
        removed = _prune(out, written, with_builds)
    finally:
        conn.close()
    return {"files": written, "removed": removed, "seconds": time.perf_counter() - started, "out": out,
            "characters": len(characters), "hunts": len(cat.hunts)}


# O que o gerador e dono de apagar: paginas que so existem por causa de um personagem
# (apagado, renomeado ou com outra hunt) ficavam em docs/ e iam para o Pages (16/09/2026).
_OWNED = (("personagens", "*.html", False), ("print", "charms-*.html", False), ("print", "helper-personagem-*.html", False),
          ("hunts", "*.html", False), ("print", "helper-*.html", True), ("builds", "*.html", True))


def _prune(out, written, with_builds):
    keep = {p.resolve() for p in written}
    removed = []
    for folder, pattern, only_with_builds in _OWNED:
        if only_with_builds and not with_builds:
            continue
        for path in sorted((out / folder).glob(pattern)):
            if path.resolve() not in keep and path.is_file():
                path.unlink()
                removed.append(path)
    return removed
