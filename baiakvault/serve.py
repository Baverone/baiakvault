"""`py -m baiakvault serve`: serve `docs/` e o modo de edicao em `/editar`.

Porto fixo 8774 (8770 riftvault, 8771 mtgvault, 8773 o Treinador antigo).
Bind 127.0.0.1 por defeito; `BAIAKVAULT_BIND=0.0.0.0` poe-o na rede de casa
para o telemovel: **ler e livre, escrever exige o token** de
`data/serve.token` (nasce no primeiro arranque, fica fora do git). A pagina
mete o token nos formularios quando e aberta do proprio PC; de fora, ha um
campo para o escrever (a pagina do PC mostra-o).

E a **unica porta de escrita** na `vault.db` (com o importador de capturas
da ordem 4, que usa a mesma camada `db.Vault`). Formularios simples, sem
JavaScript. Cada escrita valida contra o catalogo (chave desconhecida = erro
legivel, nada gravado), leva `source='manual'` e `seen_at`, e regenera o site
(sem as paginas das builds, que nao mudam com os dados dele).

Nada disto fala com o baiakidle.com.
"""
import datetime as dt
import http.server
import os
import secrets
import sqlite3
import threading
import urllib.parse
from pathlib import Path

from . import advisor
from . import build as build_module
from . import builds as builds_module
from . import catalog as catalog_module
from . import db as db_module
from . import formulas as F
from . import html as h
from . import treecode

PORT = 8774
LOCAL_ADDRESSES = ("127.0.0.1", "::1", "localhost")
TOKEN_PATH = Path(__file__).resolve().parent.parent / "data" / "serve.token"
VOCATION_LABEL = build_module.VOCATION_LABEL
GOAL_LABEL = build_module.GOAL_LABEL
SLOT_LABEL = advisor.SLOT_LABEL
FORM_SLOTS = ("weapon", "shield", "helmet", "armor", "legs", "boots", "amulet", "ring", "ammo", "backpack")
MAX_BODY = 500_000


class FormError(Exception):
    pass


def read_token(path=None):
    """O token de escrita. Nasce na primeira corrida, fora do git."""
    path = Path(path or TOKEN_PATH)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_urlsafe(18), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


# --- leitura dos campos ---------------------------------------------------------------------
def _one(fields, key, default=None):
    v = (fields.get(key) or [None])[0]
    if v is None:
        return default
    v = str(v).strip()
    return v if v != "" else default


def _int(fields, key, label=None):
    """Inteiro ou None. Em branco e «nao sei», nunca 0."""
    v = _one(fields, key)
    if v is None:
        return None
    try:
        return int(v.replace(".", "").replace(" ", ""))
    except ValueError:
        raise FormError("%s tem de ser um numero inteiro, nao %r" % (label or key, v))


def _float(fields, key, label=None):
    v = _one(fields, key)
    if v is None:
        return None
    try:
        return float(v.replace(",", "."))
    except ValueError:
        raise FormError("%s tem de ser um numero, nao %r" % (label or key, v))


def _checked(fields, key):
    return _one(fields, key) is not None


def _date(fields, key="seen_at"):
    v = _one(fields, key)
    if v is None:
        return None
    try:
        dt.date.fromisoformat(v[:10])
    except ValueError:
        raise FormError("a data «visto a» tem de ser AAAA-MM-DD, nao %r" % v)
    return v


# --- HTML dos formularios -------------------------------------------------------------------
def _options(pairs, selected=None, blank="?"):
    out = ['<option value="">%s</option>' % h.esc(blank)] if blank is not None else []
    for value, label in pairs:
        sel = ' selected' if str(value) == str(selected if selected is not None else "") else ""
        out.append('<option value="%s"%s>%s</option>' % (h.esc(value), sel, h.esc(label)))
    return "".join(out)


def _datalist(ident, names):
    return '<datalist id="%s">%s</datalist>' % (ident, "".join('<option value="%s">' % h.esc(n) for n in names))


def _token_field(local, token):
    if local:
        return '<input type="hidden" name="token" value="%s">' % h.esc(token)
    return ('<p><label>token (esta na pagina aberta no PC, ou em data/serve.token) '
            '<input name="token" size="26" required></label></p>')


def _form(action, body, local, token, button="Gravar", cls=""):
    return ('<form method="post" action="%s" class="edicao %s">%s%s<p><button>%s</button></p></form>'
            % (h.esc(action), cls, body, _token_field(local, token), h.esc(button)))


