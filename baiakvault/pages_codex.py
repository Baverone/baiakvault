"""O Codex para o Andre (ordem 11, 21/09/2026): o valor de cada missao para a party dele, o custo em
kills e horas, a XP perdida, e o plano de ordenacao — mais as paginas `codex/index.html`,
`codex/missoes.html` e o cartao `print/codex-plano.html`.

O valor de uma missao e o que os seus stats rendem em DPS na party: o modelo linear da ordem 10
(`builds.stat_model`: fraccao do DPS do ciclo por +1 de cada stat, medida no simulador sobre a build
«prioridades» de cada um ao nivel dele, com a rotacao/arma fixadas), a media dos 5 ponderada pelo DPS
de cada um — ou seja, a variacao do DPS da party. Os bonus do Codex sao **por conta (por confirmar)**.
Stats que nao sao dano (absorcao, HP, mana, leech, defesa, armadura, velocidade, cura) valem 0 no dano
e mostram-se como «sobrevivencia/utilidade»; `onslaught` («+x % chance de fatal») fica a 0 porque o
cliente nao diz quanto vale um fatal (o combate e do servidor).

O custo: kills para fechar o degrau (`codex.Codex.kills_needed`, com o progresso dele quando a BD o
tem) a dividir pelos kills/h da party nessa hunt — o DPS de cada um dos 5 com a SUA build contra o
pack dessa hunt no simulador (a build nao se refaz por hunt), 57 normais + 1 boss por ciclo. So para
hunts com nivel minimo <= o nivel do mais alto (as outras «ainda nao»). A XP perdida = horas x (XP/h
da melhor hunt ao alcance - XP/h dessa hunt), com a XP/h do proprio simulador (kills/h x XP por kill).
"""
from . import builds as B
from . import codex as C
from . import html as h
from . import sim

# O que conta para o dano no modelo (o resto e «sobrevivencia/utilidade» = 0)
DAMAGE_STATS = ("atkPct", "spellDmgPct", "critChance", "critDmg", "attackSpeedPct", "elementDmgPct")
UTILITY_LABEL = {"absorbPct": "resistencia", "hpPct": "vida", "manaPct": "mana", "lifeLeech": "roubo de vida",
                 "manaLeech": "roubo de mana", "defFlat": "defesa", "armorFlat": "armadura", "moveSpeed": "velocidade",
                 "spellHealPct": "cura", "onslaught": "onslaught (fatal: o cliente nao diz quanto vale)"}
# As hunts «quando subirem» que a ordem pede por nome (600-610)
NEXT_HUNTS = ("norcferatu-cave", "quararaider-cave", "afflictedstrider-cave", "lavafungos-cave", "varnisheddiremaw-cave")
AC_SLOTS = {"free": 1, "vip": 2, "sub": 10}   # $X: slots do Auto Collect por plano
# Calibracao (captura de 21/09/2026, Livraria FIRE II, ~40 k kills no degrau): os itens exclusivos da hunt
# batem a +-10 % com a contagem media (1+max)/2; os outros vinham com stock de fora e nao servem para calibrar
CALIBRATION_NOTE = ("taxas do bestiario com contagem media (1+max)/2 por drop: nos itens exclusivos da Livraria FIRE "
                    "(talon, purple tome, burnt scroll, flask, soul orb) batem a ±10 % com a captura de 21/09/2026; "
                    "dead brain, slime heart, poisonous slime e clay lump vinham com stock de fora")


