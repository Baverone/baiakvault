"""O optimizador: para (vocacao, objectivo, nivel) devolve a build — arvore por
ordem de compra, equipamento BiS por slot com alternativas, rotacao para o
Helper, numeros e fontes. Tudo pelo simulador (`sim.py`) e pelas formulas
(`formulas.py`); nada aqui e opiniao, e o que o canal diz entra a parte,
citado, na pagina.

As oito builds (pedido do Andre, 16/09/2026): knight tank/damage, druid
heal/damage, sorcerer damage, paladin damage, monk support/damage.

Metricas por objectivo (decisao de 16/09/2026, registada no CLAUDE.md):

- ``damage``  — DPS efectivo num ciclo de hunt (57 normais com as areas a
  apanhar o pack + o boss da wave 10 com x3 HP, so alvo unico). E a omissao
  desde 16/09/2026 13:30 («quero dano, nao importa o custo»): pocoes e runas a
  vontade nos mages e no paladin, sem tecto de gold; no knight e no monk a mana
  continua a ser a restricao (sem pocoes de mana, cliente); sobreviver ao pack
  e ao boss e restricao minima, nao peso (`damage_constraints`).
- ``best``    — o mesmo DPS sujeito a aguentar, a sustentar a mana em todos e,
  no druid, a curar o knight da party (`best_constraints`) — a equilibrada.
- ``tank``    — tempo ate morrer com o pack inteiro em cima (HP / pressao
  mitigada menos o leech) x DPS^0,3: matar mais depressa tambem e sobreviver,
  mas um no de ataque so ganha a um de defesa se render ~3x mais em %.
- ``heal`` / ``support`` — cura por segundo sustentavel em 60 s (a melhor
  cura propria que a mana aguenta, mais a cura aliada se existir) x DPS^0,3.

Algoritmo da arvore: guloso preguicoso por ganho marginal por ponto, com
«lookahead» nos pre-requisitos (um no fechado e avaliado com o caminho mais
barato ate ele, um rank em cada no intermedio). A ordem sai como caminho de
subida: o passo k avalia-se ao nivel que k pontos gastos pressupoem, com o
equipamento e a rotacao desse nivel. Limitacoes: guloso nao e optimo (nao
troca compras feitas), os «notables» caros so entram quando o ganho/ponto os
justifica, e a metrica depende das convencoes de `formulas.py`.
"""
import heapq
import itertools
import math
import time

from . import formulas as F
from . import sim
from . import treecode

# A omissao e a build das «prioridades do Andre» (decisao dele, 21/09/2026, ordem 9): a arvore
# segue uma ordem estrita de categorias (Avatar > Exp > Loot > Crit > Ataque > Dano critico >
# Elemento > o resto pelo guloso de DPS) — ver PRIORITY_ORDER. Sobrepoe-se a omissao «dano» de
# 16/09/2026 13:30 SO na omissao: a «dano» (DPS puro), a «melhor» e as outras ficam disponiveis
# para comparacao, e a pagina da «prioridades» mostra o que a «dano» daria a mais.
DEFAULT_GOAL = "priority"
PRIORITY_GOAL = "priority"
BUILDS = (("knight", "priority"), ("druid", "priority"), ("sorcerer", "priority"), ("paladin", "priority"), ("monk", "priority"),
          ("knight", "damage"), ("druid", "damage"), ("sorcerer", "damage"), ("paladin", "damage"), ("monk", "damage"),
          ("knight", "best"), ("druid", "best"), ("sorcerer", "best"), ("paladin", "best"), ("monk", "best"),
          ("knight", "tank"), ("druid", "heal"), ("monk", "support"))
LEVELS = (50, 100, 200, 300, 500, 800, 1200, 1500)
GOAL_LABEL = {"priority": "prioridades", "best": "melhor", "damage": "dano", "tank": "tank", "heal": "cura", "support": "support"}
# --- as prioridades do Andre (21/09/2026) — constantes para ele afinar -------------------------
# A ordem das etapas; cada uma esgota-se (todos os ranks de todos os nos dela que os pontos
# deixem comprar) antes da seguinte. «avatar» e o notable de tier 11 mais o caminho ligado mais
# barato; «exp»/«loot» ordenam-se pelo proprio efeito por ponto (o simulador nao mede XP nem
# loot); «crit»/«attack»/«critdmg»/«element» pelo ganho de DPS por ponto medido no simulador,
# restrito aos nos da categoria; «rest» e o guloso de DPS de sempre (e a unica etapa onde a poda
# `prune_and_refill` entra: um rank de Exp rende 0 de DPS e a poda tirava-o).
PRIORITY_ORDER_ORDEM_9 = ("avatar", "exp", "loot", "crit", "attack", "critdmg", "element", "rest")
# Ordem 10 (decisao do Andre, 21/09/2026 13:00): «Quero Avatar, e depois quero que me indiques o
# que e melhor: se Atk, se Chance Critico, se Dano Critico.» Duas etapas: o Avatar (com a rota
# escolhida pelo DPS da build final) e «damage» — todos os pontos restantes no que rende mais
# DPS medido no simulador (o mesmo stat pela conta por ponto, stats diferentes pelo simulador
# em pacotes do mesmo tamanho, ordem 9c), com a poda so aqui. Exp e Loot deixam de ser
# prioridade (so entram como ligacao ou quando nao ha onde por um ponto). Para voltar a ordem
# da 9: PRIORITY_ORDER = PRIORITY_ORDER_ORDEM_9 (a estrutura por etapas ficou).
# Ordem 10b (o Andre precisou a regra, 21/09/2026 13:05): «No caso seria assim: Avatar, Exp, Loot,
# e tu decides o resto.» Quatro etapas: Avatar (rota escolhida como abaixo), Exp e Loot pelo efeito
# por ponto (as etapas 2-3 da ordem 9, esgotam-se antes da seguinte), e «damage» = a etapa 2 da
# ordem 10 sobre o que sobra. A rota avalia-se pelo vector (Avatar, +% exp, +% loot, DPS do modelo
# linear); a poda so na etapa «damage» e nunca toca nas etapas 1-3.
PRIORITY_ORDER = ("avatar", "exp", "loot", "damage")
PRIORITY_LABEL = {"avatar": "Avatar", "exp": "Exp", "loot": "Loot", "crit": "Crit", "attack": "Ataque",
                  "critdmg": "Dano critico", "element": "Elemento", "rest": "O que sobrar", "damage": "Dano"}
# O modelo linear do dano (ordem 10): o valor marginal de +1 de cada stat, medido no simulador
# sobre a arvore «rota + Avatar» (media das perturbacoes +1 e +2, para tirar o ruido da grelha);
# e o que ordena os ranks do mesmo stat na etapa «damage», avalia as centenas de rotas e responde
# ao «Atk vs Chance de critico vs Dano critico». Volta a medir-se a cada PRIORITY_MODEL_REFRESH
# pontos gastos na etapa (crit e dano critico multiplicam-se: os marginais mudam com a build).
PRIORITY_MODEL_STATS = ("atkPct", "spellDmgPct", "critChance", "critDmg", "attackSpeedPct", "elementDmgPct")
PRIORITY_MODEL_DELTAS = (1.0, 2.0)
PRIORITY_MODEL_REFRESH = 40
PRIORITY_REPORT_STATS = ("attack", "critChance", "critDmg")   # as tres linhas do «o que rende mais»
PRIORITY_ATTACK_STATS = {"knight": ("atkPct",), "monk": ("atkPct",), "paladin": ("atkPct", "spellDmgPct"),
                         "sorcerer": ("spellDmgPct",), "druid": ("spellDmgPct",)}
# stat do `efeito_por_rank` -> categoria; um no pertence a categoria de MAIOR prioridade entre os
# seus efeitos (Berserk Mastery atkPct+critDmg -> attack; Lord of Destruction critChance+critDmg
# -> crit; Guiding Presence exp+loot -> exp; Rage of the Skies energy+spellDmg -> attack; Twin
# Bursts so elemento -> element). `elementDmgPct` so conta nos elementos que a rotacao e a arma
# usam; os outros valem 0 e ficam no «rest». O que nao tem stat destes (HP, armor, leech, attack
# speed, mana, regen, Battle Tactics, notables de efeito especial) e «rest».
PRIORITY_STAT_CATEGORY = {"expPct": "exp", "lootPct": "loot", "critChance": "crit", "atkPct": "attack",
                          "spellDmgPct": "attack", "critDmg": "critdmg", "elementDmgPct": "element"}
AVATAR_NODE = {"knight": "k_avatar_steel", "paladin": "p_avatar_light", "sorcerer": "s_avatar_storm",
               "druid": "d_avatar_nature", "monk": "m_avatar_balance"}
# A rota ate ao Avatar (correccao do Andre, 21/09/2026, ordem 9b): NAO e a mais barata, e a que
# deixa a build final melhor pela ordem das prioridades — os nos da rota compram-se de qualquer
# maneira, e se passarem por Exp/Loot/Crit ja rendem. Enumeram-se todas as rotas que so sobem
# (`avatar_routes`), cada uma avalia-se pelo vector lexicografico (`route_vector`, contas por stat)
# e fica a melhor; empate -> a mais barata -> a de menos nos.
PRIORITY_ROUTE_MAX_DELAY = 5     # abaixo do Avatar: a rota escolhida nao o atrasa mais de N niveis face a mais barata
PRIORITY_ROUTE_MAX_ENUM = 2000   # acima disto poda-se por dominancia antes de avaliar (regista-se em `routes_pruned`)
PRIORITY_ROUTE_SIM_TIES = 8      # rotas empatadas no vector por stat que o simulador desempata (as demais: mais barata)
# Dentro de uma categoria (etapas 4-7; ordem 9c, 21/09/2026): entre ranks que dao o MESMO stat
# decide a conta por stat (efeito por ponto exacto, com o caminho que faltar no custo), sem
# simulador; o simulador so decide entre os melhores ranks de stats diferentes da mesma
# categoria e entre empates. Causa: o guloso de `optimize_tree` media cada rank na grelha de
# 60 s e o ruido (o mesmo +1,5 % de ataque saia de -0,03 % a +0,15 % por ponto) mandava mais do
# que o custo — o knight 548 comprou Warlust 5 (15 pontos por 2,5 %) com Warlord's Edge 3 (3
# pontos por 1,5 %) por comprar. False = o guloso do simulador da ordem 9.
PRIORITY_GREEDY_BY_STAT = True
PRIORITY_STAT_SIM_TIE = 0.02     # ganhos do simulador a menos de 2 % um do outro sao empate: fica o mais barato
# Tecto de gold/h dos supplies (pocoes em regime + runas) na escolha da rotacao: existe como
# parametro (`Planner(gold_cap=…)`, `choose_rotation(gold_cap=…)`) mas a omissao e SEM tecto
# — «nao importa o custo» (Andre, 16/09/2026 13:30).
GOLD_CAP_DEFAULT = None
GOAL_ASKED = {("knight", "tank"): "Sobreviver", ("knight", "damage"): "Dar dano",
              ("druid", "heal"): "Curar bastante", ("druid", "damage"): "Dar dano",
              ("sorcerer", "damage"): "Dar dano", ("paladin", "damage"): "Dar dano",
              ("monk", "support"): "Curar (support)", ("monk", "damage"): "Dar dano",
              ("knight", "best"): "A melhor possivel", ("druid", "best"): "A melhor possivel",
              ("sorcerer", "best"): "A melhor possivel", ("paladin", "best"): "A melhor possivel",
              ("monk", "best"): "A melhor possivel"}
PRIORITY_ASKED = "Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide)"


def priority_stages_before_damage():
    """Os rotulos das etapas antes da «damage» («Avatar, Exp e Loot»), para as frases da
    pagina e do veredicto: seguem `PRIORITY_ORDER`, nao um texto fixo."""
    labels = [PRIORITY_LABEL[s] for s in PRIORITY_ORDER if s != "damage"]
    if len(labels) <= 1:
        return labels[0] if labels else ""
    return ", ".join(labels[:-1]) + " e " + labels[-1]
for _voc in AVATAR_NODE:
    GOAL_ASKED[(_voc, PRIORITY_GOAL)] = PRIORITY_ASKED


def metric_goal(goal):
    """A metrica com que uma build se mede: a «prioridades» mede-se como a «dano» (DPS
    sustentado x nao morrer) — so a construcao da arvore e diferente."""
    return "damage" if goal == PRIORITY_GOAL else goal
SLOTS = ("weapon", "shield", "helmet", "armor", "legs", "boots", "amulet", "ring")
SECONDARY_DPS_EXPONENT = 0.3
TTD_CAP = 600.0
CANDIDATES_PER_SLOT = 20
EQUIPMENT_PASSES = 1
ROTATION_POOL = 5
MIN_LEVEL = 8
USELESS_IMBUEMENTS = ("increase speed",)  # nao entra em metrica nenhuma
# «best»: DPS do ciclo sujeito a aguentar o pack e o boss e a sustentar a mana (e, no
# druid, a curar o knight). Cada condicao falhada corta a metrica pela fraccao em que
# falha, elevada a BEST_PENALTY_POWER — uma penalizacao e nao um corte seco, para o
# guloso ter por onde subir a partir da arvore vazia (16/09/2026, ordem 6).
BEST_PENALTY_POWER = 2.0
# Poupar para um no caro: o caminho so espera `wait` niveis sem comprar nada quando o
# pacote rende pelo menos (1 + SAVE_MARGIN) x o que os mesmos pontos rendem nos outros
# nos, os dois medidos no simulador ao nivel em que se chega la. Pacotes que esperam
# ate SAVE_CHECK_MIN_WAIT niveis (ranks de small) nao passam pelo teste. Recusado, o
# no so se reconsidera quando os pequenos ja renderem SAVE_RETRY_DROP menos por ponto
# do que a alternativa rendia (limita o numero de testes). Decisao de 16/09/2026
# (ordem 6): a regra «espera <= 15 % do nivel ou <= 60 niveis» proposta na supervisao
# proibiria para sempre qualquer notable acima de 60 pontos (o caminho nunca tem pontos
# por gastar), por isso compara-se o integral no tempo, que e o que ela queria aproximar.
SAVE_CHECK_MIN_WAIT = 20
SAVE_MARGIN = 0.10
SAVE_RETRY_DROP = 0.20
SAVE_RETRY_SHARE = 0.25   # so se volta a testar depois de gastar 25 % do custo do no desde a recusa
# Regra do Andre (16/09/2026 13:00): «usar beams para hunt nao serve; beam so serve para
# boss». Os feiticos de linha ficam fora da rotacao de hunt; no boss continuam candidatos.
BEAM_SPELLS = ("exevo vis lux", "exevo gran vis lux", "exevo max mort")
# Elemento a que a hunt e (quase) imune: um feitico cujo multiplicador medio de elemento
# no pack (1 - resistencia media, ja com o pierce) fique abaixo disto nao entra na rotacao
# de hunt. 16/09/2026: na Livraria FIRE 3 dos 4 sao imunes a fogo e a optimizacao «a
# qualquer mana» ainda metia Hell's Core (1 100 de mana por 2,4 de dano/mana).
HUNT_ELEMENT_MIN_MULT = 0.5
# Ordem 8 (16/09/2026): o guloso depende do caminho (o knight «dano» a 527 ficava 25 % abaixo
# da «best»; o monk «dano» a 306 sem Battle Tactics). O `plan()` avalia tambem o prefixo do
# caminho da «best» (ou da «dano», quando se pede a «best») com a metrica pedida e fica com
# o melhor — o proprio caminho ganha os empates ate PATH_CANDIDATE_MARGIN.
PATH_CANDIDATES = True
PATH_CANDIDATE_MARGIN = 0.005
# Podar nos de ligacao (ordem 8, o que o Andre viu: «pontos em fogo sem usar fogo»): um small
# a rank 1 cujo ganho na metrica e ~0 (abaixo de PRUNE_GAIN_PCT) e cuja remocao mantem a
# arvore ligada sai, e os pontos voltam a gastar-se pelo guloso. Um no fica «so ligacao»
# quando rende ~0 mas tira-lo desligava a arvore; «ponto que sobrou» quando o refill o comprou
# a render ~0 (1-2 pontos sem rank de dano que os aceite vao para HP/absorcao).
PRUNE_GAIN_PCT = 0.05
PRUNE_MAX_ROUNDS = 60     # ranks tirados por passagem (cada um e uma avaliacao por no da arvore)
PRUNE_OUTER_ROUNDS = 3    # podar -> gastar -> podar outra vez (o refill pode deixar outro no sem ganho)
PRUNE_REVERT_PCT = 0.5    # podar + gastar nunca deixa a metrica mais de isto abaixo do que estava (ruido da grelha)
DEFENSIVE_EFFECTS = ("hpPct", "absorbPct", "armorFlat", "defFlat", "hpRegenFlat", "hpRegenPct")
# nos com nome de fogo mas efeito generico (`spellDmgPct`): o Andre estranhou os nomes
FIRE_NAMED_GENERIC = ("Wildfire", "Inferno", "Cataclysm")


# --- alvo de referencia ---------------------------------------------------------------------
def reference_hunt(cat, level):
    """A hunt que o jogo recomenda ao nivel: a de `nivel_minimo` mais alto que
    ainda cabe; empate pelo indice de XP do jogo."""
    best = None
    for h in cat.hunts:
        lv = h.get("nivel_minimo") or 0
        if lv > level:
            continue
        key = (lv, h.get("indice_xp") or 0)
        if best is None or key > best[0]:
            best = (key, h["id"])
    return best[1] if best else cat.hunts[0]["id"]


# --- metrica ---------------------------------------------------------------------------
def rotation_slots(profile, target, spells):
    """Slots por prioridade (dano por lancamento decrescente) com o minimo de
    bichos das areas: a area so compensa a partir de N alvos quando N x dano por
    alvo ultrapassa o melhor golpe de alvo unico. Uma runa de area nao gasta mana
    (so gold): fica a `F.RUNE_AREA_MIN_MOBS` (convencao ⚠)."""
    strikes = [s for s in spells if s["tipo"] != "area"]
    best_single = max([sim.spell_damage(profile, s, target, True) for s in strikes] or [0.0])
    slots = []
    for s in spells:
        min_mobs = 1
        if s["tipo"] == "area" and sim.is_rune(s):
            min_mobs = max(1, min(target.pack, F.RUNE_AREA_MIN_MOBS))
        elif s["tipo"] == "area" and best_single > 0:
            per_target = sim.spell_damage(profile, s, target, True)
            if per_target > 0:
                min_mobs = max(1, min(target.pack, int(math.ceil(best_single / per_target))))
        slots.append(sim.RotationSlot(s, min_mobs))
    slots.sort(key=lambda sl: -sim.spell_damage(profile, sl.spell, target, False))
    return slots