def _seen_at_field(value=None):
    value = value or dt.date.today().isoformat()
    return '<label>visto a <input type="date" name="seen_at" value="%s"></label>' % h.esc(value[:10])


def _msg(msg, err):
    out = []
    if err:
        out.append('<p class="aviso">Nao gravado: %s</p>' % h.esc(err))
    if msg:
        out.append('<p class="ok">%s</p>' % h.esc(msg))
    return "".join(out)


EDIT_CSS = """<style>
form.edicao{background:#171a20;border:1px solid #2a2f38;border-radius:8px;padding:8px 12px;margin:8px 0}
form.edicao label{display:inline-block;margin:2px 10px 2px 0}
form.edicao input[type=number]{width:5em}form.edicao input[type=text]{width:16em}
form.edicao table input[type=number]{width:4em}
.ok{color:#8fd18f}.aviso{color:#ffb86b}
details.seccao{margin:10px 0}details.seccao summary{font-size:16px;font-weight:600;cursor:pointer}
</style>"""


def page_index(cat, vault, local, token, msg=None, err=None):
    parts = ["<h1>Modo de edicao</h1>",
             '<p class="mudo">A unica porta de escrita na vault.db. Tudo o que gravares leva fonte «manual» e a data '
             "«visto a». Em branco quer dizer «nao sei» e fica NULL — nunca 0.</p>", _msg(msg, err)]
    chars = vault.characters()
    if chars:
        parts.append("<ul>%s</ul>" % "".join(
            '<li><a href="/editar/%s">%s</a> <small class="mudo">%s, nivel %s · <a href="/personagens/%s.html">pagina</a></small></li>'
            % (h.esc(c["slug"]), h.esc(c["name"]), h.esc(VOCATION_LABEL.get(c["vocation"], c["vocation"])),
               h.fmt(c["level"]), h.esc(c["slug"])) for c in chars))
    else:
        parts.append('<p class="mudo">Ainda nao ha personagens.</p>')
    parts.append("<h2>Novo personagem</h2>")
    parts.append(_form("/editar/novo",
                       '<p><label>nome <input type="text" name="name" required></label>'
                       '<label>vocacao <select name="vocation">%s</select></label></p>'
                       % _options([(v, VOCATION_LABEL[v]) for v in db_module.GOALS_BY_VOCATION]),
                       local, token, "Criar"))
    if local and token:
        parts.append('<p class="mudo"><small>Token para escrever a partir do telemovel: <code>%s</code></small></p>' % h.esc(token))
    return h.page("Edicao — BaiakVault", "".join(parts), root="/", here="", extra_head=EDIT_CSS)


def _character_form(cat, ch, local, token):
    voc = ch.get("vocation")
    goals = db_module.GOALS_BY_VOCATION.get(voc, ()) if voc else db_module.GOALS
    hunts = sorted(cat.hunts, key=lambda x: ((x.get("nivel_minimo") or 0), x["nome"]))
    body = [
        '<p><label>nome <input type="text" value="%s" disabled></label>' % h.esc(ch["name"]),
        '<label>vocacao <select name="vocation">%s</select></label>'
        % _options([(v, VOCATION_LABEL[v]) for v in db_module.GOALS_BY_VOCATION], voc),
        '<label>nivel <input type="number" name="level" min="1" max="5000" value="%s"></label>' % h.esc(ch.get("level") or ""),
        '<label>VIP <select name="vip">%s</select></label>' % _options([("1", "sim"), ("0", "nao")], ch.get("vip")),
        '</p><p><label>hunt actual <select name="current_hunt">%s</select></label>'
        % _options([(x["id"], "%s (%s+)" % (x["nome"], x.get("nivel_minimo") or 0)) for x in hunts], ch.get("current_hunt")),
        '<label>objectivo <select name="goal">%s</select></label>'
        % _options([(g, GOAL_LABEL[g]) for g in goals], ch.get("goal"),
                   blank="? (usa %s)" % GOAL_LABEL[db_module.default_goal(voc)] if voc else "?"),
        '</p><p><label>notas <input type="text" name="notes" value="%s"></label>%s</p>'
        % (h.esc(ch.get("notes") or ""), _seen_at_field(ch.get("seen_at"))),
        '<p class="mudo"><small>Um campo em branco nao apaga o que la esta. Para apagar de proposito: '
        '<label><input type="checkbox" name="clear_notes"> limpar notas</label> '
        '<label><input type="checkbox" name="clear_hunt"> limpar hunt</label></small></p>',
    ]
    return _form("/editar/%s/personagem" % ch["slug"], "".join(body), local, token)


