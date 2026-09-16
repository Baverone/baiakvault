"""As paginas dos charms: o guia dos 24 com «os teus charms», as regras
(`docs/charms.md` -> HTML), a seccao «Charms para esta hunt» das hunts, a
seccao «Charms» do personagem, o bloco por nivel das builds e o cartao de
print para copiar para o jogo. So HTML; a logica esta em `charms.py`.
"""
from . import advisor
from . import charms as C
from . import html as h
from . import pages_builds

KIND_LABEL = {"offensive": "ofensivo", "defensive": "defensivo", "passive": "passivo"}
ELEMENT_LABEL = {"physical": "fisico", "fire": "fogo", "earth": "terra", "ice": "gelo",
                 "energy": "energia", "death": "morte", "holy": "sagrado"}
CATEGORY_LABEL = {"major": "maior", "minor": "menor"}

PRINT_CSS = """\
body{margin:0;background:#fff;color:#111;font:13px/1.35 system-ui,-apple-system,"Segoe UI",sans-serif}
.card{width:390px;padding:10px 12px;box-sizing:border-box}
h1{font-size:15px;margin:0 0 2px}h2{font-size:12px;margin:10px 0 4px;color:#444;text-transform:uppercase;letter-spacing:.3px}
table{width:100%;border-collapse:collapse;font-size:12px}td,th{padding:3px 4px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}
th{color:#555;font-weight:600}small{color:#666;font-size:11px}b{font-weight:700}
ul{margin:2px 0;padding-left:16px}.mv{color:#8a4b00}
"""


def _pct(value):
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


def _warn(text):
    return '<span class="aviso">%s</span>' % h.esc(text)


# --- regras -------------------------------------------------------------------------------------
def render_rules(md_text, generated_at):
    body = pages_builds.markdown_to_html(md_text)
    body += '<p><a href="index.html">&larr; charms</a></p>'
    return h.page("Regras dos charms — BaiakVault", body, root="../", here="charms", generated_at=generated_at)


# --- o guia + os teus charms --------------------------------------------------------------------------
def _next_charm_text(cat, state, goal):
    sugs = advisor.charm_suggestions(cat, state, goal) if goal else []
    if not sugs:
        return '<span class="mudo">nada a sugerir</span>'
    s = sugs[0]
    return "<b>%s</b> <small class=\"mudo\">%s · custo: %s</small>" % (h.esc(s["action"]), h.esc(s["why"]), h.esc(s.get("cost") or "—"))


