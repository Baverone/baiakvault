"""As paginas das builds: `builds/index.html`, `builds/<vocacao>-<objectivo>.html`
(seccoes por nivel), os cartoes `print/helper-<vocacao>-<objectivo>-<nivel>.html`
e a pagina de validacao (a partir de `docs/builds/validacao.md`).

Tudo o que aqui se escreve vem do `builds.Planner`; o que o canal diz entra
citado, nunca como numero. Os numeros sao estimativas do simulador — a pagina
diz que sao, e diz de onde vem cada constante (`formulas.CONSTANTS`).
"""
import math
import re

from . import builds as B
from . import formulas as F
from . import html as h
from . import sim

VOCATION_LABEL = {"knight": "Knight (EK)", "monk": "Monk", "paladin": "Paladin (RP)",
                  "sorcerer": "Sorcerer (MS)", "druid": "Druid (ED)"}
ELEMENT_LABEL = {"physical": "fisico", "fire": "fogo", "earth": "terra", "ice": "gelo",
                 "energy": "energia", "death": "morte", "holy": "sagrado"}
SLOT_LABEL = {"weapon": "arma", "shield": "escudo", "helmet": "elmo", "armor": "armadura",
              "legs": "pernas", "boots": "botas", "amulet": "amuleto", "ring": "anel", "ammo": "municao"}
SOURCE_LABEL = {F.SOURCE_CLIENT: "cliente", F.SOURCE_GUIDE: "guia", F.SOURCE_CHANNEL: "canal",
                F.SOURCE_CONVENTION: "convencao ⚠"}
CANAL = "canal CharllonLobo"

# Dicas do canal por vocacao, citadas (video id) — nunca numeros do motor.
CANAL_TIPS = {
    "knight": [
        ("Cura: Exura Med a 85% e pocao Supreme a 85% — as duas partem juntas e recuperam um golpe grande de boss", "8HFN4cgQW1A"),
        ("Ataque na hunt: «nao fazer nada» + alvo de menor vida; no boss: diagonal a 2 tiles", "DKI-6xqdOTc, rP83AhzvK9M"),
        ("Amuleto pelo dano dominante da hunt (Light Pendant energia, Magma Amulet fogo, Terra Amulet terra, Protection fisico); SSA abaixo de 50% na hunt e 60-65% no boss; Def Ring no boss; Death Ring nas livrarias", "mSE11hHamRs, rP83AhzvK9M"),
        ("Com ML suficiente (Moonlight Nectar, amuletos) a UH rune volta a ser a melhor cura do EK", "XoXW2_eg-fQ"),
        ("Battle Tactics primeiro; Avatar a partir do ~320", "q3eBC2GvwIg"),
    ],
    "sorcerer": [
        ("Cura: Ultimate a 85%; Utamo Vita sempre activo, renovar abaixo de 10%", "8HFN4cgQW1A"),
        ("Ataque: mais perto, 3 tiles; no boss diagonal a 3 tiles e magias single-target (2 UE + Max Vis/Frigo + SD)", "DKI-6xqdOTc, rP83AhzvK9M"),
        ("Anel: Plasma > 55%, Might < 50%; amuleto: Protection > 50%, SSA < 40% (boss: Might 50%, ataque 60%, SSA 65%)", "mSE11hHamRs"),
        ("Avatar a partir do ~320: tudo critico; charm Divine Strike", "q3eBC2GvwIg"),
    ],
    "druid": [
        ("Cura: Ultimate a 85%; cura aliada: EK a 85% com «priorizar a minha cura» DESMARCADO; Utamo sempre, renovar < 10%", "8HFN4cgQW1A"),
        ("Ataque: mais perto, 3 tiles; no boss diagonal a 3 tiles", "DKI-6xqdOTc, rP83AhzvK9M"),
        ("Anel: Plasma > 55%, Might < 50%; amuleto: Protection > 50%, SSA < 40%", "mSE11hHamRs"),
    ],
    "paladin": [
        ("O canal nao cobre o Paladin. Ponto de partida seguro: como o MS (3 tiles, anel/amuleto do padrao mage)", "helper.md"),
    ],
    "monk": [
        ("O canal nao cobre o Monk. Ponto de partida: como o EK sem o «nao fazer nada» (nao tanka como o Knight); nao copiar a build do Knight", "helper.md"),
    ],
}


def slug(vocation, goal):
    return "%s-%s" % (vocation, goal)


def title(vocation, goal):
    return "%s — %s" % (VOCATION_LABEL[vocation], B.GOAL_ASKED.get((vocation, goal), B.GOAL_LABEL[goal]))


def _n(value, decimals=0):
    return h.fmt(value, decimals)


def _pct(value, decimals=0):
    return h.fmt(value, decimals, "%")


def _seconds(value):
    if value is None:
        return h.UNKNOWN
    if value >= B.TTD_CAP:
        return "&gt; 10 min"
    return h.fmt(value, 0, " s")


