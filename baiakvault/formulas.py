"""As formulas do jogo, transcritas a letra, com a fonte ao lado de cada uma.

Tres fontes, por esta ordem de confianca (decisao de 16/09/2026):

- ``cliente``  — esta no bundle publico do cliente do jogo
  (``https://baiakidle.com/jogar/assets/index-DnzxFejS.js``, 09/09/2026).
  E a conta do proprio jogo: as formulas dos feiticos, a arvore (custo por
  rank, orcamento, pre-requisitos, efeitos), o ataque da arma, o empilhar das
  absorcoes, o prey, as pocoes.
- ``guia``     — ``guiabaiakidle.com`` (build planner, ``character-planner``
  JS, lido a 16/09/2026): armadura 520/24 %, bloqueio 650/18 %, leech 0.55,
  base de HP/mana, skill tipico por nivel, multiplicadores da wave 10.
  E convencao de um site da comunidade, nao do jogo.
- ``convencao`` — decisao nossa onde nem o cliente nem o guia tem numero
  (o dano do ataque automatico, o intervalo do ataque automatico, quantos
  bichos uma area apanha). Sai sempre marcado com aviso na pagina.

Nada aqui le ficheiros nem vai a rede: sao funcoes puras sobre numeros. O
que vem do catalogo entra por argumento. Cada constante esta registada em
``CONSTANTS`` com a fonte e o sitio exacto de onde veio, para a pagina de
fontes se gerar daqui e nao de memoria.
"""
import ast
import math
import re

SOURCE_CLIENT = "cliente"
SOURCE_GUIDE = "guia"
SOURCE_CHANNEL = "canal"
SOURCE_CONVENTION = "convencao"

BUNDLE = "https://baiakidle.com/jogar/assets/index-DnzxFejS.js (bundle do jogo, 2026-09-09)"
GUIDE_PLANNER = "https://guiabaiakidle.com/_astro/character-planner.D0n3Vxn3.js (lido a 2026-09-16)"
GUIDE_BUILDS = "https://guiabaiakidle.com/_astro/build-planner.B6PN3Q2m.js (lido a 2026-09-16)"

ELEMENTS = ("physical", "energy", "earth", "fire", "ice", "holy", "death")


class Constant:
    __slots__ = ("key", "value", "source", "where", "note")

    def __init__(self, key, value, source, where, note=""):
        self.key, self.value, self.source, self.where, self.note = key, value, source, where, note


CONSTANTS = {}


def _c(key, value, source, where, note=""):
    CONSTANTS[key] = Constant(key, value, source, where, note)
    return value


def const(key):
    return CONSTANTS[key].value


# --- cliente -------------------------------------------------------------------
ATTACK_GCD_MS = _c("attack_gcd_ms", 2000, SOURCE_CLIENT,
                   BUNDLE + " — `QO=2e3` e `cooldown_ataque_ms` em bruto/constantes.json",
                   "cooldown de grupo dos feiticos de ataque")
HEAL_GCD_MS = _c("heal_gcd_ms", 1000, SOURCE_GUIDE,
                 "guiabaiakidle.com/en/wiki/build-planner/ («Healing uses a separate 1-second group»)",
                 "o cliente separa o grupo `healing` do `attack` (funcao e0e) mas o valor vem do servidor")
POTION_EXHAUST_MS = _c("potion_exhaust_ms", 1000, SOURCE_GUIDE,
                       "guiabaiakidle.com wiki (pocoes de HP e mana partilham 1 s)")

# j0 do bundle: hpPerLevel/manaPerLevel por vocacao. `mlFactor`/`skillFactor`
# tambem la estao mas o cliente nao os usa em lado nenhum: nao se sabe o que
# significam, ficam de fora.
VOCATION_GROWTH = _c("vocation_growth", {
    "knight": {"hp_per_level": 15, "mana_per_level": 5},
    "paladin": {"hp_per_level": 10, "mana_per_level": 15},
    "sorcerer": {"hp_per_level": 5, "mana_per_level": 30},
    "druid": {"hp_per_level": 5, "mana_per_level": 30},
    "monk": {"hp_per_level": 13, "mana_per_level": 8},
}, SOURCE_CLIENT, BUNDLE + " — objecto `j0` (hpPerLevel, manaPerLevel)",
    "o guia usa monk 12 HP / 10 mana; o cliente diz 13 / 8 — segue-se o cliente")