def render_index(cat, characters, states, advice_by_slug, generated_at):
    """`characters` sao as linhas da BD; `states` {slug: estado do advisor}."""
    major = [c for c in cat.charms if c.get("category") == "major"]
    minor = [c for c in cat.charms if c.get("category") == "minor"]
    headers = ["charm", "tipo", "elemento", "chance T1 / T2 / T3", "pontos T1 / T2 / T3", "o que faz"]
    parts = ["<h1>Charms</h1>",
             '<p class="mudo">Os %d charms tal como estao no cliente do jogo: categoria, tipo, elemento, '
             "chance e custo por tier, e a descricao a letra. Cada charm prende-se a <b>uma</b> criatura do "
             "bestiario; uma criatura leva um maior e um menor; ha um limite de criaturas com charm (2, 6 com VIP, "
             "25 com a Charm Expansion); um maior exige o bestiario da criatura fechado. Os maiores pagam-se em "
             "Charm Points, os menores em echoes (que vem de subir maiores). "
             '<a href="regras.html">As regras todas, com a fonte de cada uma</a>.</p>' % len(cat.charms),
             '<h2>Maiores <span class="marca major">%d</span></h2>' % len(major),
             h.table(headers, _charm_rows(major), numeric=(3, 4)),
             '<h2>Menores <span class="marca minor">%d</span></h2>' % len(minor),
             h.table(headers, _charm_rows(minor), numeric=(3, 4)),
             "<h2>Os teus charms</h2>"]
    if not characters:
        parts.append('<div class="cartao"><p class="mudo">Sem personagens na BD. Quando houver, aqui aparecem os charms '
                     "de cada um (tier, pontos, echoes, limite) e o proximo a subir.</p></div>")
    for ch in characters:
        state = states.get(ch["slug"]) or {}
        advice = advice_by_slug.get(ch["slug"]) or {}
        points = state.get("charm_points") or {}
        own = C.owner_from_state(state)
        limit, limit_source = C.slot_limit(own)
        have = {c["charm_key"]: c for c in state.get("charms") or []}
        rows = []
        for c in cat.charms:
            mine = have.get(c["key"])
            if not mine:
                continue
            creature = cat.creature_by_key.get(mine.get("assigned_creature_key") or "")
            tier = mine["tier"]
            nxt = (c.get("points") or [None] * 3)[tier] if tier < C.MAX_TIER else None
            rows.append([h.esc(c["name"]), h.esc(CATEGORY_LABEL.get(c["category"], c["category"])),
                         "%s / %d — %s" % (h.fmt(tier), C.MAX_TIER, _pct((c.get("chance") or [None] * 3)[tier - 1])),
                         h.esc(creature["nome"]) if creature else '<span class="mudo">sem criatura</span>',
                         ("%s %s" % (h.fmt(nxt), "pontos" if c["category"] == "major" else "echoes")) if nxt else '<span class="mudo">maximo</span>'])
        parts.append('<div class="cartao"><h3><a href="../personagens/%s.html">%s</a></h3>%s%s%s</div>' % (
            h.esc(ch["slug"]), h.esc(ch["name"]),
            h.kv([
                ("charms desbloqueados", "%d de %d" % (len(rows), len(cat.charms))),
                ("charm points disponiveis / gastos", "%s / %s" % (h.fmt(points.get("points_available")), h.fmt(points.get("points_spent")))),
                ("echoes (para os menores)", h.fmt(points.get("echoes"))),
                ("limite de criaturas com charm", "%s <small class=\"mudo\">(%s)</small>" % (h.fmt(limit), h.esc(limit_source))),
                ("proximo a desbloquear / subir", _next_charm_text(cat, state, advice.get("goal") or state.get("goal"))),
                ("charms por hunt", '<a href="../personagens/%s.html#charms">na pagina do personagem</a>' % h.esc(ch["slug"])),
            ]),
            h.table(["charm", "cat.", "tier — chance", "criatura atribuida agora", "proximo tier custa"], rows, numeric=(4,)) if rows
            else '<p class="mudo">Sem charms registados.</p>',
            ""))
    parts.append('<p class="aviso">Os charm points que cada entrada do bestiario da <b>nao estao no cliente</b> (e o '
                 "servidor que calcula); le-se no ecra dos Charms. Aqui fica «?» ate haver leitura.</p>")
    parts.append(h.source_line(cat.source_of("bestiario"), cat.seen_at("bestiario")))
    return h.page("Charms — BaiakVault", "".join(parts), root="../", here="charms", generated_at=generated_at)


# --- a recomendacao em HTML ---------------------------------------------------------------------------
def assignment_table(rec, with_current=True):
    rows = []
    for a in rec["assignments"]:
        current = a.get("current_creature_key")
        why = h.esc(a["why"])
        if a.get("warns"):
            why += " " + " ".join(_warn(w) for w in a["warns"])
        row = ["<b>%s</b> <small class=\"mudo\">T%s %s</small>" % (h.esc(a["name"]), h.fmt(a["tier"]), _pct(a.get("chance"))),
               "<b>%s</b>" % h.esc(a["creature_name"]), why]
        if with_current:
            if current == a["creature_key"]:
                row.append('<span class="mudo">ja esta</span>')
            elif current is None:
                row.append("atribuir")
            else:
                row.append("mover de %s" % h.esc((rec.get("_names") or {}).get(current, current)))
        rows.append(row)
    headers = ["charm", "criatura", "porque"] + (["hoje"] if with_current else [])
    if rows:
        return h.table(headers, rows)
    if not rec.get("owned"):
        return '<p class="mudo">Sem charms registados: nada a atribuir (modo de edicao, seccao Charms).</p>'
    return '<p class="mudo">Nenhum charm com lugar nesta hunt.</p>'


def _grouped_left_out(rec):
    """[(nomes, razao)] — a mesma razao agrupa os charms (o tecto deixa 7 maiores de fora pela mesma razao)."""
    groups = []
    for x in rec["left_out"]:
        for g in groups:
            if g[1] == x["reason"]:
                g[0].append(x["name"])
                break
        else:
            groups.append(([x["name"]], x["reason"]))
    return groups


def left_out_list(rec):
    if not rec["left_out"]:
        return ""
    return '<p class="mudo"><small>Fica de fora: %s.</small></p>' % "; ".join(
        "<b>%s</b> — %s" % (h.esc(", ".join(names)), h.esc(reason)) for names, reason in _grouped_left_out(rec))


