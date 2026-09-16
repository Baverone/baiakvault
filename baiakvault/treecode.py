"""O codigo de build do cliente («Exportar» / «Colar codigo para importar…») e as
regras da arvore, transcritos a letra do bundle publico do jogo
(`index-DnzxFejS.js`, 09/09/2026; lido na ordem 8, 16/09/2026).

O codigo e texto que o Andre copia do proprio cliente e cola no BaiakVault, ou o
contrario — e a fonte mais exacta que ha da arvore dele, sem capturas e sem
tocar no jogo. Nada aqui fala com o baiakidle.com.

Funcoes do cliente e o nome aqui:

- `IK(voc)`   -> `ordered_nodes`: os nos da vocacao por `id` (ordem de string do JS)
- `V3e`       -> `encode(voc, level, ranks)`: `BT1-<K|P|S|D|M><nivel|F>-<hex>`
- `U3e`       -> `decode(code)`: `(voc, nivel ou None, ranks)`; `None` se invalido
- `MK`        -> `adjacency`: `requires` liga pai->filho E filho->pai
- `LK`        -> `connected`: flood a partir dos nos de tier 0 com rank >= 1
- `O3e`       -> `is_connected`: todos os nos com rank >= 1 estao em `connected`
- `D3e`       -> `count_active`
- `Ik`        -> `next_rank_cost`; `z3e` -> `node_cost`; `Up` -> `points_spent`
- `yD`        -> `can_add_rank`: rank < max; tier 0 ou um vizinho com rank >= 1; cabe no nivel
- `F3e`       -> `refund_rank_cost`: tirar o ultimo rank so se a arvore continuar ligada
- `j3e`       -> `sanitize`: deita fora nos desconhecidos/zero e os que nao ligam ao tier 0
- `fD`        -> `import_cost`: 0 se 0 pontos gastos, senao 1000 + 200 x pontos (= Reset All)

O handler de «Carregar» do cliente (a seguir a `U3e` no bundle) faz, por esta
ordem: `decode`; vocacao igual a do personagem; `sanitize`; `points_spent <= level`;
«ja e a tua build»; gold >= `import_cost(pontos gastos AGORA)`; confirmacao
«Importar esta build vai SUBSTITUIR a sua atual e custar {cost} gold».
`validate_import` faz as tres verificacoes do meio e devolve a arvore limpa.
"""
import math
import re

VOCATION_LETTER = {"knight": "K", "paladin": "P", "sorcerer": "S", "druid": "D", "monk": "M"}   # H3e
LETTER_VOCATION = {v: k for k, v in VOCATION_LETTER.items()}                                      # G3e
_CODE_RE = re.compile(r"^BT1-([KPSDM])(F|\d{1,7})-([0-9A-F]*)$")
IMPORT_BASE_GOLD = 1000    # B3e
IMPORT_PER_POINT_GOLD = 200   # $3e
REFUND_PER_POINT_GOLD = 400   # R3e (gD): devolver um rank custa 400 x pontos do rank


class TreeCodeError(ValueError):
    pass


# --- os nos ---------------------------------------------------------------------------------------
def _nodes(cat, vocation):
    tree = cat.tree_by_vocation.get(vocation)
    if not tree:
        raise TreeCodeError("vocacao desconhecida: %r" % vocation)
    return tree["nos"]


def ordered_nodes(cat, vocation):
    """`IK`: os nos por `id` — o `<`/`>` do JS compara por code point, o mesmo que a
    ordenacao de strings do Python para estes ids ASCII."""
    return sorted(_nodes(cat, vocation), key=lambda n: n["id"])


def _max_rank(node):
    return node.get("rank_maximo") or 1


# --- codigo ---------------------------------------------------------------------------------------
def encode(cat, vocation, level, ranks):
    """`V3e(voc, level, ranks)`: um digito hexadecimal por no na ordem de `IK`, sem os
    zeros finais, em maiusculas; nivel «F» se nulo."""
    ranks = ranks or {}
    digits = "".join(format(min(max(0, int(ranks.get(n["id"], 0) or 0)), _max_rank(n)), "x")
                     for n in ordered_nodes(cat, vocation))
    digits = re.sub(r"0+$", "", digits)
    lv = "F" if level is None else str(max(1, int(math.floor(level))))
    return "BT1-%s%s-%s" % (VOCATION_LETTER[vocation], lv, digits.upper())