HP_BASE = _c("hp_base", 100, SOURCE_GUIDE, GUIDE_PLANNER + " — `100+n.hpLevel*e.level`",
             "o cliente so tem o crescimento por nivel; a base e convencao do guia")
MANA_BASE = _c("mana_base", 90, SOURCE_GUIDE, GUIDE_PLANNER + " — `90+n.manaLevel*e.level`")

WEAPON_BASE_ATTACK = _c("weapon_base_attack", 6, SOURCE_CLIENT,
                        BUNDLE + " — funcao B1e: `atk:6+(t?.atk??0)`",
                        "todo o ataque tem +6 de base, mesmo sem arma")
AMMO_ATTACK_FACTOR = _c("ammo_attack_factor", 1.4, SOURCE_CLIENT,
                        BUNDLE + " — `_1e=1.4` e `P1e={\"diamond arrow\":1.2}`",
                        "o ataque da municao conta x1,4 (diamond arrow x1,2)")
AMMO_ATTACK_FACTOR_SPECIAL = _c("ammo_attack_factor_special", {"diamond arrow": 1.2},
                                SOURCE_CLIENT, BUNDLE + " — `P1e`")
UPGRADE_WEAPON_ATK_PCT = _c("upgrade_weapon_atk_pct_per_level", 1.0, SOURCE_CLIENT,
                            BUNDLE + " — funcao l5: `e.atkPct+=t.upLevel*1`")
UPGRADE_ARMOR_DEF_FACTOR = _c("upgrade_armor_def_factor_per_level", 0.005, SOURCE_CLIENT,
                              BUNDLE + " — funcao l5: `armorFlat+=def*(upLevel*.005)`")
IMBUEMENT_CRIT_CHANCE = _c("imbuement_crit_chance_pct", 5, SOURCE_CLIENT,
                           BUNDLE + " — `FY=5` (o imbuement Strike da +5 % de chance de critico alem do dano)")
TREE_POINTS_PER_LEVEL = _c("tree_points_per_level", 1, SOURCE_CLIENT,
                           BUNDLE + " — `yD(o,i,te.id,a.level)`: o orcamento da arvore e o nivel",
                           "e a importacao de build recusa `Up(o,_e)>a.level`")
TREE_RESPEC_BASE = _c("tree_respec_gold_base", 1000, SOURCE_CLIENT, BUNDLE + " — `B3e=1e3,$3e=200,fD=e=>B3e+$3e*e`")
TREE_RESPEC_PER_POINT = _c("tree_respec_gold_per_point", 200, SOURCE_CLIENT, BUNDLE + " — `fD`")
TREE_REFUND_PER_POINT = _c("tree_refund_gold_per_point", 400, SOURCE_CLIENT, BUNDLE + " — `R3e=400,gD=e=>R3e*e`")

PREY_STARS_MAX = _c("prey_stars_max", 10, SOURCE_CLIENT, BUNDLE + " — `RK=10`")