def evaluate(profile, target, rotation, boss_rotation=None, heal=None, attackers=None):
    """Corre o simulador nos dois cenarios e devolve as metricas da build."""
    heal = heal if heal is not None else default_heal(profile)
    pack = sim.simulate(profile, target, rotation, boss=False, heal=heal)
    boss = sim.simulate(profile, target, boss_rotation or rotation, boss=True, heal=heal)
    dps_cycle = sim.cycle_dps(pack.dps, boss.dps, target)
    # o mesmo ciclo com o DPS sustentado (knight/monk: so os feiticos que a mana paga)
    dps_cycle_sustained = sim.cycle_dps(pack.dps_sustained, boss.dps_sustained, target)
    n_att = attackers if attackers is not None else target.pack
    # o pack inteiro em cima, com as curas e as pocoes do Helper: e o «aguenta» da build
    # «best» (o `ttd_pack` analitico abaixo ignora curas e pocoes e fica na pagina)
    full = sim.simulate(profile, target, rotation, boss=False, heal=heal, attackers=n_att)
    pressure_pack, max_hit, _ = sim.pressure(profile, target, boss=False, attackers=n_att)
    _, boss_max_hit, _ = sim.pressure(profile, target, boss=True)
    # so o dano que rouba (ataque normal + strikes; `F.LEECH_SCOPE`), nao o DPS todo
    leech_hps = pack.leech_hps
    hps_self, heal_spell = sim.sustained_hps(profile)
    hps_friend, friend_spell = sim.sustained_hps(profile, friend=True)
    # tempo ate morrer, com tecto de 10 min: quando o leech cobre a pressao o
    # numero deixa de ter significado (e a pagina diz «> 10 min»)
    net = max(0.05, pressure_pack - leech_hps - profile.bonuses["hpRegenFlat"])
    ttd_pack = min(TTD_CAP, profile.hp_max / net)
    ttd_one = min(TTD_CAP, profile.hp_max / max(0.05, pack.pressure - leech_hps - profile.bonuses["hpRegenFlat"]))
    mit = sim.mitigation(profile, target)
    inc = target.incoming
    total_in = sum(inc.values()) or 1.0
    mitigated_share = sum(inc[el] * (1 - mit[el]) for el in F.ELEMENTS) / total_in
    ehp = profile.hp_max / max(0.05, 1 - mitigated_share)
    return {
        "dps_pack": pack.dps, "dps_boss": boss.dps, "dps_cycle": dps_cycle, "auto_dps": pack.auto_dps,
        "dps_pack_sustained": pack.dps_sustained, "dps_boss_sustained": boss.dps_sustained,
        "dps_cycle_sustained": dps_cycle_sustained, "mana_sustain": pack.mana_sustain,
        "boss_mana_sustain": boss.mana_sustain,
        "hps_self": hps_self, "hps_friend": hps_friend, "heal_spell": heal_spell, "friend_spell": friend_spell,
        "hps_sim": pack.hps, "leech_hps": leech_hps, "leech_dps": pack.leech_dps,
        "pressure_one": pack.pressure, "pressure_pack": pressure_pack, "max_hit": max_hit,
        "boss_max_hit": boss_max_hit, "ttd_pack": ttd_pack, "ttd_one": ttd_one, "ehp": ehp,
        "mitigated_share": mitigated_share, "hp_max": profile.hp_max, "mana_max": profile.mana_max,
        "hp_regen_flat": profile.bonuses["hpRegenFlat"], "armor": profile.armor, "defense": profile.defense,
        "mana_demand": pack.mana_demand, "mana_demand_attacks": pack.mana_demand_attacks,
        "mana_income": pack.mana_income, "mana_empty_at": pack.mana_empty_at,
        "mana_end": pack.mana_end, "boss_mana_empty_at": boss.mana_empty_at,
        "hp_potions": pack.hp_potions, "mana_potions": pack.mana_potions,
        "gold_per_hour": pack.gold_per_hour, "boss_gold_per_hour": boss.gold_per_hour,
        "hp_min": pack.hp_min, "death_at": pack.death_at, "boss_death_at": boss.death_at,
        "casts": pack.casts, "boss_casts": boss.casts,
        "uses_mana_potions": profile.uses_mana_potions,
        "survive_pack_s": sim.time_to_death(full, TTD_CAP), "survive_boss_s": sim.time_to_death(boss, TTD_CAP),
        "full_death_at": full.death_at, "full_hp_min": full.hp_min, "full_hp_potions": full.hp_potions,
        "full_mana_demand": full.mana_demand, "attackers_full": n_att,
        # a pressao do pack sobre o knight da party, quando o alvo a traz (druid «best»)
        "ally_pressure": getattr(target, "ally_pressure", None),
    }


def best_constraints(metrics):
    """As condicoes da build «melhor», cada uma como fraccao cumprida (1 = cumprida):
    aguentar o pack inteiro e o boss mais de 10 min (o simulador de 60 s com as
    curas e as pocoes do Helper, tendencia da vida extrapolada), mana sustentavel
    (knight/monk sem pocoes: o que o leech e os itens repoem cobre o que a rotacao
    gasta; mages/paladin com pocoes: a mana nao se esgota nos 60 s) e, quando o alvo
    traz `ally_pressure` (o druid a curar o knight da party), a cura aliada
    sustentavel cobre a pressao do pack sobre o knight."""
    out = {}
    out["survive_pack"] = max(0.01, min(1.0, metrics["survive_pack_s"] / TTD_CAP))
    out["survive_boss"] = max(0.01, min(1.0, metrics["survive_boss_s"] / TTD_CAP))
    if metrics.get("uses_mana_potions"):
        empty = metrics.get("mana_empty_at")
        out["mana"] = 1.0 if empty is None else max(0.01, empty / 60.0)
    else:
        demand = metrics.get("full_mana_demand", metrics["mana_demand"])   # com as curas do pack inteiro
        out["mana"] = 1.0 if demand <= 0 else min(1.0, metrics["mana_income"] / demand)
    ally = metrics.get("ally_pressure")
    if ally:
        out["heal_ally"] = min(1.0, metrics["hps_friend"] / ally)
    return out


def damage_constraints(metrics):
    """As condicoes da build de «dano» (Andre, 16/09/2026 13:30: so dano e XP, o custo
    nao conta): sobrevivencia como restricao MINIMA — nao morrer no pack inteiro nem
    no boss da hunt de referencia (as mesmas leituras da «melhor»). A mana do knight
    e do monk (sem pocoes, cliente) nao e condicao a parte: entra no proprio DPS
    sustentado (`dps_cycle_sustained`: so os feiticos que o leech e os itens pagam).
    Mages e paladin bebem pocoes a vontade: o custo sai em «gold/h»."""
    return {"survive_pack": max(0.01, min(1.0, metrics["survive_pack_s"] / TTD_CAP)),
            "survive_boss": max(0.01, min(1.0, metrics["survive_boss_s"] / TTD_CAP))}


def goal_constraints(metrics, goal):
    """As condicoes que a metrica do objectivo impoe ({} nos objectivos sem elas)."""
    goal = metric_goal(goal)
    if goal == "best":
        return best_constraints(metrics)
    if goal == "damage":
        return damage_constraints(metrics)
    return {}


def score_of(metrics, goal):
    goal = metric_goal(goal)
    dps = max(1e-6, metrics["dps_cycle"])
    if goal in ("damage", "best"):
        if goal == "damage":
            dps = max(1e-6, metrics.get("dps_cycle_sustained", metrics["dps_cycle"]))
        factor = 1.0
        for frac in goal_constraints(metrics, goal).values():
            factor *= max(1e-3, frac) ** BEST_PENALTY_POWER
        return dps * factor
    if goal == "tank":
        # EHP (vida a dividir pelo que passa da mitigacao, com o pack em cima) x
        # sustain (o leech e a regen cobrem ate 100 % da pressao: no maximo
        # duplica) x DPS^0,3. Nao se usa o TTD directamente porque com leech a
        # cobrir a pressao ele fica infinito e deixava de distinguir builds.
        sustain = min(1.0, (metrics["leech_hps"] + metrics["hp_regen_flat"]) / max(1e-6, metrics["pressure_pack"]))
        return metrics["ehp"] * (1 + sustain) * dps ** SECONDARY_DPS_EXPONENT
    hps = metrics["hps_self"] + 0.5 * metrics["hps_friend"]
    return max(1e-6, hps) * dps ** SECONDARY_DPS_EXPONENT


def default_heal(profile):
    """A cura propria do Helper: a melhor sem runa (as runas custam gold por
    lancamento e ficam como alternativa na pagina)."""
    heals = [s for s in sim.heal_spells(profile) if not s.get("custo_gold")]
    if not heals:
        return sim.best_heal(profile)
    return max(heals, key=lambda s: profile.heal_amount(s))


# --- rotacao -------------------------------------------------------------------------------
def rotation_value(r, profile, goal):
    """O que uma rotacao vale: o DPS dos 60 s; nas builds «best» e «dano» o DPS
    SUSTENTADO no knight/monk (sem pocoes de mana: so a fraccao dos feiticos de
    mana que o leech e os itens pagam se mantem — o ataque normal e as runas nao
    dependem da mana; `sim.simulate`); na «best» os outros ainda perdem se a mana
    se esgota nos 60 s. Na «dano» mages/paladin bebem a vontade (ponto 0,
    16/09/2026). Ate 16/09/2026 (ordem 7, ponto 6) era o DPS todo x (fraccao)^2:
    com as runas a nao gastar mana isso deixava o monk so com Sudden Death no boss."""
    goal = metric_goal(goal)
    if goal not in ("best", "damage"):
        return r.dps
    if not profile.uses_mana_potions:
        return r.dps_sustained
    if goal == "damage":
        return r.dps
    frac = 1.0 if r.mana_empty_at is None else max(0.01, r.mana_empty_at / 60.0)
    return r.dps * max(1e-3, frac) ** BEST_PENALTY_POWER


def hunt_exclusions(profile, target, runes=True):
    """{palavras: motivo} dos feiticos de ataque que nao entram na rotacao de
    HUNT: os beams (regra do Andre) e os do elemento a que o pack e imune
    (`HUNT_ELEMENT_MIN_MULT`). No boss nao ha exclusoes."""
    out = {}
    pierce = profile.specials.get("element_pierce", 0.0)
    for s in sim.attack_spells(profile, runes=runes):
        words = s["palavras"]
        if words in BEAM_SPELLS:
            out[words] = "beam: so no boss (decisao do Andre, 16/09/2026)"
            continue
        el = F.spell_element(words)
        mult = F.resist_factor(target.resist.get(el, 0.0), pierce)
        if mult < HUNT_ELEMENT_MIN_MULT:
            out[words] = ("%s: a hunt resiste %.0f %% em media (multiplicador %.2f < %.1f)"
                          % (el, target.resist.get(el, 0.0), mult, HUNT_ELEMENT_MIN_MULT))
    return out


def rotation_pool(profile, target, boss=False, runes=True, top=ROTATION_POOL):
    """Os candidatos da forca bruta: os `top` feiticos de mana com mais dano por
    lancamento, mais a melhor runa de area e a melhor runa de alvo unico contra
    este alvo (as runas de area do cliente tem todas a mesma formula e so mudam
    de elemento: entra «a melhor runa do elemento da hunt», nao quatro iguais a
    ocupar a pool). Na hunt, sem os beams nem os feiticos do elemento a que o pack
    e imune (`hunt_exclusions`); se isso nao deixasse nenhum, fica so a regra dos
    beams."""
    spells = sim.attack_spells(profile, runes=runes)
    if not boss and spells:
        excluded = hunt_exclusions(profile, target, runes)
        kept = [s for s in spells if s["palavras"] not in excluded]
        if not kept:
            kept = [s for s in spells if s["palavras"] not in BEAM_SPELLS]
        spells = kept
    if not spells:
        return []
    spells.sort(key=lambda s: -sim.spell_damage(profile, s, target, boss))
    pool = [s for s in spells if not sim.is_rune(s)][:top]
    for kind in ("area", "strike"):
        best_rune = next((s for s in spells if sim.is_rune(s) and s["tipo"] == kind), None)
        if best_rune is not None and sim.spell_damage(profile, best_rune, target, boss) > 0:
            pool.append(best_rune)
    return pool


def choose_rotation(profile, target, boss=False, runes=True, top=ROTATION_POOL, size=4, goal=None,
                    gold_cap=GOLD_CAP_DEFAULT):
    """Escolhe ate 4 feiticos por forca bruta na `rotation_pool`: o conjunto que
    o simulador diz render mais (pela metrica do objectivo — `rotation_value`) e
    a ordem de prioridade = dano por lancamento decrescente. As runas entram como
    candidatas normais, com o gold por lancamento (ponto 6, 16/09/2026); com
    `gold_cap` (gold/h de pocoes em regime + runas) as rotacoes acima dele nao
    entram — a omissao e sem tecto (`GOLD_CAP_DEFAULT`, decisao do Andre)."""
    pool = rotation_pool(profile, target, boss, runes, top)
    if not pool:
        return [], None
    heal = default_heal(profile)
    best = None
    fallback = None
    for k in range(1, min(size, len(pool)) + 1):
        for combo in itertools.combinations(pool, k):
            slots = rotation_slots(profile, target, list(combo))
            r = sim.simulate(profile, target, slots, boss=boss, heal=heal)
            value = rotation_value(r, profile, goal)
            if gold_cap is not None and r.gold_per_hour > gold_cap:
                # acima do tecto: so serve se nada couber (a mais barata das que passam nao existe)
                if fallback is None or r.gold_per_hour < fallback[2].gold_per_hour:
                    fallback = (value, slots, r)
                continue
            # empate (ate 0,5 %): mais feiticos no Helper e melhor, cobre mais situacoes
            if best is None or value > best[0] * 1.005:
                best = (value, slots, r)
    if best is None:
        best = fallback
    return best[1], best[2]


# --- equipamento ---------------------------------------------------------------------------
def _item_ok(item, vocation, level):
    if not item.get("slot"):
        return False
    if item.get("cargas") or item.get("duracao_s"):
        return False  # consumiveis de emergencia (SSA, Might Ring): nao sao BiS permanente
    if (item.get("nivel") or 0) > level:
        return False
    vocs = item.get("vocacoes")
    if vocs and vocation not in vocs:
        return False
    return True


def _static_rank(item, goal):
    """Pre-filtro barato para nao simular os 750 armas todas: nivel exigido e
    os numeros brutos do item. O simulador decide entre os que passam."""
    s = (item.get("nivel") or 0) * 2.0
    s += (item.get("ataque") or 0) + (item.get("ataque_elemental") or 0)
    s += ((item.get("wand_min") or 0) + (item.get("wand_max") or 0)) / 2.0
    s += (item.get("armadura") or 0) * 3 + (item.get("defesa") or 0) * 0.5
    s += sum((item.get("skills") or {}).values()) * 8
    s += (item.get("crit_chance") or 0) * 4 + (item.get("crit_dano") or 0) + (item.get("life_leech") or 0) * 3
    s += (item.get("mana_leech") or 0) * 3 + sum((item.get("absorcao") or {}).values()) * 0.5
    return s


def candidates(cat, vocation, level, slot, goal, limit=CANDIDATES_PER_SLOT):
    items = [i for i in cat.equippable if i["slot"] == slot and _item_ok(i, vocation, level)]
    if vocation in sim.MAGES and slot == "weapon":
        items = [i for i in items if i.get("tipo_de_arma") == "wand"]
    items.sort(key=lambda i: -_static_rank(i, goal))
    return items[:limit]


def best_ammo(cat, weapon, level):
    if not weapon or not weapon.get("municao"):
        return None
    kind = weapon["municao"]
    pool = [i for i in cat.items if i.get("municao") == kind and not i.get("slot")
            and (i.get("nivel") or 0) <= level]
    if not pool:
        return None
    return max(pool, key=lambda i: F.ammo_attack(i["nome"], i.get("ataque")))


def choose_imbuements(item, goal, target, vocation=None):
    """Que imbuement por em cada slot do item, pelo objectivo: dano -> Strike
    (critico), depois Vampirism; tank -> proteccao do elemento dominante da
    hunt, depois Vampirism; cura/support -> Void (mana leech), depois Vampirism;
    «best» como dano, mas no knight/monk (sem pocoes de mana) o Void primeiro:
    a mana e uma restricao e o leech so vale no ataque normal e nos strikes.
    So o que a categoria do item permite (cliente)."""
    cats = item.get("imbuement_categorias") or []
    n = item.get("imbuement_slots") or 0
    if not n:
        return []
    dominant = target.dominant_element()
    prot_name = "elemental protection " + dominant
    goal = metric_goal(goal)
    if goal in ("best", "damage"):
        # na «dano» a mana continua a ser a restricao do knight/monk (ponto 0, 16/09/2026)
        goal = "damage" if (vocation is None or F.USES_MANA_POTIONS.get(vocation, True)) else "sustain"
    prefs = {
        "sustain": ["mana leech", "life leech", "critical hit", prot_name],
        "damage": ["critical hit", "life leech", "mana leech", prot_name],
        "tank": [prot_name, "life leech", "critical hit", "mana leech"],
        "heal": ["mana leech", "life leech", prot_name, "critical hit"],
        "support": ["mana leech", "life leech", prot_name, "critical hit"],
    }[goal]
    # skillboost da skill principal e sempre bom para dano
    chosen = []
    for pref in prefs + [c for c in cats if c.startswith("skillboost")] + cats:
        if len(chosen) >= n:
            break
        if pref in cats and pref not in chosen and pref not in USELESS_IMBUEMENTS:
            chosen.append(pref)
    return chosen[:n]


def _imb_keys(cat, categories):
    lista = (cat.meta("itens").get("imbuements") or {}).get("lista") or []
    keys = []
    for c in categories:
        for imb in lista:
            if imb.get("cat") == c:
                keys.append((imb["key"], 3))
                break
    return keys


def fixed_weapon_entry(cat, item, goal, target, vocation):
    """A arma que ele fixou como entrada do equipamento (imbuements pelo objectivo)."""
    imbs = choose_imbuements(item, goal, target, vocation)
    return {"item": item, "up": 0, "imbuements": _imb_keys(cat, imbs), "imbuement_cats": imbs, "fixed": True}


