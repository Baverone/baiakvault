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
from . import treecode
from . import validation

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
             '<p class="mudo">Primeiro a build das <b>prioridades do Andre</b> de cada vocacao — a omissao desde '
             "21/09/2026: a arvore segue a ordem estrita Avatar › Exp › Loot › Crit › Ataque › Dano critico › "
             "Elemento › o que sobrar, cada etapa esgotada antes da seguinte, e a pagina diz quanto a build de dano "
             "daria a mais. Depois a build de <b>dano</b> de cada vocacao — a omissao de 16/09/2026 "
             "(decisao do Andre: «quero dano, nao importa o custo, importa e o dano e a XP»): o maior DPS "
             "do ciclo na hunt de referencia (e XP/h), com pocoes de mana e runas a vontade nos mages e no "
             "paladin (o custo sai em gold/h, sem tecto), o knight e o monk limitados pela mana que o leech "
             "e os itens repoem (o cliente nao lhes da pocoes de mana), e sobreviver ao pack e ao boss so "
             "como restricao minima. Depois a build <b>melhor</b> (equilibrada: aguenta, sustenta a mana, o "
             "druid cura o knight) e as builds por objectivo. Tudo para qualquer nivel (aqui os "
             "representativos): arvore por ordem de compra, equipamento BiS por slot, rotacao para o Helper "
             "e numeros do simulador. <b>Os numeros sao estimativas</b>: as formulas dos feiticos e da arvore "
             "sao as do cliente do jogo; o resto vem do guia ou e convencao nossa, e esta marcado (ver a "
             'seccao «Fontes» de cada build e a <a href="validacao.html">validacao cruzada</a>).</p>']
    first_best = next(b for b in B.BUILDS if b[1] == "best")
    first_damage = next(b for b in B.BUILDS if b[1] == "damage")
    first_other = next(b for b in B.BUILDS if b[1] not in (B.PRIORITY_GOAL, "damage", "best"))
    parts.append('<h2 class="separador">As prioridades do Andre (omissao desde 21/09/2026)</h2>')
    for voc, goal in B.BUILDS:
        s = slug(voc, goal)
        if (voc, goal) == first_damage:
            parts.append('<h2 class="separador">A build de «dano» (DPS puro) de cada vocacao</h2>')
        if (voc, goal) == first_best:
            parts.append('<h2 class="separador">A build «melhor» (equilibrada) de cada vocacao</h2>')
        if (voc, goal) == first_other:
            parts.append('<h2 class="separador">As builds por objectivo</h2>')
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
                              "mana/s gasta / ganha", "gold/h (pocoes + runas)", "rotacao (hunt)"], rows,
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
                 "O roubo de vida e de mana so conta no ataque normal e nas magias de alvo unico, nunca nas "
                 "areas (cliente: texto dos charms Vampiric Embrace / Void's Call). "
                 "<b>gold/h (pocoes + runas)</b>: as runas ao gold por lancamento do cliente; as pocoes de vida "
                 "as que o Helper beberia com estes limiares; as pocoes de mana <b>em regime</b> — cada ponto de "
                 "mana que o leech e os itens nao repoem vem de uma pocao, ao preco por mana dela (a regen base do "
                 "servidor e desconhecida e conta a 0: e um tecto).</p></div>")
    parts.append(h.source_line("simulador do BaiakVault (formulas do cliente + guia + convencoes marcadas)", cat.seen_at()))
    return h.page("Builds — BaiakVault", "".join(parts), root=root, here="builds", generated_at=generated_at)


# --- pagina de uma build -------------------------------------------------------------------------
_LEVEL_JS = """<script>
(function(){var secs=document.querySelectorAll('section.nivel');var btns=document.querySelectorAll('nav.niveis a');
function show(id){secs.forEach(function(s){s.hidden=(s.id!==id)});btns.forEach(function(b){b.classList.toggle('aqui',b.getAttribute('href')==='#'+id)})}
btns.forEach(function(b){b.addEventListener('click',function(e){e.preventDefault();history.replaceState({},'',b.getAttribute('href'));show(b.getAttribute('href').slice(1))})});
var first=(location.hash||'').slice(1);if(!document.getElementById(first)){first=secs[0]&&secs[0].id}if(first){show(first)}})();
</script>"""


def render_build(cat, vocation, goal, plans_by_level, generated_at, extra_by_level=None):
    """`extra_by_level` {nivel: HTML} entra no fim da seccao de cada nivel (os charms, ordem 3)."""
    root = "../"
    extra_by_level = extra_by_level or {}
    parts = ["<h1>%s</h1>" % h.esc(title(vocation, goal))]
    parts.append('<p class="mudo">Objectivo pedido: «%s». Metrica: %s. O nivel e um parametro — escolhe o teu; '
                 "quando os personagens do Andre entrarem, a pagina de cada um chama o mesmo motor com o nivel exacto.</p>"
                 % (h.esc(B.GOAL_ASKED.get((vocation, goal), "")), h.esc(_metric_text(goal))))
    parts.append('<nav class="niveis menu">%s</nav>' % "".join(
        '<a href="#n%d">nivel %d</a>' % (lv, lv) for lv in B.LEVELS))
    for level in B.LEVELS:
        parts.append(render_level_section(cat, plans_by_level[level], root, extra_by_level.get(level, "")))
    parts.append(render_sources(cat, vocation))
    parts.append('<p><a href="index.html">&larr; todas as builds</a></p>')
    return h.page("%s — Builds — BaiakVault" % title(vocation, goal), "".join(parts) + _LEVEL_JS + CODE_JS,
                  root=root, here="builds", generated_at=generated_at)


def _metric_text(goal):
    return {
        "best": "DPS efectivo no ciclo (57 normais + boss x3 HP) sujeito a aguentar o pack (> 10 min) e o boss "
                "e a sustentar a mana (knight/monk sem pocoes; os outros sem esgotar a mana); no druid, a cura "
                "aliada sustentavel tem de cobrir a pressao do pack sobre o knight «melhor» da party. Cada "
                "condicao falhada corta o DPS pela fraccao em que falha, ao quadrado",
        "damage": "DPS efectivo no ciclo (57 normais + boss x3 HP) — e XP/h — sem tecto de gold: pocoes de mana e "
                  "runas a vontade nos mages e no paladin (o custo sai em gold/h); no knight e no monk conta so o DPS "
                  "que a mana sustenta (o leech e os itens pagam os feiticos; o ataque normal e as runas nao gastam "
                  "mana). Sobreviver ao pack inteiro e ao boss e restricao minima: falhada, corta o DPS pela fraccao "
                  "em que falha, ao quadrado. Decisao do Andre, 16/09/2026 13:30",
        "tank": "EHP com o pack em cima x sustain (leech ate cobrir a pressao) x DPS^0,3",
        "heal": "cura/s sustentavel em 60 s (propria + metade da aliada) x DPS^0,3",
        "support": "cura/s sustentavel em 60 s (propria + metade da aliada) x DPS^0,3",
        "priority": "a arvore NAO se optimiza por uma metrica: segue a ordem estrita das prioridades do Andre "
                    "(21/09/2026) — 1 Avatar (o notable de tier 11 + o caminho ligado mais barato), 2 Exp, 3 Loot, "
                    "4 Critical Chance, 5 Ataque geral (atk % / dano de magia %), 6 Dano critico, 7 Elemento da rotacao "
                    "e da arma, 8 o que sobrar pelo guloso de DPS — cada etapa esgota-se antes da seguinte. O "
                    "equipamento, a rotacao e os numeros medem-se como na build «dano» (DPS do ciclo = XP/h), e a "
                    "pagina diz quanto a build «dano» do mesmo nivel daria a mais",
    }[goal]