# Pocoes (B6 = vida, $6 = mana), tal e qual o bundle. `vocs` ausente = todas.
HEALTH_POTIONS = _c("health_potions", [
    {"name": "small health potion", "min_level": 1, "heal": 75, "cost": 20},
    {"name": "health potion", "min_level": 1, "heal": 150, "cost": 50},
    {"name": "strong health potion", "min_level": 50, "heal": 300, "cost": 115, "vocs": ["knight", "paladin", "monk"]},
    {"name": "great health potion", "min_level": 80, "heal": 500, "cost": 225, "vocs": ["knight"]},
    {"name": "great spirit potion", "min_level": 80, "heal": 350, "mana": 300, "cost": 254, "vocs": ["paladin", "monk"]},
    {"name": "ultimate health potion", "min_level": 130, "heal": 750, "cost": 379, "vocs": ["knight"]},
    {"name": "ultimate spirit potion", "min_level": 130, "heal": 550, "mana": 600, "cost": 488, "vocs": ["paladin", "monk"]},
    {"name": "supreme health potion", "min_level": 200, "heal": 1000, "cost": 650, "vocs": ["knight"]},
], SOURCE_CLIENT, BUNDLE + " — lista `B6`")
MANA_POTIONS = _c("mana_potions", [
    {"name": "mana potion", "min_level": 1, "mana": 120, "cost": 56},
    {"name": "strong mana potion", "min_level": 50, "mana": 240, "cost": 108},
    {"name": "great mana potion", "min_level": 80, "mana": 400, "cost": 158},
    {"name": "great spirit potion", "min_level": 80, "heal": 350, "mana": 300, "cost": 254, "vocs": ["paladin", "monk"]},
    {"name": "superior mana potion", "min_level": 100, "mana": 600, "cost": 254, "vocs": ["sorcerer", "druid"]},
    {"name": "distilled superior mana potion", "min_level": 100, "mana": 550, "cost": 381},
    {"name": "ultimate spirit potion", "min_level": 130, "heal": 550, "mana": 600, "cost": 488, "vocs": ["paladin", "monk"]},
    {"name": "ultimate mana potion", "min_level": 130, "mana": 800, "cost": 488, "vocs": ["sorcerer", "druid"]},
    {"name": "distilled ultimate mana potion", "min_level": 130, "mana": 750, "cost": 732},
], SOURCE_CLIENT, BUNDLE + " — lista `$6`")
USES_MANA_POTIONS = _c("uses_mana_potions", {
    "knight": False, "paladin": True, "sorcerer": True, "druid": True, "monk": False,
}, SOURCE_CLIENT, BUNDLE + " — `j0[voc].usesManaPotions`",
    "o Helper do knight e do monk nao bebe pocao de mana")
# O ambito do roubo de vida/mana do equipamento: o cliente so acumula `lifeLeech`/
# `manaLeech` (a aplicacao e do servidor); a unica frase que o descreve e a dos
# charms Vampiric Embrace / Void's Call. Ate 16/09/2026 o simulador creditava o
# leech a todo o dano, areas incluidas (ordem 6, supervisao).
LEECH_SCOPE = _c("leech_scope", "ataque normal + magias de alvo unico (strike); nunca areas nem curas",
                 SOURCE_CLIENT,
                 BUNDLE + " — texto dos charms Vampiric Embrace / Void's Call (bruto/charms.json): «so vale se o "
                 "seu equipamento ja da roubo de vida [/mana], e so no ataque normal e nas magias de alvo unico»",
                 "e a melhor evidencia que ha sobre o leech do equipamento; a formula e do servidor")

# A IA de combate (cliente `u4e(level, ranks)`): «o comportamento perfeito (mira,
# posicionamento, kite) existe desde o nivel 1 e a % e a chance de o acertar em cada
# decisao — o nivel da metade da qualidade (ate 2000) e o no Battle Tactics a outra
# metade (cada rank vale +100 niveis)». Ate 16/09/2026 (ordem 7) o no era decoracao
# no motor: `efeito_por_rank` nulo, so `special.tactics`.
TACTICS_AIM_BASE = _c("tactics_aim_base", 0.5, SOURCE_CLIENT, BUNDLE + " — `u4e`: `aimChance:Math.min(1,.5+.025*i)`",
                      "chance de decisao perfeita sem nivel nem ranks")
TACTICS_AIM_PER_QP = _c("tactics_aim_per_qp", 0.025, SOURCE_CLIENT, BUNDLE + " — `u4e`: `.5+.025*i`, i = qp")
TACTICS_QP_PER_LEVEL_TIER = _c("tactics_qp_per_level_tier", 0.5, SOURCE_CLIENT,
                               BUNDLE + " — `u4e`: `Math.min(10,a*.5)`, a = floor(nivel/100)", "tecto 10 qp pelo nivel (2000)")
TACTICS_QP_RANK_CAP = _c("tactics_qp_rank_cap", 10, SOURCE_CLIENT, BUNDLE + " — `u4e`: `Math.min(10,n)`, n = ranks")
TACTICS_SEARCH_RADIUS_QP = _c("tactics_search_radius_qp", 7, SOURCE_CLIENT,
                              BUNDLE + " — `u4e`: `castSearchRadius:Math.min(1+Math.floor(i/7),3)`")