def _node_name(cat, nid):
    return (cat.node_by_id.get(nid) or {}).get("nome") or nid


def _drop_sources(cat, item, root):
    """Onde cai: monstro (hunt) ..., pela tabela de loot do cliente."""
    out = []
    for d in (item.get("cai_de") or [])[:6]:
        c = cat.creature_by_key.get(d.get("monstro"))
        chance = h.pct_of_100k(d.get("chance_por_100k"))
        if c:
            hunts = c.get("aparece_em") or []
            links = ", ".join('<a href="%shunts/%s.html">%s</a>' % (root, hid, h.esc(cat.hunt_by_id[hid]["nome"]))
                              for hid in hunts if hid in cat.hunt_by_id)
            out.append("%s (%s)%s" % (h.esc(c["nome"]), chance, " — " + links if links else ""))
        else:
            out.append("%s (%s)" % (h.esc(d.get("monstro")), chance))
    if not out:
        return '<span class="mudo">nao cai de monstro nenhum no catalogo (boss de sala, loja ou Codex — o cliente nao diz)</span>'
    return "; ".join(out)


# --- indice ------------------------------------------------------------------------------------
def render_index(cat, plans, generated_at):
    root = "../"
    parts = ["<h1>Builds</h1>",
             '<p class="mudo">As oito builds pedidas a 16/09/2026: vocacao + objectivo, para qualquer '
             "nivel (aqui os representativos). Cada uma tem a arvore por ordem de compra, o equipamento "
             "BiS por slot, a rotacao para o Helper e os numeros do simulador. <b>Os numeros sao "
             "estimativas</b>: as formulas dos feiticos e da arvore sao as do cliente do jogo; o resto "
             'vem do guia ou e convencao nossa, e esta marcado (ver a seccao «Fontes» de cada build e a '
             '<a href="validacao.html">validacao cruzada</a>).</p>']
    for voc, goal in B.BUILDS:
        s = slug(voc, goal)
        parts.append('<h2><a href="%s.html">%s</a></h2>' % (s, h.esc(title(voc, goal))))
        rows = []
        for level in B.LEVELS:
            b = plans[(voc, goal, level)]
            m = b["metrics"]
            hunt = cat.hunt_by_id[b["hunt"]]["nome"]
            rows.append([
                '<a href="%s.html#n%d">%d</a>' % (s, level, level),
                h.esc(hunt),
                _n(m["dps_cycle"]), _n(m["dps_boss"]),
                _n(m["hps_self"]), _n(m["ehp"]),
                _seconds(m["ttd_pack"]),
                "%s / %s" % (_n(m["mana_demand"], 1), _n(m["mana_income"], 1)),
                h.kk(m["gold_per_hour"]),
                h.esc(", ".join(n for n, w, mm in b["helper"]["hunt_rotation"])),
            ])
        parts.append(h.table(["nivel", "hunt de ref.", "DPS ciclo", "DPS boss", "HPS", "EHP", "aguenta o pack",
                              "mana/s gasta / ganha", "supplies gold/h", "rotacao (hunt)"], rows,
                             numeric=(0, 2, 3, 4, 5, 6, 7, 8)))
    parts.append('<h2>Como ler</h2><div class="cartao">'
                 "<p><b>DPS ciclo</b>: dano por segundo efectivo num ciclo de hunt — 57 monstros normais "
                 "(as magias de area apanham o pack) mais o boss da wave 10 com x3 HP (so alvo unico). "
                 "<b>HPS</b>: a cura propria por segundo que a mana aguenta em 60 s. <b>EHP</b>: vida a dividir "
                 "pela fraccao do dano que passa da armadura, bloqueio e absorcoes, contra a mistura de elementos "
                 "da hunt. <b>Aguenta o pack</b>: tempo ate morrer com o pack inteiro em cima, ja com o leech "
                 "(«&gt; 10 min» quando o leech cobre a pressao). <b>mana/s</b>: o que a rotacao gasta contra o que "
                 "o leech e os itens repoem — a regeneracao base do servidor nao esta em fonte nenhuma e conta a "
                 "zero, por isso «gasta &gt; ganha» quer dizer «depende de regen/pocoes», nao «impossivel». "
                 "<b>supplies</b>: pocoes que o Helper beberia com estes limiares, em gold por hora.</p></div>")
    parts.append(h.source_line("simulador do BaiakVault (formulas do cliente + guia + convencoes marcadas)", cat.seen_at()))
    return h.page("Builds — BaiakVault", "".join(parts), root=root, here="builds", generated_at=generated_at)