def render_level_section(cat, b, root, extra=""):
    level = b["level"]
    m = b["metrics"]
    prof = b["profile"]
    target = b["target"]
    hunt = cat.hunt_by_id[b["hunt"]]
    out = ['<section class="nivel" id="n%d"><h2>Nivel %d — alvo de referencia: <a href="%shunts/%s.html">%s</a> (%d+)</h2>'
           % (level, level, root, hunt["id"], h.esc(hunt["nome"]), hunt.get("nivel_minimo") or 0)]
    # resumo
    sustained = ""
    if not prof.uses_mana_potions:
        sustained = (' <small class="mudo">— sustentado (so os feiticos que a mana paga, %s deles): %s / %s / %s</small>'
                     % (_pct(m["mana_sustain"] * 100, 0), _n(m["dps_cycle_sustained"]), _n(m["dps_pack_sustained"]),
                        _n(m["dps_boss_sustained"])))
    out.append('<div class="cartao">' + h.kv([
        ("DPS ciclo / pack / boss", "%s / %s / %s%s" % (_n(m["dps_cycle"]), _n(m["dps_pack"]), _n(m["dps_boss"]), sustained)),
        ("do ataque automatico", _n(m["auto_dps"]) + ' <small class="mudo">(convencao ⚠, ver Fontes)</small>'),
        ("cura/s sustentavel (propria / aliada)", "%s / %s" % (_n(m["hps_self"]), _n(m["hps_friend"]) if m["hps_friend"] else "—")),
        ("HP / mana", "%s / %s" % (_n(m["hp_max"]), _n(m["mana_max"]))),
        ("EHP", _n(m["ehp"]) + " (%s do dano da hunt fica na mitigacao)" % _pct(m["mitigated_share"] * 100, 1)),
        ("pressao (1 monstro / pack)", "%s / %s por segundo; maior golpe %s (boss %s)"
         % (_n(m["pressure_one"]), _n(m["pressure_pack"]), _n(m["max_hit"]), _n(m["boss_max_hit"]))),
        ("aguenta (pack / 1 monstro)", "%s / %s" % (_seconds(m["ttd_pack"]), _seconds(m["ttd_one"]))),
        ("mana/s gasta / ganha", "%s / %s — %s%s" % (_n(m["mana_demand"], 1), _n(m["mana_income"], 1), _mana_verdict(m),
                                                    " ⚠ a mana por tiro da wand nao esta no catalogo: contou a 0"
                                                    if prof.wand and (prof.weapon or {}).get("mana_por_tiro") is None else "")),
        ("gold/h, pocoes + runas (hunt / boss)", "%s / %s — %d pocoes de vida e %d de mana por minuto nos 60 s; "
         'as de mana contam em regime (ver a rotacao)%s'
         % (h.kk(m["gold_per_hour"]), h.kk(m["boss_gold_per_hour"]), m["hp_potions"], m["mana_potions"],
            (" — <b>tecto: %s gold/h</b>" % h.kk(b["gold_cap"])) if b.get("gold_cap") is not None
            else ' <small class="mudo">(sem tecto: «nao importa o custo», Andre 16/09/2026)</small>')),
        ("skills assumidos", _skills_text(prof)),
        ("tactica (IA de combate)", _tactics_text(prof)),
    ]) + "</div>")
    if target.resist_fallback or target.resist_unknown:
        bits = []
        if target.resist_fallback:
            bits.append("resistencias de %s pela 2.a tabela de combate do cliente (o bestiario nao as declara) ⚠"
                        % ", ".join(target.resist_fallback))
        if target.resist_unknown:
            bits.append("%s sem resistencias em fonte nenhuma: nao entra na media (nao se assume 0)"
                        % ", ".join(target.resist_unknown))
        out.append('<p class="mudo"><small>%s.</small></p>' % h.esc("; ".join(bits)))
    if m.get("death_at") is not None or m.get("boss_death_at") is not None:
        out.append('<p class="aviso">⚠ No simulador o personagem morre (hunt aos %s s, boss aos %s s) — com esta '
                   "build a hunt de referencia e demasiado forte a solo; e o que o simulador diz, nao um erro da pagina.</p>"
                   % (h.fmt(m.get("death_at")), h.fmt(m.get("boss_death_at"))))
    if b["goal"] in ("best", "damage", B.PRIORITY_GOAL):
        out.append(_constraints_block(m, b["goal"]))
    out.append(_tree_block(cat, b))
    out.append(_equipment_block(cat, b, root))
    out.append(_helper_block(cat, b, root))
    out.append(extra)
    out.append(_alternatives_block(cat, b))
    out.append("</section>")
    return "".join(out)


CONSTRAINT_LABEL = {
    "survive_pack": "aguenta o pack &gt; 10 min",
    "survive_boss": "aguenta o boss (60 s do simulador)",
    "mana": "mana sustentavel",
    "heal_ally": "cura aliada cobre a pressao do pack sobre o knight",
}


def _constraints_block(m, goal="best"):
    """As condicoes da build («melhor» ou «dano») e o que o simulador diz de cada uma."""
    cons = B.goal_constraints(m, goal)
    rows = []
    for key, frac in cons.items():
        if key == "mana":
            if m.get("uses_mana_potions"):
                detail = ("a mana nao se esgota nos 60 s (com pocoes; custo em «supplies»)" if frac >= 1
                          else "a mana esgota-se aos %s s mesmo com pocoes" % h.fmt(m.get("mana_empty_at")))
            else:
                detail = "gasta %s (rotacao + curas com o pack inteiro) / ganha %s mana/s sem pocoes (cliente: o Helper nao as bebe)" % (
                    _n(m["full_mana_demand"], 1), _n(m["mana_income"], 1))
        elif key == "heal_ally":
            detail = "cura aliada sustentavel %s/s contra %s/s de pressao sobre o knight «melhor» ao mesmo nivel" % (
                _n(m["hps_friend"]), _n(m["ally_pressure"]))
        elif key == "survive_boss":
            detail = "aguenta %s o boss (x1,5 dano), com curas e pocoes" % _seconds(m["survive_boss_s"])
        else:
            detail = "aguenta %s com o pack inteiro (%d) em cima, com curas e pocoes; vida minima %s" % (
                _seconds(m["survive_pack_s"]), m.get("attackers_full") or 0, _n(m["full_hp_min"]))
        rows.append([CONSTRAINT_LABEL[key], "cumprida" if frac >= 1 else "<b>falha a %s</b>" % _pct(frac * 100, 0), detail])
    ok = all(f >= 1 for f in cons.values())
    label = {"best": "«melhor»", "damage": "de «dano» (restricao minima: nao morrer)"}.get(
        goal, "«prioridades» (medida como a de «dano»: nao morrer)")
    return ('<div class="cartao"><h4>Condicoes da build %s%s</h4>%s</div>'
            % (label, "" if ok else ' <span class="aviso">— nem todas cumpridas: a metrica da build (nao o DPS mostrado) '
                                    'esta cortada por isso; e o melhor que o optimizador encontrou a este nivel</span>',
               h.table(["condicao", "estado", "o que o simulador diz"], rows)))


def tactics_summary(prof):
    """«Tactica: nivel N · X % (raio Y)» com o no e sem ele — o painel do personagem
    mostra o mesmo (cliente u4e); o que uma decisao imperfeita vale e convencao."""
    ranks = prof.specials.get("tactics", 0)
    with_node = prof.tactics
    without = F.battle_tactics(prof.level, 0)
    return {"ranks": ranks, "with": with_node, "without": without,
            "quality_with": prof.ai_quality, "quality_without": F.tactics_quality(without["aim_chance"])}


def _tactics_text(prof):
    t = tactics_summary(prof)
    w, o = t["with"], t["without"]
    text = "Tactica: nivel %d · <b>%s</b> (raio %d)" % (w["tier"], _pct(w["aim_chance"] * 100, 1), w["cast_search_radius"])
    if t["ranks"]:
        text += (" com Battle Tactics %d; sem o no: nivel %d · %s (raio %d)"
                 % (t["ranks"], o["tier"], _pct(o["aim_chance"] * 100, 1), o["cast_search_radius"]))
    else:
        text += " (sem ranks de Battle Tactics)"
    text += (' <small class="mudo">— chance de decisao perfeita da IA (cliente u4e); uma imperfeita rende %s do dano '
             "e apanha o que a perfeita evitaria (convencao ⚠): factor %s no dano%s; kite infinito %s</small>"
             % (_pct(F.TACTICS_IMPERFECT_FACTOR * 100), ("%.3f" % t["quality_with"]).replace(".", ","),
                (" (%s sem o no)" % ("%.3f" % t["quality_without"]).replace(".", ",")) if t["ranks"] else "",
                "sim" if w["infinite_kite"] else "nao (tier 3 destrava)"))
    return text


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