TACTICS_INFINITE_KITE_TIER = _c("tactics_infinite_kite_tier", 3, SOURCE_CLIENT, BUNDLE + " — `u4e`: `infiniteKite:o>=3`, o = tier")
# O que uma decisao imperfeita vale face a uma perfeita: nem o cliente nem o guia dizem
# (a IA corre no servidor). Convencao de 16/09/2026 (ordem 7): rende 60 % do dano e apanha
# o dano que a perfeita evitaria (o factor de dano recebido e o simetrico, 1 + 0,4 x imperfeitas).
TACTICS_IMPERFECT_FACTOR = _c("tactics_imperfect_factor", 0.6, SOURCE_CONVENTION,
                              "uma decisao imperfeita da IA rende 60 % do dano de uma perfeita (e apanha o que a perfeita evitaria)",
                              "o Andre pode medir: DPS com e sem ranks de Battle Tactics")
TACTICS_RADIUS_TO_TARGETS = _c("tactics_radius_to_targets", True, SOURCE_CONVENTION,
                               "o `castSearchRadius` (1..3) soma-se ao raio da area para contar os alvos apanhados "
                               "(raio 1 = 3 alvos, 2 = 5, 3+ = o pack); um raio de procura maior encontra a posicao "
                               "que apanha mais bichos")

# --- guia -----------------------------------------------------------------------
ARMOR_DENOMINATOR = _c("armor_denominator", 520, SOURCE_GUIDE, GUIDE_PLANNER + " — `j/(j+520)*100`")
ARMOR_CAP_PCT = _c("armor_cap_pct", 24, SOURCE_GUIDE, GUIDE_PLANNER + " — `W(...,0,24)`")
SHIELD_DENOMINATOR = _c("shield_denominator", 650, SOURCE_GUIDE, GUIDE_PLANNER + " — `M/(M+650)*10`")
SHIELDING_DENOMINATOR = _c("shielding_denominator", 900, SOURCE_GUIDE, GUIDE_PLANNER + " — `shielding/900*10`")
BLOCK_CAP_PCT = _c("block_cap_pct", 18, SOURCE_GUIDE, GUIDE_PLANNER + " — `W(...,0,18)`")
LEECH_EFFECTIVE_FACTOR = _c("leech_effective_factor", 0.55, SOURCE_GUIDE, GUIDE_PLANNER + " — `b*I/100*.55`")
CRIT_BASE_BONUS_PCT = _c("crit_base_bonus_pct", 50, SOURCE_GUIDE, GUIDE_PLANNER + " — `critChance*(50+critDamage)/1e4`",
                         "um critico faz +50 % de dano, mais o `critDmg` da build")
BOSS_HP_MULT = _c("wave10_boss_hp_mult", 3.0, SOURCE_GUIDE, "guiabaiakidle.com/en/wiki/server-data/ (`te=3` no planner)")
BOSS_DMG_MULT = _c("wave10_boss_dmg_mult", 1.5, SOURCE_GUIDE, "guiabaiakidle.com/en/wiki/server-data/ (`z=1.5` no planner)")
BOSS_XP_MULT = _c("wave10_boss_xp_mult", 2.5, SOURCE_GUIDE, "guiabaiakidle.com/en/wiki/server-data/ (`ne=2.5` no planner)")
CYCLE_NORMAL_KILLS = _c("cycle_normal_kills", 57, SOURCE_GUIDE, GUIDE_PLANNER + " — `L=57,R=58`")
GUIDE_DPS_A = _c("guide_dps_curve_a", 7.012, SOURCE_GUIDE, GUIDE_PLANNER + " — `F=7.012,I=.948`",
                 "curva de DPS de referencia do guia, so para validacao cruzada")