def optimize_equipment(cat, vocation, level, goal, tree, target, rotation=None, passes=EQUIPMENT_PASSES,
                       gold_cap=GOLD_CAP_DEFAULT, fixed_weapon=None):
    """BiS por slot: para cada slot, o candidato que mais sobe a metrica com o
    resto do equipamento fixo; duas passagens para as dependencias (arma <->
    escudo, skills). Devolve (equipamento, alternativas por slot, metricas).
    `fixed_weapon` (item do catalogo) e a arma que ELE fixou (ordem 8): fica, se o
    nivel a deixar usar, e o resto optimiza-se a volta dela."""
    equipment = {}
    alternatives = {}
    if fixed_weapon is not None and _item_ok(fixed_weapon, vocation, level):
        equipment["weapon"] = fixed_weapon_entry(cat, fixed_weapon, goal, target, vocation)
        if vocation == "paladin":
            ammo = best_ammo(cat, fixed_weapon, level)
            if ammo:
                equipment["ammo"] = {"item": ammo}
    prof = sim.Profile(cat, vocation, level, tree, equipment)
    rot = rotation or choose_rotation(prof, target, goal=goal, gold_cap=gold_cap)[0]

    def metric_for(eq):
        # a metrica do objectivo, com empates (ate 0,5 %) decididos pela
        # sobrevivencia: entre duas armas iguais em DPS fica a que da mais EHP
        p = sim.Profile(cat, vocation, level, tree, eq)
        r = rot if rot else choose_rotation(p, target, goal=goal, gold_cap=gold_cap)[0]
        m = evaluate(p, target, r)
        s = score_of(m, goal)
        return (round(math.log(max(1e-9, s)) / 0.005), m["ehp"] * m["ttd_pack"]), m

    base_score, _ = metric_for(equipment)
    slots = list(SLOTS)
    if vocation != "knight":
        # so o knight usa escudo (vocacoes.json); o paladin poe o quiver ai, mages/monk nada
        slots.remove("shield")
    if (equipment.get("weapon") or {}).get("fixed"):
        slots.remove("weapon")
    for _ in range(passes):
        for slot in slots:
            weapon = (equipment.get("weapon") or {}).get("item")
            if slot == "shield" and weapon and weapon.get("duas_maos"):
                equipment.pop("shield", None)
                continue
            scored = []
            for item in candidates(cat, vocation, level, slot, goal):
                if slot == "weapon" and vocation == "knight" and item.get("duas_maos") and equipment.get("shield"):
                    trial = {k: v for k, v in equipment.items() if k != "shield"}
                else:
                    trial = dict(equipment)
                imbs = choose_imbuements(item, goal, target, vocation)
                trial[slot] = {"item": item, "up": 0, "imbuements": _imb_keys(cat, imbs), "imbuement_cats": imbs}
                if slot == "weapon" and vocation == "paladin":
                    ammo = best_ammo(cat, item, level)
                    trial["ammo"] = {"item": ammo} if ammo else None
                    if trial["ammo"] is None:
                        trial.pop("ammo")
                s, m = metric_for(trial)
                scored.append((s, item["nome"], trial, m))
            if not scored:
                continue
            scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
            best_s, _, best_trial, _ = scored[0]
            if best_s >= base_score:
                equipment = best_trial
                base_score = best_s
            alternatives[slot] = [{"equip": t[slot], "metrics": m, "score": score_of(m, goal)}
                                  for s, _, t, m in scored[:4]]
    prof = sim.Profile(cat, vocation, level, tree, equipment)
    return equipment, alternatives, prof


# --- arvore -------------------------------------------------------------------------------
def _adjacency(cat, vocation):
    tree = cat.tree_by_vocation[vocation]
    adj = {n["id"]: set() for n in tree["nos"]}
    for n in tree["nos"]:
        for req in n.get("requer") or []:
            adj[n["id"]].add(req)
            adj[req].add(n["id"])
    return adj


def can_buy(node, ranks, adj):
    """Regra do cliente (yD): rank < maximo e (tier 0 ou um vizinho com rank >= 1)."""
    if ranks.get(node["id"], 0) >= (node.get("rank_maximo") or 1):
        return False
    if node.get("tier", 0) == 0:
        return True
    return any(ranks.get(v, 0) >= 1 for v in adj[node["id"]])


def unlock_path(node, ranks, adj, node_by_id, exclude=()):
    """O caminho mais barato (um rank por no intermedio) do que ja esta comprado
    ate `node`. Dijkstra na adjacencia. Devolve lista de ids a comprar antes.
    Os `exclude` nao servem de caminho (o refill nao recompra o que se podou)."""
    if can_buy(node, ranks, adj):
        return []
    bought = {k for k, v in ranks.items() if v >= 1}
    # fontes: nos comprados, e os de tier 0 (comprar rank 1 custa o seu custo)
    dist = {}
    heap = []
    for nid, n in node_by_id.items():
        if nid in bought:
            dist[nid] = (0, [])
            heapq.heappush(heap, (0, nid, []))
        elif n.get("tier", 0) == 0 and nid not in exclude:
            c = F.tree_rank_cost(n, 0)
            dist[nid] = (c, [nid])
            heapq.heappush(heap, (c, nid, [nid]))
    target = node["id"]
    while heap:
        d, nid, path = heapq.heappop(heap)
        if dist.get(nid, (math.inf, None))[0] < d:
            continue
        if target in adj[nid]:
            return path
        for v in adj[nid]:
            if v == target or v in bought or v in exclude:
                continue
            n = node_by_id[v]
            c = d + F.tree_rank_cost(n, ranks.get(v, 0))
            if c < dist.get(v, (math.inf, None))[0]:
                dist[v] = (c, path + [v])
                heapq.heappush(heap, (c, v, path + [v]))
    return None


class TreeStep:
    __slots__ = ("node_id", "rank", "cost", "cumulative", "level", "score", "gain_per_point", "saving", "stage", "link")

    def __init__(self, node_id, rank, cost, cumulative, level, score, gain_per_point, saving=None, stage=None, link=False):
        self.node_id, self.rank, self.cost = node_id, rank, cost
        self.cumulative, self.level, self.score, self.gain_per_point = cumulative, level, score, gain_per_point
        # so no passo que fecha uma poupanca longa: {"wait", "from_level", "gain_pct",
        # "alt_gain_pct", "alt"} — o que a espera rende face a gastar os mesmos pontos
        # nos outros nos (ver SAVE_*)
        self.saving = saving
        # a etapa das prioridades (PRIORITY_ORDER) em que o rank entrou; None nas outras builds
        self.stage = stage
        # so nas prioridades: o rank entrou como caminho de desbloqueio de outro (o custo e desse)
        self.link = link


def optimize_tree(cat, vocation, goal, budget, equipment_at, rotation_at, target_at, start_ranks=None,
                  level_of=None, exclude=(), check_saving=True, boss_rotation_at=None, heal_at=None,
                  stop_at_zero_gain=False, only=None):
    """Caminho guloso de compra ate `budget` pontos. `equipment_at(level)`,
    `rotation_at(level, profile)` e `target_at(level)` dao o contexto do nivel
    em que cada ponto se gasta (level = pontos gastos, minimo 8, ou `level_of`).
    `boss_rotation_at(level, profile)` e `heal_at(profile)` (opcionais) fecham o
    contexto: sem eles a rotacao de hunt serve de rotacao de boss e a cura e a
    omissao — desde a ordem 8 o refill passa os mesmos que a pagina usa, senao a
    condicao «aguenta o boss» media-se noutra rotacao e comprava defesa a mais.
    `exclude` sao nos que nao se compram nem servem de caminho; `check_saving` liga
    o teste da poupanca (SAVE_*), que se desliga na chamada aninhada que calcula a
    alternativa. `only` (ordem 9) restringe os nos que se COMPRAM como alvo a esse
    conjunto — o caminho de desbloqueio continua a passar por qualquer no."""
    tree = cat.tree_by_vocation[vocation]
    node_by_id = {n["id"]: n for n in tree["nos"]}
    adj = _adjacency(cat, vocation)
    ranks = dict(start_ranks or {})
    spent = sum(F.tree_total_cost(node_by_id[k], v) for k, v in ranks.items() if k in node_by_id)
    steps = []

    contexts = {}
    baselines = {}

    def level_for(points):
        # o nivel em que se tem `points` pontos: o proprio numero (1 ponto por nivel)
        if level_of:
            return level_of(points)
        return max(MIN_LEVEL, points)

    def context(level):
        # equipamento/rotacao/alvo do nivel (mudam so nos checkpoints, ver Planner)
        if level not in contexts:
            eq = equipment_at(level, ranks)
            prof = sim.Profile(cat, vocation, level, ranks, eq)
            boss_rot = boss_rotation_at(level, prof) if boss_rotation_at else None
            heal = heal_at(prof) if heal_at else None
            contexts[level] = (eq, target_at(level), rotation_at(level, prof), boss_rot, heal)
        return contexts[level]

    def score_with(level, trial_ranks):
        eq, target, rot, boss_rot, heal = context(level)
        p = sim.Profile(cat, vocation, level, trial_ranks, eq)
        return score_of(evaluate(p, target, rot, boss_rot, heal), goal)

    def baseline(level):
        if level not in baselines:
            baselines[level] = score_with(level, ranks)
        return baselines[level]

    def package(node):
        """(ganho por ponto, custo, compras, score, nivel) de comprar um rank de
        `node` com o caminho de desbloqueio se preciso. O pacote avalia-se ao
        nivel em que se pode pagar (pontos gastos + custo), contra a base desse
        mesmo nivel — so assim um notable de 100 pontos e um small de 1 ponto
        sao comparaveis."""
        path = unlock_path(node, ranks, adj, node_by_id, exclude)
        if path is None:
            return None
        trial = dict(ranks)
        cost = 0
        purchases = []
        for nid in path + [node["id"]]:
            n = node_by_id[nid]
            cost += F.tree_rank_cost(n, trial.get(nid, 0))
            trial[nid] = trial.get(nid, 0) + 1
            purchases.append((nid, trial[nid]))
        if spent + cost > budget:
            return None
        level = level_for(spent + cost)
        s = score_with(level, trial)
        # ganho RELATIVO por ponto: em absoluto um notable avaliado a nivel 157
        # ganharia sempre a um small avaliado a nivel 8
        gain = (s / max(1e-9, baseline(level)) - 1.0) / cost
        return gain, cost, purchases, s, level

    def saving_verdict(nid, cost, s, level):
        """Poupar `cost` pontos para este pacote (chega-se la ao `level`) contra
        gastar os mesmos pontos nos outros nos, avaliados os dois no mesmo
        nivel e contexto. Devolve (poupa?, ganho %, ganho % da alternativa,
        alternativa). Decisao de 16/09/2026 (ordem 6), ver SAVE_MARGIN."""
        alt_ranks, alt_steps = optimize_tree(
            cat, vocation, goal, spent + cost, equipment_at, rotation_at, target_at, start_ranks=ranks,
            level_of=lambda pts: level, exclude=set(exclude) | {nid}, check_saving=False,
            boss_rotation_at=boss_rotation_at, heal_at=heal_at)
        base = max(1e-9, baseline(level))
        gain_pct = (s / base - 1.0) * 100.0
        alt_pct = (score_with(level, alt_ranks) / base - 1.0) * 100.0 if alt_steps else 0.0
        alt = [(st.node_id, st.rank) for st in alt_steps]
        return gain_pct >= alt_pct * (1.0 + SAVE_MARGIN), gain_pct, alt_pct, alt

    # Guloso preguicoso: a fila guarda o ultimo ganho/ponto conhecido de cada no.
    # Tira-se o topo; se o valor e velho, re-avalia-se e reinsere-se; se ja e
    # fresco (calculado neste estado) compra-se. Cada estado re-avalia no
    # maximo N nos, por isso termina.
    heap = [(-math.inf, nid) for nid in node_by_id if nid not in exclude and (only is None or nid in only)]
    heapq.heapify(heap)
    fresh = {}
    parked = {}     # no -> ganho/ponto da alternativa: poupanca recusada neste estado, fora da fila ate se comprar algo
    no_test = set()  # nos que voltam a fila sem mais nada compravel: entram sem o teste (a alternativa e nada)
    last_rejected = {}   # no -> pontos gastos quando a poupanca foi recusada
    dropped = set()      # so com `only`: os que nao cabiam, para re-avaliar a cada compra
    while heap or parked:
        if not heap:
            for pid, alt_pp in parked.items():
                heapq.heappush(heap, (-alt_pp, pid))
                no_test.add(pid)
            parked = {}
        neg_gain, nid = heapq.heappop(heap)
        node = node_by_id[nid]
        if ranks.get(nid, 0) >= (node.get("rank_maximo") or 1):
            continue
        if nid in fresh:
            gain, cost, purchases, s, level = fresh[nid]
        else:
            pkg = package(node)
            if pkg is None:
                # nao cabe no orcamento: sai da fila. Com `only` (uma etapa das prioridades, que
                # tem de ESGOTAR a categoria) volta a fila a proxima compra: o caminho pode ficar
                # mais barato quando um vizinho entra
                if only is not None:
                    dropped.add(nid)
                continue
            gain, cost, purchases, s, level = pkg
            fresh[nid] = pkg
            if heap and gain < -heap[0][0]:
                heapq.heappush(heap, (-gain, nid))
                continue
        if stop_at_zero_gain and gain <= 0.0:
            break   # o melhor que ha nao rende: o refill deixa o resto para os «pontos que sobram»
        saving = None
        wait = level - level_for(spent)
        if check_saving and node.get("tipo") != "small" and wait > SAVE_CHECK_MIN_WAIT and nid not in no_test:
            # poupar N niveis sem comprar nada so quando rende mais do que os
            # pequenos pelos mesmos pontos; senao o no sai da fila ate se comprar
            # outra coisa (senao ficava a ocupar o topo) e so se volta a testar
            # quando o melhor dos outros tiver caido SAVE_RETRY_DROP e ja se
            # gastaram SAVE_RETRY_SHARE do custo dele desde a recusa
            best_other = -heap[0][0] if heap else gain
            if spent - last_rejected.get(nid, -math.inf) < cost * SAVE_RETRY_SHARE:
                fresh.pop(nid, None)
                parked[nid] = min(gain, best_other) * (1.0 - SAVE_RETRY_DROP)
                continue
            ok, gain_pct, alt_pct, alt = saving_verdict(nid, cost, s, level)
            if not ok:
                fresh.pop(nid, None)
                last_rejected[nid] = spent
                parked[nid] = min(gain, best_other) * (1.0 - SAVE_RETRY_DROP)
                continue
            saving = {"wait": wait, "from_level": level_for(spent), "gain_pct": gain_pct,
                      "alt_gain_pct": alt_pct, "alt": alt}
        for pid, r in purchases:
            c = F.tree_rank_cost(node_by_id[pid], r - 1)
            spent += c
            ranks[pid] = r
            steps.append(TreeStep(pid, r, c, spent, level_for(spent), s, gain,
                                  saving if pid == nid else None))
        fresh = {}
        baselines = {}
        contexts = {}
        no_test = set()
        # os que esperavam por outro estado voltam a fila com a chave da alternativa
        for pid, alt_pp in parked.items():
            heapq.heappush(heap, (-alt_pp, pid))
        parked = {}
        for pid in dropped:
            heapq.heappush(heap, (-math.inf, pid))
        dropped = set()
        heapq.heappush(heap, (-gain, nid))
    return ranks, steps


def next_purchase(cat, vocation, goal, level, ranks, equipment, target, rotation=None, top=3):
    """O proximo passo a partir de um estado real: as `top` compras com mais
    ganho por ponto que cabem no orcamento do nivel. Para a ordem 3."""
    tree = cat.tree_by_vocation[vocation]
    node_by_id = {n["id"]: n for n in tree["nos"]}
    adj = _adjacency(cat, vocation)
    spent = sum(F.tree_total_cost(node_by_id[k], v) for k, v in ranks.items() if k in node_by_id)
    budget = F.tree_budget(level)
    prof = sim.Profile(cat, vocation, level, ranks, equipment)
    rot = rotation or choose_rotation(prof, target, goal=goal)[0]
    current = score_of(evaluate(prof, target, rot), goal)
    out = []
    for nid, node in node_by_id.items():
        if ranks.get(nid, 0) >= (node.get("rank_maximo") or 1):
            continue
        path = unlock_path(node, ranks, adj, node_by_id)
        if path is None:
            continue
        trial = dict(ranks)
        cost = 0
        for pid in path + [nid]:
            cost += F.tree_rank_cost(node_by_id[pid], trial.get(pid, 0))
            trial[pid] = trial.get(pid, 0) + 1
        if spent + cost > budget:
            continue
        s = score_of(evaluate(sim.Profile(cat, vocation, level, trial, equipment), target, rot), goal)
        out.append({"node": nid, "name": node["nome"], "rank": trial[nid], "cost": cost,
                    "via": path, "score": s, "gain_pct": (s / current - 1) * 100 if current else 0.0})
    out.sort(key=lambda x: -(x["score"] - current) / max(1, x["cost"]))
    return out[:top], current, budget - spent