# O botao «Copiar» do codigo de build: navigator.clipboard com fallback de seleccao (o mesmo
# que o cliente faz no «Exportar»). JavaScript vanilla, so aqui.
CODE_JS = """<script>
(function(){document.querySelectorAll('button.copiar').forEach(function(b){b.addEventListener('click',function(){
var t=document.getElementById(b.getAttribute('data-alvo'));if(!t){return}var v=t.value||t.textContent;
function ok(){b.textContent='Copiado!';setTimeout(function(){b.textContent='Copiar'},1300)}
function fb(){try{t.focus();t.select();document.execCommand('copy');ok()}catch(e){}}
if(navigator.clipboard){navigator.clipboard.writeText(v).then(ok,fb)}else{fb()}})})})();
</script>"""

ROLE_LABEL = {B.ROLE_DAMAGE: "dano", B.ROLE_LINK: "so ligacao", B.ROLE_TACTICS: "tactica", B.ROLE_LEFTOVER: "ponto que sobrou"}
ROLE_LABEL.update({k: v for k, v in B.PRIORITY_LABEL.items() if k != "rest"})
STAGE_NUMBER = {stage: i + 1 for i, stage in enumerate(B.PRIORITY_ORDER)}


def _stage_text(stage):
    if stage is None:
        return h.UNKNOWN
    return "%d. %s" % (STAGE_NUMBER.get(stage, 0), B.PRIORITY_LABEL.get(stage, stage))


def _pct_signed(x, decimals=1):
    return ("%+.*f%%" % (decimals, x)).replace(".", ",")


def priority_block(cat, b, root="../", with_avatar_code=True):
    """O que so a build «prioridades» tem: os totais por categoria, o Avatar (sim/nao
    e a que nivel cabe, com a build desse nivel e o codigo), os pontos que sobraram e
    para onde foram, as categorias que a vocacao nao tem, e o que a build «dano» do
    mesmo nivel daria a mais (informacao — nunca substitui a escolha dele)."""
    info = b.get("priority")
    if not info:
        return ""
    voc, level = b["vocation"], b["level"]
    tot = info["totals"]
    node_by_id = {n["id"]: n for n in cat.tree_by_vocation[voc]["nos"]}
    avatar = node_by_id[B.AVATAR_NODE[voc]]
    out = ['<div class="cartao"><h4>As prioridades do Andre nesta arvore (nivel %d)</h4>' % level]
    if info["avatar"]:
        avatar_text = ("<b>sim</b> — %s com o caminho mais barato (%s: %d pontos + 300); cabe a partir do nivel %d"
                       % (h.esc(avatar["nome"]), h.esc(", ".join(_node_name(cat, p) for p in info["avatar_path"])),
                          (info["avatar_level"] or 300) - 300, info["avatar_level"] or 0))
    else:
        avatar_text = ("<b>nao</b> — %s <b>cabe ao nivel %s</b> (caminho mais barato %s pontos + 300 &gt; %d): "
                       "esta etapa salta-se agora e as restantes seguem; no nivel %s o passo e importar a build desse "
                       "nivel (respec pelo cliente fD = 1000 + 200 x pontos gastos — o gold nao conta, decisao de 16/09/2026)"
                       % (h.esc(avatar["nome"]), _n(info["avatar_level"]), _n((info["avatar_level"] or 300) - 300), level,
                          _n(info["avatar_level"])))
    rows = [("1. Avatar", avatar_text)]
    have = {}
    for nid, node in node_by_id.items():
        for stat in (node.get("efeito_por_rank") or {}):
            c = B.PRIORITY_STAT_CATEGORY.get(stat)
            if c:
                have.setdefault(c, set()).add(node["nome"])
    for stage, text in (("exp", "+%s exp" % _pct(tot["expPct"], 1)), ("loot", "+%s loot" % _pct(tot["lootPct"], 1)),
                        ("crit", "+%s critical chance" % _pct(tot["critChance"], 1)),
                        ("attack", "+%s atk / +%s dano de magia" % (_pct(tot["atkPct"], 1), _pct(tot["spellDmgPct"], 1))),
                        ("critdmg", "+%s dano critico" % _pct(tot["critDmg"], 1)),
                        ("element", ", ".join("+%s %s" % (_pct(v, 1), ELEMENT_LABEL.get(el, el)) for el, v in sorted(tot["element"].items()))
                         or "nenhum no de elemento da rotacao/arma comprado")):
        pts = info["stage_points"].get(stage, 0)
        if stage in ("exp", "loot") and not have.get(stage):
            text = "<b>a vocacao nao tem nos de %s</b> — nada a comprar nesta etapa" % B.PRIORITY_LABEL[stage]
        elif stage == "element":
            text += " <small class=\"mudo\">(elementos da rotacao e da arma: %s)</small>" % h.esc(
                ", ".join(ELEMENT_LABEL.get(el, el) for el in info["elements"]))
        rows.append((_stage_text(stage), "%s <small class=\"mudo\">— %s ponto%s nesta etapa</small>" % (text, _n(pts), "" if pts == 1 else "s")))
    rest_pts = info["stage_points"].get("rest", 0)
    rest_nodes = [(_node_name(cat, st.node_id), st.rank) for st in b.get("order") or [] if st.stage == "rest"]
    rest_text = ("%s ponto%s: %s" % (_n(rest_pts), "" if rest_pts == 1 else "s",
                                       h.esc(", ".join("%s %d" % (n, r) for n, r in rest_nodes[-12:])) or "—")
                 if rest_pts else "0 pontos — as sete etapas gastaram tudo")
    rows.append(("8. O que sobrar (guloso de DPS)", rest_text))
    out.append(h.kv(rows))
    if not have.get("exp") and not have.get("loot"):
        out.append('<p class="mudo">Esta vocacao nao tem nos de Exp nem de Loot na arvore do cliente: as etapas 2 e 3 '
                   "ficam vazias e passa-se ao Crit.</p>")
    dmg = b.get("damage_plan")
    if dmg:
        pm, dm = b["metrics"], dmg["metrics"]
        dps_diff = (dm["dps_cycle"] / pm["dps_cycle"] - 1) * 100 if pm["dps_cycle"] else None
        gold_diff = ((dm["gold_per_hour"] / pm["gold_per_hour"] - 1) * 100) if pm["gold_per_hour"] else None
        out.append('<p><b>Contra a build «dano» do mesmo nivel</b> (o maior DPS do simulador, sem prioridades): '
                   "a build de dano daria <b>%s de DPS do ciclo</b> (%s vs %s = XP/h) e %s de gold/h (%s vs %s) — "
                   'informacao, nunca substitui a escolha dele; <a href="%sbuilds/%s.html#n%d">ver a build de dano</a>.</p>'
                   % (_pct_signed(dps_diff) if dps_diff is not None else h.UNKNOWN, _n(dm["dps_cycle"]), _n(pm["dps_cycle"]),
                      (_pct_signed(gold_diff) if gold_diff is not None else ("0 nas duas" if not dm["gold_per_hour"] else h.UNKNOWN)),
                      h.kk(dm["gold_per_hour"]), h.kk(pm["gold_per_hour"]), root, slug(voc, "damage"), level))
    ap = b.get("avatar_plan")
    if ap is not None:
        ap_info = ap["priority"]
        out.append('<h4>A build com o %s, ao nivel %d</h4>' % (h.esc(avatar["nome"]), ap["level"]))
        out.append('<p class="mudo">Pontos por etapa: %s. Totais: +%s exp, +%s loot, +%s crit, +%s atk / +%s dano de magia, '
                   "+%s dano critico.</p>" % (
                       h.esc(", ".join("%s %d" % (B.PRIORITY_LABEL[s], p) for s, p in ap_info["stage_points"].items() if p)),
                       _pct(ap_info["totals"]["expPct"], 1), _pct(ap_info["totals"]["lootPct"], 1), _pct(ap_info["totals"]["critChance"], 1),
                       _pct(ap_info["totals"]["atkPct"], 1), _pct(ap_info["totals"]["spellDmgPct"], 1), _pct(ap_info["totals"]["critDmg"], 1)))
        rows = []
        for st in ap["order"]:
            rows.append([_stage_text(st.stage), h.esc(_node_name(cat, st.node_id)), "%d" % st.rank, _n(st.cumulative)])
        out.append("<details><summary>Ordem de compra ao nivel %d (%d passos)</summary>%s</details>"
                   % (ap["level"], len(rows), h.table(["etapa", "no", "rank", "ate ao nivel"], rows, numeric=(2, 3))))
        if with_avatar_code:
            out.append(code_block(treecode.encode(cat, voc, ap["level"], ap["tree"]),
                                  "codigo-%s-%d-avatar" % (slug(voc, b["goal"]), level),
                                  spent_label="e o codigo a importar quando chegares ao nivel %d" % ap["level"]))
    out.append("</div>")
    return "".join(out)