# --- o modelo por personagem ----------------------------------------------------------------------
def account_model(cat, planner, characters, advice_by_slug):
    """Por personagem com build: `{slug, name, vocation, level, dps, model, elements, hunt, plan}`.
    O modelo mede-se uma vez por (voc, nivel, hunt, fixadas) e fica no `Planner`."""
    out = []
    for c in characters:
        advice = advice_by_slug.get(c["slug"]) or {}
        plan = advice.get("plan")
        if not plan:
            continue
        key = ("model", c["vocation"], c["level"], plan["hunt"], tuple(plan.get("fixed_rotation") or ()), plan.get("fixed_weapon"))
        if key not in planner._codex:
            elements = B.priority_elements(plan["profile"], plan["rotation"])
            planner._codex[key] = B.stat_model(cat, c["vocation"], c["level"], plan["tree"], plan["equipment"], plan["target"],
                                               plan["rotation"], plan["boss_rotation"], plan["heal"], elements), elements
        model, elements = planner._codex[key]
        out.append({"slug": c["slug"], "name": c["name"], "vocation": c["vocation"], "level": c["level"],
                    "dps": model["_dps"], "model": model, "elements": sorted(elements), "hunt": plan["hunt"], "plan": plan})
    return out


def mission_value(bonus, chars):
    """(ganho % do DPS da party, [(nome, ganho %)], [(stat, elemento, valor)] sem valor de dano).
    Ganho de um personagem = soma(bonus x marginal); a party = media ponderada pelo DPS."""
    per_char = []
    utility = []
    for stat, el, v in C.bonus_stats(bonus):
        if stat not in DAMAGE_STATS:
            utility.append((stat, el, v))
    total_dps = sum(c["dps"] for c in chars) or 0.0
    party = 0.0
    for c in chars:
        gain = 0.0
        for stat, el, v in C.bonus_stats(bonus):
            if stat == "elementDmgPct":
                gain += v * c["model"]["elementDmgPct"].get(el, 0.0)
            elif stat in DAMAGE_STATS:
                gain += v * c["model"].get(stat, 0.0)
        per_char.append((c["name"], gain * 100.0))
        if total_dps:
            party += gain * c["dps"] / total_dps
    return party * 100.0, per_char, utility


# --- o custo: kills/h da party por hunt -------------------------------------------------------------
def party_rates(cat, planner, chars, hunt_id):
    """`{kills_h, xp_h, dps_pack, dps_boss}` da party na hunt, com a build de cada um contra o pack dela."""
    key = ("rates", hunt_id, tuple((c["slug"], c["level"], c["hunt"]) for c in chars))
    if key in planner._codex:
        return planner._codex[key]
    target = sim.Target(cat, hunt_id)
    dps_pack = dps_boss = 0.0
    for c in chars:
        plan = c["plan"]
        if plan["hunt"] == hunt_id:
            m = plan["metrics"]
            dps_pack += m["dps_pack"]
            dps_boss += m["dps_boss"]
        else:
            prof = plan["profile"]
            dps_pack += sim.simulate(prof, target, plan["rotation"], boss=False, heal=plan["heal"]).dps
            dps_boss += sim.simulate(prof, target, plan["boss_rotation"], boss=True, heal=plan["heal"]).dps
    kills_h = C.kills_per_hour(dps_pack, dps_boss, target)
    planner._codex[key] = out = {"kills_h": kills_h, "xp_h": (kills_h * target.exp) if kills_h else None,
                                 "dps_pack": dps_pack, "dps_boss": dps_boss, "exp_per_kill": target.exp}
    return out