def decode(cat, code):
    """`U3e(code)`: `(vocacao, nivel ou None, {no: rank})`, ou `None` se o codigo nao
    bate no formato. Digitos a mais ignoram-se, a menos valem 0; cada digito fica em
    `min(digito, rank maximo)` e os zeros nao entram."""
    m = _CODE_RE.match(str(code or "").strip().upper())
    if not m:
        return None
    vocation = LETTER_VOCATION.get(m.group(1))
    if not vocation:
        return None
    level = None if m.group(2) == "F" else (int(m.group(2)) or None)   # `Number.parseInt(...) || null`
    digits = m.group(3)
    ranks = {}
    for node, d in zip(ordered_nodes(cat, vocation), digits):
        value = int(d, 16)
        if value > 0:
            ranks[node["id"]] = min(value, _max_rank(node))
    return vocation, level, ranks


# --- regras da arvore -----------------------------------------------------------------------------
def adjacency(cat, vocation):
    """`MK`: {id: [vizinhos]} — cada `requires` liga nos dois sentidos."""
    adj = {n["id"]: [] for n in _nodes(cat, vocation)}
    for n in _nodes(cat, vocation):
        for req in n.get("requer") or []:
            adj[n["id"]].append(req)
            if req in adj:
                adj[req].append(n["id"])
    return adj


def connected(cat, vocation, ranks):
    """`LK`: os nos (rank >= 1) alcancaveis a partir dos de tier 0 com rank >= 1,
    so por vizinhos com rank >= 1."""
    adj = adjacency(cat, vocation)
    seen = set()
    stack = []
    for n in _nodes(cat, vocation):
        if n.get("tier", 0) == 0 and (ranks.get(n["id"], 0) or 0) >= 1:
            seen.add(n["id"])
            stack.append(n["id"])
    while stack:
        nid = stack.pop()
        for v in adj.get(nid, ()):
            if v not in seen and (ranks.get(v, 0) or 0) >= 1:
                seen.add(v)
                stack.append(v)
    return seen


def count_active(cat, vocation, ranks):
    """`D3e`: quantos nos tem rank >= 1."""
    return sum(1 for n in _nodes(cat, vocation) if (ranks.get(n["id"], 0) or 0) >= 1)


def is_connected(cat, vocation, ranks):
    """`O3e`: todos os nos com rank >= 1 ligam ao tier 0."""
    return len(connected(cat, vocation, ranks)) == count_active(cat, vocation, ranks)


def next_rank_cost(node, rank):
    """`Ik`: o proximo rank de um small custa `cost x (rank + 1)`; um notable `cost`."""
    if node.get("tipo") == "small":
        return node["custo_por_rank"] * (rank + 1)
    return node["custo_por_rank"]


def node_cost(node, rank):
    """`z3e`: do zero ao rank — small `cost x r(r+1)/2`; notable `cost` se r > 0."""
    r = min(max(0, int(rank or 0)), _max_rank(node))
    if node.get("tipo") == "small":
        return node["custo_por_rank"] * r * (r + 1) // 2
    return node["custo_por_rank"] if r > 0 else 0


def points_spent(cat, vocation, ranks):
    """`Up`: os pontos gastos na arvore (nos desconhecidos nao contam, como no cliente)."""
    by_id = {n["id"]: n for n in _nodes(cat, vocation)}
    return sum(node_cost(by_id[k], r) for k, r in (ranks or {}).items() if k in by_id and (r or 0) > 0)