def code_block(code, ident, spent_now=None, spent_label=None):
    """O codigo de build do cliente com «Copiar», a frase de onde o colar e o custo de
    importar: `fD` = 1000 + 200 x pontos gastos AGORA (0 sem pontos). `spent_now` e
    o que a BD diz que ele tem gastos («?» sem isso)."""
    if spent_now is None:
        cost = ("%s <small class=\"mudo\">(1000 + 200 x pontos gastos agora — nao sei quantos tens gastos%s)</small>"
                % (h.UNKNOWN, ("; " + spent_label) if spent_label else ""))
    else:
        gold = treecode.import_cost(spent_now)
        cost = ("<b>%s gold</b> <small class=\"mudo\">(cliente fD: %s; %s pontos gastos agora%s)</small>"
                % (h.kk(gold), "1000 + 200 x pontos" if gold else "0 sem pontos gastos", _n(spent_now),
                   ("; " + spent_label) if spent_label else ""))
    return ('<div class="cartao codigo"><h4>Codigo da arvore (Exportar / Importar do cliente)</h4>'
            '<p><input type="text" id="%s" value="%s" readonly size="%d" spellcheck="false"> '
            '<button type="button" class="copiar" data-alvo="%s">Copiar</button></p>'
            '<p class="mudo">Na arvore do personagem: <b>Colar codigo para importar…</b> → <b>Carregar</b>. '
            "Importar substitui a arvore actual e custa %s. O formato e o do proprio cliente (`BT1-`, um digito "
            "hexadecimal por no; lido no bundle a 16/09/2026 — se o «Exportar» do jogo deixar de dar `BT1-`, "
            "o formato mudou).</p></div>"
            % (h.esc(ident), h.esc(code), min(80, max(30, len(code) + 2)), h.esc(ident), cost))


def _validation_line(cat, b):
    chk = B.tree_check(cat, b["vocation"], b["level"], b["tree"])
    bits = ["ligada a partir do tier 0" if chk["connected"] else "<b>NAO ligada ao tier 0</b>",
            "ranks ≤ maximo" if chk["max_rank_ok"] else "<b>rank acima do maximo</b>",
            "%s de %s pontos" % (_n(chk["spent"]), _n(chk["budget"]))]
    return ('<p class="mudo"><small>Valida pelas regras do cliente (O3e/yD/Up): %s%s.</small></p>'
            % ("; ".join(bits), "" if chk["ok"] else " — <b>⚠ invalida</b>"))


def _fire_note(cat, tree):
    names = [cat.node_by_id[nid]["nome"] for nid in tree if cat.node_by_id[nid]["nome"] in B.FIRE_NAMED_GENERIC]
    if not names:
        return ""
    return ('<p class="mudo"><small>Nota sobre os nomes: %s tem nome de fogo mas o efeito e generico '
            "(<code>spellDmgPct</code>: +dano de TODAS as magias, cliente) — nao sao nos de fogo.</small></p>"
            % h.esc(", ".join(names)))


def _tree_block(cat, b, root="../", with_code=True):
    steps = b.get("order") or b["steps"]
    fill = b["fill_steps"]
    roles = b.get("roles") or {}
    priority = b["goal"] == B.PRIORITY_GOAL
    out = ["<h3>Arvore — %s/%s pontos</h3>" % (_n(b["points_spent"]), _n(b["points_budget"]))]
    rows = []
    # ordem de compra, comprimida: um no seguido ate ao rank em que muda (na «prioridades» tambem
    # so dentro da mesma etapa: o mesmo no pode entrar como caminho e subir de rank noutra etapa)
    order = []
    for st in steps:
        stage = getattr(st, "stage", None)
        if order and order[-1][0] == st.node_id and order[-1][4] == stage:
            order[-1] = (st.node_id, st.rank, order[-1][2], st.cumulative, stage)
        else:
            order.append((st.node_id, st.rank, st.rank, st.cumulative, stage))
    for nid, r_to, r_from, cum, stage in order:
        role, gain = roles.get(nid, (None, None))
        role_text = h.esc(ROLE_LABEL.get(role, "?"))
        if gain is not None and role == B.ROLE_DAMAGE:
            role_text += ' <small class="mudo">%s</small>' % ("+%.1f%%" % gain).replace(".", ",")
        row = [h.esc(_node_name(cat, nid)),
               ("%d" % r_to) if r_from == r_to else "%d → %d" % (r_from, r_to),
               _n(cum), role_text]
        if priority:
            row.insert(0, h.esc(_stage_text(stage)))
        rows.append(row)
    if priority:
        out.append('<p class="mudo">Ordem de compra <b>por etapas</b> (Avatar → Exp → Loot → Crit → Ataque → Dano critico → '
                   "Elemento → o resto), e a que ele clica no jogo; o numero e o nivel em que se chega la (cada nivel da um "
                   "ponto — cliente). <b>Clicavel a mao</b>: cada no, quando entra, ja tem um vizinho comprado (regra yD). O "
                   "papel: a etapa a que o no pertence; <b>so ligacao</b> quando so entrou como caminho (rank 1) para "
                   "chegar a um no de uma etapa acima; na etapa 8 os papeis de sempre (<b>dano</b> com o ganho medido, "
                   "<b>tactica</b>, <b>ponto que sobrou</b>). Dentro de cada etapa a ordem e por rendimento por ponto: "
                   "Exp e Loot pelo proprio efeito por ponto; Crit, Ataque, Dano critico e Elemento pelo ganho de DPS por "
                   "ponto medido no simulador com a rotacao desta build.</p>")
        out.append(h.table(["etapa", "no", "rank", "ate ao nivel", "papel"], rows, numeric=(3,)))
    else:
        out.append('<p class="mudo">Ordem de compra a subir de nivel (o numero e o nivel em que se chega la, '
                   "porque cada nivel da um ponto — cliente), <b>clicavel a mao</b>: cada no, quando entra, ja tem um "
                   "vizinho comprado (regra yD do cliente). O papel de cada no: <b>dano</b> (o que rende na metrica, com o "
                   "ganho de o ter), <b>so ligacao</b> (rende ~0 mas segura o ramo), <b>tactica</b> (Battle Tactics), "
                   "<b>ponto que sobrou</b> (gasto no fim, sem rank de dano que o aceitasse — vai para HP/absorcao).</p>")
        out.append(h.table(["no", "rank", "ate ao nivel", "papel"], rows, numeric=(2,)))
    out.append(_validation_line(cat, b))
    out.append(_fire_note(cat, b["tree"]))
    if priority:
        out.append(priority_block(cat, b, root))   # com o codigo do nivel do Avatar, se ainda nao cabe
    if b.get("pruned"):
        out.append('<p class="mudo">Podados no fim (rendiam ~0 na metrica e a arvore continua ligada sem eles; os pontos '
                   "voltaram a gastar-se): %s.</p>" % h.esc("; ".join(
                       "%s %d → %d" % (_node_name(cat, nid), a, c) for nid, a, c in b["pruned"])))
    if b.get("path_scores") and len(b["path_scores"]) > 1:
        used = b.get("path_goal")
        out.append('<p class="mudo"><small>Caminho usado: o da build «%s» (metrica %s contra %s do outro caminho — o '
                   "guloso depende do caminho, e o plano avalia os dois).</small></p>" % (
                       h.esc(B.GOAL_LABEL.get(used, used)), _n(b["path_scores"].get(used), 1),
                       ", ".join(_n(v, 1) for k, v in b["path_scores"].items() if k != used)))
    if with_code:
        out.append(code_block(treecode.encode(cat, b["vocation"], b["level"], b["tree"]),
                              "codigo-%s-%d" % (slug(b["vocation"], b["goal"]), b["level"]),
                              spent_label="com os %d pontos desta arvore gastos seriam %s gold"
                              % (b["points_spent"], h.kk(treecode.import_cost(b["points_spent"])))))
    savings = [st for st in steps if getattr(st, "saving", None)]
    if savings:
        out.append('<p class="mudo">Onde o caminho poupa em vez de comprar pequenos (so quando rende pelo menos '
                   "%s%% mais do que os mesmos pontos nos outros nos, medidos no simulador ao nivel em que se "
                   "chega la): %s.</p>" % (_n(B.SAVE_MARGIN * 100), "; ".join(_saving_text(cat, st) for st in savings)))
    if b["next_step"] is not None:
        ns = b["next_step"]
        sv = getattr(ns, "saving", None)
        out.append('<p class="aviso">O caminho esta a poupar para <b>%s</b> (%s pontos, chega ao nivel %s)%s.</p>'
                   % (h.esc(_node_name(cat, ns.node_id)), _n(ns.cost), _n(ns.cumulative),
                      (" — " + _saving_text(cat, ns)) if sv else ""))
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