# --- a build inteira -----------------------------------------------------------------------
class Planner:
    """Calcula e guarda as builds: um caminho de arvore por (vocacao,
    objectivo), equipamento e rotacao nos niveis representativos, e a build
    completa por nivel. `plan(vocation, goal, level)` responde a qualquer nivel."""

    def __init__(self, cat, levels=LEVELS, hunt_by_level=None, gold_cap=GOLD_CAP_DEFAULT):
        self.cat = cat
        self.levels = tuple(levels)
        self.hunt_by_level = hunt_by_level or {}
        self.gold_cap = gold_cap   # tecto de gold/h dos supplies na rotacao; None = sem tecto (omissao)
        self._targets = {}
        self._equipment = {}   # (voc, goal, checkpoint) -> equipment
        self._rotation = {}    # (voc, goal, checkpoint) -> (hunt rotation, boss rotation)
        self._paths = {}       # (voc, goal, hunt ou None) -> (ranks, steps)
        self._ally = {}        # (hunt, checkpoint) -> pressao do pack sobre o knight «best»
        self._priority = {}    # (voc, nivel, hunt, fixed) -> a build «prioridades» (ordem 9)
        self._plans = {}       # (voc, goal, nivel, hunt, fixed) -> a build montada (ordem 9)
        self._codex = {}       # o modelo por personagem e os kills/h da party por hunt (ordem 11; `pages_codex`)
        self.timings = {}

    # contexto por nivel: usa o checkpoint (nivel representativo) mais alto <= nivel
    def checkpoint(self, level):
        below = [lv for lv in self.levels if lv <= level]
        return max(below) if below else self.levels[0]

    def target(self, level, hunt_id=None, strict=False):
        """A hunt de referencia do nivel; com `hunt_id` (a hunt dele), essa — mas
        so a partir do nivel minimo dela (salvo `strict`): abaixo, o caminho segue
        as hunts que o jogo recomenda (senao a arvore de um nivel 8 optimizava-se
        para uma hunt de 500 em que morre ao segundo, e comprava so sobrevivencia)."""
        hunt = hunt_id
        if hunt and not strict and (self.cat.hunt_by_id[hunt].get("nivel_minimo") or 0) > level:
            hunt = None
        hunt = hunt or self.hunt_by_level.get(level) or reference_hunt(self.cat, level)
        if hunt not in self._targets:
            self._targets[hunt] = sim.Target(self.cat, hunt)
        return self._targets[hunt]

    def target_for(self, vocation, goal, level, hunt_id=None, strict=False):
        """O alvo de uma build: a hunt de referencia do nivel (ou `hunt_id`, a hunt
        dele; `strict` = mesmo abaixo do nivel minimo dela) e, no druid «best», a
        pressao do pack sobre o knight «best» da mesma party (mesmo nivel
        representativo e hunt) — e o que a cura aliada tem de cobrir."""
        target = self.target(level, hunt_id, strict)
        if vocation == "druid" and goal == "best":
            return sim.with_ally(target, self.ally_pressure(target.hunt_id, level))
        return target

    def ally_pressure(self, hunt_id, level):
        """A pressao do pack sobre o knight «best» ao nivel representativo: na hunt
        de referencia do nivel (o knight «best» generico desse checkpoint — um
        proxy, nao se calcula um knight por cada hunt de referencia) ou, se a hunt
        e a dele, nessa."""
        cp = self.checkpoint(level)
        reference = hunt_id == self.target(level).hunt_id
        key = (None if reference else hunt_id, cp)
        if key not in self._ally:
            self._ally[key] = None   # guarda contra recursao (o knight nao precisa do druid)
            knight = self.plan("knight", "best", cp, hunt_id=key[0])
            self._ally[key] = knight["metrics"]["pressure_pack"]
        return self._ally[key]

    # --- o que ele fixou (ordem 8): rotacao e arma sao dados, nao sugestoes ------------------
    @staticmethod
    def fixed_key(fixed_rotation=None, fixed_weapon=None):
        """A chave de cache do que ele fixou: `None` quando nao fixou nada."""
        if not fixed_rotation and not fixed_weapon:
            return None
        return (tuple(fixed_rotation) if fixed_rotation else None, (fixed_weapon or "").lower() or None)

    def _fixed_weapon_item(self, fixed):
        if not fixed or not fixed[1]:
            return None
        return self.cat.item_by_key.get(fixed[1])

    def fixed_rotation_slots(self, profile, target, fixed, boss=False):
        """A rotacao fixada como slots do simulador — so os feiticos que o nivel ja
        da; `None` se nenhum (o caminho abaixo do nivel deles segue o optimizador)."""
        if not fixed or not fixed[0]:
            return None
        by_name = {s["nome"]: s for s in sim.attack_spells(profile)}
        spells = [by_name[n] for n in fixed[0] if n in by_name]
        if not spells:
            return None
        return rotation_slots(profile, target, spells)

    def _tree_prefix(self, vocation, goal, budget, hunt_id=None, fixed=None):
        ranks, steps = self._paths.get((vocation, goal, hunt_id, fixed), ({}, []))
        out = {}
        for st in steps:
            if st.cumulative > budget:
                break
            out[st.node_id] = st.rank
        return out

    def equipment_at(self, vocation, goal, level, ranks=None, hunt_id=None, fixed=None):
        """O equipamento do checkpoint (nivel representativo) <= nivel. Calcula-se
        uma vez, com a arvore que o caminho tem ao chegar la, e serve o caminho
        e as paginas — e o que torna as builds todas possiveis em segundos."""
        cp = self.checkpoint(level)
        key = (vocation, goal, cp, hunt_id, fixed)
        if key not in self._equipment:
            tree = dict(ranks) if ranks is not None else self._tree_prefix(vocation, goal, F.tree_budget(cp), hunt_id, fixed)
            target = self.target_for(vocation, goal, cp, hunt_id)
            eq, alts, _ = optimize_equipment(self.cat, vocation, cp, goal, tree, target, gold_cap=self.gold_cap,
                                             fixed_weapon=self._fixed_weapon_item(fixed))
            self._equipment[key] = (eq, alts)
        return self._equipment[key][0]

    def rotation(self, profile, target, boss, goal, runes=True, fixed=None):
        """A rotacao: na hunt a que ele fixou (se o nivel ja a der), senao a que o
        optimizador escolhe. No boss e sempre a do optimizador: o que ele fixou foi a
        rotacao de hunt (decisao de 16/09/2026 14:30) e o Helper tem o separador Boss a
        parte. Devolve (slots, SimResult)."""
        if fixed and not boss:
            slots = self.fixed_rotation_slots(profile, target, fixed, boss)
            if slots is not None:
                return slots, sim.simulate(profile, target, slots, boss=boss, heal=default_heal(profile))
        return choose_rotation(profile, target, boss=boss, runes=runes, goal=goal, gold_cap=self.gold_cap)

    def rotation_at(self, vocation, goal, level, profile, hunt_id=None, fixed=None, boss=False):
        cp = self.checkpoint(level)
        key = (vocation, goal, cp, hunt_id, fixed)
        if key not in self._rotation:
            target = self.target_for(vocation, goal, cp, hunt_id)
            hunt_rot, _ = self.rotation(profile, target, False, goal, fixed=fixed)
            boss_rot, _ = self.rotation(profile, target, True, goal, fixed=fixed)
            self._rotation[key] = (hunt_rot, boss_rot)
        return self._rotation[key][1 if boss else 0]

    def path(self, vocation, goal, budget=None, hunt_id=None, fixed=None):
        """O caminho de compra de (vocacao, objectivo): pela hunt de referencia de
        cada nivel, ou, com `hunt_id`, pela hunt dele a todos os niveis — a arvore
        acompanha o elemento da hunt (na Livraria FIRE o sorcerer nao compra
        nos de fogo), decisao de 16/09/2026 (ordem 6). Com `fixed` (rotacao/arma
        dele), o caminho e para essa rotacao a partir do nivel em que ela existe."""
        key = (vocation, goal, hunt_id, fixed)
        if key not in self._paths:
            t0 = time.perf_counter()
            budget = budget or F.tree_budget(max(self.levels))
            self._paths[key] = ({}, [])
            ranks, steps = optimize_tree(
                self.cat, vocation, goal, budget,
                equipment_at=lambda lv, ranks: self.equipment_at(vocation, goal, lv, ranks, hunt_id, fixed),
                rotation_at=lambda lv, prof: self.rotation_at(vocation, goal, lv, prof, hunt_id, fixed),
                # o caminho avalia com a rotacao de hunt tambem no boss (simplificacao de sempre):
                # com a rotacao de boss propria o guloso do monk «dano» a 306 caia 10 % (ordem 8,
                # testado) — o refill e a poda ao nivel da pagina e que usam o contexto completo
                target_at=lambda lv: self.target_for(vocation, goal, lv, hunt_id),
                level_of=lambda points: max(MIN_LEVEL, min(max(self.levels), points)))
            self._paths[key] = (ranks, steps)
            self.timings[key] = time.perf_counter() - t0
        return self._paths[key]

    def _candidate(self, vocation, goal, path_goal, level, hunt_id, fixed, target, equipment=None):
        """Uma arvore candidata ao nivel: o prefixo do caminho de `path_goal` com o
        equipamento e a rotacao do objectivo pedido, os pontos que sobram gastos
        (`fill_tree`). Devolve o estado por avaliar (a pontuacao decide entre candidatos).
        `equipment` ja escolhido evita o optimizador de equipamento (o candidato do outro
        caminho compara-se com o mesmo equipamento; so se ganhar se optimiza para ele)."""
        cat = self.cat
        self.path(vocation, path_goal, hunt_id=hunt_id, fixed=fixed)
        budget = F.tree_budget(level)
        tree = self._tree_prefix(vocation, path_goal, budget, hunt_id, fixed)
        steps = [st for st in self._paths[(vocation, path_goal, hunt_id, fixed)][1] if st.cumulative <= budget]
        key = (vocation, goal, level, hunt_id, fixed)
        if equipment is not None:
            eq, alts = equipment
        elif path_goal == goal and key in self._equipment and self.target(level, hunt_id).hunt_id == target.hunt_id:
            eq, alts = self._equipment[key]
        else:
            eq, alts, _ = optimize_equipment(cat, vocation, level, goal, tree, target, gold_cap=self.gold_cap,
                                             fixed_weapon=self._fixed_weapon_item(fixed))
        prof = sim.Profile(cat, vocation, level, tree, eq)
        hunt_rot, _ = self.rotation(prof, target, False, goal, fixed=fixed)
        boss_rot, _ = self.rotation(prof, target, True, goal, fixed=fixed)
        heal = default_heal(prof)
        # o que o caminho deixa por gastar (a poupar para um notable) gasta-se agora ao nivel da pagina
        tree, fill_steps = fill_tree(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal)
        score = score_of(evaluate(sim.Profile(cat, vocation, level, tree, eq), target, hunt_rot, boss_rot, heal), goal)
        return {"path_goal": path_goal, "tree": tree, "steps": steps, "fill_steps": fill_steps, "eq": eq, "alts": alts,
                "hunt_rot": hunt_rot, "boss_rot": boss_rot, "heal": heal, "score": score}

    def plan(self, vocation, goal, level, hunt_id=None, fixed_rotation=None, fixed_weapon=None):
        """A build completa a um nivel (na hunt de referencia do nivel, ou na
        `hunt_id` dele — caminho, equipamento e rotacao todos por essa hunt; com a
        rotacao/arma que ele fixou, se as houver). Dicionario pronto para a pagina.

        O guloso depende do caminho (relatorio-7): desde a ordem 8 avaliam-se, com a
        metrica pedida, o prefixo do proprio caminho e o do caminho da «best» (ou da
        «dano», quando se pede a «best») e fica o melhor; sobre o vencedor corre a
        melhoria local e o `prune_and_refill` (nos de ligacao que deixaram de ser
        precisos saem e os pontos voltam a gastar-se)."""
        if goal == PRIORITY_GOAL:
            return self.plan_priority(vocation, level, hunt_id, fixed_rotation, fixed_weapon)
        cat = self.cat
        fixed = self.fixed_key(fixed_rotation, fixed_weapon)
        # a build montada (fill, melhoria local, poda) custa ~1,2 s e a «prioridades» pede a «dano»
        # do mesmo nivel: guarda-se (ordem 9); os dicionarios sao so de leitura para quem os pede
        cache_key = (vocation, goal, level, hunt_id, fixed)
        if cache_key in self._plans:
            return self._plans[cache_key]
        budget = F.tree_budget(level)
        target = self.target_for(vocation, goal, level, hunt_id, strict=True)   # a hunt dele, mesmo abaixo do minimo
        candidates = [self._candidate(vocation, goal, goal, level, hunt_id, fixed, target)]
        other = "best" if goal != "best" else "damage"   # o outro caminho e sempre um dos dois com caminho por nivel
        if PATH_CANDIDATES and other in {g for v, g in BUILDS if v == vocation}:
            candidates.append(self._candidate(vocation, goal, other, level, hunt_id, fixed, target,
                                              equipment=(candidates[0]["eq"], candidates[0]["alts"])))
        # empate (ate 0,5 %) fica com o proprio caminho: a ordem de compra dele e a que a pagina conta
        best = max(candidates[1:], key=lambda c: c["score"], default=None)
        chosen = candidates[0]
        if best is not None and best["score"] > chosen["score"] * (1 + PATH_CANDIDATE_MARGIN):
            # o outro caminho ganhou com o equipamento do proprio: agora o equipamento optimiza-se
            # para ele — e fica o melhor dos dois (o guloso por slot a partir do zero pode cair num
            # optimo local pior, ex.: knight 50 com uma arma de duas maos que o deixa sem escudo)
            chosen = best
            eq, alts, _ = optimize_equipment(cat, vocation, level, goal, chosen["tree"], target, gold_cap=self.gold_cap,
                                             fixed_weapon=self._fixed_weapon_item(fixed))
            prof = sim.Profile(cat, vocation, level, chosen["tree"], eq)
            hunt_rot, _ = self.rotation(prof, target, False, goal, fixed=fixed)
            boss_rot, _ = self.rotation(prof, target, True, goal, fixed=fixed)
            heal = default_heal(prof)
            s_new = _score_tree(cat, vocation, goal, level, chosen["tree"], eq, target, hunt_rot, boss_rot, heal)
            if s_new > chosen["score"]:
                chosen.update({"eq": eq, "alts": alts, "hunt_rot": hunt_rot, "boss_rot": boss_rot, "heal": heal, "score": s_new})
        tree, steps, fill_steps, eq, alts = chosen["tree"], chosen["steps"], chosen["fill_steps"], chosen["eq"], chosen["alts"]
        hunt_rot, boss_rot, heal = chosen["hunt_rot"], chosen["boss_rot"], chosen["heal"]
        path_used = chosen["path_goal"]
        path_scores = {c["path_goal"]: c["score"] for c in candidates}
        # uma melhoria local: se desviar os ultimos pontos render mais com este equipamento, desvia-se
        tree, improved = local_improve(cat, vocation, goal, level, tree, steps + fill_steps, eq, target,
                                       hunt_rot, boss_rot, heal)
        # e os nos de ligacao que deixaram de ser precisos saem; os pontos voltam a gastar-se
        tree, pruned, refill_steps = prune_and_refill(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal)
        prof = sim.Profile(cat, vocation, level, tree, eq)
        new_hunt_rot, hunt_sim = self.rotation(prof, target, False, goal, fixed=fixed)
        new_boss_rot, boss_sim = self.rotation(prof, target, True, goal, fixed=fixed)
        # a escolha da rotacao olha so ao DPS (sustentado) de 60 s, nao as condicoes de sobreviver:
        # se a rotacao nova deixar a metrica (com as condicoes) pior do que a que a arvore foi
        # optimizada para, fica a antiga (monk «dano» 306: a nova gastava a mana das curas e a
        # metrica caia de 1 110 para 264 — ordem 8)
        heal = default_heal(prof)
        s_new = _score_tree(cat, vocation, goal, level, tree, eq, target, new_hunt_rot, new_boss_rot, heal)
        s_old = _score_tree(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal)
        if s_new >= s_old:
            hunt_rot, boss_rot = new_hunt_rot, new_boss_rot
        else:
            hunt_sim = sim.simulate(prof, target, hunt_rot, boss=False, heal=heal)
            boss_sim = sim.simulate(prof, target, boss_rot, boss=True, heal=heal)
        # a mesma escolha so com magias de mana: e o que as runas compram (a pagina mostra os dois)
        hunt_rot_no_runes, hunt_sim_no_runes = self.rotation(prof, target, False, goal, runes=False)
        boss_rot_no_runes, boss_sim_no_runes = self.rotation(prof, target, True, goal, runes=False)
        # com rotacao fixada: a que o optimizador escolheria, para a pagina mostrar as duas
        model_rot = model_sim = None
        if fixed and fixed[0]:
            model_rot, model_sim = choose_rotation(prof, target, boss=False, goal=goal, gold_cap=self.gold_cap)
        heal = default_heal(prof)
        metrics = evaluate(prof, target, hunt_rot, boss_rot, heal)
        alternatives = tree_alternatives(cat, vocation, goal, level, tree, steps + fill_steps + refill_steps, eq, target,
                                         hunt_rot, boss_rot, heal)
        spent = sum(F.tree_total_cost(cat.node_by_id[k], v) for k, v in tree.items())
        next_step = None
        path_steps = self._paths[(vocation, path_used, hunt_id, fixed)][1]
        for st in path_steps:
            if st.cumulative > budget:
                next_step = st
                break
        order = purchase_order(cat, vocation, tree, steps + fill_steps + refill_steps)
        roles = node_roles(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal, fill_steps + refill_steps)
        self._plans[cache_key] = out = {
            "vocation": vocation, "goal": goal, "level": level, "hunt": target.hunt_id, "target": target,
            "profile": prof, "tree": tree, "steps": steps, "fill_steps": fill_steps, "improved": improved,
            "pruned": pruned, "refill_steps": refill_steps, "order": order, "roles": roles,
            "path_goal": path_used, "path_scores": path_scores,
            "next_step": next_step, "points_spent": spent, "points_budget": budget,
            "equipment": eq, "equipment_alternatives": alts,
            "rotation": hunt_rot, "boss_rotation": boss_rot,
            "hunt_sim": hunt_sim, "boss_sim": boss_sim,
            "rotation_no_runes": hunt_rot_no_runes, "hunt_sim_no_runes": hunt_sim_no_runes,
            "boss_rotation_no_runes": boss_rot_no_runes, "boss_sim_no_runes": boss_sim_no_runes,
            "fixed_rotation": list(fixed[0]) if fixed and fixed[0] else None,
            "fixed_weapon": fixed[1] if fixed else None,
            "model_rotation": model_rot, "model_sim": model_sim,
            "heal": heal, "metrics": metrics, "score": score_of(metrics, goal),
            "tree_alternatives": alternatives,
            "helper": helper_config(prof, target, hunt_rot, boss_rot, heal, metrics, hunt_sim, boss_sim),
            "gold_cap": self.gold_cap,
        }
        return out

    def plan_priority(self, vocation, level, hunt_id=None, fixed_rotation=None, fixed_weapon=None, route=None):
        """A build «prioridades do Andre» (21/09/2026): a arvore por `priority_tree` ao
        nivel exacto, a partir do equipamento e da rotacao da build «dano» do mesmo
        nivel (que fica ao lado, em numero — e a comparacao que a pagina mostra); depois
        o equipamento optimiza-se para a arvore das prioridades e a rotacao volta a
        escolher-se (a fixada por ele fica). Sem caminho por nivel: cada nivel constroi-se
        do zero, e a ordem de compra sai por etapas. Abaixo do nivel do Avatar (ordem 9b)
        a build leva a rota ja comprada (plano B) e `avatar_plans` compara os planos A
        (so a rota, guardar o resto, sem gold) e B (gastar tudo e importar ao nivel X);
        `route` forca a rota (e o que a build do nivel X recebe)."""
        cat = self.cat
        goal = PRIORITY_GOAL
        fixed = self.fixed_key(fixed_rotation, fixed_weapon)
        cache_key = (vocation, level, hunt_id, fixed, tuple(route) if route else None)
        if cache_key in self._priority:
            return self._priority[cache_key]
        budget = F.tree_budget(level)
        damage = self.plan(vocation, "damage", level, hunt_id=hunt_id, fixed_rotation=fixed_rotation, fixed_weapon=fixed_weapon)
        target = damage["target"]
        eq, hunt_rot, boss_rot, heal = damage["equipment"], damage["rotation"], damage["boss_rotation"], damage["heal"]
        elements = priority_elements(damage["profile"], hunt_rot)

        def score_fn(trial):
            # desempate entre rotas com o mesmo vector: o DPS medido, no contexto da build «dano»
            return _score_tree(cat, vocation, "damage", level, trial, eq, target, hunt_rot, boss_rot, heal)

        tree, steps, info = priority_tree(cat, vocation, level, eq, target, hunt_rot, boss_rot, heal, elements,
                                          route=route, score_fn=score_fn)
        # o equipamento para ESTA arvore (a da «dano» serviu de contexto para a construir)
        eq, alts, _ = optimize_equipment(cat, vocation, level, goal, tree, target, gold_cap=self.gold_cap,
                                         fixed_weapon=self._fixed_weapon_item(fixed))
        prof = sim.Profile(cat, vocation, level, tree, eq)
        hunt_rot, hunt_sim = self.rotation(prof, target, False, goal, fixed=fixed)
        boss_rot, boss_sim = self.rotation(prof, target, True, goal, fixed=fixed)
        heal = default_heal(prof)
        hunt_rot_no_runes, hunt_sim_no_runes = self.rotation(prof, target, False, goal, runes=False)
        boss_rot_no_runes, boss_sim_no_runes = self.rotation(prof, target, True, goal, runes=False)
        model_rot = model_sim = None
        if fixed and fixed[0]:
            model_rot, model_sim = choose_rotation(prof, target, boss=False, goal=goal, gold_cap=self.gold_cap)
        metrics = evaluate(prof, target, hunt_rot, boss_rot, heal)
        order = purchase_order(cat, vocation, tree, steps)
        roles = priority_roles(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal, steps, info)
        spent = _spent(cat, tree)
        # o Avatar fora de alcance: a build do nivel em que cabe, com a MESMA rota e o codigo (a mesma
        # hunt e o que ele fixou), e os dois planos ate la (ordem 9b)
        avatar_plan = avatar_plans = None
        if not info["avatar"] and info["avatar_level"] is not None and info["avatar_level"] > level:
            avatar_plan = self.plan_priority(vocation, info["avatar_level"], hunt_id, fixed_rotation, fixed_weapon,
                                             route=tuple(info["avatar_path"]))
            avatar_plans = self.avatar_plans(vocation, level, info, avatar_plan, prof, eq, target, hunt_rot, boss_rot, heal, metrics)
        self._priority[cache_key] = out = {
            "vocation": vocation, "goal": goal, "level": level, "hunt": target.hunt_id, "target": target,
            "profile": prof, "tree": tree, "steps": steps, "fill_steps": [], "improved": [],
            "pruned": info["pruned"], "refill_steps": [], "order": order, "roles": roles,
            "path_goal": goal, "path_scores": {}, "next_step": None, "points_spent": spent, "points_budget": budget,
            "equipment": eq, "equipment_alternatives": alts,
            "rotation": hunt_rot, "boss_rotation": boss_rot, "hunt_sim": hunt_sim, "boss_sim": boss_sim,
            "rotation_no_runes": hunt_rot_no_runes, "hunt_sim_no_runes": hunt_sim_no_runes,
            "boss_rotation_no_runes": boss_rot_no_runes, "boss_sim_no_runes": boss_sim_no_runes,
            "fixed_rotation": list(fixed[0]) if fixed and fixed[0] else None,
            "fixed_weapon": fixed[1] if fixed else None,
            "model_rotation": model_rot, "model_sim": model_sim,
            "heal": heal, "metrics": metrics, "score": score_of(metrics, goal),
            "tree_alternatives": {"freed": 0, "removed": [], "base": dict(tree), "options": []},
            "helper": helper_config(prof, target, hunt_rot, boss_rot, heal, metrics, hunt_sim, boss_sim),
            "gold_cap": self.gold_cap,
            # o que e so da «prioridades»
            "priority": info, "damage_plan": damage, "avatar_plan": avatar_plan, "avatar_plans": avatar_plans,
        }
        return out

    def avatar_plans(self, vocation, level, info, avatar_plan, prof, eq, target, hunt_rot, boss_rot, heal, metrics_b):
        """Os dois planos ate ao nivel X em que o Avatar cabe (ordem 9b), com numeros:
        A — sem respec: agora so a rota (R pontos) e guardar o resto; ao nivel X o Avatar
        de uma vez; sem gold, mas ate la anda com (nivel - R) pontos por gastar (o DPS
        mede-se no simulador com a rota so, o mesmo equipamento e rotacao do plano B).
        B — gastar agora pela ordem (a build desta pagina) e ao nivel X importar a build
        com o Avatar (fD = 1000 + 200 x pontos gastos nessa altura, com tudo gasto = X).
        Recomendado por omissao o B: o gold nao conta para ele (16/09/2026) e o A deixa-o
        dezenas de niveis mais fraco."""
        cat = self.cat
        route = list(info["avatar_path"])
        cost = info["route"]["cost"]
        level_x = info["avatar_level"]
        tree_a = {nid: 1 for nid in route}
        prof_a = sim.Profile(cat, vocation, level, tree_a, eq)
        metrics_a = evaluate(prof_a, target, hunt_rot, boss_rot, heal)
        dps_a, dps_b = metrics_a["dps_cycle"], metrics_b["dps_cycle"]
        return {"level": level_x, "route": route, "route_cost": cost,
                "route_ranks": {nid: avatar_plan["tree"].get(nid, 0) for nid in route},
                "cheapest_level": info["route"]["cheapest_level"], "cheapest_cost": info["route"]["cheapest_cost"],
                "a": {"dps": dps_a, "unspent": F.tree_budget(level) - cost, "gold": 0, "tree": tree_a, "metrics": metrics_a},
                "b": {"dps": dps_b, "unspent": F.tree_budget(level) - _spent(cat, prof.tree), "gold": treecode.import_cost(F.tree_budget(level_x)),
                      "gold_points": F.tree_budget(level_x), "metrics": metrics_b},
                "dps_diff_pct": (dps_b / dps_a - 1) * 100 if dps_a else None,
                "recommended": "B"}