def changes_list(rec):
    ch = [c for c in rec["changes"] if c["kind"] != "keep"]
    if not rec["changes"]:
        return ""
    if not ch:
        return '<p class="mudo">Nada a mudar: o que tens atribuido e o recomendado.</p>'
    items = []
    for c in ch:
        if c["kind"] == "move":
            items.append("<li><b>%s</b>: mover de %s para <b>%s</b> <small class=\"mudo\">(~%s gold)</small></li>"
                         % (h.esc(c["name"]), h.esc(c["from"]), h.esc(c["to"]), h.fmt(c["gold"])))
        elif c["kind"] == "assign":
            items.append("<li><b>%s</b>: atribuir a <b>%s</b> <small class=\"mudo\">(gratis, esta livre)</small></li>"
                         % (h.esc(c["name"]), h.esc(c["to"])))
        else:
            items.append("<li><b>%s</b> fica em %s%s</li>" % (
                h.esc(c["name"]), h.esc(c["from"]),
                " (nao e desta hunt: nao faz nada aqui, mas nao ha lugar melhor)" if not c.get("in_hunt") else ""))
    return "<b>O que mudar:</b><ul>%s</ul>" % "".join(items)


def notes_list(rec):
    if not rec["notes"]:
        return ""
    return '<p class="mudo"><small>%s.</small></p>' % "; ".join(h.esc(n) for n in rec["notes"])


def _with_names(cat, rec):
    rec["_names"] = {c["chave"]: c["nome"] for c in cat.creatures}
    return rec


def render_recommendation(cat, rec, with_current=True, title=None):
    _with_names(cat, rec)
    out = []
    if title:
        out.append("<h3>%s</h3>" % title)
    if rec["limit"] is not None:
        out.append('<p class="mudo"><small>Limite: %s criaturas com charm (%s); usadas aqui: %d.</small></p>'
                   % (h.fmt(rec["limit"]), h.esc(rec["limit_source"]), len(rec["used"])))
    out.append(assignment_table(rec, with_current))
    out.append(left_out_list(rec))
    if with_current:
        out.append(changes_list(rec))
    out.append(notes_list(rec))
    return "".join(out)


# --- seccoes -------------------------------------------------------------------------------------------
def render_hunt_section(cat, root, per_character, ceiling):
    """`per_character` = [(personagem, rec)], `ceiling` = rec com todos os charms (tecto)."""
    out = ["<h2>Charms para esta hunt</h2>"]
    if per_character:
        for ch, rec in per_character:
            title = ('<a href="%spersonagens/%s.html">%s</a> — com os charms que tens registados'
                     % (root, h.esc(ch["slug"]), h.esc(ch["name"])))
            card = render_recommendation(cat, rec, True, title)
            if rec.get("_print"):
                card += ('<p><small><a href="%sprint/charms-%s-%s.html">cartao para copiar para o jogo</a></small></p>'
                         % (root, h.esc(ch["slug"]), h.esc(rec["hunt_id"])))
            out.append('<div class="cartao">%s</div>' % card)
    else:
        out.append('<p class="mudo">Sem personagens na BD; fica so o tecto.</p>')
    out.append('<details><summary>Tecto: todos os 24 charms ao tier 3 (nivel %s)</summary><div class="cartao">%s</div></details>'
               % (h.fmt(ceiling.get("_level")), render_recommendation(cat, ceiling, False)))
    out.append('<p class="mudo"><small>Regras e fontes: <a href="%scharms/regras.html">charms/regras</a>. O motor assume que o dano '
               "extra dos elementais respeita a resistencia do monstro (⚠ por confirmar).</small></p>" % root)
    return "".join(out)