def _saving_text(cat, st):
    """«poupar N niveis (do A ao B) para X rende +Y % face a +Z % de comprar pequenos (…)»."""
    sv = st.saving
    alt = {}
    for nid, rank in sv["alt"]:
        alt[nid] = rank
    alt_text = ", ".join("%s %d" % (_node_name(cat, nid), r) for nid, r in alt.items()) or "nada compravel"
    return h.esc("poupar %d niveis (do %d ao %d) para %s rende %+.1f%% face a %+.1f%% de comprar pequenos (%s)"
                 % (sv["wait"], sv["from_level"], st.level, _node_name(cat, st.node_id), sv["gain_pct"],
                    sv["alt_gain_pct"], alt_text)).replace(".", ",")


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


def _excluded_text(hc):
    """A linha «beams: so no boss» (regra do Andre) e o que ficou fora da rotacao de hunt e porque."""
    bits = ["beams: so no boss (decisao do Andre, 16/09/2026)"]
    for name, words, why in hc.get("hunt_excluded") or ():
        bits.append("%s (%s): fora da hunt — %s" % (name, words, why))
    return '<p class="mudo"><small>%s.</small></p>' % h.esc("; ".join(bits))


ROTATION_HEADERS = ["slot", "magia", "≥N", "custo por lancamento", "lancamentos/min", "gold/h"]


def _rotation_rows(rotation, costs, supplies, boss=False):
    """As linhas da tabela da rotacao: por feitico o custo (mana, ou gold no caso das
    runas — cliente), os lancamentos por minuto do simulador e o gold/h; no fim a
    linha do total «gold/h (pocoes + runas)» — as pocoes de mana em regime."""
    by_words = {c["words"]: c for c in costs}
    rows = []
    for i, (name, words, min_mobs) in enumerate(rotation, 1):
        c = by_words.get(words)
        if c and c["rune"]:
            cost = "<b>%s gold</b> (runa; mana %s)" % (_n(c["gold_per_cast"]), _n(c["mana"]))
        elif c:
            cost = "%s mana" % _n(c["mana"])
        else:
            cost = h.UNKNOWN
        rows.append(["slot %d" % i, "<b>%s</b> <code>%s</code>" % (h.esc(name), h.esc(words)),
                     ("≥%d mobs" % min_mobs) if (min_mobs and not boss) else "—", cost,
                     _n(c["casts_per_min"], 1) if c else h.UNKNOWN,
                     h.kk(c["gold_per_hour"]) if c else h.UNKNOWN])
    if supplies:
        rows.append(["", "<b>gold/h (pocoes + runas)</b>", "", "runas %s · pocoes de vida %s · pocoes de mana em regime %s"
                     % (h.kk(supplies["runes"]), h.kk(supplies["hp_potions"]), h.kk(supplies["mana_potions"])),
                     "", "<b>%s</b>" % h.kk(supplies["total"])])
    return rows


def _runes_note(rotation, costs):
    """O que se assumiu sobre as runas quando ha uma na rotacao (convencoes ⚠)."""
    if not any(c["rune"] for c in (costs or [])):
        return ""
    return ('<p class="mudo"><small>Runas na rotacao (teste do Andre, 16/09/2026): o gold por lancamento e o '
            "`goldCost` do cliente e a mana (5) tambem; assumido ⚠ que apanham o spellDmgPct e o elemento da "
            "arvore como qualquer feitico e que ocupam o cooldown de grupo de ataque (2 s); o «≥%d» de uma runa "
            "de area e convencao ⚠ (nao gasta mana, so gold).</small></p>" % F.RUNE_AREA_MIN_MOBS)


def _no_runes_note(b):
    """«Sem runas» — a mesma escolha so com magias de mana, para se ver o que as runas compram."""
    bits = []
    for label, rot_key, sim_key, base_key in (("hunt", "rotation_no_runes", "hunt_sim_no_runes", "hunt_sim"),
                                              ("boss", "boss_rotation_no_runes", "boss_sim_no_runes", "boss_sim")):
        rot, r, base = b.get(rot_key), b.get(sim_key), b.get(base_key)
        if not rot or r is None or base is None:
            continue
        with_runes = any(sim.is_rune(sl.spell) for sl in (b["rotation"] if label == "hunt" else b["boss_rotation"]))
        if not with_runes:
            continue
        bits.append("%s sem runas: %s → DPS %s (%s) por %s gold/h" % (
            label, ", ".join(sl.spell["nome"] for sl in rot), _n(r.dps),
            ("%+.0f%%" % ((r.dps / base.dps - 1) * 100)) if base.dps else h.UNKNOWN, h.kk(r.gold_per_hour)))
    if not bits:
        return ""
    return '<p class="mudo">%s.</p>' % h.esc("; ".join(bits))


def _pct_diff(a, b):
    if not b:
        return h.UNKNOWN
    return ("%+.0f%%" % ((a / b - 1) * 100)).replace(".", ",")


def fixed_rotation_note(b):
    """Com a rotacao fixada por ele: a que o optimizador escolheria ao lado, com a diferenca
    de DPS e de gold/h em numero. Nunca se substitui a escolha dele; mostram-se as duas."""
    if not b.get("fixed_rotation"):
        return ""
    bits = []
    r, mr = b.get("hunt_sim"), b.get("model_sim")
    rot, mrot = b.get("rotation") or [], b.get("model_rotation") or []
    if r is not None and mr is not None:
        fixed_names = [sl.spell["nome"] for sl in rot]
        model_names = [sl.spell["nome"] for sl in mrot]
        if fixed_names == model_names:
            bits.append("hunt: o modelo escolheria a mesma (%s)" % h.esc(", ".join(fixed_names)))
        else:
            d = abs(mr.dps / r.dps - 1) * 100 if r.dps else 0.0
            verdict = ("diferenca dentro do erro do modelo" if d < 5 else "diferenca que vale a pena testar no jogo")
            if r.gold_per_hour or mr.gold_per_hour:
                gold = "%s de gold/h (%s vs %s)" % (_pct_diff(mr.gold_per_hour, r.gold_per_hour) if r.gold_per_hour else h.UNKNOWN,
                                                   h.kk(mr.gold_per_hour), h.kk(r.gold_per_hour))
            else:
                gold = "gold/h a 0 nas duas (sem runas nem pocoes de mana)"   # knight/monk: «? (0 vs 0)» era enganador
            bits.append("hunt: o modelo prefere <b>%s</b> por %s de DPS (%s vs %s) e %s; escolheste %s — %s"
                        % (h.esc(", ".join(model_names)), _pct_diff(mr.dps, r.dps), _n(mr.dps), _n(r.dps),
                           gold, h.esc(", ".join(fixed_names)), verdict))
    bits.append("boss: a do optimizador (%s) — fixaste a rotacao de hunt, nao a de boss"
                % h.esc(", ".join(sl.spell["nome"] for sl in (b.get("boss_rotation") or []))))
    weapon = b.get("fixed_weapon")
    head = ("<b>Rotacao de hunt fixada por ti</b> (%s%s; decisao tua de 16/09/2026 14:30 — e um dado, nao uma sugestao: "
            "a arvore recomendada foi calculada para ela)." % (h.esc(", ".join(b["fixed_rotation"])),
                                                              (" com a arma %s" % h.esc(weapon)) if weapon else ""))
    return '<div class="cartao"><p>%s</p><p class="mudo">%s.</p></div>' % (head, "; ".join(bits))