# --- tudo junto ------------------------------------------------------------------------------------
def compute(cat, planner, characters, advice_by_slug, progress=None, vip=None):
    """O relatorio do Codex: personagens, hunts (kills/h, XP/h), as 686 missoes com valor, custo e
    estado, e o plano por seccoes. Puro a menos do simulador (via `planner`)."""
    cx = C.Codex(cat)
    progress = progress or {}
    chars = account_model(cat, planner, characters, advice_by_slug)
    party_level = max((c["level"] for c in chars), default=None)
    hunts = {}
    for hunt in cat.hunts:
        min_level = hunt.get("nivel_minimo") or 0
        reachable = bool(chars) and party_level is not None and min_level <= party_level
        row = {"id": hunt["id"], "name": hunt["nome"], "min_level": min_level, "reachable": reachable,
               "kills_h": None, "xp_h": None}
        if reachable:
            row.update(party_rates(cat, planner, chars, hunt["id"]))
        hunts[hunt["id"]] = row
    best_xp = max((r for r in hunts.values() if r["xp_h"]), key=lambda r: r["xp_h"], default=None)
    current_hunt = chars[0]["hunt"] if chars else None
    missions = []
    for m in cx.missions():
        value, per_char, utility = mission_value(m["bonus"], chars)
        row = {"mission": m, "value_pct": value, "per_char": per_char, "utility": utility,
               "kills": None, "hours": None, "xp_lost": None, "status": None, "value_per_hour": None,
               "bottleneck": None, "unknown": [], "progress": progress.get(m["id"]), "hunt": None}
        p = progress.get(m["id"])
        if p and p.get("done"):
            row["status"] = "concluida"
        if m["cat"] == "hunt":
            hr = hunts[m["hunt_id"]]
            row["hunt"] = hr
            kn = cx.kills_needed(m["hunt_id"], m["step"], (p or {}).get("progress"))
            row["kills"], row["bottleneck"], row["unknown"] = kn["kills"], kn["bottleneck"], kn["unknown"]
            if row["status"] != "concluida":
                if kn["complete"]:
                    row["status"] = "por entregar"
                elif p:
                    row["status"] = "em curso"    # esta a faze-la: o nivel da hunt ja nao e argumento
                elif not hr["reachable"]:
                    row["status"] = "ainda nao (nivel %d)" % hr["min_level"]
                else:
                    row["status"] = "por fazer"
                if hr["reachable"] and hr["kills_h"] and row["kills"] is not None:
                    row["hours"] = row["kills"] / hr["kills_h"]
                    if best_xp and hr["xp_h"] is not None:
                        row["xp_lost"] = row["hours"] * max(0.0, best_xp["xp_h"] - hr["xp_h"])
                    row["value_per_hour"] = (value / row["hours"]) if row["hours"] > 0 else None
        elif m["cat"] == "boss":
            if row["status"] is None:
                row["status"] = "por fazer"
        else:
            if row["status"] is None:
                row["status"] = "por fazer"
        missions.append(row)
    by_id = {r["mission"]["id"]: r for r in missions}
    return {"codex": cx, "chars": chars, "party_level": party_level, "hunts": hunts, "best_xp": best_xp,
            "current_hunt": current_hunt, "missions": missions, "by_id": by_id, "vip": vip,
            "plan": _plan(cat, cx, chars, hunts, missions, by_id, current_hunt, best_xp, party_level)}