def _spent(cat, tree):
    return sum(F.tree_total_cost(cat.node_by_id[k], v) for k, v in tree.items())


def fill_tree(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal):
    """Gasta os pontos que sobram do prefixo do caminho, ao nivel da pagina, com
    o mesmo guloso preguicoso de `optimize_tree` (nivel e contexto fixos)."""
    if _spent(cat, tree) >= F.tree_budget(level):
        return dict(tree), []
    return optimize_tree(cat, vocation, goal, F.tree_budget(level),
                         equipment_at=lambda lv, ranks: eq, rotation_at=lambda lv, p: hunt_rot,
                         target_at=lambda lv: target, start_ranks=tree, level_of=lambda pts: level,
                         boss_rotation_at=lambda lv, p: boss_rot, heal_at=lambda p: heal)


def tree_alternatives(cat, vocation, goal, level, tree, steps, eq, target, hunt_rot, boss_rot, heal):
    """Os tres melhores nos em que os ultimos ~10 pontos poderiam ter ido: a
    metrica de cada um para se ver o que se perde (ou ganha) ao desviar."""
    node_by_id = {n["id"]: n for n in cat.tree_by_vocation[vocation]["nos"]}
    adj = _adjacency(cat, vocation)
    if not steps:
        return {"freed": 0, "removed": [], "base": dict(tree), "options": []}
    # tira os ultimos passos ate libertar >= 10 pontos (ou o ultimo notable)
    freed = 0
    base = dict(tree)
    removed = []
    for st in reversed(steps):
        if freed >= 10:
            break
        if base.get(st.node_id, 0) != st.rank:
            break  # o passo ja nao bate com a arvore (melhoria local mexeu aqui)
        base[st.node_id] = st.rank - 1
        if base[st.node_id] <= 0:
            base.pop(st.node_id)
        freed += st.cost
        removed.append(st.node_id)
    out = []
    for nid, node in node_by_id.items():
        if nid in removed:
            continue
        if base.get(nid, 0) >= (node.get("rank_maximo") or 1):
            continue
        path = unlock_path(node, base, adj, node_by_id)
        if path is None:
            continue
        trial = dict(base)
        cost = 0
        for pid in path + [nid]:
            cost += F.tree_rank_cost(node_by_id[pid], trial.get(pid, 0))
            trial[pid] = trial.get(pid, 0) + 1
        # gasta o que sobrou em mais ranks do mesmo no, se der
        while cost < freed and trial[nid] < (node.get("rank_maximo") or 1):
            c = F.tree_rank_cost(node, trial[nid])
            if cost + c > freed:
                break
            cost += c
            trial[nid] += 1
        if cost > freed:
            continue
        p = sim.Profile(cat, vocation, level, trial, eq)
        m = evaluate(p, target, hunt_rot, boss_rot, heal)
        out.append({"node": nid, "name": node["nome"], "rank": trial[nid], "metrics": m,
                    "score": score_of(m, goal), "tree": trial})
    out.sort(key=lambda x: -x["score"])
    return {"freed": freed, "removed": removed, "base": base, "options": out[:3]}


def local_improve(cat, vocation, goal, level, tree, steps, eq, target, hunt_rot, boss_rot, heal, rounds=4):
    """Melhoria local: enquanto desviar os ultimos ~10 pontos para outro no render
    mais de 0,2 % com o equipamento deste nivel, adopta-se o desvio. Devolve a
    arvore e a lista dos desvios feitos."""
    improved = []
    steps = list(steps)
    for _ in range(rounds):
        prof = sim.Profile(cat, vocation, level, tree, eq)
        current = score_of(evaluate(prof, target, hunt_rot, boss_rot, heal), goal)
        alts = tree_alternatives(cat, vocation, goal, level, tree, steps, eq, target, hunt_rot, boss_rot, heal)
        if not alts["options"] or alts["options"][0]["score"] <= current * 1.002:
            break
        best = alts["options"][0]
        improved.append({"removed": list(alts["removed"]), "to": best["name"], "rank": best["rank"],
                         "gain_pct": (best["score"] / current - 1) * 100})
        before = alts["base"]
        tree = best["tree"]
        # os passos removidos saem; cada rank comprado no desvio entra como passo
        # proprio (com o seu custo real), senao o `freed` da ronda seguinte mente
        n_removed = len(alts["removed"])
        steps = steps[:-n_removed] if n_removed else steps
        steps.extend(_diff_steps(cat, before, tree, level, best["score"]))
        # o que sobrou do orcamento (se o desvio custou menos) preenche-se
        tree, extra = fill_tree(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal)
        steps.extend(extra)
    return tree, improved


def _diff_steps(cat, before, after, level, score):
    steps = []
    spent = _spent(cat, before)
    for nid, r_after in after.items():
        r_before = before.get(nid, 0)
        node = cat.node_by_id[nid]
        for r in range(r_before + 1, r_after + 1):
            c = F.tree_rank_cost(node, r - 1)
            spent += c
            steps.append(TreeStep(nid, r, c, spent, level, score, 0.0))
    return steps


# --- podar os nos de ligacao e os papeis de cada no (ordem 8) -------------------------------------
def _score_tree(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal):
    return score_of(evaluate(sim.Profile(cat, vocation, level, tree, eq), target, hunt_rot, boss_rot, heal), goal)


def _is_defensive(node):
    per = node.get("efeito_por_rank") or {}
    return any(k in per for k in DEFENSIVE_EFFECTS)


def prune_and_refill(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal, protected=None):
    """Enquanto houver um rank cujo ganho na metrica e ~0 (< PRUNE_GAIN_PCT) e cuja
    remocao mantem a arvore ligada (`treecode.is_connected`, cliente O3e), tira-se —
    o pedido era o small a rank 1 comprado so como caminho; a mesma regra rank a rank
    apanha tambem o que o caminho comprou para sobreviver e deixou de fazer falta
    (o knight «dano» a 527 tinha Fire Ward 10 e Bulwark 10 a render 0 depois de o
    Battle Tactics entrar). No fim os pontos libertados voltam a gastar-se com o
    guloso, sem recomprar o que se podou; ate PRUNE_OUTER_ROUNDS vezes. Devolve
    (arvore, [(no, rank antes, rank depois)], passos do refill). `protected` {no: rank}
    (ordem 9) sao ranks que a poda nao toca — as etapas 1 a 7 das prioridades."""
    tree = dict(tree)
    pruned = {}
    refill = []
    protected = protected or {}

    def loss_of(nid):
        """(perda % na metrica, arvore sem o ultimo rank de `nid`), ou None se o tirar desliga a arvore."""
        if tree[nid] <= protected.get(nid, 0):
            return None
        trial = dict(tree)
        if trial[nid] > 1:
            trial[nid] -= 1
        else:
            trial.pop(nid)
            if not treecode.is_connected(cat, vocation, trial):
                return None
        s = _score_tree(cat, vocation, goal, level, trial, eq, target, hunt_rot, boss_rot, heal)
        return (base / max(1e-9, s) - 1.0) * 100.0, trial

    for _ in range(PRUNE_OUTER_ROUNDS):
        before = dict(tree)
        base = base_before = _score_tree(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal)
        # guloso preguicoso: a fila guarda a ultima perda conhecida de cada no; tira-se o de menor
        # perda, re-avalia-se no estado actual e, se continua abaixo do limiar, sai um rank (e o
        # no volta a fila com a perda nova). Nao se re-avaliam os outros todos a cada rank tirado
        heap = []
        for nid in tree:
            lt = loss_of(nid)
            if lt is not None and lt[0] < PRUNE_GAIN_PCT:
                heapq.heappush(heap, (lt[0], nid))
        removed_ranks = 0
        while heap and removed_ranks < PRUNE_MAX_ROUNDS:
            loss, nid = heapq.heappop(heap)
            if nid not in tree:
                continue
            lt = loss_of(nid)
            if lt is None or lt[0] >= PRUNE_GAIN_PCT:
                continue
            if heap and lt[0] > heap[0][0]:
                heapq.heappush(heap, (lt[0], nid))   # ja nao e o de menor perda: volta a fila com o valor fresco
                continue
            tree = lt[1]
            removed_ranks += 1
            base = _score_tree(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal)
            if nid in tree:
                heapq.heappush(heap, (lt[0], nid))
        removed = {nid: (before[nid], tree.get(nid, 0)) for nid in before if before[nid] != tree.get(nid, 0)}
        if not removed:
            break
        # os pontos libertados: o guloso, mas sem voltar a comprar o que se podou
        exclude = set(pruned) | set(removed)
        tree, steps = _refill(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal, exclude=exclude)
        after = _score_tree(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal)
        if (not steps or max(st.gain_per_point for st in steps) <= PRUNE_GAIN_PCT / 100.0
                or after < base_before * (1.0 - PRUNE_REVERT_PCT / 100.0)):
            # o refill so encontrou pontos a render ~0 (arvore saturada: nivel alto, dano todo
            # comprado — trocar uns zeros por outros so faria ruido), ou a metrica ficou pior do que
            # antes de podar (o simulador tem ruido de grelha: uma cura que muda de segundo mexe
            # na tendencia da vida): fica como estava
            tree = before
            break
        for nid, (a, b) in removed.items():
            pruned[nid] = (pruned.get(nid, (a, a))[0], b)
        refill.extend(steps)
    return tree, [(nid, a, b) for nid, (a, b) in pruned.items()], refill


def _refill(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal, exclude=()):
    """Gasta o que sobra ao nivel: o guloso de `optimize_tree` (sem os `exclude`); se
    ainda sobrar (nada compravel fora deles), entra o que for compravel — primeiro os
    nos de HP/absorcao (1-2 pontos sem rank de dano que os aceite: «ponto que sobrou»)."""
    if _spent(cat, tree) >= F.tree_budget(level):
        return dict(tree), []
    tree, steps = optimize_tree(cat, vocation, goal, F.tree_budget(level),
                                equipment_at=lambda lv, ranks: eq, rotation_at=lambda lv, p: hunt_rot,
                                target_at=lambda lv: target, start_ranks=tree, level_of=lambda pts: level,
                                exclude=exclude, boss_rotation_at=lambda lv, p: boss_rot, heal_at=lambda p: heal,
                                stop_at_zero_gain=True)
    adj = _adjacency(cat, vocation)
    node_by_id = {n["id"]: n for n in cat.tree_by_vocation[vocation]["nos"]}
    spent = _spent(cat, tree)
    budget = F.tree_budget(level)
    while spent < budget:
        options = [n for nid, n in node_by_id.items() if can_buy(n, tree, adj)
                   and F.tree_rank_cost(n, tree.get(nid, 0)) <= budget - spent]
        if not options:
            break
        # o que se podou so volta se nao houver mais nada em que por o ponto
        options.sort(key=lambda n: (n["id"] in exclude, not _is_defensive(n), F.tree_rank_cost(n, tree.get(n["id"], 0)), n["id"]))
        n = options[0]
        c = F.tree_rank_cost(n, tree.get(n["id"], 0))
        tree[n["id"]] = tree.get(n["id"], 0) + 1
        spent += c
        steps.append(TreeStep(n["id"], tree[n["id"]], c, spent, level, 0.0, 0.0))
    return tree, steps


ROLE_DAMAGE, ROLE_LINK, ROLE_TACTICS, ROLE_LEFTOVER = "dano", "so ligacao", "tactica", "ponto que sobrou"


def node_roles(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal, refill_steps=()):
    """O papel de cada no da arvore final: `tactica` (Battle Tactics), `so ligacao`
    (rende ~0 na metrica mas tira-lo desligava a arvore), `ponto que sobrou` (o
    refill comprou-o a render ~0) ou `dano` (rende na metrica). Devolve
    {no: (papel, ganho % de o ter)}."""
    base = _score_tree(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal)
    roles = {}
    for nid, rank in tree.items():
        node = cat.node_by_id[nid]
        if (node.get("especial") or {}).get("key") == "tactics":
            roles[nid] = (ROLE_TACTICS, None)
            continue
        # o que o no da por si: a metrica sem os ranks dele (o simulador soma efeitos, nao
        # exige ligacao — por isso mede-se mesmo quando tira-lo desligava a arvore)
        trial = dict(tree)
        trial.pop(nid)
        s = _score_tree(cat, vocation, goal, level, trial, eq, target, hunt_rot, boss_rot, heal)
        gain_pct = (base / max(1e-9, s) - 1.0) * 100.0
        if gain_pct >= PRUNE_GAIN_PCT:
            roles[nid] = (ROLE_DAMAGE, gain_pct)
        elif not treecode.is_connected(cat, vocation, trial):
            roles[nid] = (ROLE_LINK, gain_pct)       # rende ~0 mas segura o ramo
        else:
            roles[nid] = (ROLE_LEFTOVER, gain_pct)   # rende ~0 e nada depende dele: pontos sem sitio melhor
    return roles


def purchase_order(cat, vocation, tree, hint_steps=()):
    """A ordem de compra da arvore FINAL, clicavel a mao pelas regras do cliente (`yD`):
    segue a ordem dos passos conhecidos enquanto cada um puder entrar; um passo que
    ainda nao pode (o vizinho que o abria foi podado) espera pela vez; o que faltar
    entra por BFS a partir do tier 0. Lista de TreeStep com o custo real e o
    acumulado (= o nivel em que se chega la)."""
    node_by_id = {n["id"]: n for n in cat.tree_by_vocation[vocation]["nos"]}
    adj = _adjacency(cat, vocation)
    wanted = {nid: r for nid, r in tree.items() if r >= 1}
    queue = []
    seen = set()
    stage_of = {}
    for st in hint_steps:   # sem repetidos: a melhoria local e o refill podem recomprar um rank tirado
        key = (st.node_id, st.rank)
        if st.rank <= wanted.get(st.node_id, 0) and key not in seen:
            seen.add(key)
            queue.append(key)
            stage_of[key] = getattr(st, "stage", None)
    # o que os passos nao cobrem (podado e recomprado, refill) entra por BFS
    for nid, r in sorted(wanted.items(), key=lambda kv: (node_by_id[kv[0]].get("tier", 0), kv[0])):
        for rank in range(1, r + 1):
            if (nid, rank) not in seen:
                seen.add((nid, rank))
                queue.append((nid, rank))
    state = {}
    spent = 0
    order = []
    while queue:
        picked = None
        for i, (nid, rank) in enumerate(queue):
            if state.get(nid, 0) != rank - 1:
                continue
            node = node_by_id[nid]
            if can_buy(node, state, adj):
                picked = i
                break
        if picked is None:
            break   # nao devia acontecer numa arvore ligada; o teste da propriedade apanha
        nid, rank = queue.pop(picked)
        node = node_by_id[nid]
        c = F.tree_rank_cost(node, rank - 1)
        spent += c
        state[nid] = rank
        order.append(TreeStep(nid, rank, c, spent, spent, 0.0, 0.0, stage=stage_of.get((nid, rank))))
    return order


# --- as prioridades do Andre (ordem 9, 21/09/2026) -------------------------------------------------
def priority_category(node, elements, vocation=None):
    """A categoria de um no: a de maior prioridade entre os seus efeitos
    (`PRIORITY_STAT_CATEGORY`); o Avatar da vocacao e «avatar»; `elementDmgPct` so
    conta nos `elements` (os que a rotacao e a arma usam); o resto e «rest»."""
    if vocation and node["id"] == AVATAR_NODE.get(vocation):
        return "avatar"
    best = "rest"
    for stat, value in (node.get("efeito_por_rank") or {}).items():
        cat_name = PRIORITY_STAT_CATEGORY.get(stat)
        if cat_name is None:
            continue
        if stat == "elementDmgPct":
            if not any(el in (elements or ()) for el in (value or {})):
                continue
        # a categoria e a da ordem 9 (o que o no e), mesmo com PRIORITY_ORDER reduzida a duas etapas
        if PRIORITY_ORDER_ORDEM_9.index(cat_name) < PRIORITY_ORDER_ORDEM_9.index(best):
            best = cat_name
    return best