# --- pagina de uma build -------------------------------------------------------------------------
_LEVEL_JS = """<script>
(function(){var secs=document.querySelectorAll('section.nivel');var btns=document.querySelectorAll('nav.niveis a');
function show(id){secs.forEach(function(s){s.hidden=(s.id!==id)});btns.forEach(function(b){b.classList.toggle('aqui',b.getAttribute('href')==='#'+id)})}
btns.forEach(function(b){b.addEventListener('click',function(e){e.preventDefault();history.replaceState({},'',b.getAttribute('href'));show(b.getAttribute('href').slice(1))})});
var first=(location.hash||'').slice(1);if(!document.getElementById(first)){first=secs[0]&&secs[0].id}if(first){show(first)}})();
</script>"""


def render_build(cat, vocation, goal, plans_by_level, generated_at):
    root = "../"
    parts = ["<h1>%s</h1>" % h.esc(title(vocation, goal))]
    parts.append('<p class="mudo">Objectivo pedido: «%s». Metrica: %s. O nivel e um parametro — escolhe o teu; '
                 "quando os personagens do Andre entrarem, a pagina de cada um chama o mesmo motor com o nivel exacto.</p>"
                 % (h.esc(B.GOAL_ASKED.get((vocation, goal), "")), h.esc(_metric_text(goal))))
    parts.append('<nav class="niveis menu">%s</nav>' % "".join(
        '<a href="#n%d">nivel %d</a>' % (lv, lv) for lv in B.LEVELS))
    for level in B.LEVELS:
        parts.append(render_level_section(cat, plans_by_level[level], root))
    parts.append(render_sources(cat, vocation))
    parts.append('<p><a href="index.html">&larr; todas as builds</a></p>')
    return h.page("%s — Builds — BaiakVault" % title(vocation, goal), "".join(parts) + _LEVEL_JS,
                  root=root, here="builds", generated_at=generated_at)


def _metric_text(goal):
    return {
        "damage": "DPS efectivo no ciclo (57 normais + boss x3 HP)",
        "tank": "EHP com o pack em cima x sustain (leech ate cobrir a pressao) x DPS^0,3",
        "heal": "cura/s sustentavel em 60 s (propria + metade da aliada) x DPS^0,3",
        "support": "cura/s sustentavel em 60 s (propria + metade da aliada) x DPS^0,3",
    }[goal]


def render_level_section(cat, b, root):
    level = b["level"]
    m = b["metrics"]
    prof = b["profile"]
    target = b["target"]
    hunt = cat.hunt_by_id[b["hunt"]]
    out = ['<section class="nivel" id="n%d"><h2>Nivel %d — alvo de referencia: <a href="%shunts/%s.html">%s</a> (%d+)</h2>'
           % (level, level, root, hunt["id"], h.esc(hunt["nome"]), hunt.get("nivel_minimo") or 0)]
    # resumo
    out.append('<div class="cartao">' + h.kv([
        ("DPS ciclo / pack / boss", "%s / %s / %s" % (_n(m["dps_cycle"]), _n(m["dps_pack"]), _n(m["dps_boss"]))),
        ("do ataque automatico", _n(m["auto_dps"]) + ' <small class="mudo">(convencao ⚠, ver Fontes)</small>'),
        ("cura/s sustentavel (propria / aliada)", "%s / %s" % (_n(m["hps_self"]), _n(m["hps_friend"]) if m["hps_friend"] else "—")),
        ("HP / mana", "%s / %s" % (_n(m["hp_max"]), _n(m["mana_max"]))),
        ("EHP", _n(m["ehp"]) + " (%s do dano da hunt fica na mitigacao)" % _pct(m["mitigated_share"] * 100, 1)),
        ("pressao (1 monstro / pack)", "%s / %s por segundo; maior golpe %s (boss %s)"
         % (_n(m["pressure_one"]), _n(m["pressure_pack"]), _n(m["max_hit"]), _n(m["boss_max_hit"]))),
        ("aguenta (pack / 1 monstro)", "%s / %s" % (_seconds(m["ttd_pack"]), _seconds(m["ttd_one"]))),
        ("mana/s gasta / ganha", "%s / %s — %s" % (_n(m["mana_demand"], 1), _n(m["mana_income"], 1), _mana_verdict(m))),
        ("supplies (hunt / boss)", "%s / %s gold/h — %d pocoes de vida e %d de mana por minuto"
         % (h.kk(m["gold_per_hour"]), h.kk(m["boss_gold_per_hour"]), m["hp_potions"], m["mana_potions"])),
        ("skills assumidos", _skills_text(prof)),
    ]) + "</div>")
    if m.get("death_at") is not None or m.get("boss_death_at") is not None:
        out.append('<p class="aviso">⚠ No simulador o personagem morre (hunt aos %s s, boss aos %s s) — com esta '
                   "build a hunt de referencia e demasiado forte a solo; e o que o simulador diz, nao um erro da pagina.</p>"
                   % (h.fmt(m.get("death_at")), h.fmt(m.get("boss_death_at"))))
    out.append(_tree_block(cat, b))
    out.append(_equipment_block(cat, b, root))
    out.append(_helper_block(cat, b, root))
    out.append(_alternatives_block(cat, b))
    out.append("</section>")
    return "".join(out)