def _tree_form(cat, ch, vault, local, token):
    voc = ch.get("vocation")
    if not voc:
        return '<p class="mudo">Sem vocacao nao ha arvore. Grava a vocacao primeiro.</p>'
    have = {t["node_key"]: t for t in vault.tree_of(ch["id"])}
    nodes = sorted(cat.tree_by_vocation[voc]["nos"], key=lambda n: (n.get("tier", 0), n.get("coluna", 0), n["nome"]))
    rows = []
    spent = 0
    for n in nodes:
        t = have.get(n["id"])
        rank = t["rank"] if t else None
        cost = F.tree_total_cost(n, rank) if rank else 0
        spent += cost
        rows.append([h.esc(n["nome"]), h.esc(n.get("tipo")), h.fmt(n.get("tier")),
                     '<input type="number" name="rank_%s" min="0" max="%d" value="%s">' % (
                         n["id"], n.get("rank_maximo") or 1, "" if rank is None else rank),
                     h.fmt(n.get("rank_maximo")),
                     "%s / %s" % (h.fmt(cost) if rank is not None else h.UNKNOWN, h.fmt(n.get("custo_do_zero_ao_maximo"))),
                     h.esc(", ".join((n.get("requer") or [])) or "—")])
    level = ch.get("level")
    body = ['<p class="mudo">Rank comprado por no; em branco = nao sei (nao mexe). 0 = sei que nao comprou. '
            "Pontos gastos: <b>%s</b> de %s que o nivel da.</p>"
            % (h.fmt(spent), h.fmt(F.tree_budget(level)) if level else h.UNKNOWN),
            h.table(["no", "tipo", "tier", "rank", "max", "custo gasto / ate ao max", "requer"], rows, numeric=(2, 4, 5)),
            "<p>%s</p>" % _seen_at_field()]
    # a melhor fonte que ha (ordem 8): o codigo «Exportar» da arvore do jogo, exacto, sem capturas
    code_body = ['<p><b>Cola aqui o codigo Exportar da tua arvore</b> (na arvore do jogo, botao «Exportar» — copia um '
                 "codigo <code>BT1-…</code> para o clipboard). Valida-se como o cliente valida ao importar: vocacao, "
                 "ligacao ao tier 0 e pontos ≤ nivel; grava a arvore INTEIRA (o que nao esta no codigo fica a 0, que "
                 "e uma afirmacao).</p>",
                 '<p><input type="text" name="codigo" size="70" placeholder="BT1-%s%s-…" spellcheck="false"> %s</p>'
                 % (h.esc(treecode.VOCATION_LETTER.get(voc, "?")), h.esc(str(level or "F")), _seen_at_field())]
    out = _form("/editar/%s/arvore/codigo" % ch["slug"], "".join(code_body), local, token, "Gravar a arvore do codigo")
    out += _form("/editar/%s/arvore" % ch["slug"], "".join(body), local, token)
    out += _form("/editar/%s/arvore/limpar" % ch["slug"],
                 '<p class="mudo">Esquecer a arvore toda (volta a «desconhecida»): '
                 '<label><input type="checkbox" name="confirmar" required> confirmo</label></p>', local, token, "Limpar arvore")
    return out


def _rotation_form(cat, ch, local, token):
    """A rotacao e a arma que ELE fixou (ordem 8): sao dados, nao sugestoes."""
    voc = ch.get("vocation")
    if not voc:
        return '<p class="mudo">Sem vocacao nao ha feiticos. Grava a vocacao primeiro.</p>'
    spells = sorted((s for s in cat.vocation_by_name[voc]["feiticos"] if s["tipo"] in ("strike", "area") and s.get("formula_dano")),
                    key=lambda s: (s["nivel"], s["nome"]))
    fixed = ch.get("fixed_rotation") or []
    body = ['<p class="mudo">A rotacao de hunt que decidiste (ordem = prioridade, ate 4). Com ela fixada, a arvore '
            "recomendada e calculada para ela e a pagina mostra ao lado a que o optimizador escolheria, com a diferenca "
            "em numero — nunca a substitui. Em branco nos 4 = nao fixada (fica a do optimizador).</p><p>"]
    for i in range(4):
        body.append('<label>slot %d <select name="spell_%d">%s</select></label>' % (
            i + 1, i, _options([(s["nome"], "%s (%s, nivel %d%s)" % (s["nome"], s["palavras"], s["nivel"],
                                                                     ", runa %d gold" % s["custo_gold"] if s.get("custo_gold") else ""))
                                for s in spells], fixed[i] if i < len(fixed) else None, blank="—")))
    body.append("</p>")
    weapons = item_choices(cat, "weapon", voc, None)
    body.append('%s<p><label>arma fixada <input type="text" name="weapon" list="armas" value="%s"></label> '
                '<label><input type="checkbox" name="clear_weapon"> deixar de fixar a arma</label> %s</p>'
                % (_datalist("armas", weapons), h.esc(cat.item_name(ch["fixed_weapon"]) if ch.get("fixed_weapon") else ""),
                   _seen_at_field()))
    return _form("/editar/%s/rotacao" % ch["slug"], "".join(body), local, token)