def priority_elements(profile, hunt_rot):
    """Os elementos que a rotacao de hunt e a arma usam: o de cada feitico da rotacao
    (`F.spell_element`), o do golpe da arma (fisico nas armas de corpo a corpo e
    arcos, mais a parte elemental dela; o da wand nos mages)."""
    elements = set()
    for sl in hunt_rot or ():
        elements.add(F.spell_element(sl.spell["palavras"]))
    if profile.wand:
        elements.add(profile.wand["element"])
    else:
        elements.add("physical")
        if profile.attack_element_share and profile.weapon_element:
            elements.add(profile.weapon_element)
    return frozenset(elements)


def avatar_reach(cat, vocation, tree=None):
    """(custo do caminho ligado mais barato ate ao Avatar a partir de `tree`, caminho,
    nivel em que cabe a partir da arvore vazia). O nivel = caminho + 300, porque cada
    nivel da um ponto (cliente)."""
    node_by_id = {n["id"]: n for n in cat.tree_by_vocation[vocation]["nos"]}
    adj = _adjacency(cat, vocation)
    avatar = node_by_id[AVATAR_NODE[vocation]]
    ranks = dict(tree or {})
    path = unlock_path(avatar, ranks, adj, node_by_id)
    if path is None:
        return None, [], None
    cost = sum(F.tree_rank_cost(node_by_id[p], ranks.get(p, 0)) for p in path) + F.tree_rank_cost(avatar, 0)
    return cost, path, cost


def _effect_value(node, stage, elements=()):
    """O efeito de um rank na categoria: a soma dos stats dela (`atkPct` + `spellDmgPct`
    no Ataque); no Elemento so os `elements` (os da rotacao e da arma)."""
    per = node.get("efeito_por_rank") or {}
    total = 0.0
    for k, v in per.items():
        if PRIORITY_STAT_CATEGORY.get(k) != stage:
            continue
        if k == "elementDmgPct":
            total += sum(float(x) for el, x in (v or {}).items() if el in elements and isinstance(x, (int, float)))
        elif isinstance(v, (int, float)):
            total += float(v)
    return total


def _stat_signature(node):
    """Os stats de um no, para saber quando dois ranks dao «o mesmo»: so entao a conta por
    stat os compara (ordem 9c). Berserk Mastery (atkPct+critDmg) nao e o mesmo que Fury (atkPct).
    `elementDmgPct` holy e physical ficam na mesma assinatura de proposito (ordem 10): o modelo
    linear compara-os exactamente pelos marginais de cada elemento — separa-los entregava-os ao
    simulador ruidoso e o paladin 284 caia de 2 126 para 1 880 DPS."""
    return tuple(sorted((node.get("efeito_por_rank") or {}).keys()))


def _stage_by_effect(node_by_id, adj, tree, budget, category, stage, elements, buy, score_fn=None, path_cache=None):
    """Uma etapa pelo efeito por ponto (com o caminho que faltar no custo), ate nao caber
    mais nenhum rank da categoria. `buy(nid, is_link)` poe um rank e regista o passo.
    Com `score_fn(tree)` (ordem 9c, etapas 4-7): entre ranks com o MESMO stat decide a
    conta por stat; o simulador so decide entre os melhores de stats diferentes da mesma
    categoria (atkPct vs spellDmgPct; um notable que traz outra coisa) — o `optimize_tree`
    media cada rank de +1,5 % de ataque na grelha de 60 s e o ruido (de -0,03 % a +0,15 %
    por ponto para o mesmo stat) mandava mais do que o custo. Sem `score_fn` (Exp/Loot)
    tudo se compara pelo efeito por ponto, como na ordem 9. Entre stats diferentes o
    simulador mede pacotes do MESMO tamanho (o rank mais caro dos candidatos contra os
    ranks do mesmo stat dos outros ate igualar o custo): a +1,5 % de Fury contra os 50
    pontos de Combat Mastery ainda era ruido; 50 pontos de Fury/Warlord/Cleave nao.
    `path_cache` como em `_rank_candidates` (as etapas Exp/Loot correm por cada uma das
    centenas de rotas na escolha da rota, ordem 10b)."""
    spent = sum(F.tree_total_cost(node_by_id[k], v) for k, v in tree.items())

    def candidates(state, spent_state):
        """assinatura de stats -> (efeito/ponto, no, caminho, custo) do melhor rank dela em `state`"""
        groups = {}
        bought = frozenset(k for k, v in state.items() if v) if path_cache is not None else None
        for nid, node in node_by_id.items():
            if category[nid] != stage or state.get(nid, 0) >= (node.get("rank_maximo") or 1):
                continue
            if path_cache is None:
                path = unlock_path(node, state, adj, node_by_id)
            else:
                key = (nid, bought)
                if key in path_cache:
                    path = path_cache[key]
                else:
                    path = path_cache[key] = unlock_path(node, state, adj, node_by_id)
            if path is None:
                continue
            c = sum(F.tree_rank_cost(node_by_id[p], state.get(p, 0)) for p in path) + F.tree_rank_cost(node, state.get(nid, 0))
            if spent_state + c > budget:
                continue
            value = _effect_value(node, stage, elements) / c
            key = _stat_signature(node) if score_fn else ()
            cur = groups.get(key)
            # empate no efeito por ponto: o mais barato (fica mais para os outros), depois o id
            if cur is None or (-value, c, nid) < (-cur[0], cur[3], cur[1]):
                groups[key] = (value, nid, path, c)
        return groups

    while True:
        groups = candidates(tree, spent)
        if not groups:
            return
        if len(groups) == 1:
            _, nid, path, c = next(iter(groups.values()))
        else:
            base = max(1e-9, score_fn(tree))
            size = max(g[3] for g in groups.values())
            best = None
            for key, (value, nid, path, c) in groups.items():
                trial = dict(tree)
                for p in path + [nid]:
                    trial[p] = trial.get(p, 0) + 1
                pkg = c
                # o pacote: mais ranks do mesmo stat, pela mesma conta, ate ao tamanho do rank mais caro
                while pkg < size:
                    nxt = candidates(trial, spent + pkg).get(key)
                    if nxt is None or pkg + nxt[3] > size:
                        break
                    for p in nxt[2] + [nxt[1]]:
                        trial[p] = trial.get(p, 0) + 1
                    pkg += nxt[3]
                gain = (score_fn(trial) / base - 1.0) / pkg
                # empate no simulador (ate PRIORITY_STAT_SIM_TIE, relativo): o mais barato, depois o id
                tol = abs(best[0]) * PRIORITY_STAT_SIM_TIE + 1e-12 if best else 0.0
                if best is None or gain > best[0] + tol or (gain >= best[0] - tol and (c, nid) < (best[3], best[1])):
                    best = (gain, nid, path, c)
            _, nid, path, c = best
        for p in path:
            buy(p, True)
        buy(nid, False)
        spent += c


def _stage_candidates(node_by_id, adj, tree, budget, category, stages, elements):
    """Ha algum rank de uma das `stages` (exp/loot) ligado e a caber com o caminho no custo?
    (a verificacao da regra «Exp e Loot antes do dano» depois da poda, ordem 10b)"""
    spent = sum(F.tree_total_cost(node_by_id[k], v) for k, v in tree.items())
    for nid, node in node_by_id.items():
        if category[nid] not in stages or tree.get(nid, 0) >= (node.get("rank_maximo") or 1):
            continue
        path = unlock_path(node, tree, adj, node_by_id)
        if path is None:
            continue
        c = sum(F.tree_rank_cost(node_by_id[p], tree.get(p, 0)) for p in path) + F.tree_rank_cost(node, tree.get(nid, 0))
        if spent + c <= budget:
            return True
    return False


# --- o modelo linear do dano e a etapa «damage» (ordem 10, 21/09/2026) ----------------------------
def stat_model(cat, vocation, level, tree, eq, target, hunt_rot, boss_rot, heal, elements, deltas=PRIORITY_MODEL_DELTAS):
    """O valor marginal de cada stat, medido no simulador sobre `tree`: fraccao do DPS (a
    metrica «dano») por +1 do stat — `{"atkPct": f, ..., "elementDmgPct": {el: f}}`, mais
    `"_base"` (a metrica sem perturbacao) e `"_dps"` (o DPS do ciclo). Media das
    perturbacoes `deltas` (+1 e +2) para tirar o ruido da grelha de 2 s. Os elementos
    so os `elements` (os da rotacao e da arma); os outros valem 0. Mede-se o DPS do ciclo
    (o que ele pergunta: dano), nao a metrica com a sobrevivencia — sobre «rota + Avatar»
    a fraccao de sobrevivencia e minuscula e qualquer +1 % dava +60 % na metrica; a
    sobrevivencia continua a contar onde o simulador decide (`score_fn`, a metrica «dano»)."""
    def dps(extra):
        prof = sim.Profile(cat, vocation, level, tree, eq, extra=extra)
        return evaluate(prof, target, hunt_rot, boss_rot, heal)["dps_cycle"]

    base = max(1e-9, dps(None))
    model = {"_base": base, "_dps": base, "elementDmgPct": {}}

    def slope(extra):
        vals = []
        for d in deltas:
            ex = {k: (v * d if isinstance(v, (int, float)) else {el: x * d for el, x in v.items()}) for k, v in extra.items()}
            vals.append((dps(ex) / base - 1.0) / d)
        return sum(vals) / len(vals)

    for stat in PRIORITY_MODEL_STATS:
        if stat == "elementDmgPct":
            for el in sorted(elements or ()):
                model["elementDmgPct"][el] = slope({"elementDmgPct": {el: 1.0}})
        else:
            model[stat] = slope({stat: 1.0})
    return model


def _merge_model(old, new):
    """O modelo refrescado: um stat que passa a medir <= 0 e ruido da grelha (um stat de dano nunca
    tira DPS) e fica com o valor anterior — senao, dentro da mesma assinatura, «-0,6/8» ganhava a
    «-0,5/5» e o rank caro entrava antes do barato (visto no knight 300 sem Avatar)."""
    out = dict(new)
    for k, v in old.items():
        if k == "elementDmgPct":
            out[k] = {el: (x if x > 0 else old[k].get(el, 0.0)) for el, x in new[k].items()}
        elif not k.startswith("_") and isinstance(v, (int, float)) and new.get(k, 0.0) <= 0.0:
            out[k] = v
    return out


def model_rank_value(node, model):
    """O que um rank de `node` vale no modelo linear (fraccao de DPS): a soma dos stats
    do `efeito_por_rank` x marginal; o que nao esta no modelo (HP, armor, leech, mana,
    Battle Tactics, notables de efeito especial) vale 0 — e o simulador que decide esses."""
    per = node.get("efeito_por_rank") or {}
    total = 0.0
    for k, v in per.items():
        if k == "elementDmgPct":
            for el, x in (v or {}).items():
                if isinstance(x, (int, float)):
                    total += x * model["elementDmgPct"].get(el, 0.0)
        elif k in model and isinstance(v, (int, float)):
            total += v * model[k]
    return total


def _rank_candidates(node_by_id, adj, state, budget, spent_state, value_of, skip=(), by_signature=True, path_cache=None):
    """assinatura de stats -> (valor/ponto, no, caminho, custo) do melhor rank compravel dela
    em `state` (empate: o mais barato, depois o id); `value_of(node)` e o valor de um rank.
    `path_cache` {(no, nos comprados): caminho}: o caminho de desbloqueio so depende de QUAIS
    nos estao comprados (os do caminho estao todos a 0), e a mesma arvore pergunta-o
    milhares de vezes (o `unlock_path` era 80 % do tempo da escolha da rota)."""
    groups = {}
    bought = frozenset(k for k, v in state.items() if v) if path_cache is not None else None
    for nid, node in node_by_id.items():
        if nid in skip or state.get(nid, 0) >= (node.get("rank_maximo") or 1):
            continue
        if path_cache is None:
            path = unlock_path(node, state, adj, node_by_id)
        else:
            key = (nid, bought)
            if key in path_cache:
                path = path_cache[key]
            else:
                path = path_cache[key] = unlock_path(node, state, adj, node_by_id)
        if path is None:
            continue
        c = sum(F.tree_rank_cost(node_by_id[p], state.get(p, 0)) for p in path) + F.tree_rank_cost(node, state.get(nid, 0))
        if spent_state + c > budget:
            continue
        value = value_of(node) / c
        key = _stat_signature(node) if by_signature else ()
        cur = groups.get(key)
        if cur is None or (-value, c, nid) < (-cur[0], cur[3], cur[1]):
            groups[key] = (value, nid, path, c)
    return groups


def _stage_damage(node_by_id, adj, tree, budget, buy, score_fn, model_fn, skip=(), min_gain=0.0, history=None):
    """A etapa «damage» (ordem 10): todos os pontos restantes no que rende mais DPS. A
    regra da 9c sobre TODOS os nos: dentro da mesma assinatura de stats decide o modelo
    linear por ponto (exacto, com o caminho que faltar no custo); entre assinaturas
    diferentes decide o simulador em pacotes do mesmo tamanho (o rank mais caro contra
    ranks da mesma assinatura dos outros ate igualar o custo). Os nos sem stat no modelo
    (HP, armor, tacticas, notables de efeito especial) valem 0 no modelo e so o simulador
    os pode meter. `model_fn(tree)` mede o modelo de novo (a cada PRIORITY_MODEL_REFRESH
    pontos: crit e dano critico multiplicam-se). Para quando o melhor pacote rende
    <= `min_gain` por ponto no simulador (o resto e do `_refill`: «ponto que sobrou»).
    Devolve o ultimo modelo medido."""
    spent = sum(F.tree_total_cost(node_by_id[k], v) for k, v in tree.items())
    model = model_fn(tree)
    next_refresh = spent + PRIORITY_MODEL_REFRESH
    # `history` [(pontos gastos a partir dos quais vigora, modelo)]: o teste de propriedade repete
    # os passos com o modelo que estava em vigor em cada compra
    if history is not None:
        history.append((spent, model))
    # fila preguicosa entre assinaturas: o ganho medido de uma assinatura fica valido enquanto o
    # melhor rank dela (no, custo) e o tamanho do pacote nao mudarem; a do vencedor mede-se de novo
    # a cada compra e todas a cada refresh do modelo (sem isto eram G simulacoes por rank comprado)
    gains = {}
    paths = {}
    while True:
        if spent >= next_refresh:
            model = _merge_model(model, model_fn(tree))
            next_refresh = spent + PRIORITY_MODEL_REFRESH
            gains.clear()
            if history is not None:
                history.append((spent, model))
        groups = _rank_candidates(node_by_id, adj, tree, budget, spent, lambda n: model_rank_value(n, model), skip=skip,
                                  path_cache=paths)
        if not groups:
            return model
        if len(groups) == 1:
            value, nid, path, c = next(iter(groups.values()))
            if value <= min_gain:
                return model
            key, gain = next(iter(groups)), value
        else:
            base = None
            size = max(g[3] for g in groups.values())
            best = None
            for key, (value, nid, path, c) in groups.items():
                cached = gains.get(key)
                if cached is not None and cached[1] == (nid, c, size):
                    gain = cached[0]
                else:
                    if base is None:
                        base = max(1e-9, score_fn(tree))
                    trial = dict(tree)
                    for p in path + [nid]:
                        trial[p] = trial.get(p, 0) + 1
                    pkg = c
                    while pkg < size:
                        nxt = _rank_candidates(node_by_id, adj, trial, budget, spent + pkg,
                                               lambda n: model_rank_value(n, model), skip=skip, path_cache=paths).get(key)
                        if nxt is None or pkg + nxt[3] > size:
                            break
                        for p in nxt[2] + [nxt[1]]:
                            trial[p] = trial.get(p, 0) + 1
                        pkg += nxt[3]
                    gain = (score_fn(trial) / base - 1.0) / pkg
                    gains[key] = (gain, (nid, c, size))
                tol = abs(best[0]) * PRIORITY_STAT_SIM_TIE + 1e-12 if best else 0.0
                if best is None or gain > best[0] + tol or (gain >= best[0] - tol and (c, nid) < (best[3], best[1])):
                    best = (gain, nid, path, c, key)
            gain, nid, path, c, key = best
            if gain <= min_gain:
                # o simulador nao ve ganho em nenhum pacote (a metrica «dano» tem patamares: a
                # sobrevivencia e a grelha de 2 s), mas o modelo ainda ve dano por comprar: fica o
                # melhor rank do modelo — so se para quando nem o modelo ve nada
                key, (value, nid, path, c) = max(groups.items(), key=lambda kv: kv[1][0])
                if value <= min_gain:
                    return model
                gain = value
        for p in path:
            buy(p, True)
        buy(nid, False, gain)   # o ganho por ponto (modelo, ou simulador quando ele decidiu) fica no passo
        spent += c
        gains.pop(key, None)


def route_damage_score(cat, vocation, level, route, model, with_avatar=True, path_cache=None):
    """A rota avaliada pelo modelo linear do dano (ordem 10): a rota a rank 1 + o Avatar +
    os pontos restantes gastos pelo mesmo modelo (ganho por ponto exacto, com o caminho
    que faltar no custo, so o que rende > 0). Devolve (valor no modelo = soma das
    fraccoes de DPS, arvore) ou None se a rota nao cabe. `path_cache` partilha-se entre
    as centenas de rotas (as arvores parecem-se)."""
    got = route_priority_score(cat, vocation, level, route, model, None, frozenset(), with_avatar=with_avatar,
                               path_cache=path_cache, stages=())
    return (got[0][3], got[1]) if got else None


def route_priority_score(cat, vocation, level, route, model, category, elements, with_avatar=True, path_cache=None,
                         stages=None):
    """A rota avaliada pelas prioridades (ordem 10b): a rota a rank 1 + o Avatar, depois as
    etapas `stages` (as de `PRIORITY_ORDER` entre o Avatar e a «damage»: Exp, Loot) pelo
    efeito por ponto, e os pontos restantes pelo modelo linear do dano (ganho por ponto
    exacto, com o caminho que faltar no custo, so o que rende > 0). Devolve (vector, arvore)
    — vector = (Avatar 1/0, +% exp, +% loot, valor no modelo = soma das fraccoes de DPS) —
    ou None se a rota nao cabe. `path_cache` partilha-se entre as centenas de rotas."""
    node_by_id = {n["id"]: n for n in cat.tree_by_vocation[vocation]["nos"]}
    adj = _adjacency(cat, vocation)
    budget = F.tree_budget(level)
    tree = {p: 1 for p in route}
    if with_avatar:
        tree[AVATAR_NODE[vocation]] = 1
    spent = _spent(cat, tree)
    if spent > budget:
        return None
    skip = {AVATAR_NODE[vocation]}
    paths = path_cache if path_cache is not None else {}
    if stages is None:
        stages = tuple(s for s in PRIORITY_ORDER if s not in ("avatar", "damage", "rest"))
    if stages:
        if category is None:
            category = {nid: priority_category(n, elements, vocation) for nid, n in node_by_id.items()}

        def buy(nid, is_link=False):
            tree[nid] = tree.get(nid, 0) + 1
        for stage in stages:
            _stage_by_effect(node_by_id, adj, tree, budget, category, stage, elements, buy, path_cache=paths)
        spent = _spent(cat, tree)
    while True:
        groups = _rank_candidates(node_by_id, adj, tree, budget, spent, lambda n: model_rank_value(n, model),
                                  skip=skip, by_signature=False, path_cache=paths)
        if not groups:
            break
        value, nid, path, c = groups[()]
        if value <= 0.0:
            break
        for p in path + [nid]:
            tree[p] = tree.get(p, 0) + 1
        spent += c
    total = sum(model_rank_value(node_by_id[nid], model) * r for nid, r in tree.items() if nid in node_by_id)
    tot = priority_totals(cat, vocation, tree, elements) if stages else {"expPct": 0.0, "lootPct": 0.0}
    return (1 if with_avatar else 0, round(tot["expPct"], 6), round(tot["lootPct"], 6), total), tree