def _helper_block(cat, b, root, print_link=True):
    hc = b["helper"]
    prof = b["profile"]
    m = b["metrics"]
    out = ["<h3>Rotacao para o Helper</h3>",
           '<p class="mudo">Com os nomes dos campos do jogo (etiquetas do cliente). O que vem do canal esta '
           "marcado [canal]; o resto e o simulador.</p>", fixed_rotation_note(b)]
    rot_rows = _rotation_rows(hc["hunt_rotation"], hc.get("hunt_costs") or [], hc.get("hunt_supplies"))
    boss_rows = _rotation_rows(hc["boss_rotation"], hc.get("boss_costs") or [], hc.get("boss_supplies"), boss=True)
    rune_note = _no_runes_note(b)
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
        ("Magias de Ataque — Rotação (ordem = prioridade · ≥N = mín. de mobs)",
         h.table(ROTATION_HEADERS, rot_rows, numeric=(4, 5)) + _excluded_text(hc) + _runes_note(hc["hunt_rotation"], hc.get("hunt_costs"))),
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
        ("Magias de Ataque — Rotação", h.table(ROTATION_HEADERS, boss_rows, numeric=(4, 5))),
        ("Posição de ataque / Distância do alvo", "<b>Fica num dos cantos diagonais do alvo</b> a <b>%d tiles</b> <small class=\"mudo\">[canal rP83AhzvK9M]</small>"
         % (2 if prof.vocation in ("knight", "monk") else 3)),
        ("Cura", "igual a da hunt; SSA abaixo de <b>%d%%</b> <small class=\"mudo\">[canal]</small>" % (65 if prof.vocation == "knight" else 60)),
        ("numeros", "DPS %s, maior golpe do boss %s, mana %s" % (_n(m["dps_boss"]), _n(m["boss_max_hit"]),
                                                                 ("esgota aos %d s" % m["boss_mana_empty_at"]) if m["boss_mana_empty_at"] is not None else "aguenta os 60 s")),
    ]) + rune_note + "</div>")
    if print_link:
        out.append('<p><a href="%sprint/helper-%s-%d.html">cartao para copiar (390 px)</a></p>'
                   % (root, slug(prof.vocation, b["goal"]), b["level"]))
    return "".join(out)


# As quatro pranchas do canal (video h8KqkibxfOc): opiniao, citada. Uma prancha por
# rank de Battle Tactics; a prancha so decide ONDE (cliente).
CANAL_BOARDS = (("encerramento", "fechar o pack: todos colados ao alvo para as areas apanharem tudo"),
                ("UE", "a party junta no centro para o Ultimate Explosion/areas grandes apanharem o pack inteiro"),
                ("waves", "em linha atras do tank para os waves/beams cobrirem a frente"),
                ("main", "a posicao de sempre: tank a frente, mages e paladin a 3 tiles"))
BOARDS_VIDEO = "h8KqkibxfOc"


def render_tactics_block(cat, hunt, plans):
    """O bloco «Tacticas» de uma hunt: pranchas = ranks de Battle Tactics de cada
    personagem, o que uma prancha decide (so posicao — cliente) e as quatro do canal."""
    rows = []
    for c, b in plans:
        ranks = b["profile"].specials.get("tactics", 0)
        t = b["profile"].tactics
        rows.append([h.esc(c["name"]), "%d" % ranks, "nivel %d · %s (raio %d)" % (t["tier"], _pct(t["aim_chance"] * 100, 1), t["cast_search_radius"]),
                     "sim" if t["infinite_kite"] else "nao"])
    out = ["<h3>Tacticas (pranchas)</h3>",
           '<p class="mudo">Cliente: «Uma prancha por ponto de Battle Tactics … Nunca decide magia, cura nem '
           "pocao: so ONDE»; «cada rank vale +100 niveis de IA e afia a CHANCE de jogar perfeito — mira, "
           "posicionamento e reacao (nivel 3 de tatica destrava o kite infinito sem tank)». As pranchas que "
           "tem sao os ranks de Battle Tactics na arvore registada (build recomendada quando a dele nao esta).</p>"]
    if rows:
        out.append(h.table(["personagem", "pranchas (ranks)", "tactica", "kite infinito"], rows))
    pack = int(hunt.get("max_vivos") or 1)
    suggested = "UE + main" if pack >= 4 else "main"
    out.append('<p>As quatro pranchas do canal [%s]: %s. Para esta hunt (%d vivos): <b>%s</b>. '
               '<b>Exportar as pranchas actuais antes de importar</b> as do canal — a importacao substitui.'
               '<br><small class="mudo">opiniao do canal CharllonLobo, nao medida</small></p>'
               % (BOARDS_VIDEO, "; ".join("<b>%s</b> — %s" % (h.esc(n), h.esc(d)) for n, d in CANAL_BOARDS), pack, suggested))
    return "".join(out)


def render_hunt_helper(cat, hunt, plans, root):
    """Na pagina da hunt: o Helper (rotacao hunt/boss, cura, pocoes) de cada
    personagem dele que a tem como actual, com as etiquetas do jogo, e as Tacticas."""
    out = ["<h2>Helper e Tacticas nesta hunt</h2>"]
    if not plans:
        out.append('<p class="mudo">O bloco do Helper por vocacao aparece aqui quando um personagem tiver esta '
                   "hunt como actual (a rotacao e por nivel e equipamento, calcula-se por personagem). "
                   'As builds genericas estao em <a href="%sbuilds/index.html">Builds</a>.</p>' % root)
    for c, b in plans:
        out.append('<h3>%s — %s nivel %d (build recomendada %s)</h3>'
                   % (h.esc(c["name"]), h.esc(VOCATION_LABEL.get(b["vocation"], b["vocation"])), b["level"],
                      h.esc(B.GOAL_LABEL.get(b["goal"], b["goal"]))))
        out.append(_helper_block(cat, b, root, print_link=False))   # o cartao so existe nos niveis representativos
        out.append('<p class="mudo"><small>%s</small></p>' % _tactics_text(b["profile"]))
    out.append(render_tactics_block(cat, hunt, plans))
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


def render_print(cat, b, generated_at, name=None):
    """O cartao do Helper (390 px, autonomo). Com `name` e o cartao de um personagem
    dele: a rotacao e a que ele fixou, quando a fixou (`b["fixed_rotation"]`)."""
    hc = b["helper"]
    prof = b["profile"]
    hunt = cat.hunt_by_id[b["hunt"]]["nome"]
    head = title(prof.vocation, b["goal"]) if not name else "%s (%s)" % (name, title(prof.vocation, b["goal"]))
    fixed_line = ("<small>rotacao de hunt fixada por ti (%s)%s</small>" % (
        h.esc(", ".join(b["fixed_rotation"])), (" · arma %s" % h.esc(b["fixed_weapon"])) if b.get("fixed_weapon") else "")
    ) if b.get("fixed_rotation") else ""
    rune_gold = {c["words"]: c["gold_per_cast"] for c in (hc.get("hunt_costs") or []) + (hc.get("boss_costs") or []) if c["rune"]}

    def rune_tag(w):
        return (" · runa %s gold" % _n(rune_gold[w])) if w in rune_gold else ""
    rot = "".join("<li>%s <code>%s</code>%s%s</li>" % (h.esc(n), h.esc(w), (" ≥%d" % mm) if mm else "", rune_tag(w))
                  for n, w, mm in hc["hunt_rotation"])
    boss = "".join("<li>%s <code>%s</code>%s</li>" % (h.esc(n), h.esc(w), rune_tag(w)) for n, w, mm in hc["boss_rotation"])
    hs, bs = hc.get("hunt_supplies"), hc.get("boss_supplies")
    gold_line = ("<small>gold/h (pocoes + runas): hunt %s · boss %s</small>"
                 % (h.kk(hs["total"]) if hs else h.UNKNOWN, h.kk(bs["total"]) if bs else h.UNKNOWN))
    body = ['<div class="card"><h1>Helper — %s, nivel %d</h1><small>ref. %s · BaiakVault %s</small>%s'
            % (h.esc(head), b["level"], h.esc(hunt), h.esc(generated_at), fixed_line),
            "<h2>Cura automática</h2>",
            h.kv([("Cura própria", "%s <code>%s</code>" % (h.esc(hc["heal_spell"]), h.esc(hc["heal_words"]))),
                  ("Cura em", "%d%% de vida" % hc["heal_at"]),
                  ("Potion de vida", "%s · beber abaixo de %d%%" % (h.esc(hc["hp_potion"]), hc["hp_below"])),
                  ("Potion de mana", ("%s · beber abaixo de %d%%" % (h.esc(hc["mana_potion"]), hc["mana_below"])) if hc["mana_potion"] else "nenhuma")]),
            "<h2>Magias de Ataque — Hunt (ordem = prioridade)</h2><ol>%s</ol>" % rot,
            "<small>beams so no boss (Andre, 16/09/2026)%s</small>"
            % "".join("; %s fora: %s" % (h.esc(n), h.esc(why.split(":")[0])) for n, w, why in hc.get("hunt_excluded") or ()),
            "<h2>Magias de Ataque — Boss</h2><ol>%s</ol>" % boss,
            gold_line,
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
            % (h.esc("Helper %s %d — BaiakVault" % (head, b["level"])), PRINT_CSS, "".join(body)))


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