def _plan(cat, cx, chars, hunts, missions, by_id, current_hunt, best_xp, party_level):
    """As seccoes do plano, ja ordenadas (cada linha com o porque)."""
    def open_hunt(r):
        return r["mission"]["cat"] == "hunt" and r["status"] not in ("concluida",)

    # (a) agora: a hunt actual — o degrau em curso ou o proximo por fazer dela
    now = []
    if current_hunt:
        for step in range(3):
            r = by_id.get(("hunt-%s" % current_hunt) if step == 0 else "hunt-%s-%d" % (current_hunt, step + 1))
            if r and r["status"] != "concluida":
                now.append(r)
                break
    # (b) as Livrarias: o Dominio I (ou o proximo degrau aberto) das 4, por valor por hora
    libraries = [r for r in missions if open_hunt(r) and r["mission"]["hunt_id"].startswith("livraria")
                 and r["mission"]["step"] == _next_step(by_id, r["mission"]["hunt_id"])]
    libraries.sort(key=lambda r: -(r["value_per_hour"] or 0))
    # (c) quando subirem: as hunts 600-610 pedidas, com o nivel
    later = [by_id["hunt-" + hid] for hid in NEXT_HUNTS if "hunt-" + hid in by_id]
    later.sort(key=lambda r: (r["hunt"]["min_level"], -r["value_pct"]))
    # (d) bosses: por valor (os elementos das rotacoes dele contam no modelo); I = so resistencia
    bosses = [r for r in missions if r["mission"]["cat"] == "boss" and r["status"] != "concluida" and r["mission"]["step"] == 1]
    bosses.sort(key=lambda r: -r["value_pct"])
    bosses = bosses[:12]
    # (e) sets ao tier 0: ganho pequeno, quase gratis
    gear = [r for r in missions if r["mission"]["cat"] == "gear" and r["mission"]["step"] == 0 and r["status"] != "concluida"]
    gear.sort(key=lambda r: -r["value_pct"])
    # (f) degraus II e III de hunts ao alcance, por valor por hora (honesto: as horas x5/x15)
    deep = [r for r in missions if open_hunt(r) and r["mission"]["step"] >= 1 and r["hours"] is not None]
    deep.sort(key=lambda r: -(r["value_per_hour"] or 0))
    # a ordenacao geral: todas as missoes de hunt ao alcance por valor de DPS por hora
    ranked = [r for r in missions if open_hunt(r) and r["value_per_hour"] is not None]
    ranked.sort(key=lambda r: -r["value_per_hour"])
    return {"now": now, "libraries": libraries, "later": later, "bosses": bosses, "gear": gear[:15], "deep": deep[:12],
            "ranked": ranked[:20]}


def _next_step(by_id, hunt_id):
    for step in range(3):
        r = by_id.get(("hunt-%s" % hunt_id) if step == 0 else "hunt-%s-%d" % (hunt_id, step + 1))
        if r and r["status"] != "concluida":
            return step
    return 3


# --- paginas ------------------------------------------------------------------------------------------
def _pct(v, decimals=2):
    return h.fmt(v, decimals, " %") if v is not None else h.UNKNOWN


def _hours(v):
    if v is None:
        return h.UNKNOWN
    if v < 1:
        return h.fmt(v * 60, 0, " min")
    return h.fmt(v, 1, " h")


def _gold(v):
    if v is None:
        return h.UNKNOWN
    if v == 0:
        return "gratis"
    return h.kk(v)


def _status(r):
    s = r["status"] or h.UNKNOWN
    if r["status"] == "em curso" and r["progress"] and r["progress"].get("progress"):
        m = r["mission"]
        done = sum(min(q, v or 0) for q, v in zip((x["qty"] for x in m["req"]), r["progress"]["progress"]))
        total = sum(x["qty"] for x in m["req"])
        s += " (%s dos itens)" % h.fmt(100.0 * done / total, 0, " %")
    return h.esc(s)


def _mission_link(r, root):
    return '<a href="%scodex/missoes.html#m%d">#%d %s</a>' % (root, r["mission"]["number"], r["mission"]["number"], h.esc(r["mission"]["name"]))


def _why(r, report):
    """A frase do porque de uma linha do plano."""
    m = r["mission"]
    bits = []
    if r["value_pct"] > 0:
        best = max(r["per_char"], key=lambda x: x[1]) if r["per_char"] else None
        bits.append("+%s de DPS na party" % h.fmt(r["value_pct"], 2, " %") + (
            " (mais no %s: +%s)" % (h.esc(best[0]), h.fmt(best[1], 2, " %")) if best and best[1] > 0 else ""))
    elif r["utility"]:
        bits.append("so sobrevivencia/utilidade: " + ", ".join(
            "%s%s +%s" % (UTILITY_LABEL.get(s, s), (" " + el) if el else "", h.fmt(v, 3)) for s, el, v in r["utility"]))
    if m["cat"] == "hunt":
        if r["hours"] is not None:
            bits.append("%s (%s kills, gargalo %s)" % (_hours(r["hours"]), h.fmt(r["kills"]), h.esc(r["bottleneck"])))
        elif r["kills"] is not None:
            bits.append("%s kills (gargalo %s)" % (h.fmt(r["kills"]), h.esc(r["bottleneck"])))
        if r["xp_lost"] is not None:
            bits.append("XP perdida %s" % h.kk(r["xp_lost"]) if r["xp_lost"] > 0 else "sem XP perdida (e a melhor hunt de XP ao alcance)")
        if r["unknown"]:
            bits.append("sem drop conhecido: %s" % h.esc(", ".join(r["unknown"])))
    if m["unlock_gold"]:
        bits.append("abrir custa %s" % _gold(m["unlock_gold"]))
    return "; ".join(bits) if bits else "nada a dizer"