# --- a rota ate ao Avatar (ordem 9b, 21/09/2026) ---------------------------------------------------
def avatar_routes(cat, vocation):
    """Todas as rotas ligadas do tier 0 ate ao Avatar que so sobem (cada passo vai de um
    no para um que o `requer`), por ordem de clique, com o custo a rank 1 (sem os 300 do
    Avatar). Um desvio para baixo nunca faz falta: um no vizinho da rota compra-se na
    etapa dele sem custo de ligacao. Lista de (custo, [ids]) — centenas por vocacao."""
    tree = cat.tree_by_vocation[vocation]
    node_by_id = {n["id"]: n for n in tree["nos"]}
    up = {nid: [] for nid in node_by_id}
    for n in tree["nos"]:
        for req in n.get("requer") or []:
            up[req].append(n["id"])
    avatar = AVATAR_NODE[vocation]
    routes = []

    def walk(nid, path, cost):
        for v in up[nid]:
            if v == avatar:
                routes.append((cost, list(path)))
            elif up[v]:
                path.append(v)
                walk(v, path, cost + F.tree_rank_cost(node_by_id[v], 0))
                path.pop()

    for nid, n in node_by_id.items():
        if n.get("tier", 0) == 0 and nid != avatar:
            walk(nid, [nid], F.tree_rank_cost(n, 0))
    return routes


def route_vector(cat, vocation, level, route, category, elements, with_avatar=True):
    """O vector lexicografico de uma rota ao nivel (as prioridades por ordem): (Avatar 1/0,
    +% exp, +% loot, +% crit, +% atk+spell, +% dano critico, +% elemento util, pontos que
    sobram para o resto). Contas por stat, SEM simulador: a rota a rank 1 (+ o Avatar),
    depois as etapas 2-7 pelo efeito por ponto com o caminho que faltar — e o que deixa
    avaliar centenas de rotas; a build da rota escolhida faz-se depois com o simulador
    (`priority_tree`). Devolve (vector, arvore) ou None se a rota nao cabe."""
    node_by_id = {n["id"]: n for n in cat.tree_by_vocation[vocation]["nos"]}
    adj = _adjacency(cat, vocation)
    budget = F.tree_budget(level)
    tree = {}

    def buy(nid, is_link=False):
        tree[nid] = tree.get(nid, 0) + 1

    for p in route:
        buy(p)
    if with_avatar:
        buy(AVATAR_NODE[vocation])
    if _spent(cat, tree) > budget:
        return None
    for stage in ("exp", "loot", "crit", "attack", "critdmg", "element"):
        _stage_by_effect(node_by_id, adj, tree, budget, category, stage, elements, buy)
    tot = priority_totals(cat, vocation, tree, elements)
    vector = (1 if with_avatar else 0, tot["expPct"], tot["lootPct"], tot["critChance"], tot["atkPct"] + tot["spellDmgPct"],
              tot["critDmg"], sum(tot["element"].values()), budget - _spent(cat, tree))
    return vector, tree


def _dominated_routes(routes, category):
    """Poda por dominancia: uma rota que so acrescenta nos sem categoria a outra (os
    mesmos nos de categoria ou menos, e custa o mesmo ou mais) nunca ganha. Devolve
    (rotas que ficam, quantas sairam)."""
    keyed = [(c, r, frozenset(n for n in r if category.get(n, "rest") != "rest")) for c, r in routes]
    keep = []
    for i, (c, r, cats) in enumerate(keyed):
        dominated = any(j != i and c2 <= c and cats2 >= cats and (c2 < c or cats2 > cats or j < i)
                        for j, (c2, r2, cats2) in enumerate(keyed))
        if not dominated:
            keep.append((c, r))
    return keep, len(routes) - len(keep)


def choose_avatar_route(cat, vocation, level, elements, score_fn=None, max_delay=PRIORITY_ROUTE_MAX_DELAY, forced=None,
                        model=None):
    """A rota ate ao Avatar mais util (ordem 9b). Ao nivel em que o Avatar cabe: todas as
    rotas que cabem no orcamento, avaliadas a esse nivel. Abaixo: so as que nao o atrasam
    mais de `max_delay` niveis face a mais barata, avaliadas todas ao mesmo nivel (mais
    barata + 300 + max_delay) — o nivel do Avatar passa a ser o custo da escolhida + 300.
    Com `model` (ordem 10, o modelo linear do dano de `stat_model`): cada rota avalia-se
    por `route_damage_score`, as PRIORITY_ROUTE_SIM_TIES melhores confirmam-se com a
    arvore inteira no simulador (`score_fn`) e ganha a de maior DPS; empate -> a mais
    barata -> a de menos nos. Sem `model` (ordem 9b): o vector lexicografico por stat,
    empate -> `score_fn` -> a mais barata -> a de menos nos. `forced` salta a escolha (a
    build do nivel do Avatar leva a rota escolhida abaixo dele). Devolve um dicionario
    com a escolhida, a mais barata, a melhor no modelo e os numeros da enumeracao."""
    node_by_id = {n["id"]: n for n in cat.tree_by_vocation[vocation]["nos"]}
    category = {nid: priority_category(n, elements, vocation) for nid, n in node_by_id.items()}
    avatar_cost = F.tree_rank_cost(node_by_id[AVATAR_NODE[vocation]], 0)
    routes = avatar_routes(cat, vocation)
    if not routes:
        return None
    cheapest_cost = min(c for c, _ in routes)
    cheapest = min((r for r in routes if r[0] == cheapest_cost), key=lambda r: len(r[1]))
    budget = F.tree_budget(level)
    fits = cheapest_cost + avatar_cost <= budget
    if fits:
        eval_level = level
        cands = [(c, r) for c, r in routes if c + avatar_cost <= budget]
    else:
        eval_level = cheapest_cost + avatar_cost + max_delay
        cands = [(c, r) for c, r in routes if c <= cheapest_cost + max_delay]
    pruned = ties = sim_ties = 0
    model_best = model_score = sim_score = cheapest_sim = cheapest_model = None
    sim_agrees = None
    vector_10b = cheapest_10b = None
    dps_best = None   # ordem 10b: a rota de maior DPS no modelo, sem olhar a Exp/Loot (a pagina mostra-a ao lado)
    if forced is not None:
        route = list(forced)
        cost = sum(F.tree_rank_cost(node_by_id[p], 0) for p in route)
        vec = route_vector(cat, vocation, eval_level, route, category, elements)
        vector = vec[0] if vec else None
        if model is not None:
            got = route_priority_score(cat, vocation, eval_level, route, model, category, elements)
            model_score = got[0][3] if got else None
            vector_10b = got[0] if got else None
    elif model is not None:
        # ordem 10/10b: cada rota avalia-se pelo vector (Avatar, +% exp, +% loot, DPS do modelo linear)
        # — Exp e Loot pelas contas por stat das etapas 2-3, o DPS pelo modelo sobre o que sobra; entre
        # rotas com o mesmo exp e loot ganha a de maior DPS, e as melhores confirmam-se no simulador
        if len(cands) > PRIORITY_ROUTE_MAX_ENUM:
            cands, pruned = _dominated_routes(cands, category)
        scored = []
        paths = {}
        for c, r in cands:
            got = route_priority_score(cat, vocation, eval_level, r, model, category, elements, path_cache=paths)
            if got is not None:
                scored.append((got[0][3], -c, -len(r), r, got[1], got[0]))
        # a rota de maior DPS no modelo (ignorando Exp/Loot): e o que a ordem 10 escolhia
        scored.sort(key=lambda s: (s[0], s[1], s[2]), reverse=True)
        dps_best_entry = scored[0]
        # o grupo das prioridades: o maior (exp, loot); dentro dele o modelo ordena
        top_key = max(s[5][1:3] for s in scored)
        group = [s for s in scored if s[5][1:3] == top_key]
        group.sort(key=lambda s: (s[0], s[1], s[2]), reverse=True)
        model_best, model_score = list(group[0][3]), group[0][0]
        cheapest_entry = next((s for s in scored if s[3] == cheapest[1]), None)
        cheapest_model = cheapest_entry[0] if cheapest_entry else None
        cheapest_10b = cheapest_entry[5] if cheapest_entry else None
        cheapest_in_group = cheapest_entry is not None and any(s is cheapest_entry for s in group)
        if score_fn is not None:
            # as melhores do grupo no modelo confirmam-se no simulador; a mais barata e a de maior DPS
            # medem-se tambem (para a pagina), mas so entram na escolha se tiverem o mesmo exp e loot
            top = group[:PRIORITY_ROUTE_SIM_TIES]
            if cheapest_in_group and not any(s is cheapest_entry for s in top):
                top.append(cheapest_entry)
            extra = [s for s in (cheapest_entry, dps_best_entry) if s is not None and not any(s is t for t in top)]
            sim_scores = {id(s): score_fn(s[4]) for s in top + extra}
        else:
            top = group[:1]
            sim_scores = {id(top[0]): top[0][0]}
            if dps_best_entry is not top[0]:
                sim_scores[id(dps_best_entry)] = dps_best_entry[0]
        sim_ties = len(top)
        winner = max(top, key=lambda s: (sim_scores[id(s)], s[1], s[2]))
        route, cost = list(winner[3]), -winner[1]
        sim_score = sim_scores[id(winner)]
        vector_10b = winner[5]
        cheapest_sim = sim_scores.get(id(cheapest_entry)) if cheapest_entry else None
        vec = route_vector(cat, vocation, eval_level, route, category, elements)
        vector = vec[0] if vec else None
        dps_best = {"route": list(dps_best_entry[3]), "cost": -dps_best_entry[1], "level": -dps_best_entry[1] + avatar_cost,
                    "vector": dps_best_entry[5], "model_score": dps_best_entry[0],
                    "sim_score": sim_scores.get(id(dps_best_entry)), "same": dps_best_entry is winner,
                    "same_exp_loot": dps_best_entry[5][1:3] == top_key}
        if score_fn is not None:
            model_best_sim = sim_scores[id(group[0])]
            sim_agrees = {"agrees": winner is group[0], "model_best_sim": model_best_sim,
                          "diff_pct": (sim_score / model_best_sim - 1.0) * 100.0 if model_best_sim else None}
    else:
        if len(cands) > PRIORITY_ROUTE_MAX_ENUM:
            cands, pruned = _dominated_routes(cands, category)
        scored = []
        for c, r in cands:
            got = route_vector(cat, vocation, eval_level, r, category, elements)
            if got is not None:
                scored.append((got[0], -c, -len(r), r, got[1]))
        best_vec = max(s[0] for s in scored)
        tied = [s for s in scored if s[0] == best_vec]
        ties = len(tied)
        sim_scores = {}
        if ties > 1 and score_fn is not None:
            tied.sort(key=lambda s: (s[1], s[2]), reverse=True)
            for s in tied[:PRIORITY_ROUTE_SIM_TIES]:
                sim_scores[id(s)] = score_fn(s[4])
            sim_ties = len(sim_scores)
        winner = max(tied, key=lambda s: (sim_scores.get(id(s), -math.inf), s[1], s[2]))
        route, cost, vector = list(winner[3]), -winner[1], winner[0]
    cheapest_vec = route_vector(cat, vocation, eval_level, cheapest[1], category, elements)
    return {"route": route, "cost": cost, "level": cost + avatar_cost, "vector": vector, "forced": forced is not None,
            "cheapest_route": list(cheapest[1]), "cheapest_cost": cheapest_cost, "cheapest_level": cheapest_cost + avatar_cost,
            "cheapest_vector": cheapest_vec[0] if cheapest_vec else None,
            "fits": fits, "eval_level": eval_level, "routes_total": len(routes), "routes_candidates": len(cands),
            "routes_pruned": pruned, "ties": ties, "sim_ties": sim_ties, "max_delay": max_delay,
            # ordem 10: a escolha pelo DPS
            "by_model": model is not None, "model_best_route": model_best, "model_score": model_score,
            "sim_score": sim_score, "cheapest_sim": cheapest_sim, "cheapest_model": cheapest_model,
            "sim_check": sim_agrees if isinstance(sim_agrees, dict) else None,
            # ordem 10b: o vector (Avatar, +% exp, +% loot, DPS do modelo) da escolhida e da mais barata,
            # e a rota de maior DPS no modelo (a que a ordem 10 escolhia) para a pagina comparar
            "vector_10b": vector_10b, "cheapest_vector_10b": cheapest_10b, "dps_best": dps_best,
            "priority_stages": tuple(s for s in PRIORITY_ORDER if s not in ("avatar", "damage", "rest"))}


def priority_tree(cat, vocation, level, eq, target, hunt_rot, boss_rot, heal, elements, route=None, score_fn=None):
    """A arvore pelas prioridades do Andre (21/09/2026), etapa a etapa (`PRIORITY_ORDER`;
    desde a 10b: Avatar, Exp, Loot, «damage»): 1 a rota mais util ate ao Avatar
    (`choose_avatar_route`, ordem 9b/10b) + o Avatar — se o Avatar nao couber, compra-se a
    rota na mesma (e o plano B: gastar agora e importar a build com o Avatar ao nivel em
    que cabe) e diz-se o nivel; 2 Exp e 3 Loot pelo efeito por ponto (com o caminho que
    faltar no custo), cada uma esgotada antes da seguinte; «damage» (ordem 10) tudo o que
    sobra no que rende mais DPS, com o modelo linear medido sobre a arvore das etapas 1-3
    e a poda so aqui (nunca toca nas etapas anteriores). Da ordem 9 ficam disponiveis:
    4-7 o mesmo stat pela conta por stat e stats diferentes da categoria pelo simulador
    (ordem 9c; desligado, `PRIORITY_GREEDY_BY_STAT`, o guloso de DPS restrito a categoria);
    8 o resto pelo guloso de DPS e a poda so aqui. `route` forca
    a rota (a build do nivel do Avatar usa a mesma que se escolheu abaixo dele).
    Devolve (arvore, passos com etapa, info) — info: avatar (bool), avatar_level (o da
    rota escolhida), avatar_path (= a rota), route {...} (a escolha e a mais barata),
    category {no: categoria}, link {no comprado so como caminho}, stage_points por
    etapa, pruned, totals por stat."""
    node_by_id = {n["id"]: n for n in cat.tree_by_vocation[vocation]["nos"]}
    adj = _adjacency(cat, vocation)
    budget = F.tree_budget(level)
    category = {nid: priority_category(n, elements, vocation) for nid, n in node_by_id.items()}
    tree = {}
    steps = []
    link = set()
    info = {"avatar": False, "avatar_level": None, "avatar_path": [], "category": category, "elements": sorted(elements),
            "stage_points": {}, "pruned": [], "link": link, "route": None, "pre_damage_tree": None}

    def spent():
        return _spent(cat, tree)

    def buy(nid, stage, is_link=False, gain=0.0):
        node = node_by_id[nid]
        c = F.tree_rank_cost(node, tree.get(nid, 0))
        tree[nid] = tree.get(nid, 0) + 1
        steps.append(TreeStep(nid, tree[nid], c, spent(), level, 0.0, gain or 0.0, stage=stage, link=is_link))
        if is_link and tree[nid] == 1 and category[nid] != stage:
            link.add(nid)

    def score_tree(trial):
        return _score_tree(cat, vocation, "damage", level, trial, eq, target, hunt_rot, boss_rot, heal)

    def model_at(trial, at_level=level):
        return stat_model(cat, vocation, at_level, trial, eq, target, hunt_rot, boss_rot, heal, elements)

    info["stat_model"] = info["stat_report"] = None
    for stage in PRIORITY_ORDER:
        before = spent()
        if stage == "avatar":
            # 1. a rota mais util ate ao Avatar, e o Avatar se couber. Ordem 10: a rota escolhe-se
            # pelo DPS — o modelo linear medido sobre «rota mais barata + Avatar» ao nivel de
            # avaliacao ordena as rotas, o simulador confirma as melhores
            model0 = None
            if "damage" in PRIORITY_ORDER and route is None:
                probe = choose_avatar_route(cat, vocation, level, elements, forced=())
                if probe is not None:
                    base_tree = {p: 1 for p in probe["cheapest_route"]}
                    base_tree[AVATAR_NODE[vocation]] = 1
                    model0 = model_at(base_tree, probe["eval_level"])
            choice = choose_avatar_route(cat, vocation, level, elements, score_fn=score_fn, forced=route, model=model0)
            if choice is not None:
                info["route"] = choice
                info["avatar_level"], info["avatar_path"] = choice["level"], list(choice["route"])
                for p in choice["route"]:
                    buy(p, "avatar", is_link=True)
                if choice["level"] <= budget:
                    buy(AVATAR_NODE[vocation], "avatar")
                    info["avatar"] = True
        elif stage in ("exp", "loot"):
            # pelo efeito por ponto (o caminho que faltar conta no custo)
            _stage_by_effect(node_by_id, adj, tree, budget, category, stage, elements,
                             lambda nid, is_link, stage=stage: buy(nid, stage, is_link=is_link))
        elif stage in ("crit", "attack", "critdmg", "element"):
            # dentro da categoria: o mesmo stat pela conta por stat, stats diferentes pelo simulador
            # (ordem 9c); ou, desligado, o guloso de DPS por ponto medido no simulador, restrito a categoria
            only = {nid for nid, c in category.items() if c == stage}
            if only and spent() < budget and PRIORITY_GREEDY_BY_STAT:
                _stage_by_effect(node_by_id, adj, tree, budget, category, stage, elements,
                                 lambda nid, is_link, stage=stage: buy(nid, stage, is_link=is_link), score_fn=score_tree)
            elif only and spent() < budget:
                start = dict(tree)
                tree, st = optimize_tree(cat, vocation, "damage", budget,
                                         equipment_at=lambda lv, ranks: eq, rotation_at=lambda lv, p: hunt_rot,
                                         target_at=lambda lv: target, start_ranks=tree, level_of=lambda pts: level,
                                         boss_rotation_at=lambda lv, p: boss_rot, heal_at=lambda p: heal, only=only)
                for s in st:
                    s.stage = stage
                    if category[s.node_id] != stage and s.rank == 1 and start.get(s.node_id, 0) == 0:
                        link.add(s.node_id)
                steps.extend(st)
        elif stage == "damage":
            # ordem 10: tudo o que sobra no que rende mais DPS (9c sobre todos os nos); o modelo
            # medido sobre a arvore das etapas anteriores («rota + Avatar + Exp + Loot», 10b) e o
            # «o que rende mais» da pagina, antes de gastar; a poda nao toca nessas etapas
            protected = dict(tree)
            info["pre_damage_tree"] = dict(tree)   # a arvore das etapas 1-3: e sobre ela que o bloco e a validacao 1e contam
            model_start = model_at(tree)
            info["stat_model"] = model_start
            info["stat_report"] = priority_stat_report(cat, vocation, level, tree, model_start, elements, eq=eq)
            skip = {AVATAR_NODE[vocation]} if not info["avatar"] else set()
            info["stat_models"] = []
            _stage_damage(node_by_id, adj, tree, budget,
                          lambda nid, is_link, gain=0.0: buy(nid, "damage", is_link=is_link, gain=gain), score_tree, model_at,
                          skip=skip, history=info["stat_models"])
            # o que ficou (nada a render > 0 no simulador): o «ponto que sobrou» do guloso de sempre, e a poda
            tree, st = _refill(cat, vocation, "damage", level, tree, eq, target, hunt_rot, boss_rot, heal)
            for s in st:
                s.stage = "damage"
            steps.extend(st)
            before_prune = dict(tree)
            tree, pruned, refill_steps = prune_and_refill(cat, vocation, "damage", level, tree, eq, target, hunt_rot,
                                                          boss_rot, heal, protected=protected)
            info["prune_reverted"] = None
            after_prune = dict(before_prune)
            for n, a, c in pruned:
                if c:
                    after_prune[n] = c
                else:
                    after_prune.pop(n, None)
            if pruned and _stage_candidates(node_by_id, adj, after_prune, budget, category,
                                            [s for s in PRIORITY_ORDER if s in ("exp", "loot")], elements):
                # 10b: a poda libertou pontos com que um rank de Exp/Loot passava a caber — e a regra e Exp e
                # Loot antes de um ponto ir ao dano. A poda rende ~0 por definicao: fica como estava, e diz-se
                info["prune_reverted"] = [(n, a, c) for n, a, c in pruned]
                tree, pruned, refill_steps = before_prune, [], []
            for s in refill_steps:
                s.stage = "damage"
            steps.extend(refill_steps)
            info["pruned"] = pruned
        elif stage == "rest":
            # o guloso de DPS de sempre, e a poda so sobre o que esta etapa comprou
            protected = dict(tree)
            tree, st = _refill(cat, vocation, "damage", level, tree, eq, target, hunt_rot, boss_rot, heal)
            for s in st:
                s.stage = "rest"
            steps.extend(st)
            tree, pruned, refill_steps = prune_and_refill(cat, vocation, "damage", level, tree, eq, target, hunt_rot,
                                                          boss_rot, heal, protected=protected)
            for s in refill_steps:
                s.stage = "rest"
            steps.extend(refill_steps)
            info["pruned"] = pruned
        info["stage_points"][stage] = spent() - before
    info["totals"] = priority_totals(cat, vocation, tree, elements)
    if info["stat_report"] is not None:
        priority_stat_report_finish(cat, vocation, info["stat_report"], tree, steps, info)
    return tree, steps, info