def render_character_section(cat, root, character, rec_current, neighbours, printable):
    """`rec_current` pode ser None (sem hunt actual). `neighbours` = [(hunt, rec)]."""
    out = ['<h2 id="charms">Charms por hunt</h2>']
    if rec_current is not None:
        out.append('<div class="cartao">%s%s</div>' % (
            render_recommendation(cat, rec_current, True, "Hunt actual: %s" % h.esc(rec_current["hunt_name"])),
            ('<p><small><a href="%sprint/charms-%s-%s.html">cartao para copiar para o jogo</a></small></p>'
             % (root, h.esc(character["slug"]), h.esc(rec_current["hunt_id"]))) if printable else ""))
    else:
        out.append('<p class="mudo">Sem hunt actual registada — sem hunt nao ha criatura para escolher. '
                   "Abaixo, as hunts mais proximas do teu nivel.</p>")
    if neighbours:
        rows = []
        for hunt, rec in neighbours:
            first = rec["assignments"][:3]
            rows.append(['<a href="%shunts/%s.html">%s</a> (%s+)' % (root, h.esc(hunt["id"]), h.esc(hunt["nome"]), h.fmt(hunt.get("nivel_minimo"))),
                         h.esc("; ".join("%s → %s" % (a["name"], a["creature_name"]) for a in first)) or '<span class="mudo">—</span>',
                         h.fmt(sum(1 for c in rec["changes"] if c["kind"] in ("move", "assign"))),
                         '<a href="%sprint/charms-%s-%s.html">cartao</a>' % (root, h.esc(character["slug"]), h.esc(hunt["id"])) if printable else ""])
        out.append("<h3>Hunts vizinhas em nivel</h3>" + h.table(["hunt", "os primeiros charms", "mudancas", ""], rows, numeric=(2,)))
    out.append('<p class="mudo"><small>Cada hunt tem a tabela completa na sua pagina. Regras: '
               '<a href="%scharms/regras.html">charms/regras</a>.</small></p>' % root)
    return "".join(out)


def render_build_charms(cat, rec, root):
    """O bloco por nivel das builds: o tecto (todos os charms) na hunt de referencia."""
    _with_names(cat, rec)
    return ('<h3>Charms recomendados em <a href="%shunts/%s.html">%s</a> (tecto)</h3>'
            '<p class="mudo"><small>A build generica nao sabe que charms tens: isto e a atribuicao ideal com os 24 ao tier 3 '
            "e as estatisticas desta build (critico, roubo, HP). A tua pagina de personagem usa os teus.</small></p>%s%s%s"
            % (root, h.esc(rec["hunt_id"]), h.esc(rec["hunt_name"]), assignment_table(rec, False), left_out_list(rec), notes_list(rec)))


# --- cartao de print -------------------------------------------------------------------------------------
def render_print(cat, character, rec, generated_at):
    """390 px, sem menu, com os nomes que o jogo usa (charm e monstro em ingles)."""
    rows = []
    for a in rec["assignments"]:
        mark = ""
        if a.get("current_creature_key") == a["creature_key"]:
            mark = "<small>ja esta</small>"
        elif a.get("current_creature_key"):
            mark = '<small class="mv">mover</small>'
        rows.append("<tr><td><b>%s</b> <small>T%s</small></td><td>%s</td><td>%s</td></tr>"
                    % (h.esc(a["name"]), h.fmt(a["tier"]), h.esc(a["creature_name"]), mark))
    left = ""
    if rec["left_out"]:
        left = "<h2>Sem lugar / nao vale</h2><ul>%s</ul>" % "".join(
            "<li>%s <small>— %s</small></li>" % (h.esc(", ".join(names)), h.esc(reason)) for names, reason in _grouped_left_out(rec))
    moves = [c for c in rec["changes"] if c["kind"] == "move"]
    cost = ""
    if moves:
        cost = "<p><small>%d charm%s a mover, ~%s gold cada (1 000 x nivel).</small></p>" % (
            len(moves), "" if len(moves) == 1 else "s", h.fmt(moves[0]["gold"]))
    body = ('<div class="card"><h1>Charms — %s</h1><small>%s, nivel %s · limite %s criaturas · BaiakVault %s</small>'
            "<h2>Charm → monstro</h2><table><tr><th>charm</th><th>monstro</th><th></th></tr>%s</table>%s%s"
            "<p><small>%s</small></p></div>"
            % (h.esc(rec["hunt_name"]), h.esc(character["name"]), h.fmt(character.get("level")), h.fmt(rec["limit"]),
               h.esc(generated_at), "".join(rows) or '<tr><td colspan="3">nenhum charm com lugar</td></tr>', cost, left,
               h.esc("; ".join(rec["notes"])) if rec["notes"] else "estimativa do BaiakVault, nao medida no jogo"))
    return ("<!doctype html><html lang=\"pt\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" "
            "content=\"width=device-width,initial-scale=1\"><title>%s</title><style>%s</style></head><body>%s</body></html>"
            % (h.esc("Charms %s — %s — BaiakVault" % (character["name"], rec["hunt_name"])), PRINT_CSS, body))