def _mana_verdict(m):
    if m["mana_income"] >= m["mana_demand"]:
        return "sustentavel so com leech e itens"
    if m["mana_empty_at"] is None:
        return "a pool aguenta os 60 s; em regime faltam %s mana/s (regen base do servidor desconhecida, ou pocoes)" \
            % _n(m["mana_demand"] - m["mana_income"], 1)
    return "⚠ a mana esgota-se aos %d s; sobe o minimo de bichos das areas ou tira a magia mais cara" % m["mana_empty_at"]


def _skills_text(prof):
    parts = []
    for k, v in sorted(prof.skills.items()):
        if v:
            parts.append("%s %s" % (k, h.fmt(v)))
    note = " (skill tipico do guia + itens; o real dele substitui)" if prof.assumed_skill else ""
    return h.esc(", ".join(parts)) + '<small class="mudo">%s</small>' % note


def _tree_block(cat, b):
    steps = b["steps"]
    fill = b["fill_steps"]
    out = ["<h3>Arvore — %s/%s pontos</h3>" % (_n(b["points_spent"]), _n(b["points_budget"]))]
    rows = []
    by_node = {}
    for st in steps:
        by_node.setdefault(st.node_id, []).append(st.rank)
    # ordem de compra, comprimida: um no seguido ate ao rank em que muda
    order = []
    for st in steps:
        if order and order[-1][0] == st.node_id:
            order[-1] = (st.node_id, st.rank, order[-1][2], st.cumulative)
        else:
            order.append((st.node_id, st.rank, st.rank, st.cumulative))
    for nid, r_to, r_from, cum in order:
        rows.append([h.esc(_node_name(cat, nid)),
                     ("%d" % r_to) if r_from == r_to else "%d → %d" % (r_from, r_to),
                     _n(cum)])
    out.append('<p class="mudo">Ordem de compra a subir de nivel (o numero e o nivel em que se chega la, '
               "porque cada nivel da um ponto — cliente). Um no fechado abre-se com um rank nos vizinhos, "
               "e esses ranks estao na ordem.</p>")
    out.append(h.table(["no", "rank", "ate ao nivel"], rows, numeric=(2,)))
    if b["next_step"] is not None:
        ns = b["next_step"]
        out.append('<p class="aviso">O caminho esta a poupar para <b>%s</b> (%s pontos, chega ao nivel %s).</p>'
                   % (h.esc(_node_name(cat, ns.node_id)), _n(ns.cost), _n(ns.cumulative)))
    if fill:
        out.append('<p class="mudo">Os pontos que sobram a este nivel, gastos agora (atrasam o proximo notable em '
                   "%s niveis): %s.</p>" % (_n(sum(st.cost for st in fill)),
                                            h.esc(", ".join("%s %d" % (_node_name(cat, st.node_id), st.rank) for st in fill))))
    if b["improved"]:
        out.append('<p class="mudo">Melhoria local com o equipamento deste nivel: %s.</p>' % h.esc("; ".join(
            "em vez de %s, %s %d (+%.1f%%)" % (", ".join(_node_name(cat, r) for r in im["removed"]), im["to"], im["rank"], im["gain_pct"])
            for im in b["improved"])))
    # a arvore final
    final = sorted(b["tree"].items(), key=lambda kv: (-kv[1], kv[0]))
    out.append("<details><summary>A arvore final, no a no (%d nos)</summary>" % len(final))
    out.append(h.table(["no", "rank", "efeito por rank", "custo total"], [
        [h.esc(_node_name(cat, nid)), "%d / %d" % (r, cat.node_by_id[nid]["rank_maximo"]),
         h.esc(_effect_text(cat.node_by_id[nid])), _n(F.tree_total_cost(cat.node_by_id[nid], r))]
        for nid, r in final], numeric=(1, 3)))
    out.append("</details>")
    return "".join(out)


def _effect_text(node):
    per = node.get("efeito_por_rank")
    if not per:
        return node.get("descricao") or "—"
    bits = []
    for k, v in per.items():
        if isinstance(v, dict):
            if "$expr" in v:
                bits.append("absorcao +%s%% em todos" % v["$expr"][3:-1])
            else:
                bits.append("%s %s" % (k, ", ".join("%s +%s" % (ELEMENT_LABEL.get(e, e), x) for e, x in v.items())))
        else:
            bits.append("%s +%s" % (k, v))
    return "; ".join(bits)