GUIDE_DPS_P = _c("guide_dps_curve_p", 0.948, SOURCE_GUIDE, GUIDE_PLANNER + " — `I=.948`")
# Skill «tipico» a um nivel, quando nao se sabe o real. E a suposicao do guia.
SKILL_AT_LEVEL = _c("skill_at_level", {
    "knight": (42, 0.15), "monk": (38, 0.15), "paladin": (42, 0.145),
    "sorcerer": (15, 0.1), "druid": (15, 0.1),
}, SOURCE_GUIDE, GUIDE_PLANNER + " — `42+e.level*.15` (knight), `38+.15` (monk), `42+.145` (paladin), `15+.1` (mages)",
    "skill de arma (ou magic level) esperado a um nivel; o real dele substitui isto")

# --- convencao (nao ha fonte; marcado com aviso na pagina) -------------------------
AUTO_ATTACK_INTERVAL_MS = _c("auto_attack_interval_ms", 2000, SOURCE_CONVENTION,
                             "o cliente divide o dano dos monstros por 2 s (`QO=2e3`, funcao K0e); assume-se o mesmo para o jogador",
                             "intervalo do ataque automatico; `attackSpeedPct` encurta-o")
AUTO_ATTACK_SKILL_FACTOR = _c("auto_attack_skill_factor", 0.085, SOURCE_CONVENTION,
                              "formula do Tibia (TibiaWiki): max = nivel/5 + 0,085 x ataque x skill; min = nivel/5. "
                              "O cliente copia as formulas dos feiticos do Tibia (Brutal Strike e igual), mas nao traz "
                              "a do golpe da arma — e do servidor",
                              "so para o golpe da arma (melee, punho, distancia); wands usam wand_min/max do cliente")
DISTANCE_HIT_CHANCE = _c("distance_hit_chance", 1.0, SOURCE_CONVENTION,
                         "nao ha formula de chance de acerto no cliente nem no guia; conta-se 100 %",
                         "o paladin sai optimista por isto")
AREA_TARGETS = _c("area_targets_by_radius", {None: 3, 1: 3, 2: 5, 3: 7, 4: 9, 5: 9, 6: 9, 7: 9},
                  SOURCE_CONVENTION, "quantos bichos uma magia de area apanha, por raio, limitado ao pack da hunt (`max_vivos`)",
                  "raio 1 = 3 alvos, raio 2 = 5, raio 3+ = o pack inteiro; sem raio (wave/beam) = 3")
CLEAVE_ADJACENT = _c("cleave_adjacent_targets", 2, SOURCE_CONVENTION,
                     "monstros adjacentes ao alvo que um corte (Cleaving Strikes) apanha, limitado ao pack menos 1")
EXECUTE_TIME_SHARE = _c("execute_time_share", 0.25, SOURCE_CONVENTION,
                        "fraccao do tempo em que o alvo esta abaixo de 25 % do HP (Executioner / Culling Shot)")
MANA_REGEN_BASE = _c("mana_regen_base_per_s", None, SOURCE_CONVENTION,
                     "a regeneracao base de mana e do servidor: nao esta no cliente nem no guia. Fica desconhecida "
                     "e a rotacao avalia-se pela mana que gasta e pela autonomia da pool cheia",
                     "desconhecido nao e zero: nao entra em conta nenhuma")
HP_REGEN_BASE = _c("hp_regen_base_per_s", None, SOURCE_CONVENTION,
                   "regeneracao base de vida: do servidor, desconhecida")


# --- feiticos: as formulas do cliente, compiladas a letra -------------------------------
# `xp` e `DO` sao os dois helpers do bundle que as formulas usam:
#   xp=(e,t)=>[Math.max(e[0],t[0]),Math.max(e[1],t[1])]
#   DO=(e,t,a)=>{const n=(e/3+(t+a)*3.5)*1.5;return[n*.75,n]}
def _xp(a, b):
    return [max(a[0], b[0]), max(a[1], b[1])]


def _DO(e, t, a):
    n = (e / 3 + (t + a) * 3.5) * 1.5
    return [n * 0.75, n]


_ALLOWED_NODES = (ast.Expression, ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div,
                  ast.UnaryOp, ast.USub, ast.Constant, ast.Name, ast.Call, ast.List,
                  ast.Tuple, ast.Load)
_ALLOWED_CALLS = {"_xp", "_DO"}
_PARAM_NAMES = ("e", "t", "a", "n", "o", "i")
_ARROW = re.compile(r"^\((?P<params>[^)]*)\)\s*=>\s*(?P<body>.*)$", re.S)
_BLOCK = re.compile(r"^\{const\s+(?P<var>\w+)=(?P<expr>.+?);return(?P<ret>.+)\}$", re.S)
_LEADING_DOT = re.compile(r"(?<![\w.])\.(\d)")