def item_choices(cat, slot, vocation=None, level=None):
    """Os nomes dos itens que cabem no slot (e na vocacao/nivel, se se souberem)."""
    if slot == "ammo":
        pool = [i for i in cat.items if i.get("municao") and not i.get("slot")]
    elif slot == "backpack":
        pool = [i for i in cat.items if not i.get("slot") and ("backpack" in i["nome"] or "bag" in i["nome"])]
    else:
        pool = [i for i in cat.equippable if i["slot"] == slot]
        if vocation:
            pool = [i for i in pool if not i.get("vocacoes") or vocation in i["vocacoes"]]
        if level:
            pool = [i for i in pool if (i.get("nivel") or 0) <= level]
    return sorted(i["nome"] for i in pool)


def _equipment_forms(cat, ch, vault, local, token):
    have = {e["slot"]: e for e in vault.equipment_of(ch["id"])}
    imb_names = sorted({i["name"] for i in (cat.meta("itens").get("imbuements") or {}).get("lista") or []})
    out = ['<p class="mudo">Por slot: o item (escreve o nome; a lista sugere os equipaveis pela tua vocacao e nivel), '
           "o upgrade, os imbuements (ex.: <code>Vampirism:3, Strike:2</code>; <code>nenhum</code> = sei que nao tem) "
           "e os atributos da forja em % que interessam ao motor. Em branco = nao sei.</p>",
           _datalist("imbuements", imb_names)]
    for slot in FORM_SLOTS:
        if slot == "shield" and ch.get("vocation") not in (None, "knight"):
            continue
        e = have.get(slot)
        attrs = (e or {}).get("attributes")
        imbs = (e or {}).get("imbuements")
        names = item_choices(cat, slot, ch.get("vocation"), ch.get("level"))
        state = "desconhecido" if e is None else ("vazio" if not e.get("item_key") else e["item_name"] or e["item_key"])
        body = [
            _datalist("itens-%s" % slot, names),
            '<p><b>%s</b> <small class="mudo">(registado: %s)</small></p>' % (h.esc(SLOT_LABEL.get(slot, slot)), h.esc(state)),
            '<input type="hidden" name="slot" value="%s">' % slot,
            '<p><label>item <input type="text" name="item" list="itens-%s" value="%s"></label>' % (slot, h.esc((e or {}).get("item_name") or "")),
            '<label><input type="checkbox" name="vazio"> sei que esta vazio</label>',
            '<label><input type="checkbox" name="esquecer"> esquecer (volta a desconhecido)</label></p>',
            '<p><label>upgrade <input type="number" name="upgrade" min="0" max="50" value="%s"></label>' % h.esc((e or {}).get("upgrade_level") if (e or {}).get("upgrade_level") is not None else ""),
            '<label>imbuements <input type="text" name="imbuements" list="imbuements" value="%s"></label></p>'
            % h.esc("nenhum" if imbs == [] else ", ".join(str(x) for x in (imbs or []))),
            "<p>atributos da forja: " + " ".join(
                '<label>%s <input type="number" step="0.1" name="attr_%s" value="%s"></label>'
                % (label, key, h.esc((attrs or {}).get(key) if (attrs or {}).get(key) is not None else ""))
                for key, label in (("crit_chance", "critico %"), ("crit_dano", "dano critico %"),
                                   ("life_leech", "roubo de vida %"), ("mana_leech", "roubo de mana %"))),
            '<label><input type="checkbox" name="sem_atributos"%s> sei que nao tem</label></p>' % (" checked" if attrs == {} else ""),
            "<p>%s</p>" % _seen_at_field((e or {}).get("seen_at")),
        ]
        out.append(_form("/editar/%s/equipamento" % ch["slug"], "".join(body), local, token))
    return "".join(out)