# --- validacao cruzada: o simulador no perfil de referencia, e o markdown -------------------------
def engine_numbers(cat, ref=validation.REFERENCE):
    """Os mesmos numeros de `validation.hand_calculation`, mas pelo simulador."""
    equipment = {}
    for slot, name in ref["equipment"].items():
        equipment[slot] = {"item": cat.item_by_key[name], "up": 0, "imbuements": list(ref["imbuements"].get(slot) or [])}
    prof = sim.Profile(cat, ref["vocation"], ref["level"], ref["tree"], equipment)
    target = sim.Target(cat, ref["hunt"])
    by_name = {s["nome"]: s for s in prof.spells}
    rotation = B.rotation_slots(prof, target, [by_name[n] for n in ref["rotation"]])
    m = B.evaluate(prof, target, rotation, rotation, heal=by_name[ref["heal"]])
    return {"heal_per_cast": prof.heal_amount(by_name[ref["heal"]]),
            "tree_points": sum(F.tree_total_cost(cat.node_by_id[k], r) for k, r in ref["tree"].items()),
            "hp_max": prof.hp_max, "mana_max": prof.mana_max, "magic_level": prof.skills["magic"],
            "dps_pack": m["dps_pack"], "dps_boss": m["dps_boss"], "dps_cycle": m["dps_cycle"],
            # so a rotacao: a conta a mao nao simula as curas (que desde 16/09/2026 acontecem
            # tambem no perfil de referencia, porque o leech deixou de curar pelas areas)
            "auto_dps": m["auto_dps"], "mana_demand": m["mana_demand_attacks"], "ai_quality": prof.ai_quality}


def engine_numbers_rune(cat, ref=validation.REFERENCE_RUNE):
    """Os numeros de `validation.hand_calculation_rune` pelo simulador: a rotacao fixada
    (Rage of the Skies + Avalanche) em 60 s sem cura e com pocoes — o gold/h das runas e
    o das pocoes de mana em regime sao os do simulador; as pocoes de vida ficam de fora
    da comparacao (dependem do ciclo de cura)."""
    equipment = {}
    for slot, name in ref["equipment"].items():
        equipment[slot] = {"item": cat.item_by_key[name], "up": 0, "imbuements": list(ref["imbuements"].get(slot) or [])}
    prof = sim.Profile(cat, ref["vocation"], ref["level"], ref["tree"], equipment)
    target = sim.Target(cat, ref["hunt"])
    by_name = {s["nome"]: s for s in prof.spells}
    rotation = B.rotation_slots(prof, target, [by_name[n] for n in ref["rotation"]])
    pack = sim.simulate(prof, target, rotation, boss=False, heal=None)
    boss = sim.simulate(prof, target, rotation, boss=True, heal=None)
    first, rune = by_name[ref["rotation"][0]], by_name[ref["rotation"][1]]
    return {"tree_points": sum(F.tree_total_cost(cat.node_by_id[k], r) for k, r in ref["tree"].items()),
            "ai_quality": prof.ai_quality, "magic_level": prof.skills["magic"], "hp_max": prof.hp_max, "mana_max": prof.mana_max,
            "casts_first": pack.casts.get(first["palavras"], 0), "casts_rune": pack.casts.get(rune["palavras"], 0),
            "dps_pack": pack.dps, "dps_boss": boss.dps, "dps_cycle": sim.cycle_dps(pack.dps, boss.dps, target),
            "auto_dps": pack.auto_dps, "mana_demand": pack.mana_demand_attacks,
            "runes_gold_per_hour": pack.runes_per_hour, "mana_potions_gold_per_hour": pack.mana_potions_per_hour}


def validation_rows(cat):
    return validation.compare(validation.hand_calculation(cat), engine_numbers(cat))


def validation_rows_rune(cat):
    return validation.compare(validation.hand_calculation_rune(cat), engine_numbers_rune(cat), labels=validation.LABELS_RUNE)


def _md_num(x, decimals=1):
    if isinstance(x, int):
        return h.fmt(x)
    return h.fmt(x, decimals)