def _rows(rs, report, root, with_hours=True):
    rows = []
    for r in rs:
        m = r["mission"]
        rows.append([_mission_link(r, root), h.esc(C.format_bonus_line(m["bonus"]) or "—"), _pct(r["value_pct"]),
                     _hours(r["hours"]) if with_hours else h.UNKNOWN,
                     (h.kk(r["xp_lost"]) if r["xp_lost"] else ("0" if r["xp_lost"] == 0 else h.UNKNOWN)) if with_hours else h.UNKNOWN,
                     _gold(m["unlock_gold"]), _status(r), '<small class="mudo">%s</small>' % _why(r, report)])
    return h.table(["missao", "bonus", "DPS party", "horas", "XP perdida", "gold", "estado", "porque"], rows, numeric=(2, 3, 4, 5))


def render_index(cat, report, generated_at):
    root = "../"
    chars, plan = report["chars"], report["plan"]
    cx = report["codex"]
    parts = ["<h1>Codex — o plano</h1>",
             '<p class="mudo">O que fechar e por que ordem, pelo <b>ganho de DPS da party por hora</b> com a XP perdida ao lado '
             "(decisao de 16/09/2026: dano e XP). As recompensas calculam-se no cliente (deterministicas, ver "
             '<a href="missoes.html">todas as missoes</a>); confirmadas no ecra do Andre a 21/09/2026 (#130 e #131). '
             "Os bonus do Codex sao <b>por conta</b> (por confirmar); o gold dos degraus e a omissao do cliente, "
             "o II confirmado por ele (50 M).</p>"]
    if not chars:
        parts.append('<div class="cartao"><p>Sem personagens com build na BD: sem modelo nao ha valor nem horas. '
                     "As missoes e os kills continuam na <a href=\"missoes.html\">tabela</a>.</p></div>")
    else:
        parts.append("<h2>A party</h2>")
        rows = []
        for c in chars:
            rows.append([h.esc(c["name"]), h.esc(c["vocation"]), h.fmt(c["level"]), h.fmt(c["dps"]),
                         h.esc(", ".join(c["elements"])),
                         " · ".join("%s %s" % (k, h.fmt(c["model"].get(k, 0.0) * 100, 2, " %")) for k in ("atkPct", "spellDmgPct", "critChance", "critDmg"))
                         + " · " + " · ".join("%s %s" % (el, h.fmt(v * 100, 2, " %")) for el, v in sorted(c["model"]["elementDmgPct"].items()))])
        parts.append(h.table(["personagem", "vocacao", "nivel", "DPS (build prioridades)", "elementos da rotacao/arma", "+1 % de cada stat rende"], rows, numeric=(2, 3)))
        cur = report["hunts"].get(report["current_hunt"]) if report["current_hunt"] else None
        best = report["best_xp"]
        parts.append(h.kv([
            ("hunt actual", "%s — %s kills/h da party, %s XP/h" % (h.esc(cur["name"]), h.fmt(cur["kills_h"]), h.kk(cur["xp_h"])) if cur else h.UNKNOWN),
            ("melhor hunt de XP ao alcance", "%s (%s XP/h)" % (h.esc(best["name"]), h.kk(best["xp_h"])) if best else h.UNKNOWN),
            ("nivel do mais alto", h.fmt(report["party_level"])),
            ("slots do Auto Collect", "assumido 1 (free); com VIP 2, com sub 10 — a BD %s" % (
                "diz VIP" if report["vip"] else ("nao sabe o plano dele" if report["vip"] is None else "diz sem VIP"))),
        ]))
        parts.append('<p class="mudo"><small>Kills/h = DPS dos 5 com a build de cada um contra o pack da hunt (a build nao se refaz por hunt; '
                     "sobrevivencia nao entra), 57 normais + 1 boss x3 HP por ciclo. %s.</small></p>" % h.esc(CALIBRATION_NOTE))

        parts.append("<h2>(a) Agora, sem mudar de hunt</h2>")
        if plan["now"]:
            r = plan["now"][0]
            parts.append('<div class="cartao"><p><b>Auto Collect com %s</b> — %s.</p>' % (_mission_link(r, root), _why(r, report)))
            if r["progress"] and r["progress"].get("progress"):
                kn = cx.kills_needed(r["mission"]["hunt_id"], r["mission"]["step"], r["progress"]["progress"])
                rows = [[h.esc(x["item"]), h.fmt(x["done"]), h.fmt(x["qty"]), h.fmt(x["missing"]),
                         h.fmt(x["rate"], 4) if x["rate"] is not None else h.UNKNOWN, h.fmt(x["kills"]) if x["kills"] is not None else h.UNKNOWN]
                        for x in kn["rows"]]
                parts.append(h.table(["item", "entregue", "pede", "falta", "por kill (bestiario)", "kills que faltam"], rows, numeric=(1, 2, 3, 4, 5)))
            parts.append("<p>Travas do AC: <b>incluir equipamentos NAO</b>; <b>nunca consumir forjados/com upgrade SIM</b>; "
                         "<b>nunca consumir com imbuement SIM</b>; raridade «Incomum ou melhor» (um item forjado nunca serve uma hunt: "
                         "cliente <code>t4e</code>, so tier 0); auto-desbloquear gold conforme quiseres (o III custa 500 M). "
                         "Com 1 slot so cabe esta; com 2 (VIP) entra a seguir a de maior valor por hora que use itens em comum "
                         "(silken bookmark, glowing rune, book page, poisonous slime, clay lump aparecem em varias Livrarias — o AC entrega "
                         "«na ordem da lista» a todas as escolhidas); com 10 entram as 4 Livrarias e os sets.</p></div>")
        else:
            parts.append('<p class="mudo">Sem hunt actual registada.</p>')

        parts.append("<h2>(b) A rotacao das Livrarias</h2>")
        parts.append('<p class="mudo">O proximo degrau aberto de cada Livraria, por valor de DPS por hora. As quatro sao de nivel 500 '
                     "com XP parecida: a XP perdida diz se mudar custa alguma coisa.</p>")
        parts.append(_rows(plan["libraries"], report, root))
        parts.append("<h2>(c) Quando subirem</h2>")
        parts.append(_rows(plan["later"], report, root))
        parts.append("<h2>(d) Bosses</h2>")
        parts.append('<p class="mudo">O degrau I de um boss e so resistencia (absorb); e o II (50 M, confirmado no degrau II das hunts) '
                     "que da o dano elemental — aqui os II por valor para as rotacoes dele (energy e ice no sorcerer, ice no druid, "
                     "fisico no knight e no monk, holy no paladin: so contam os elementos que cada rotacao/arma usa). O custo em kills "
                     "nao se sabe (o cliente nao traz o loot dos bosses de sala) e as cargas diarias de boss sao um orcamento a parte: "
                     "nao competem com a hunt.</p>")
        parts.append(_rows(plan["bosses"], report, root, with_hours=False))
        parts.append("<h2>(e) Equipamento: os sets ao tier Comum</h2>")
        parts.append('<p class="mudo">Cada peca x1 ao tier 0 (sem forja): ganhos pequenos e quase gratis. Os tiers Incomum/Raro/Epico '
                     "pedem cada peca forjada a esse tier e 50 M / 500 M / 1 000 M para abrir. A BD nao sabe o que ele tem na bag: "
                     "a coluna «pecas» diz de que monstro caem e o preco de NPC.</p>")
        rows = []
        for r in plan["gear"]:
            m = r["mission"]
            pieces = []
            for req in m["req"]:
                it = cat.item_by_key.get(req["item"]) or {}
                src = ", ".join((cat.creature_by_key.get(d["monstro"]) or {}).get("nome", d["monstro"]) for d in (it.get("cai_de") or [])[:3])
                pieces.append("%s (NPC %s%s)" % (h.esc(req["item"]), h.fmt(it.get("preco_npc")), ("; cai de " + h.esc(src)) if src else ""))
            rows.append([_mission_link(r, root), h.esc(C.format_bonus_line(m["bonus"])), _pct(r["value_pct"]), "<br>".join(pieces)])
        parts.append(h.table(["set", "bonus", "DPS party", "pecas"], rows, numeric=(2,)))
        parts.append("<h2>(f) Os degraus II e III</h2>")
        parts.append('<p class="mudo">x5 e x15 a lista, 50 M e 500 M para abrir. Por valor de DPS por hora; quando as horas sao '
                     "centenas, nao compensa mudar de hunt para isso — so por AC enquanto se caca la de qualquer maneira.</p>")
        parts.append(_rows(plan["deep"], report, root))
        parts.append("<h2>A ordenacao geral (hunts ao alcance)</h2>")
        parts.append(_rows(plan["ranked"], report, root))
    parts.append('<p><a href="%sprint/codex-plano.html">cartao do plano para imprimir</a> · <a href="missoes.html">todas as %d missoes</a></p>'
                 % (root, len(report["missions"])))
    parts.append('<p class="mudo"><small>Fonte: bundle publico do cliente (%s), funcoes $5e/Iq/O5e/qX/H5e/F5e/K5e/Wr/MX; catalogo visto a %s. Gerado a %s.</small></p>'
                 % (h.esc(cat.source_of("ac")), h.esc(cat.seen_at()), h.esc(generated_at)))
    return h.page("Codex — BaiakVault", "".join(parts), root=root, here="codex", generated_at=generated_at)