def _charms_form(cat, ch, vault, local, token):
    have = {c["charm_key"]: c for c in vault.charms_of(ch["id"])}
    points = vault.charm_points_of(ch["id"]) or {}
    creatures = sorted(c["nome"] for c in cat.creatures)
    rows = []
    for charm in cat.charms:
        c = have.get(charm["key"])
        creature = cat.creature_by_key.get((c or {}).get("assigned_creature_key") or "")
        rows.append([h.esc(charm["name"]), h.esc(charm.get("kind")),
                     h.esc("/".join(str(p) for p in charm.get("points") or [])),
                     '<select name="tier_%s">%s</select>' % (charm["key"], _options([(1, "1"), (2, "2"), (3, "3")], (c or {}).get("tier"), blank="nao tem")),
                     '<input type="text" name="criatura_%s" list="criaturas" value="%s">' % (charm["key"], h.esc(creature["nome"] if creature else ""))])
    body = [_datalist("criaturas", creatures),
            '<p><label>charm points disponiveis <input type="number" name="points_available" min="0" value="%s"></label>'
            % h.esc(points.get("points_available") if points.get("points_available") is not None else ""),
            '<label>gastos <input type="number" name="points_spent" min="0" value="%s"></label>'
            % h.esc(points.get("points_spent") if points.get("points_spent") is not None else ""),
            '<label>echoes <input type="number" name="echoes" min="0" value="%s"></label></p>'
            % h.esc(points.get("echoes") if points.get("echoes") is not None else ""),
            '<p><label>limite de monstros com charm (o Y de «X/Y») <input type="number" name="slot_limit" min="1" value="%s"></label>'
            % h.esc(points.get("slot_limit") if points.get("slot_limit") is not None else ""),
            '<label>Charm Expansion <select name="expansion">%s</select></label></p>'
            % _options([("1", "sim"), ("0", "nao")], points.get("expansion")),
            '<p class="mudo">A lista e a dos 24 charms do jogo; «nao tem» e uma afirmacao (o charm sai). '
            "A criatura e a que esta atribuida agora no jogo; a recomendada por hunt esta na pagina do personagem "
            "e de cada hunt. Sem limite registado o motor assume 2 monstros (6 com VIP) — o minimo "
            '(<a href="/charms/regras.html">regras</a>). Um campo em branco nao apaga o que la esta.</p>',
            h.table(["charm", "tipo", "pontos t1/t2/t3", "tier", "criatura atribuida"], rows),
            "<p>%s</p>" % _seen_at_field(points.get("seen_at"))]
    return _form("/editar/%s/charms" % ch["slug"], "".join(body), local, token)


def _bestiary_form(cat, ch, vault, local, token):
    rows = vault.bestiary_of(ch["id"])
    out = []
    if rows:
        out.append(h.table(["criatura", "kills", "meta", "visto a"], [
            [h.esc((cat.creature_by_key.get(r["creature_key"]) or {}).get("nome") or r["creature_key"]), h.fmt(r["kills"]),
             h.fmt((cat.creature_by_key.get(r["creature_key"]) or {}).get("meta_kills")), h.esc(r["seen_at"])] for r in rows],
            numeric=(1, 2)))
    body = ['<p><label>criatura <input type="text" name="criatura" list="criaturas" required></label>',
            '<label>kills <input type="number" name="kills" min="0" required></label> %s</p>' % _seen_at_field()]
    out.append(_form("/editar/%s/bestiario" % ch["slug"], "".join(body), local, token, "Gravar kills"))
    return "".join(out)


def page_character(cat, vault, ch, local, token, msg=None, err=None):
    parts = ['<h1>Editar: %s</h1>' % h.esc(ch["name"]),
             '<p><a href="/editar">&larr; personagens</a> · <a href="/personagens/%s.html">a pagina dele</a></p>' % h.esc(ch["slug"]),
             _msg(msg, err)]
    sections = [("Personagem", _character_form(cat, ch, local, token), True),
                ("Rotacao e arma fixadas", _rotation_form(cat, ch, local, token), False),
                ("Arvore", _tree_form(cat, ch, vault, local, token), False),
                ("Equipamento", _equipment_forms(cat, ch, vault, local, token), False),
                ("Charms", _charms_form(cat, ch, vault, local, token), False),
                ("Bestiario (opcional)", _bestiary_form(cat, ch, vault, local, token), False)]
    for title, body, open_ in sections:
        parts.append('<details class="seccao"%s><summary>%s</summary>%s</details>' % (" open" if open_ else "", h.esc(title), body))
    parts.append('<details class="seccao"><summary>Apagar</summary>%s</details>' % _form(
        "/editar/%s/apagar" % ch["slug"],
        '<p class="aviso">Apagar e decisao tua e nao se desfaz. Escreve o nome exacto para confirmar: '
        '<input type="text" name="confirmar"></p>', local, token, "Apagar personagem"))
    return h.page("Editar %s — BaiakVault" % ch["name"], "".join(parts), root="/", here="", extra_head=EDIT_CSS)