def _equipment_block(cat, b, root):
    out = ["<h3>Equipamento BiS por slot</h3>",
           '<p class="mudo">O que o simulador diz que mais sobe a metrica neste nivel, slot a slot, entre os itens '
           "que a vocacao pode usar. Aneis e amuletos com cargas (SSA, Might Ring) nao entram aqui: sao os de "
           "emergencia do Helper, abaixo. «Vende ao NPC por» e o unico preco que o cliente tem.</p>"]
    rows = []
    for slot in list(B.SLOTS) + ["ammo"]:
        eq = b["equipment"].get(slot)
        if not eq:
            if slot in ("shield", "ammo"):
                continue
            rows.append([h.esc(SLOT_LABEL[slot]), '<span class="mudo">nada compensa</span>', "", "", "", ""])
            continue
        item = eq["item"]
        imbs = eq.get("imbuement_cats") or []
        alts = (b["equipment_alternatives"].get(slot) or [])[1:3]
        alt_text = "; ".join("%s (%s)" % (h.esc(a["equip"]["item"]["nome"]), _n(a["score"], 0)) for a in alts) or "—"
        rows.append([
            h.esc(SLOT_LABEL.get(slot, slot)),
            "<b>%s</b> %s" % (h.esc(item["nome"]), _item_stats(item)),
            _n(item.get("nivel")) if item.get("nivel") else "—",
            _drop_sources(cat, item, root) + (" · vende ao NPC por %s" % h.kk(item["preco_npc"]) if item.get("preco_npc") else ""),
            h.esc(", ".join(imbs)) if imbs else ('<span class="mudo">sem slots</span>' if not item.get("imbuement_slots") else "—"),
            alt_text,
        ])
    out.append(h.table(["slot", "item", "nivel", "de onde vem", "imbuements a por", "alternativas (metrica)"], rows, numeric=(2,)))
    sets = _codex_sets(cat, b)
    if sets:
        out.append('<p class="mudo"><small>Conjuntos do catalogo que estas pecas fecham: %s — no cliente os '
                   "conjuntos sao <b>entregas do Codex</b> (bonus permanente ao entregar as 4 pecas), nao bonus "
                   "por vestir.</small></p>" % h.esc("; ".join(sets)))
    return "".join(out)


def _item_stats(item):
    bits = []
    if item.get("ataque"):
        bits.append("atk %s" % item["ataque"])
    if item.get("ataque_elemental"):
        bits.append("+%s %s" % (item["ataque_elemental"], ELEMENT_LABEL.get(item.get("elemento"), item.get("elemento") or "?")))
    if item.get("wand_min") is not None:
        bits.append("%s-%s %s, %s mana/tiro" % (item["wand_min"], item["wand_max"],
                                                 ELEMENT_LABEL.get(item.get("elemento"), item.get("elemento") or "?"), h.fmt(item.get("mana_por_tiro"))))
    if item.get("armadura"):
        bits.append("arm %s" % item["armadura"])
    if item.get("defesa"):
        bits.append("def %s" % item["defesa"])
    for k, v in (item.get("skills") or {}).items():
        bits.append("%s +%s" % (k, v))
    for k, v in (item.get("absorcao") or {}).items():
        bits.append("%s %s%%" % (ELEMENT_LABEL.get(k, k), ("+%s" % v) if v > 0 else v))
    for src, label in (("crit_chance", "crit %"), ("crit_dano", "crit dmg %"), ("life_leech", "life leech %"), ("mana_leech", "mana leech %")):
        if item.get(src):
            bits.append("%s +%s" % (label, item[src]))
    if item.get("duas_maos"):
        bits.append("duas maos")
    return '<small class="mudo">%s</small>' % h.esc(", ".join(bits)) if bits else ""


def _codex_sets(cat, b):
    names = {eq["item"]["nome"].lower() for eq in b["equipment"].values() if eq}
    out = []
    for s in cat.meta("itens").get("conjuntos") or []:
        pieces = [p.lower() for p in s.get("pieces") or []]
        got = [p for p in pieces if p in names]
        if len(got) >= 2:
            out.append("%s (%d/%d)" % (s["name"], len(got), len(pieces)))
    return out