def can_add_rank(cat, vocation, ranks, node_id, level):
    """`yD`: pode-se por um ponto em `node_id`? rank < maximo; tier 0 ou QUALQUER
    vizinho de `MK` com rank >= 1; e `Up + Ik <= level`."""
    by_id = {n["id"]: n for n in _nodes(cat, vocation)}
    node = by_id.get(node_id)
    if not node:
        return False
    rank = ranks.get(node_id, 0) or 0
    if rank >= _max_rank(node):
        return False
    if node.get("tier", 0) > 0 and not any((ranks.get(v, 0) or 0) >= 1 for v in adjacency(cat, vocation)[node_id]):
        return False
    return points_spent(cat, vocation, ranks) + next_rank_cost(node, rank) <= level


def refund_rank_cost(cat, vocation, ranks, node_id):
    """`F3e`: os pontos que tirar o ultimo rank devolve, ou `None` se nao se pode
    (sem rank, ou a arvore deixava de estar ligada)."""
    by_id = {n["id"]: n for n in _nodes(cat, vocation)}
    node = by_id.get(node_id)
    if not node:
        return None
    rank = ranks.get(node_id, 0) or 0
    if rank < 1:
        return None
    if rank == 1:
        trial = dict(ranks)
        trial[node_id] = 0
        if not is_connected(cat, vocation, trial):
            return None
    return next_rank_cost(node, rank - 1)


def sanitize(cat, vocation, ranks):
    """`j3e`: so nos conhecidos com rank > 0 (ao maximo), e destes so os que ligam ao
    tier 0 — o resto cai em silencio, como no cliente."""
    by_id = {n["id"]: n for n in _nodes(cat, vocation)}
    out = {}
    for k, v in (ranks or {}).items():
        node = by_id.get(k)
        if not node or not isinstance(v, (int, float)) or v <= 0:
            continue
        out[k] = min(int(math.floor(v)), _max_rank(node))
    keep = connected(cat, vocation, out)
    return {k: v for k, v in out.items() if k in keep}


def import_cost(points_spent_now):
    """`fD`: o gold que importar (ou o Reset All) custa, pelos pontos gastos AGORA."""
    return 0 if points_spent_now <= 0 else IMPORT_BASE_GOLD + IMPORT_PER_POINT_GOLD * int(points_spent_now)


def refund_cost(points_of_rank):
    """`gD`: devolver um rank custa 400 x os pontos desse rank."""
    return REFUND_PER_POINT_GOLD * int(points_of_rank)


def validate_import(cat, vocation, level, code):
    """As verificacoes do handler de «Carregar» que nao dependem do gold: o codigo e
    valido, e da vocacao, e a arvore limpa (`sanitize`) cabe no nivel. Devolve
    `(ranks limpos, nivel do codigo, o que caiu no sanitize)`; `TreeCodeError` com a
    frase do cliente quando nao passa."""
    decoded = decode(cat, code)
    if decoded is None:
        raise TreeCodeError("Codigo invalido.")
    code_voc, code_level, ranks = decoded
    if code_voc != vocation:
        raise TreeCodeError("Essa build e de %s — nao da tua vocacao (%s)." % (code_voc, vocation))
    clean = sanitize(cat, vocation, ranks)
    dropped = sorted(k for k in ranks if k not in clean)
    needed = points_spent(cat, vocation, clean)
    if level is not None and needed > level:
        raise TreeCodeError("Essa build precisa de nivel %d (tens %d)." % (needed, level))
    return clean, code_level, dropped


def purchase_order_is_clickable(cat, vocation, steps, level=None):
    """A ordem de compra e clicavel a mao: cada passo `(no, rank)` passa `yD` no estado
    em que entra (com o orcamento = pontos gastos + o custo do passo quando `level`
    nao vem). Devolve o primeiro passo que falha, ou `None`."""
    by_id = {n["id"]: n for n in _nodes(cat, vocation)}
    state = {}
    for nid, rank in steps:
        node = by_id.get(nid)
        if node is None or (state.get(nid, 0) or 0) != rank - 1:
            return (nid, rank)
        budget = level if level is not None else points_spent(cat, vocation, state) + next_rank_cost(node, rank - 1)
        if not can_add_rank(cat, vocation, state, nid, budget):
            return (nid, rank)
        state[nid] = rank
    return None