def _report_stats(vocation):
    """As tres linhas do «o que rende mais»: (chave, rotulo, stats do modelo que somam)."""
    return (("attack", "Ataque", PRIORITY_ATTACK_STATS.get(vocation, ("atkPct",))),
            ("critChance", "Chance de critico", ("critChance",)),
            ("critDmg", "Dano critico", ("critDmg",)))


def priority_stat_report(cat, vocation, level, tree, model, elements, eq=None):
    """O bloco «Depois do Avatar: o que rende mais» (ordem 10), como dados, sobre a arvore
    «rota + Avatar» e o modelo medido nela: por linha (Ataque, Chance de critico, Dano
    critico) o que +1 % rende no simulador (fraccao e DPS), o melhor rank compravel agora
    desse stat (no, rank, custo, ganho por ponto) — os totais comprados e o veredicto
    preenche-os `priority_stat_report_finish` no fim da build. O porque do dano critico e
    o do cliente: o dano esperado e 1 + chance x (50 + critDmg)/10 000, e no Avatar
    «crita sempre» durante 15 s, por isso a chance efectiva ja e alta."""
    node_by_id = {n["id"]: n for n in cat.tree_by_vocation[vocation]["nos"]}
    adj = _adjacency(cat, vocation)
    budget = F.tree_budget(level)
    spent = _spent(cat, tree)
    rows = []
    for key, label, stats in _report_stats(vocation):
        per_unit = sum(model.get(s, 0.0) for s in stats) / len(stats)
        # o melhor rank compravel agora que de este stat (por ganho de DPS por ponto no modelo)
        best = None
        for nid, node in node_by_id.items():
            per = node.get("efeito_por_rank") or {}
            if not any(s in per for s in stats) or tree.get(nid, 0) >= (node.get("rank_maximo") or 1):
                continue
            path = unlock_path(node, tree, adj, node_by_id)
            if path is None:
                continue
            c = sum(F.tree_rank_cost(node_by_id[p], tree.get(p, 0)) for p in path) + F.tree_rank_cost(node, tree.get(nid, 0))
            if spent + c > budget:
                continue
            effect = sum(float(per.get(s) or 0.0) for s in stats)
            gain = model_rank_value(node, model) / c
            if best is None or gain > best["gain_per_point"]:
                best = {"node_id": nid, "name": node["nome"], "rank": tree.get(nid, 0) + 1, "cost": c, "path": list(path),
                        "effect": effect, "gain_per_point": gain}
        rows.append({"key": key, "label": label, "stats": stats, "per_unit": per_unit, "dps_per_unit": per_unit * model["_dps"],
                     "best": best, "bought_pct": 0.0, "bought_points": 0})
    prof = sim.Profile(cat, vocation, level, tree, eq or {})
    return {"rows": rows, "dps_base": model["_dps"], "level": level, "verdict": None,
            "crit_chance_tree": sum(float((node_by_id[n].get("efeito_por_rank") or {}).get("critChance") or 0) * r
                                    for n, r in tree.items() if n in node_by_id),
            "avatar_uptime": prof.avatar_uptime(), "points_by_stat": {}, "order": []}


def priority_stat_report_finish(cat, vocation, report, tree, steps, info):
    """Fecha o bloco com a build feita: quantos % e pontos foram a cada um dos tres stats
    e ao resto (elemento, notables, tacticas, so ligacao), a ordem da etapa «damage» com
    o stat de cada passo, e o veredicto gerado da conta (o stat de maior ganho por ponto
    primeiro; «ate aos ~N pontos» = quando a build passa ao seguinte)."""
    node_by_id = {n["id"]: n for n in cat.tree_by_vocation[vocation]["nos"]}
    model = info["stat_model"] or {}
    by_key = {r["key"]: r for r in report["rows"]}

    def stat_of(nid):
        """A linha a que um no pertence: a de maior contribuicao no modelo; None = o resto."""
        per = node_by_id[nid].get("efeito_por_rank") or {}
        best, best_v = None, 0.0
        for key, label, stats in _report_stats(vocation):
            v = sum(float(per.get(s) or 0.0) * model.get(s, 0.0) for s in stats)
            if v > best_v:
                best, best_v = key, v
        return best

    points = {"attack": 0, "critChance": 0, "critDmg": 0, "rest": 0, "link": 0}
    order = []
    for st in steps:
        if st.stage != "damage":
            continue
        key = stat_of(st.node_id)
        if getattr(st, "link", False) and key is None:
            points["link"] += st.cost
        else:
            points[key or "rest"] += st.cost
        order.append({"node_id": st.node_id, "name": node_by_id[st.node_id]["nome"], "rank": st.rank, "cost": st.cost,
                      "stat": key, "link": getattr(st, "link", False), "cumulative": st.cumulative})
    for key, label, stats in _report_stats(vocation):
        by_key[key]["bought_points"] = points[key]
        by_key[key]["bought_pct"] = sum(float((node_by_id[n].get("efeito_por_rank") or {}).get(s) or 0.0) * r
                                        for n, r in tree.items() if n in node_by_id and stat_of(n) == key for s in stats)
    report["points_by_stat"] = points
    report["order"] = order
    # o veredicto: por ganho por ponto do melhor rank agora; «ate aos ~N pontos» = o ponto da
    # etapa em que a build comprou o primeiro rank do stat seguinte
    ranked = sorted((r for r in report["rows"] if r["best"]), key=lambda r: -r["best"]["gain_per_point"])
    if ranked:
        first = ranked[0]
        cum_at = {}
        start = order[0]["cumulative"] - order[0]["cost"] if order else 0
        for o in order:
            if o["stat"] and o["stat"] not in cum_at and not o["link"]:
                cum_at[o["stat"]] = o["cumulative"] - start
        parts = ["depois do %s rende mais %s (%.2f %%/pt)" % (priority_stages_before_damage(), first["label"].lower(),
                                                              first["best"]["gain_per_point"] * 100)]
        if len(ranked) > 1:
            second = ranked[1]
            n = cum_at.get(second["key"])
            if n is not None:
                parts[0] += " ate aos ~%d pontos, depois %s (%.2f %%/pt)" % (n, second["label"].lower(), second["best"]["gain_per_point"] * 100)
            else:
                parts[0] += "; %s (%.2f %%/pt) nesta build nunca chega a valer mais" % (second["label"].lower(), second["best"]["gain_per_point"] * 100)
        crit = by_key["critChance"]
        cd = by_key["critDmg"]
        u = report["avatar_uptime"]
        eff_chance = u * 100.0 + (1 - u) * report["crit_chance_tree"]
        avatar_note = ("Avatar «crita sempre» %.0f %% do tempo" % (u * 100)) if u else "ainda sem Avatar"
        why = ("dano critico so vale a chance: com %.0f %% de chance efectiva (%s) "
               "cada 1 %% de dano critico vale %.2f %% de dano e cada 1 %% de chance vale %.2f %% — os dois multiplicam-se"
               % (eff_chance, avatar_note, cd["per_unit"] * 100, crit["per_unit"] * 100))
        n_cd = cum_at.get("critDmg")
        if ranked[0]["key"] != "critDmg" and (len(ranked) < 2 or ranked[1]["key"] != "critDmg"):
            why = ("dano critico a partir dos ~%d pontos, porque %s" % (n_cd, why) if n_cd is not None
                   else "dano critico nao entrou nesta build, porque %s" % why)
        # os numeros em portugues (virgula); o unico ponto do texto e o decimal
        report["verdict"] = "; ".join(parts + [why]).replace(".", ",") + "."
        report["ranked"] = [r["key"] for r in ranked]
    return report


def priority_totals(cat, vocation, tree, elements):
    """Os totais por categoria da arvore: +% exp, loot, crit, atk, spell, crit dmg e
    elemento (so os `elements`), somados dos `efeito_por_rank` x rank."""
    out = {"expPct": 0.0, "lootPct": 0.0, "critChance": 0.0, "atkPct": 0.0, "spellDmgPct": 0.0, "critDmg": 0.0,
           "element": {}}
    for nid, rank in tree.items():
        node = cat.node_by_id.get(nid)
        if not node or not rank:
            continue
        for stat, value in (node.get("efeito_por_rank") or {}).items():
            if stat == "elementDmgPct":
                for el, v in (value or {}).items():
                    if el in elements and isinstance(v, (int, float)):
                        out["element"][el] = out["element"].get(el, 0.0) + v * rank
            elif stat in out and isinstance(value, (int, float)):
                out[stat] += value * rank
    return out


def priority_roles(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal, steps, info):
    """Os papeis na build «prioridades»: os nos das etapas 1-7 levam a etapa como papel
    (so ligacao os que so entraram como caminho); os da etapa 8 os papeis de sempre
    (`node_roles`). {no: (papel, ganho %)}."""
    stage_of = {}
    for st in steps:
        stage_of.setdefault(st.node_id, st.stage)
    # «damage» (ordem 10) e como «rest»: os papeis medidos de sempre (dano / so ligacao / tactica / ponto que sobrou)
    rest_nodes = {nid for nid, s in stage_of.items() if s in ("rest", "damage")}
    measured = node_roles(cat, vocation, goal, level, tree, eq, target, hunt_rot, boss_rot, heal)
    roles = {}
    for nid in tree:
        stage = stage_of.get(nid, "rest")
        role, gain = measured.get(nid, (ROLE_LEFTOVER, None))
        c = info["category"].get(nid, "rest")
        if nid in info["link"] and c != "rest":
            # entrou como caminho (da rota ou de outra etapa) mas e de uma categoria: ja rende nela
            roles[nid] = (c, gain)
        elif nid in info["link"] and tree[nid] == 1:
            roles[nid] = (ROLE_LINK, gain)
        elif nid in info["link"]:
            roles[nid] = (role, gain)
        elif stage in ("rest", "damage") or nid in rest_nodes:
            roles[nid] = (role, gain)
        else:
            roles[nid] = (stage, gain)
    return roles


def tree_check(cat, vocation, level, tree):
    """A linha «valida pelas regras do cliente»: ligada a partir do tier 0 (O3e), ranks
    <= maximo e pontos gastos (Up) <= os do nivel. {connected, max_rank_ok, spent, budget, ok}."""
    spent = treecode.points_spent(cat, vocation, tree)
    budget = F.tree_budget(level)
    max_ok = all(r <= (cat.node_by_id[k].get("rank_maximo") or 1) for k, r in tree.items())
    connected = treecode.is_connected(cat, vocation, tree)
    return {"connected": connected, "max_rank_ok": max_ok, "spent": spent, "budget": budget,
            "ok": connected and max_ok and spent <= budget}


# --- Helper --------------------------------------------------------------------------------
def potion_threshold(profile, target, rotation, heal):
    """O limiar de pocao mais baixo (35..85) com que o simulador nao deixa a
    vida cair abaixo de 2x o maior golpe do boss — a margem contra um pico."""
    _, boss_max_hit, _ = sim.pressure(profile, target, boss=True)
    for pct in (35, 45, 55, 65, 75, 85):
        old = profile.potion_hp_pct
        profile.potion_hp_pct = pct
        r = sim.simulate(profile, target, rotation, boss=True, heal=heal)
        profile.potion_hp_pct = old
        if r.hp_min >= 2 * boss_max_hit and r.death_at is None:
            return pct
    return 85


def spell_costs(rotation, result):
    """Por feitico da rotacao: mana e gold por lancamento (cliente), lancamentos
    por minuto no simulador e o gold/h que isso da — para a coluna «gold/h» da
    pagina. `result` e o SimResult da rotacao (None = sem lancamentos contados)."""
    out = []
    casts = (result.casts if result is not None else {}) or {}
    seconds = float(result.seconds) if result is not None else 60.0
    for sl in rotation:
        sp = sl.spell
        n = casts.get(sp["palavras"], 0)
        per_min = n * 60.0 / seconds
        gold_cast = sp.get("custo_gold") or 0
        out.append({"name": sp["nome"], "words": sp["palavras"], "rune": sim.is_rune(sp),
                    "mana": sp["mana"], "gold_per_cast": gold_cast, "casts_per_min": per_min,
                    "gold_per_hour": gold_cast * per_min * 60.0})
    return out


def supplies(result):
    """{runes, hp_potions, mana_potions, total} em gold/h, do SimResult (pocoes de
    mana em regime — ver `sim.simulate`)."""
    if result is None:
        return None
    return {"runes": result.runes_per_hour, "hp_potions": result.hp_potions_per_hour,
            "mana_potions": result.mana_potions_per_hour, "total": result.gold_per_hour}


def helper_config(profile, target, hunt_rot, boss_rot, heal, metrics, hunt_sim=None, boss_sim=None):
    """Os campos do Helper com os nomes do jogo (etiquetas do cliente)."""
    canal_85 = 85
    computed = potion_threshold(profile, target, boss_rot or hunt_rot, heal)
    heal_at = max(computed, min(canal_85, int(math.ceil(2 * metrics["boss_max_hit"] / max(1.0, profile.hp_max) * 100 / 5.0) * 5)))
    heal_at = max(35, min(85, heal_at))
    hp_pot = profile.hp_potion
    mana_pot = profile.mana_potion
    rune_heals = [s for s in sim.heal_spells(profile) if s.get("custo_gold")]
    rune_alt = max(rune_heals, key=lambda s: profile.heal_amount(s)) if rune_heals else None
    friend = [s for s in sim.heal_spells(profile, friend=True)]
    excluded = hunt_exclusions(profile, target)
    return {
        "heal_spell": heal["nome"] if heal else None,
        "heal_words": heal["palavras"] if heal else None,
        "heal_at": heal_at, "heal_at_computed": computed, "heal_at_canal": canal_85,
        "heal_rune_alternative": rune_alt,
        "hp_potion": hp_pot["name"] if hp_pot else None, "hp_below": max(computed, 35),
        "mana_potion": mana_pot["name"] if mana_pot else None, "mana_below": 25 if mana_pot else None,
        "friend_heal": friend[0]["nome"] if friend else None,
        "friend_heal_at": 85 if friend else None,
        "hunt_rotation": [(sl.spell["nome"], sl.spell["palavras"], sl.min_mobs if sl.spell["tipo"] == "area" else None) for sl in hunt_rot],
        "boss_rotation": [(sl.spell["nome"], sl.spell["palavras"], None) for sl in boss_rot],
        # (nome, palavras, motivo) do que ficou fora da rotacao de hunt — beams e imunidades
        "hunt_excluded": [(s["nome"], s["palavras"], excluded[s["palavras"]]) for s in sim.attack_spells(profile)
                          if s["palavras"] in excluded],
        # custos por feitico e gold/h (pocoes em regime + runas) dos dois cenarios
        "hunt_costs": spell_costs(hunt_rot, hunt_sim), "boss_costs": spell_costs(boss_rot, boss_sim),
        "hunt_supplies": supplies(hunt_sim), "boss_supplies": supplies(boss_sim),
        "position": _position(profile),
        "distance": _distance(profile),
        "magic_shield": profile.vocation in sim.MAGES,
        "emergency": _emergency(profile, target),
    }


def _position(profile):
    if profile.vocation == "knight":
        return "Persegue o alvo e fica colado nele (corpo a corpo)"
    if profile.vocation == "monk":
        return "Persegue o alvo e fica colado nele (corpo a corpo)"
    return "Mantém essa distância do alvo"


def _distance(profile):
    if profile.vocation in ("knight", "monk"):
        return 1
    return 3


def _emergency(profile, target):
    """Anel/amuleto de emergencia pela regra do canal (SSA, Might Ring) — e o
    amuleto elemental pelo dano dominante da hunt. Opiniao do canal, citada."""
    dominant = target.dominant_element()
    amulet = {"energy": "Light Pendant", "fire": "Magma Amulet", "earth": "Terra Amulet",
              "physical": "Protection Amulet"}.get(dominant, "Protection Amulet")
    return {"dominant_element": dominant, "amulet_standard": amulet, "amulet_emergency": "Stone Skin Amulet",
            "ring_emergency": "Might Ring", "source": "canal CharllonLobo (mSE11hHamRs, rP83AhzvK9M)"}