FILTER_JS = """<script>
(function(){var cat=document.getElementById('fcat'),st=document.getElementById('fstat'),rows=document.querySelectorAll('tr[data-cat]');
function go(){var c=cat.value,s=st.value;for(var i=0;i<rows.length;i++){var r=rows[i];
r.style.display=((c===''||r.getAttribute('data-cat')===c)&&(s===''||(' '+r.getAttribute('data-stats')+' ').indexOf(' '+s+' ')>=0))?'':'none';}}
cat.addEventListener('change',go);st.addEventListener('change',go);})();
</script>"""


def render_missions(cat, report, generated_at):
    root = "../"
    parts = ["<h1>Codex — todas as missoes</h1>",
             '<p class="mudo">As %d missoes na numeracao do cliente (#), com o bonus tal como o ecra o mostra, o valor para a party '
             "(ganho %% de DPS), os kills e as horas do «Dominio», o gold do degrau e o estado. Filtro por categoria e por stat.</p>"
             % len(report["missions"])]
    stats = sorted({s for r in report["missions"] for s, el, v in C.bonus_stats(r["mission"]["bonus"])})
    parts.append('<p><label>categoria <select id="fcat"><option value="">todas</option>%s</select></label> '
                 '<label>stat <select id="fstat"><option value="">todos</option>%s</select></label></p>'
                 % ("".join('<option value="%s">%s</option>' % (c, C.CATEGORY_LABEL[c]) for c in C.CATEGORIES),
                    "".join('<option value="%s">%s</option>' % (s, h.esc(C.STAT_LABEL.get(s, s))) for s in stats)))
    body = []
    for r in report["missions"]:
        m = r["mission"]
        cells = ['<a id="m%d"></a>#%d' % (m["number"], m["number"]), h.esc(m["name"]), h.esc(C.format_bonus_line(m["bonus"]) or "—"),
                 _pct(r["value_pct"]), h.fmt(r["kills"]) if r["kills"] is not None else h.UNKNOWN, _hours(r["hours"]),
                 (h.kk(r["xp_lost"]) if r["xp_lost"] else ("0" if r["xp_lost"] == 0 else h.UNKNOWN)),
                 _gold(m["unlock_gold"]), _status(r),
                 h.esc(("%d itens, gargalo %s" % (len(m["req"]), r["bottleneck"])) if r["bottleneck"] else "%d itens" % len(m["req"]))]
        body.append('<tr data-cat="%s" data-stats="%s">%s</tr>' % (
            m["cat"], " ".join(s for s, el, v in C.bonus_stats(m["bonus"])),
            "".join('<td%s>%s</td>' % (' class="n"' if i in (3, 4, 5, 6, 7) else "", c) for i, c in enumerate(cells))))
    head = "".join('<th%s>%s</th>' % (' class="n"' if i in (3, 4, 5, 6, 7) else "", h.esc(x)) for i, x in enumerate(
        ["#", "missao", "bonus (como no ecra)", "DPS party", "kills", "horas", "XP perdida", "gold", "estado", "pede"]))
    parts.append('<div class="tabela"><table><tr>%s</tr>%s</table></div>' % (head, "".join(body)))
    parts.append('<p class="mudo"><small>Kills = o item gargalo da lista pelas taxas do bestiario (%s); «?» quando a hunt esta acima do '
                 "nivel da party ou o loot e desconhecido. Gerado a %s.</small></p>" % (h.esc(C.DROP_COUNT_MEAN), h.esc(generated_at)))
    return h.page("Codex — missoes — BaiakVault", "".join(parts) + FILTER_JS, root=root, here="codex", generated_at=generated_at)