def _helper_block(cat, b, root):
    hc = b["helper"]
    prof = b["profile"]
    m = b["metrics"]
    out = ["<h3>Rotacao para o Helper</h3>",
           '<p class="mudo">Com os nomes dos campos do jogo (etiquetas do cliente). O que vem do canal esta '
           "marcado [canal]; o resto e o simulador.</p>"]
    rot_rows = []
    for i, (name, words, min_mobs) in enumerate(hc["hunt_rotation"], 1):
        rot_rows.append(["slot %d" % i, "<b>%s</b> <code>%s</code>" % (h.esc(name), h.esc(words)),
                         ("≥%d mobs" % min_mobs) if min_mobs else "—"])
    boss_rows = [["slot %d" % i, "<b>%s</b> <code>%s</code>" % (h.esc(n), h.esc(w)), "—"]
                 for i, (n, w, mm) in enumerate(hc["boss_rotation"], 1)]
    runes = b["boss_rotation_runes"]
    rune_note = ""
    if runes and b["boss_sim_runes"] and b["boss_sim"] and b["boss_sim_runes"].dps > b["boss_sim"].dps * 1.02:
        rune_note = ('<p class="mudo">Com runas no boss: %s → DPS %s (+%s) por %s gold/h em runas.</p>'
                     % (h.esc(", ".join(sl.spell["nome"] for sl in runes)), _n(b["boss_sim_runes"].dps),
                        _pct((b["boss_sim_runes"].dps / b["boss_sim"].dps - 1) * 100, 0), h.kk(b["boss_sim_runes"].gold_per_hour)))
    heal_rune = hc.get("heal_rune_alternative")
    heal_rune_txt = ""
    if heal_rune:
        heal_rune_txt = (' <small class="mudo">alternativa com gold: %s (%s por lancamento, %s gold cada)</small>'
                         % (h.esc(heal_rune["nome"]), _n(prof.heal_amount(heal_rune)), _n(heal_rune["custo_gold"])))
    out.append('<div class="cartao"><h4>Separador Hunt</h4>' + h.kv([
        ("Cura automática → Cura própria — escolher magia",
         "<b>%s</b> <code>%s</code> (%s por lancamento)%s" % (h.esc(hc["heal_spell"]), h.esc(hc["heal_words"]),
                                                             _n(prof.heal_amount(b["heal"])) if b["heal"] else h.UNKNOWN, heal_rune_txt)),
        ("Cura em (% de vida)", "<b>%d%%</b> <small class=\"mudo\">simulador: %d%% chega para o maior golpe do boss; o canal poe 85%% [8HFN4cgQW1A]</small>"
         % (hc["heal_at"], hc["heal_at_computed"])),
        ("Potion de vida · Beber abaixo de (% de vida)", "<b>%s</b> a <b>%d%%</b> <small class=\"mudo\">[canal: 85%% no EK, Supreme]</small>"
         % (h.esc(hc["hp_potion"]), hc["hp_below"])),
        ("Potion de mana · Beber abaixo de (% de mana)",
         ("<b>%s</b> a <b>%d%%</b> <small class=\"mudo\">(padrao do jogo, wiki)</small>" % (h.esc(hc["mana_potion"]), hc["mana_below"]))
         if hc["mana_potion"] else '<span class="mudo">nao bebe (cliente: usesManaPotions=false)</span>'),
        ("Magias de Ataque — Rotação (ordem = prioridade · ≥N = mín. de mobs)", h.table(["slot", "magia", "≥N"], rot_rows)),
        ("Posição de ataque / Distância do alvo", "%s · <b>%d tile%s</b> <small class=\"mudo\">[canal: EK «nao fazer nada»+menor vida; mages «mais perto» 3 tiles]</small>"
         % (h.esc(hc["position"]), hc["distance"], "s" if hc["distance"] != 1 else "")),
        ("Escudo mágico", ("<b>Mantém utamo vita sempre ativo</b>; Renovar escudo: <b>10%</b> <small class=\"mudo\">[canal 8HFN4cgQW1A]</small>"
                           if hc["magic_shield"] else '<span class="mudo">n/a (so mages)</span>')),
        ("Curar aliado (exura sio)", ("<b>%s</b>, gatilho <b>%d%%</b>, «Priorizar minha cura» <b>desmarcado</b> <small class=\"mudo\">[canal 8HFN4cgQW1A]</small>"
                                      % (h.esc(hc["friend_heal"]), hc["friend_heal_at"])) if hc["friend_heal"] else '<span class="mudo">esta vocacao nao tem cura aliada</span>'),
        ("Equipamento (swap por vida) — amuleto", "padrao <b>%s</b> (dano dominante da hunt: %s); emergência <b>%s</b>, Equipar com vida abaixo de <b>%d%%</b>, Restaurar acima de <b>%d%%</b> <small class=\"mudo\">[canal mSE11hHamRs]</small>"
         % (h.esc(hc["emergency"]["amulet_standard"]), h.esc(ELEMENT_LABEL.get(hc["emergency"]["dominant_element"])),
            h.esc(hc["emergency"]["amulet_emergency"]), 50 if prof.vocation == "knight" else 40, 80)),
        ("Equipamento (swap por vida) — anel", "padrao: o anel BiS acima; emergência <b>%s</b>, Equipar com vida abaixo de <b>%d%%</b> <small class=\"mudo\">[canal]</small>"
         % (h.esc(hc["emergency"]["ring_emergency"]), 40 if prof.vocation == "knight" else 50)),
    ]) + "</div>")
    out.append('<div class="cartao"><h4>Separador Boss</h4>' + h.kv([
        ("Magias de Ataque — Rotação", h.table(["slot", "magia", "≥N"], boss_rows)),
        ("Posição de ataque / Distância do alvo", "<b>Fica num dos cantos diagonais do alvo</b> a <b>%d tiles</b> <small class=\"mudo\">[canal rP83AhzvK9M]</small>"
         % (2 if prof.vocation in ("knight", "monk") else 3)),
        ("Cura", "igual a da hunt; SSA abaixo de <b>%d%%</b> <small class=\"mudo\">[canal]</small>" % (65 if prof.vocation == "knight" else 60)),
        ("numeros", "DPS %s, maior golpe do boss %s, mana %s" % (_n(m["dps_boss"]), _n(m["boss_max_hit"]),
                                                                 ("esgota aos %d s" % m["boss_mana_empty_at"]) if m["boss_mana_empty_at"] is not None else "aguenta os 60 s")),
    ]) + rune_note + "</div>")
    out.append('<p><a href="%sprint/helper-%s-%d.html">cartao para copiar (390 px)</a></p>'
               % (root, slug(prof.vocation, b["goal"]), b["level"]))
    return "".join(out)