def validation_markdown(cat, plans, rows=None, rows_rune=None):
    """O `docs/builds/validacao.md` gerado: contas a mao vs simulador, a curva do guia
    por build e nivel, e as discordancias guia/cliente. Nada e escondido: uma
    linha fora da tolerancia sai marcada (e o teste chumba)."""
    ref = validation.REFERENCE
    rows = rows if rows is not None else validation_rows(cat)
    out = ["# Validacao cruzada das builds", "",
           "Gerada pelo build a partir de `baiakvault/validation.py` (16/09/2026). Tres verificacoes: "
           "as contas de um perfil fixo refeitas a mao so com os JSON do catalogo, sem o simulador; a curva "
           "de DPS que o guia publica ao lado do DPS do ciclo do simulador; e as constantes em que o guia e o "
           "cliente do jogo discordam.", "",
           "## 1. Contas a mao vs simulador", "",
           "Perfil: **%s nivel %d em %s**, arvore de %d nos (%s), equipamento %s, imbuements %s, rotacao %s, cura %s. "
           "A conta a mao usa so `vocacoes.json` (formulas dos feiticos), `arvore.json` (custos e efeitos), "
           "`itens.json`, `bestiario.json` e `hunts.json`, com estas constantes: %s." % (
               ref["vocation"], ref["level"], cat.hunt_by_id[ref["hunt"]]["nome"], len(ref["tree"]),
               ", ".join("%s %d" % (cat.node_by_id[k]["nome"], r) for k, r in ref["tree"].items()),
               ", ".join(ref["equipment"].values()),
               "; ".join("%s: %s" % (s, ", ".join("%s T%d" % kv for kv in v)) for s, v in ref["imbuements"].items()),
               " + ".join(ref["rotation"]), ref["heal"],
               "; ".join("%s = %s (%s)" % (k, v, src) for k, (v, src) in validation.HAND_CONSTANTS.items())),
           "", "Tolerancia: %s %%." % _md_num(validation.TOLERANCE_PCT), "",
           "| numero | a mao | simulador | diferenca | |", "|---|---|---|---|---|"]
    for key, label, a, b, diff, ok in rows:
        out.append("| %s | %s | %s | %s | %s |" % (
            label, _md_num(a), _md_num(b), ("%+.2f %%" % diff).replace(".", ",") if diff is not None else "?",
            "ok" if ok else "**DIFERENTE ⚠**"))
    bad = [r for r in rows if not r[5]]
    out.append("")
    out.append("**%s**" % ("Tudo dentro da tolerancia." if not bad else
                           "%d numero(s) fora da tolerancia — o simulador e a conta a mao discordam; ver acima." % len(bad)))
    # 1b: com uma runa e Battle Tactics (ordem 8)
    rr = validation.REFERENCE_RUNE
    rows_rune = rows_rune if rows_rune is not None else validation_rows_rune(cat)
    out += ["", "## 1b. Contas a mao com uma runa e Battle Tactics (ordem 8, 16/09/2026)", "",
            "Perfil: **%s nivel %d em %s**, a rotacao que o Andre fixou (%s — a Avalanche e uma runa: %d gold por "
            "lancamento, mana 5, cooldown 2 s), Battle Tactics 7, arvore de %d nos (%s), o equipamento e os imbuements "
            "do perfil de cima. Sem cura e com pocoes: o que se confere e a rotacao na grelha de 2 s (a magia com mais "
            "dano por lancamento primeiro: Rage of the Skies cabe 6 vezes em 60 s, a runa apanha os outros 24 slots), "
            "o gold/h das runas e o das pocoes de mana **em regime** (deficit de mana x preco por mana da ultimate mana "
            "potion, %d gold por %d). As pocoes de vida dependem do ciclo de cura do simulador e nao se validam a mao. "
            "Constantes proprias desta conta: %s." % (
                rr["vocation"], rr["level"], cat.hunt_by_id[rr["hunt"]]["nome"], " + ".join(rr["rotation"]),
                next(s["custo_gold"] for s in cat.vocation_by_name[rr["vocation"]]["feiticos"] if s["nome"] == rr["rotation"][1]),
                len(rr["tree"]), ", ".join("%s %d" % (cat.node_by_id[k]["nome"], r) for k, r in rr["tree"].items()),
                validation.HAND_CONSTANTS_RUNE["ultimate_mana_potion"][0][1], validation.HAND_CONSTANTS_RUNE["ultimate_mana_potion"][0][0],
                "; ".join("%s = %s (%s)" % (k, v, src) for k, (v, src) in validation.HAND_CONSTANTS_RUNE.items()
                          if k not in validation.HAND_CONSTANTS)),
            "", "| numero | a mao | simulador | diferenca | |", "|---|---|---|---|---|"]
    for key, label, a, b, diff, ok in rows_rune:
        out.append("| %s | %s | %s | %s | %s |" % (
            label, _md_num(a), _md_num(b), ("%+.2f %%" % diff).replace(".", ",") if diff is not None else "?",
            "ok" if ok else "**DIFERENTE ⚠**"))
    bad_rune = [r for r in rows_rune if not r[5]]
    out.append("")
    out.append("**%s**" % ("Tudo dentro da tolerancia." if not bad_rune else
                           "%d numero(s) fora da tolerancia — o simulador e a conta a mao discordam; ver acima." % len(bad_rune)))
    out += ["", "## 1c. O Avatar: o caminho ligado mais barato + 300, a mao, por vocacao (ordem 9, 21/09/2026)", "",
            "A 1.a prioridade do Andre e o notable de tier 11. A conta a mao (`validation.avatar_reach_by_hand`) e um "
            "Dijkstra proprio sobre o `arvore.json` cru — um rank por no, a ligacao e o `requer` nos dois sentidos "
            "(cliente `MK`), a partir dos nos de tier 0 — sem importar o motor; ao lado o que o motor "
            "(`builds.avatar_reach`) deu. O nivel em que cabe = caminho + 300, porque cada nivel da um ponto.", "",
            "| vocacao | caminho a mao (pontos) | nivel em que cabe (a mao) | motor: pontos / nivel | ok | o caminho |",
            "|---|---|---|---|---|---|"]
    by_hand = validation.avatar_reach_by_hand(cat.raw["arvore"])
    for voc in ("knight", "paladin", "sorcerer", "druid", "monk"):
        cost, path, reach = by_hand[voc]
        m_cost, m_path, m_reach = B.avatar_reach(cat, voc)
        out.append("| %s | %s | %s | %s / %s | %s | %s |" % (
            VOCATION_LABEL[voc], _md_num(cost, 0), _md_num(reach, 0), _md_num(m_cost - 300 if m_cost is not None else None, 0),
            _md_num(m_reach, 0), "sim" if (reach == m_reach) else "**NAO**", ", ".join(path)))
    out += ["", "## 2. A curva de DPS do guia vs o DPS do ciclo do simulador", "",
            "Curva do guia: `%s x nivel^%s` (%s). E uma referencia sem vocacao, hunt nem equipamento; a razao "
            "mostra quanto cada build se afasta dela — nao ha «certo» aqui, ha o que cada um diz." % (
                _md_num(validation.GUIDE_CURVE[0], 3), _md_num(validation.GUIDE_CURVE[1], 3), validation.GUIDE_CURVE[2]),
            "", "| build | nivel | hunt | DPS ciclo (simulador) | curva do guia | razao |", "|---|---|---|---|---|---|"]
    for voc, goal in B.BUILDS:
        for level in B.LEVELS:
            b = plans.get((voc, goal, level))
            if not b:
                continue
            dps = b["metrics"]["dps_cycle"]
            g = validation.guide_dps(level)
            out.append("| %s | %d | %s | %s | %s | %s |" % (
                title(voc, goal), level, cat.hunt_by_id[b["hunt"]]["nome"], _md_num(dps, 0), _md_num(g, 0),
                ("x%.2f" % (dps / g)).replace(".", ",") if g else "?"))
    out += ["", "## 3. Onde o guia e o cliente discordam", "",
            "| o que | guia | cliente | o que se segue |", "|---|---|---|---|"]
    for what, guide, client, follow in validation.DISAGREEMENTS:
        out.append("| %s | %s | %s | %s |" % (what, guide, client, follow))
    out += ["", "## 4. A IA de combate (Battle Tactics): o que e cliente e o que e convencao", "",
            "O cliente calcula a IA em `u4e(nivel, ranks)`: `a = floor(nivel/100)`; `tier = a + ranks`; "
            "`qp = min(10, 0,5 x a) + min(10, ranks)`; **chance de decisao perfeita** = `min(1, 0,5 + 0,025 x qp)` "
            "(e o «Tactica: nivel N · X %» do painel); **raio de procura dos casts** = `min(1 + floor(qp/7), 3)`; "
            "reposicionamento minimo = `max(4000, 5000 - 50 x qp)` ms; kite infinito a partir do tier 3. "
            "Texto do cliente: «cada rank vale +100 niveis de IA e afia a CHANCE de jogar perfeito — mira, "
            "posicionamento e reacao»; sobre as pranchas: «Nunca decide magia, cura nem pocao: so ONDE».", "",
            "| o que | valor | fonte |", "|---|---|---|",
            "| chance de decisao perfeita | 0,5 + 0,025 x qp (tecto 1) | cliente `u4e` |",
            "| raio de procura dos casts | 1 + floor(qp/7), tecto 3 | cliente `u4e` |",
            "| o que uma decisao imperfeita rende | %s do dano de uma perfeita; o dano recebido x (1 + %s x imperfeitas) | **convencao ⚠** (`formulas.TACTICS_IMPERFECT_FACTOR`) |"
            % (_md_num(F.TACTICS_IMPERFECT_FACTOR * 100, 0) + " %", _md_num((1 - F.TACTICS_IMPERFECT_FACTOR), 1)),
            "| raio de procura -> alvos das areas | soma-se ao raio da magia (raio 1 = 3 alvos, 2 = 5, 3+ = o pack) | **convencao ⚠** (`formulas.TACTICS_RADIUS_TO_TARGETS`) |",
            "", "| nivel | sem o no | Battle Tactics 5 | Battle Tactics 10 |", "|---|---|---|---|"]
    for level in B.LEVELS:
        cells = []
        for ranks in (0, 5, 10):
            t = F.battle_tactics(level, ranks)
            cells.append("%s %% (raio %d, factor %s)" % (_md_num(t["aim_chance"] * 100, 1), t["cast_search_radius"],
                                                       _md_num(F.tactics_quality(t["aim_chance"]), 3)))
        out.append("| %d | %s |" % (level, " | ".join(cells)))
    out += ["", "Fontes: guia = `guiabaiakidle.com` (planner, lido a 16/09/2026); cliente = bundle publico "
            "`index-DnzxFejS.js` (09/09/2026). Nada disto foi medido na conta.", ""]
    return "\n".join(out)