# --- as escritas ---------------------------------------------------------------------------
def apply_post(cat, vault, path, fields):
    """Executa um POST do modo de edicao. Devolve (slug para onde voltar, mensagem).
    Levanta `FormError`/`VaultError` sem nada gravado quando um campo esta mal."""
    parts = [p for p in path.split("/") if p]
    if parts == ["editar", "novo"]:
        name = _one(fields, "name")
        if not name:
            raise FormError("o personagem precisa de nome")
        cid = vault.upsert_character(name, vocation=_one(fields, "vocation"), source="manual",
                                     seen_at=dt.date.today().isoformat())
        return vault.character(cid)["slug"], "criado %s" % name
    if len(parts) < 3 or parts[0] != "editar":
        raise FormError("nao existe: %s" % path)
    slug, action = parts[1], "/".join(parts[2:])
    ch = vault.character(slug)
    if ch is None:
        raise FormError("personagem %r nao existe" % slug)
    cid = ch["id"]
    seen_at = _date(fields)
    if action == "personagem":
        vault.upsert_character(ch["name"], vocation=_one(fields, "vocation"), level=_int(fields, "level", "nivel"),
                               current_hunt=_one(fields, "current_hunt"), vip=_int(fields, "vip", "VIP"),
                               goal=_one(fields, "goal"), notes=_one(fields, "notes"), source="manual", seen_at=seen_at)
        for flag, field in (("clear_notes", "notes"), ("clear_hunt", "current_hunt")):
            if _checked(fields, flag):
                vault.clear_character_field(cid, field)
        return slug, "personagem gravado"
    if action == "arvore":
        ranks = {}
        for key in fields:
            if key.startswith("rank_"):
                rank = _int(fields, key, key)
                if rank is not None:
                    ranks[key[len("rank_"):]] = rank
        n = vault.set_tree_nodes(cid, ranks, source="manual", seen_at=seen_at)
        return slug, "arvore gravada (%d nos)" % n
    if action == "arvore/codigo":
        code = _one(fields, "codigo")
        if not code:
            raise FormError("falta o codigo (Exportar na arvore do jogo)")
        if not ch.get("vocation"):
            raise FormError("grava a vocacao primeiro: o codigo valida-se contra ela")
        try:
            clean, code_level, dropped = treecode.validate_import(cat, ch["vocation"], ch.get("level"), code)
        except treecode.TreeCodeError as e:
            raise FormError(str(e))
        # a arvore inteira: o codigo e a arvore toda, o que nao esta nele e 0 (afirmacao)
        ranks = {n["id"]: clean.get(n["id"], 0) for n in cat.tree_by_vocation[ch["vocation"]]["nos"]}
        n = vault.set_tree_nodes(cid, ranks, source="manual", seen_at=seen_at)
        spent = treecode.points_spent(cat, ch["vocation"], clean)
        msg = "arvore gravada pelo codigo (%d nos, %d pontos gastos)" % (n, spent)
        if code_level and ch.get("level") and code_level != ch["level"]:
            msg += " — o codigo diz nivel %d e a BD tem %d: confirma o nivel" % (code_level, ch["level"])
        if dropped:
            msg += " — cairam por nao ligar ao tier 0 (como no cliente): %s" % ", ".join(dropped)
        return slug, msg
    if action == "arvore/limpar":
        if not _checked(fields, "confirmar"):
            raise FormError("para limpar a arvore e preciso confirmar")
        vault.clear_tree(cid)
        return slug, "arvore esquecida"
    if action == "rotacao":
        names = [_one(fields, "spell_%d" % i) for i in range(4)]
        names = [x for x in names if x]
        vault.set_fixed_rotation(cid, names or None, source="manual", seen_at=seen_at)
        if _checked(fields, "clear_weapon"):
            vault.set_fixed_weapon(cid, None, source="manual", seen_at=seen_at)
        elif _one(fields, "weapon"):
            vault.set_fixed_weapon(cid, _one(fields, "weapon"), source="manual", seen_at=seen_at)
        return slug, ("rotacao fixada: %s" % ", ".join(names)) if names else "rotacao deixou de estar fixada"
    if action == "equipamento":
        slot = _one(fields, "slot")
        if not slot:
            raise FormError("falta o slot")
        if _checked(fields, "esquecer"):
            vault.forget_equipment(cid, slot)
            return slug, "%s: esquecido" % SLOT_LABEL.get(slot, slot)
        item = None if _checked(fields, "vazio") else _one(fields, "item")
        imb_text = _one(fields, "imbuements")
        if imb_text is None:
            imbuements = None
        elif imb_text.lower() in ("nenhum", "nenhuma", "0", "-"):
            imbuements = []
        else:
            index = advisor.imbuement_index(cat)
            imbuements = []
            for piece in imb_text.split(","):
                parsed = advisor.parse_imbuement(cat, piece, index)
                if parsed is None:
                    raise FormError("imbuement desconhecido: %r (ex.: Vampirism:3)" % piece.strip())
                imbuements.append("%s:%d" % parsed if parsed[1] else parsed[0])
        if _checked(fields, "sem_atributos"):
            attributes = {}
        else:
            attributes = {k: _float(fields, "attr_" + k, k) for k in advisor.FORGE_ATTRIBUTES}
            attributes = {k: v for k, v in attributes.items() if v is not None} or None
        vault.set_equipment(cid, slot, item_key=item, upgrade_level=_int(fields, "upgrade", "upgrade"),
                            imbuements=imbuements, attributes=attributes, source="manual", seen_at=seen_at)
        return slug, "%s gravado" % SLOT_LABEL.get(slot, slot)
    if action == "charms":
        charms = []
        for charm in cat.charms:
            tier = _int(fields, "tier_" + charm["key"], charm["name"])
            if tier is None:
                continue
            charms.append((charm["key"], tier, _one(fields, "criatura_" + charm["key"])))
        n = vault.replace_charms(cid, charms, source="manual", seen_at=seen_at)
        vault.set_charm_points(cid, points_available=_int(fields, "points_available", "charm points disponiveis"),
                               points_spent=_int(fields, "points_spent", "charm points gastos"),
                               slot_limit=_int(fields, "slot_limit", "limite de monstros com charm"),
                               expansion=_int(fields, "expansion", "Charm Expansion"),
                               echoes=_int(fields, "echoes", "echoes"), source="manual", seen_at=seen_at)
        return slug, "charms gravados (%d)" % n
    if action == "bestiario":
        kills = _int(fields, "kills", "kills")
        if kills is None:
            raise FormError("faltam os kills")
        vault.set_bestiary(cid, _one(fields, "criatura"), kills, source="manual", seen_at=seen_at)
        return slug, "kills gravados"
    if action == "apagar":
        if _one(fields, "confirmar") != ch["name"]:
            raise FormError("para apagar tens de escrever o nome exacto (%s)" % ch["name"])
        vault.delete_character(cid)
        return None, "apagado %s" % ch["name"]
    raise FormError("nao existe: %s" % path)