class SpellFormula:
    """Uma formula do cliente (`formula_dano` ou `formula_cura`) tornada funcao.

    `params` diz o que a formula pede: (e,t) e magia — nivel e magic level;
    (e,t,a,n) e fisica — nivel, magic level, skill e ataque da arma;
    (e,t,a) e distancia — nivel, magic level, skill; (e,t,a,n,o,i) e o
    Shield Bash/Slam, com o (defesa do escudo) e i (skill de shielding) —
    esta leitura de o/i e suposicao nossa, o cliente nao lhes chama nada.
    """

    def __init__(self, js):
        self.js = js
        m = _ARROW.match(js.strip())
        if not m:
            raise ValueError("formula nao e uma arrow function: %r" % js)
        params = []
        for p in m.group("params").split(","):
            p = p.strip()
            if not p:
                continue
            name = p.split("=")[0].strip()
            if name not in _PARAM_NAMES:
                raise ValueError("parametro desconhecido %r em %r" % (name, js))
            params.append(name)
        self.params = tuple(params)
        body = m.group("body").strip()
        b = _BLOCK.match(body)
        if b:
            # `{const o=EXPR;return[o*.75,o]}` -> substitui o pela expressao
            var, expr, ret = b.group("var"), b.group("expr"), b.group("ret").strip()
            body = re.sub(r"\b%s\b" % re.escape(var), "(" + expr + ")", ret)
        py = _LEADING_DOT.sub(r"0.\1", body)
        py = py.replace("xp(", "_xp(").replace("DO(", "_DO(")
        tree = ast.parse(py, mode="eval")
        for node in ast.walk(tree):
            if not isinstance(node, _ALLOWED_NODES):
                raise ValueError("token nao permitido %s em %r" % (type(node).__name__, js))
            if isinstance(node, ast.Name) and node.id not in _PARAM_NAMES and node.id not in _ALLOWED_CALLS:
                raise ValueError("nome desconhecido %r em %r" % (node.id, js))
            if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_CALLS):
                raise ValueError("chamada nao permitida em %r" % js)
        self.python = py
        self._code = compile(tree, "<formula %s>" % js[:30], "eval")

    @property
    def kind(self):
        if self.params == ("e", "t"):
            return "magic"
        if self.params == ("e", "t", "a"):
            return "distance"
        if self.params == ("e", "t", "a", "n"):
            return "physical"
        return "shield"

    def __call__(self, level, magic_level=0, skill=0, attack=0, shield_def=0, shielding=0):
        env = {"e": level, "t": magic_level, "a": skill, "n": attack, "o": shield_def, "i": shielding,
               "_xp": _xp, "_DO": _DO}
        lo, hi = eval(self._code, {"__builtins__": {}}, env)  # noqa: S307 - AST validada acima
        return float(lo), float(hi)

    def average(self, *args, **kw):
        lo, hi = self(*args, **kw)
        return (lo + hi) / 2.0


_FORMULA_CACHE = {}


def compile_formula(js):
    f = _FORMULA_CACHE.get(js)
    if f is None:
        f = _FORMULA_CACHE[js] = SpellFormula(js)
    return f


# O elemento de um feitico vem das palavras (o cliente nao o escreve): vis=energia,
# flam=fogo, tera/pox=terra, frigo=gelo, san=sagrado, mort=morte; o resto e fisico.
_WORD_ELEMENT = (("vis", "energy"), ("flam", "fire"), ("tera", "earth"), ("pox", "earth"),
                 ("frigo", "ice"), ("san", "holy"), ("mort", "death"))


def spell_element(words):
    tokens = set((words or "").split())
    for word, element in _WORD_ELEMENT:
        if word in tokens:
            return element
    return "physical"


# --- personagem ---------------------------------------------------------------------------
def max_hp(vocation, level, hp_pct=0.0, hp_flat=0.0):
    """HP maximo: base do guia + crescimento por nivel do cliente, x (1 + hpPct)."""
    growth = VOCATION_GROWTH[vocation]["hp_per_level"]
    return (HP_BASE + growth * level + hp_flat) * (1 + hp_pct / 100.0)