def _alternatives_block(cat, b):
    alts = b["tree_alternatives"]
    goal = b["goal"]
    out = ["<h3>O que se perde ao desviar</h3>"]
    if not alts or not alts.get("options"):
        out.append('<p class="mudo">Sem alternativas avaliadas a este nivel.</p>')
        return "".join(out)
    removed = ", ".join("%s" % _node_name(cat, r) for r in alts["removed"])
    rows = [["<b>a build</b>", _n(b["score"], 1), _n(b["metrics"]["dps_cycle"]), _n(b["metrics"]["hps_self"]), _n(b["metrics"]["ehp"]), "—"]]
    for o in alts["options"]:
        mm = o["metrics"]
        delta = (o["score"] / b["score"] - 1) * 100 if b["score"] else 0.0
        rows.append(["%s %d" % (h.esc(o["name"]), o["rank"]), _n(o["score"], 1), _n(mm["dps_cycle"]), _n(mm["hps_self"]),
                     _n(mm["ehp"]), ("%+.1f%%" % delta).replace(".", ",")])
    out.append('<p class="mudo">Os ultimos %s pontos (%s) postos noutro no. A metrica e a do objectivo (%s).</p>'
               % (_n(alts["freed"]), h.esc(removed), h.esc(B.GOAL_LABEL[goal])))
    out.append(h.table(["se os ultimos pontos fossem para", "metrica", "DPS ciclo", "HPS", "EHP", "vs build"], rows, numeric=(1, 2, 3, 4, 5)))
    return "".join(out)


def render_sources(cat, vocation):
    out = ["<h2>Fontes e convencoes</h2>",
           '<p class="mudo">Cada constante do motor com a sua fonte. <b>cliente</b> = esta no bundle publico do '
           "jogo (e a conta do proprio jogo); <b>guia</b> = guiabaiakidle.com (convencao de um site da comunidade); "
           "<b>convencao ⚠</b> = decisao nossa, sem fonte — e onde os numeros podem estar errados.</p>"]
    rows = []
    for key, c in sorted(F.CONSTANTS.items(), key=lambda kv: ({"cliente": 0, "guia": 1, "canal": 2, "convencao": 3}[kv[1].source], kv[0])):
        val = c.value
        if isinstance(val, (dict, list)):
            val = "(tabela)"
        elif val is None:
            val = "desconhecido"
        rows.append([h.esc(key), h.esc(str(val)), h.esc(SOURCE_LABEL[c.source]), h.esc(c.where) + ((" — " + h.esc(c.note)) if c.note else "")])
    out.append(h.table(["constante", "valor", "fonte", "de onde"], rows))
    out.append("<h3>O que o canal diz para esta vocacao</h3><ul>")
    for text, video in CANAL_TIPS.get(vocation, []):
        out.append("<li>%s <small class=\"mudo\">[%s %s]</small></li>" % (h.esc(text), h.esc(CANAL), h.esc(video)))
    out.append("</ul>")
    out.append('<p class="aviso">Onde o canal diz X e a conta da Y, a pagina mostra os dois: o canal e opiniao em '
               "directo, de memoria, sem data de publicacao; os numeros aqui sao um simulador com convencoes marcadas. "
               "Nenhum dos dois foi medido na conta.</p>")
    return "".join(out)


# --- cartao de print ------------------------------------------------------------------------------
PRINT_CSS = """\
body{margin:0;background:#fff;color:#111;font:13px/1.4 system-ui,sans-serif}
.card{width:390px;padding:10px 12px;box-sizing:border-box}
h1{font-size:15px;margin:0 0 4px}h2{font-size:13px;margin:10px 0 2px;color:#333;border-bottom:1px solid #ccc}
dl{display:grid;grid-template-columns:max-content 1fr;gap:1px 8px;margin:0}dt{color:#555}dd{margin:0}
ol{margin:2px 0 2px 18px;padding:0}small{color:#666}code{font-size:12px}
"""