# --- o servidor -----------------------------------------------------------------------------
class Config:
    def __init__(self, docs, db_path=None, catalog_dir=None, token_path=None, bind="127.0.0.1"):
        self.docs = Path(docs)
        self.db_path = Path(db_path or db_module.DEFAULT_PATH)
        self.cat = catalog_module.load(catalog_dir)
        self.planner = builds_module.Planner(self.cat)
        self.token = read_token(token_path)
        self.bind = bind
        self.rebuilds = 0
        # o servidor e multi-thread e o Planner guarda caches (arvores, equipamento por
        # checkpoint) sem protecao: duas gravacoes seguidas nao podem regenerar ao mesmo tempo
        self._lock = threading.Lock()

    def rebuild(self):
        """Regenera o site depois de uma escrita (sem as paginas das builds)."""
        with self._lock:
            build_module.build(self.docs, self.db_path, cat=self.cat, planner=self.planner, with_builds=False)
            self.rebuilds += 1


def make_handler(cfg):
    class Handler(http.server.SimpleHTTPRequestHandler):
        server_version = "baiakvault"

        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(cfg.docs), **k)

        def log_message(self, fmt, *args):
            pass

        @property
        def local(self):
            return bool(self.client_address) and self.client_address[0] in LOCAL_ADDRESSES

        def _send(self, body, code=200, ctype="text/html; charset=utf-8"):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _redirect(self, to):
            self.send_response(303)
            self.send_header("Location", to)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _fields(self):
            size = int(self.headers.get("Content-Length") or 0)
            if size <= 0 or size > MAX_BODY:
                return {}
            raw = self.rfile.read(size).decode("utf-8", "replace")
            return urllib.parse.parse_qs(raw, keep_blank_values=True)

        def _can_write(self, fields):
            given = _one(fields, "token") or ""
            return bool(given) and secrets.compare_digest(given, cfg.token)

        def _with_vault(self, fn):
            conn = db_module.connect(cfg.db_path)
            try:
                return fn(db_module.Vault(conn, cfg.cat))
            finally:
                conn.close()

        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            path = urllib.parse.unquote(url.path)
            q = urllib.parse.parse_qs(url.query)
            if path == "/saude":
                return self._send("ok baiakvault\n", 200, "text/plain; charset=utf-8")
            if path in ("/editar", "/editar/"):
                token = cfg.token if self.local else ""
                return self._send(self._with_vault(lambda v: page_index(cfg.cat, v, self.local, token, _one(q, "ok"), _one(q, "erro"))))
            if path.startswith("/editar/"):
                slug = path[len("/editar/"):].strip("/")
                token = cfg.token if self.local else ""

                def render(v):
                    ch = v.character(slug)
                    if ch is None:
                        return None
                    return page_character(cfg.cat, v, ch, self.local, token, _one(q, "ok"), _one(q, "erro"))
                body = self._with_vault(render)
                if body is None:
                    return self._send("personagem %r nao existe\n" % slug, 404, "text/plain; charset=utf-8")
                return self._send(body)
            return super().do_GET()

        def do_POST(self):
            url = urllib.parse.urlparse(self.path)
            path = urllib.parse.unquote(url.path)
            fields = self._fields()
            if path == "/reiniciar":
                # ordem 9 (21/09/2026): o serve fica de pe o dia todo com o CODIGO com que arrancou;
                # depois de um merge e preciso deita-lo abaixo para o vigia `baiakvault-serve` o
                # relancar. Sem `taskkill` (a allowlist do ai-pc nega-o): com o token, responde e sai
                # (`scripts/reiniciar_serve.py` faz o pedido). So do proprio PC.
                if not self.local or not self._can_write(fields):
                    return self._send("so do PC e com o token\n", 403, "text/plain; charset=utf-8")
                self._send("a sair: o vigia relanca o serve\n", 200, "text/plain; charset=utf-8")
                threading.Timer(0.5, lambda: os._exit(0)).start()
                return None
            if not path.startswith("/editar"):
                return self._send("nao existe\n", 404, "text/plain; charset=utf-8")
            if not self._can_write(fields):
                return self._send("Escrita so com o token de data/serve.token (a pagina aberta no PC mostra-o).\n",
                                  403, "text/plain; charset=utf-8")
            try:
                slug, msg = self._with_vault(lambda v: apply_post(cfg.cat, v, path, fields))
            except (FormError, db_module.VaultError, sqlite3.Error) as e:
                # o sqlite3.Error e a rede de seguranca: uma restricao do esquema que a
                # validacao nao apanhou sai como «nao gravado» legivel, nao como resposta partida
                parts = [p for p in path.split("/") if p]
                back = "/editar/%s" % parts[1] if len(parts) >= 2 and parts[1] != "novo" else "/editar"
                return self._send(h.page("Nao gravado — BaiakVault",
                                         '<h1>Nao gravado</h1><p class="aviso">%s</p><p><a href="%s">voltar</a></p>'
                                         % (h.esc(str(e)), h.esc(back)), root="/", extra_head=EDIT_CSS), 400)
            try:
                cfg.rebuild()
            except Exception as e:  # a BD ja esta escrita; o site e que ficou por regenerar — diz-se
                msg += " — mas o site nao regenerou: %s" % e
            target = "/editar/%s" % slug if slug else "/editar"
            return self._redirect(target + "?ok=" + urllib.parse.quote(msg))

    return Handler


def serve(docs, port=PORT, bind=None, db_path=None, catalog_dir=None, token_path=None):
    bind = bind or os.environ.get("BAIAKVAULT_BIND", "127.0.0.1")
    cfg = Config(docs, db_path, catalog_dir, token_path, bind)
    srv = http.server.ThreadingHTTPServer((bind, port), make_handler(cfg))
    srv.daemon_threads = True
    print("BaiakVault em http://127.0.0.1:%d/ (bind %s); modo de edicao em /editar. Ctrl+C para parar." % (port, bind), flush=True)
    if bind != "127.0.0.1":
        print("na rede local, escrever exige o token de %s" % TOKEN_PATH, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0