def max_mana(vocation, level, mana_pct=0.0, mana_flat=0.0):
    growth = VOCATION_GROWTH[vocation]["mana_per_level"]
    return (MANA_BASE + growth * level + mana_flat) * (1 + mana_pct / 100.0)


def typical_skill(vocation, level):
    """Skill de arma (magic level para mages) que o guia assume a um nivel."""
    base, per_level = SKILL_AT_LEVEL[vocation]
    return base + per_level * level


def weapon_attack(item_atk, up_level=0, atk_pct=0.0):
    """Ataque efectivo da arma: (6 + atk) x (1 + upgrade% + atkPct%). Cliente: B1e e l5."""
    return (WEAPON_BASE_ATTACK + (item_atk or 0)) * (1 + (up_level * UPGRADE_WEAPON_ATK_PCT + atk_pct) / 100.0)


def ammo_attack(ammo_name, ammo_atk):
    factor = AMMO_ATTACK_FACTOR_SPECIAL.get((ammo_name or "").lower(), AMMO_ATTACK_FACTOR)
    return round((ammo_atk or 0) * factor)


def auto_attack_range(level, skill, attack):
    """[min, max] do golpe da arma — CONVENCAO (formula do Tibia), ver AUTO_ATTACK_SKILL_FACTOR."""
    lo = level / 5.0
    return lo, lo + AUTO_ATTACK_SKILL_FACTOR * attack * skill


def ds(a, b):
    """Empilhar duas absorcoes em %: a + b - a*b/100. Cliente: `ds=(e,t)=>e+t-e*t/100`."""
    return a + b - a * b / 100.0


def stack_pct(values):
    """Varias reducoes em % empilhadas multiplicativamente (o G do guia; igual ao ds do cliente)."""
    total = 0.0
    for v in values:
        if v:
            total = ds(total, v)
    return total


def armor_reduction_pct(armor):
    """Reducao do dano fisico pela armadura: armor/(armor+520) x 100, tecto 24 %. Guia."""
    if armor <= 0:
        return 0.0
    return min(ARMOR_CAP_PCT, armor / (armor + ARMOR_DENOMINATOR) * 100.0)


def block_pct(shield_def, shielding_skill=0.0, has_shield=True):
    """Bloqueio de escudo: def/(def+650) x 10 + shielding/900 x 10, tecto 18 %. Guia.
    So com escudo (o guia so o aplica a `hasShield`)."""
    if not has_shield:
        return 0.0
    raw = 0.0
    if shield_def > 0:
        raw += shield_def / (shield_def + SHIELD_DENOMINATOR) * 10.0
    raw += shielding_skill / SHIELDING_DENOMINATOR * 10.0
    return min(BLOCK_CAP_PCT, max(0.0, raw))


def crit_multiplier(crit_chance_pct, crit_dmg_pct):
    """Dano esperado com criticos: 1 + chance x (50 + critDmg)/10000. Guia."""
    return 1.0 + max(0.0, crit_chance_pct) * max(0.0, CRIT_BASE_BONUS_PCT + crit_dmg_pct) / 10000.0


def resist_factor(resist_pct, pierce_pct=0.0):
    """Quanto do dano passa por uma resistencia (%): 1 - r/100, nunca abaixo de 0.
    `pierce` (Ballistic Mastery) ignora essa fraccao da resistencia positiva."""
    r = resist_pct or 0.0
    if pierce_pct and r > 0:
        r = r * (1 - pierce_pct / 100.0)
    return max(0.0, 1.0 - min(100.0, r) / 100.0)


def prey_bonus_pct(kind, stars):
    """Bonus do prey por estrelas. Cliente `rye`: dmg 2s+5, def 2s+10, xp/loot 3s+10."""
    s = max(1, min(PREY_STARS_MAX, int(round(stars))))
    if kind == "dmg":
        return 2 * s + 5
    if kind == "def":
        return 2 * s + 10
    return 3 * s + 10