def render_print(cat, report, generated_at):
    """O cartao do plano (autonomo, 390 px, sem estilo.css)."""
    plan = report["plan"]
    lines = []

    def add(title, rs, n=6):
        lines.append("<h2>%s</h2>" % h.esc(title))
        if not rs:
            lines.append('<p class="m">—</p>')
        for r in rs[:n]:
            m = r["mission"]
            lines.append("<p><b>#%d %s</b> — %s<br><span class=\"m\">%s · %s · %s</span></p>" % (
                m["number"], h.esc(m["name"]), h.esc(C.format_bonus_line(m["bonus"]) or "—"),
                _pct(r["value_pct"]), _hours(r["hours"]) if r["hours"] is not None else "horas ?", _gold(m["unlock_gold"])))
    add("(a) Agora — AC", plan["now"], 1)
    add("(b) Livrarias", plan["libraries"])
    add("(c) Quando subirem", plan["later"])
    add("(d) Bosses (II)", plan["bosses"], 5)
    add("(e) Sets (Comum)", plan["gear"], 5)
    add("(f) Degraus II/III", plan["deep"], 5)
    return ("<!doctype html><html lang=\"pt\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Codex — plano</title><style>body{margin:0;background:#fff;color:#111;font:13px/1.35 system-ui,sans-serif}"
            ".c{width:390px;padding:10px 12px}h1{font-size:16px;margin:0 0 6px}h2{font-size:13px;margin:10px 0 2px;border-top:1px solid #ccc;padding-top:4px}"
            "p{margin:3px 0}.m{color:#555;font-size:12px}</style></head><body><div class=\"c\"><h1>Codex — plano (BaiakVault)</h1>"
            "<p class=\"m\">valor = ganho de DPS da party (por conta, por confirmar); horas com a party actual; gold = omissao do cliente, II confirmado. %s</p>%s"
            "</div></body></html>" % (h.esc(generated_at), "".join(lines)))