def render_print(cat, b, generated_at):
    hc = b["helper"]
    prof = b["profile"]
    hunt = cat.hunt_by_id[b["hunt"]]["nome"]
    rot = "".join("<li>%s <code>%s</code>%s</li>" % (h.esc(n), h.esc(w), (" ≥%d" % mm) if mm else "")
                  for n, w, mm in hc["hunt_rotation"])
    boss = "".join("<li>%s <code>%s</code></li>" % (h.esc(n), h.esc(w)) for n, w, mm in hc["boss_rotation"])
    body = ['<div class="card"><h1>Helper — %s, nivel %d</h1><small>ref. %s · BaiakVault %s</small>'
            % (h.esc(title(prof.vocation, b["goal"])), b["level"], h.esc(hunt), h.esc(generated_at)),
            "<h2>Cura automática</h2>",
            h.kv([("Cura própria", "%s <code>%s</code>" % (h.esc(hc["heal_spell"]), h.esc(hc["heal_words"]))),
                  ("Cura em", "%d%% de vida" % hc["heal_at"]),
                  ("Potion de vida", "%s · beber abaixo de %d%%" % (h.esc(hc["hp_potion"]), hc["hp_below"])),
                  ("Potion de mana", ("%s · beber abaixo de %d%%" % (h.esc(hc["mana_potion"]), hc["mana_below"])) if hc["mana_potion"] else "nenhuma")]),
            "<h2>Magias de Ataque — Hunt (ordem = prioridade)</h2><ol>%s</ol>" % rot,
            "<h2>Magias de Ataque — Boss</h2><ol>%s</ol>" % boss,
            "<h2>Posição de ataque</h2>",
            h.kv([("Hunt", "%s · %d tile%s" % (h.esc(hc["position"]), hc["distance"], "s" if hc["distance"] != 1 else "")),
                  ("Boss", "diagonal · %d tiles" % (2 if prof.vocation in ("knight", "monk") else 3))])]
    if hc["magic_shield"]:
        body.append("<h2>Escudo mágico</h2><dl><dt>modo</dt><dd>Mantém utamo vita sempre ativo</dd><dt>Renovar escudo</dt><dd>10%</dd></dl>")
    if hc["friend_heal"]:
        body.append("<h2>Curar aliado</h2><dl><dt>magia</dt><dd>%s</dd><dt>gatilho</dt><dd>%d%%</dd><dt>Priorizar minha cura</dt><dd>desmarcado</dd></dl>"
                    % (h.esc(hc["friend_heal"]), hc["friend_heal_at"]))
    body.append("<h2>Equipamento (swap por vida)</h2>" + h.kv([
        ("amuleto padrão", h.esc(hc["emergency"]["amulet_standard"])),
        ("amuleto de emergência", "%s · abaixo de %d%% · restaurar acima de 80%%" % (h.esc(hc["emergency"]["amulet_emergency"]), 50 if prof.vocation == "knight" else 40)),
        ("anel de emergência", "%s · abaixo de %d%%" % (h.esc(hc["emergency"]["ring_emergency"]), 40 if prof.vocation == "knight" else 50)),
    ]))
    body.append("<small>limiares de cura/pocao: simulador; escudo, aliado e swap: canal CharllonLobo. Sem prey, sem VIP.</small></div>")
    return ("<!doctype html><html lang=\"pt\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" "
            "content=\"width=device-width,initial-scale=1\"><title>%s</title><style>%s</style></head><body>%s</body></html>"
            % (h.esc("Helper %s %d — BaiakVault" % (title(prof.vocation, b["goal"]), b["level"])), PRINT_CSS, "".join(body)))


# --- validacao (markdown -> html, o minimo) -------------------------------------------------------
def markdown_to_html(text):
    """So o que o validacao.md usa: titulos, paragrafos, listas, tabelas, negrito, codigo."""
    out = []
    lines = text.splitlines()
    i = 0
    para = []

    def flush():
        if para:
            out.append("<p>%s</p>" % _inline(" ".join(para)))
            para.clear()

    while i < len(lines):
        ln = lines[i]
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1]):
            flush()
            headers = [c.strip() for c in ln.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([_inline(c.strip()) for c in lines[i].strip("|").split("|")])
                i += 1
            out.append(h.table(headers, rows))
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            flush()
            out.append("<h%d>%s</h%d>" % (len(m.group(1)), _inline(m.group(2)), len(m.group(1))))
        elif ln.startswith("- "):
            flush()
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append("<li>%s</li>" % _inline(lines[i][2:]))
                i += 1
            out.append("<ul>%s</ul>" % "".join(items))
            continue
        elif not ln.strip():
            flush()
        else:
            para.append(ln.strip())
        i += 1
    flush()
    return "".join(out)


def _inline(text):
    text = h.esc(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def render_validation(md_text, generated_at):
    return h.page("Validacao — Builds — BaiakVault", markdown_to_html(md_text), root="../", here="builds",
                  generated_at=generated_at)