# --- arvore -----------------------------------------------------------------------------
def tree_rank_cost(node, current_rank):
    """Custo do proximo rank. Cliente `Ik`: small = cost x (rank+1); notable = cost."""
    if node.get("tipo") == "small":
        return node["custo_por_rank"] * (current_rank + 1)
    return node["custo_por_rank"]


def tree_total_cost(node, rank):
    """Custo do zero ao rank. Cliente `z3e`: small = cost x r x (r+1)/2."""
    r = max(0, min(rank, node.get("rank_maximo") or 1))
    if node.get("tipo") == "small":
        return node["custo_por_rank"] * r * (r + 1) // 2
    return node["custo_por_rank"] if r > 0 else 0


def tree_budget(level):
    """Pontos de arvore que um nivel da: o proprio nivel. Cliente `yD(..., a.level)`."""
    return int(level) * TREE_POINTS_PER_LEVEL


def tree_respec_gold(points_spent):
    return TREE_RESPEC_BASE + TREE_RESPEC_PER_POINT * points_spent if points_spent > 0 else 0


def area_targets(radius, pack, search_radius=1):
    """Quantos bichos uma magia de area apanha — CONVENCAO, limitada ao pack.
    `search_radius` e o `castSearchRadius` da IA (1..3): acima de 1 soma-se ao
    raio (TACTICS_RADIUS_TO_TARGETS); sem raio (wave/beam) conta como raio 1."""
    extra = max(0, int(search_radius or 1) - 1) if TACTICS_RADIUS_TO_TARGETS else 0
    if radius is None and not extra:
        n = AREA_TARGETS[None]
    else:
        r = (1 if radius is None else int(radius)) + extra
        n = 9 if r >= 3 else AREA_TARGETS[r]
    return max(1, min(int(pack or 1), n))


def battle_tactics(level, ranks=0):
    """A IA de combate, cliente `u4e(level, ranks)` a letra: tier, qp, chance de
    decisao perfeita (`aim_chance`), raio de procura dos casts, intervalo minimo
    de reposicionamento e kite infinito."""
    a = math.floor(max(0, level) / 100)
    n = max(0, int(ranks or 0))
    tier = a + n
    qp = min(10, a * TACTICS_QP_PER_LEVEL_TIER) + min(TACTICS_QP_RANK_CAP, n)
    return {"tier": tier, "qp": qp,
            "aim_chance": min(1.0, TACTICS_AIM_BASE + TACTICS_AIM_PER_QP * qp),
            "cast_search_radius": min(1 + math.floor(qp / TACTICS_SEARCH_RADIUS_QP), 3),
            "reposition_min_ms": max(4000, 5000 - 50 * qp),
            "infinite_kite": tier >= TACTICS_INFINITE_KITE_TIER}


def tactics_quality(aim_chance):
    """Factor da IA sobre o dano: perfeita rende 1, imperfeita TACTICS_IMPERFECT_FACTOR (convencao)."""
    return aim_chance + (1.0 - aim_chance) * TACTICS_IMPERFECT_FACTOR


def tactics_taken(aim_chance):
    """Factor da IA sobre o dano recebido (convencao, simetrico): 1 + (1 - factor) x imperfeitas."""
    return 1.0 + (1.0 - aim_chance) * (1.0 - TACTICS_IMPERFECT_FACTOR)


def best_potion(potions, vocation, level):
    """A pocao mais forte que a vocacao pode beber ao nivel (a lista do cliente)."""
    allowed = [p for p in potions if p["min_level"] <= level and (not p.get("vocs") or vocation in p["vocs"])]
    if not allowed:
        return None
    return max(allowed, key=lambda p: (p.get("heal") or 0) + (p.get("mana") or 0))


def guide_reference_dps(level):
    """A curva do guia, so para comparar: 7.012 x nivel^0.948 (sem factores)."""
    return GUIDE_DPS_A * max(1, level) ** GUIDE_DPS_P


def clamp(x, lo, hi):
    return min(hi, max(lo, x))


def fmt_source(source):
    return {SOURCE_CLIENT: "cliente", SOURCE_GUIDE: "guia", SOURCE_CHANNEL: "canal",
            SOURCE_CONVENTION: "convencao"}.get(source, source)
