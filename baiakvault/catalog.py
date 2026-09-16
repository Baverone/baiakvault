"""O catalogo do jogo: os JSON de `data/catalogo/`, lidos do disco e indexados.

Vem tudo do bundle publico do cliente do jogo, extraido no ai-pc a 09/09/2026
(ver `scripts/actualizar_catalogo.py`). **Este modulo nao vai a rede** — le
ficheiros locais e mais nada. A regra da casa e que o BaiakVault nunca fala
com o `baiakidle.com`.

As chaves que o resto do projecto usa (e que a `vault.db` valida ao escrever):

- hunt        -> `id` do `hunts.json` (ex. `troll-cave`)
- criatura    -> `chave` do `bestiario.json` (ex. `swamp_troll`)
- charm       -> `key` do `bestiario.json`/`charms` (ex. `wound`)
- no da arvore-> `id` do `arvore.json` (ex. `k_fury`)
- item        -> `nome` do `itens.json` em minusculas (nao ha outra chave)
- vocacao     -> `vocacao` do `vocacoes.json` (`knight`, `monk`, ...)

O que a fonte nao da fica `None`; nunca se substitui por zero nem por media.
"""
import json
import re
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "catalogo"

FILES = ("hunts", "bestiario", "itens", "bosses", "arvore", "vocacoes",
         "ac", "rotacao")
# Os brutos que o site precisa alem dos derivados: os charms, e as arvores tal
# como estao no cliente — o `arvore.json` derivado perdeu `special`/`desc`
# (Battle Tactics, Cleaving Strikes, Executioner, Avatar...), que o motor das
# builds precisa (16/09/2026).
RAW_FILES = ("charms", "arvore_knight", "arvore_paladin", "arvore_sorcerer",
             "arvore_druid", "arvore_monk", "constantes", "feiticos")

# As contagens que o catalogo de 09/09/2026 tem. `validate` chumba se mudarem,
# de proposito: uma actualizacao do jogo deve ser vista, nao absorvida em
# silencio (e ai actualiza-se isto com data).
EXPECTED = {
    "hunts": 79, "creatures": 356, "charms": 24, "tree_nodes": 203,
    "vocations": 5, "items": 2902, "room_bosses": 386, "wave10_bosses": 61,
    "spells": 187,
}

VOCATIONS = ("knight", "monk", "paladin", "sorcerer", "druid")

# Como o Andre escreve a vocacao vs. como o cliente a escreve.
_VOCATION_ALIAS = {
    "ek": "knight", "knight": "knight", "elite knight": "knight",
    "cavaleiro": "knight",
    "rp": "paladin", "paladin": "paladin", "royal paladin": "paladin",
    "ms": "sorcerer", "sorcerer": "sorcerer", "master sorcerer": "sorcerer",
    "ed": "druid", "druid": "druid", "elder druid": "druid",
    "monk": "monk", "exalted monk": "monk", "monge": "monk",
}

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_vocation(text):
    """'EK' -> 'knight'. `None` quando nao se reconhece — nunca um palpite."""
    if not text:
        return None
    return _VOCATION_ALIAS.get(str(text).strip().lower())


class CatalogError(Exception):
    pass


class Catalog:
    """Os oito ficheiros mais o bruto dos charms, com indices por chave."""

    def __init__(self, raw, raw_charms, directory, raw_extra=None):
        self.directory = Path(directory)
        self.raw = raw
        self.raw_charms = raw_charms
        self.raw_extra = raw_extra or {}
        self.hunts = list(raw["hunts"].get("hunts") or [])
        self.creatures = list(raw["bestiario"].get("criaturas") or [])
        self.charms = list(raw["bestiario"].get("charms") or [])
        self.items = list(raw["itens"].get("itens") or [])
        self.room_bosses = list(raw["bosses"].get("bosses_de_sala") or [])
        self.wave10_bosses = list(raw["bosses"].get("bosses_de_wave_10") or [])
        self.trees = list(raw["arvore"].get("arvores") or [])
        self.vocations = list(raw["vocacoes"].get("vocacoes") or [])
        self.missions = list(raw["ac"].get("missoes") or [])
        self.rotation = list(raw["rotacao"].get("opcoes") or [])

        self.hunt_by_id = {h["id"]: h for h in self.hunts}
        self.hunt_by_name = {h["nome"].lower(): h for h in self.hunts}
        self.creature_by_key = {c["chave"]: c for c in self.creatures}
        self.creature_by_name = {c["nome"].lower(): c for c in self.creatures}
        self.charm_by_key = {c["key"]: c for c in self.charms}
        self.item_by_key = {i["nome"].lower(): i for i in self.items}
        self.tree_by_vocation = {t["vocacao"]: t for t in self.trees}
        self.node_by_id = {n["id"]: n for t in self.trees for n in (t.get("nos") or [])}
        self.node_vocation = {n["id"]: t["vocacao"]
                              for t in self.trees for n in (t.get("nos") or [])}
        self.vocation_by_name = {v["vocacao"]: v for v in self.vocations}
        self.wave10_by_hunt = {b["hunt"]: b for b in self.wave10_bosses if b.get("hunt")}
        self.equippable = [i for i in self.items if i.get("slot")]
        self.slots = sorted({i["slot"] for i in self.equippable})

        # `special`/`desc` dos nos vem do bruto (o derivado nao os tem). Ficam
        # colados ao no derivado como `especial` e `descricao` — None quando o
        # bruto nao esta (o catalogo continua a servir, so sem os especiais).
        for voc in VOCATIONS:
            raw_tree = (self.raw_extra.get("arvore_" + voc) or {}).get("dados") or {}
            for rn in raw_tree.get("nodes") or []:
                node = self.node_by_id.get(rn.get("id"))
                if node is not None:
                    node["especial"] = rn.get("special")
                    node["descricao"] = rn.get("desc")
        self.constants = ((self.raw_extra.get("constantes") or {}).get("dados") or {})

        # O mesmo para os feiticos: o derivado nao traz `goldCost` (runas),
        # `healTarget` (cura aliada), `chain`, `promo` — colam-se aqui por
        # `palavras`, como `custo_gold`, `alvo_da_cura`, `cadeia`, `promocao`.
        raw_spells = {s.get("words"): s for s in ((self.raw_extra.get("feiticos") or {}).get("dados") or [])}
        self.spells_by_words = {}
        for v in self.vocations:
            for s in v.get("feiticos") or []:
                rs = raw_spells.get(s.get("palavras")) or {}
                s["custo_gold"] = rs.get("goldCost")
                s["alvo_da_cura"] = rs.get("healTarget")
                s["cadeia"] = rs.get("chain")
                s["promocao"] = bool(rs.get("promo"))
                s["vocacao"] = v["vocacao"]
                self.spells_by_words.setdefault(s["palavras"], s)

    def meta(self, name):
        return (self.raw.get(name) or {}).get("_meta") or {}

    def source_of(self, name):
        """A fonte declarada num ficheiro, para ir para a pagina."""
        return self.meta(name).get("fonte") or "?"

    def seen_at(self, name="hunts"):
        return self.meta(name).get("visto_em")

    def counts(self):
        return {
            "hunts": len(self.hunts),
            "creatures": len(self.creatures),
            "charms": len(self.charms),
            "tree_nodes": len(self.node_by_id),
            "vocations": len(self.vocations),
            "items": len(self.items),
            "room_bosses": len(self.room_bosses),
            "wave10_bosses": len(self.wave10_bosses),
            "spells": sum(len(v.get("feiticos") or []) for v in self.vocations),
        }

    # --- perguntas que a BD faz ao escrever -----------------------------------
    def has_hunt(self, hunt_id):
        return hunt_id in self.hunt_by_id

    def has_creature(self, key):
        return key in self.creature_by_key

    def has_charm(self, key):
        return key in self.charm_by_key

    def has_node(self, node_id, vocation=None):
        if node_id not in self.node_by_id:
            return False
        return vocation is None or self.node_vocation[node_id] == vocation

    def has_item(self, key):
        return key in self.item_by_key

    def has_slot(self, slot):
        return slot in self.slots

    def item_name(self, key):
        item = self.item_by_key.get(key)
        return item["nome"] if item else None

    # --- resistencias: bestiario primeiro, depois a 2.a tabela de combate do cliente ------------
    ELEMENTS = ("physical", "energy", "earth", "fire", "ice", "holy", "death")
    RESIST_FALLBACK = "tabela de combate ⚠"

    def resistances(self, creature):
        """({elemento: %} ou None, fonte). O `bestiario.json` (tabela `Et`) nao declara
        resistencias para 154 dos 240 monstros de hunt (159 das 250 entradas, porque
        alguns aparecem em mais de uma hunt); para esses le-se a tabela `Wy`
        do cliente (`bosses_de_sala`, que tem os 386 monstros) e marca-se ⚠ — as duas
        divergem em 33 dos 86 que tem ambas. Sem nenhuma: (None, None), nunca zero.
        E a mesma leitura para o simulador e para os charms (16/09/2026: ate aqui o
        simulador contava estes 159 a 0 %)."""
        res = creature.get("resistencias")
        if res:
            return {el: (res.get(el) or 0) for el in self.ELEMENTS}, "bestiario"
        if not hasattr(self, "_combat_by_name"):
            self._combat_by_name = {b["nome"].lower(): b for b in self.room_bosses if b.get("nome")}
        alt = self._combat_by_name.get((creature.get("nome") or "").lower())
        if alt and alt.get("resistencias") is not None:
            return {el: (alt["resistencias"].get(el) or 0) for el in self.ELEMENTS}, self.RESIST_FALLBACK
        return None, None


def load(directory=None):
    """Le os ficheiros. Falha alto se faltar um: meia verdade engana."""
    directory = Path(directory or DEFAULT_DIR)
    raw = {}
    for name in FILES:
        path = directory / (name + ".json")
        if not path.is_file():
            raise CatalogError("falta o ficheiro do catalogo: %s" % path)
        try:
            raw[name] = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as e:
            raise CatalogError("JSON invalido em %s: %s" % (path, e))
    raw_charms = None
    raw_extra = {}
    for name in RAW_FILES:
        path = directory / "bruto" / (name + ".json")
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as e:
            raise CatalogError("JSON invalido em %s: %s" % (path, e))
        if name == "charms":
            raw_charms = data
        else:
            raw_extra[name] = data
    return Catalog(raw, raw_charms, directory, raw_extra)


def validate(cat):
    """Lista de problemas (vazia = valido). E o que `check` e os testes usam."""
    problems = []
    counts = cat.counts()
    for key, expected in EXPECTED.items():
        if counts.get(key) != expected:
            problems.append("%s: esperava %d, ha %s" % (key, expected, counts.get(key)))

    def unique(label, keys):
        seen, dup = set(), set()
        for k in keys:
            if not k:
                problems.append("%s: chave vazia" % label)
            elif k in seen:
                dup.add(k)
            seen.add(k)
        for d in sorted(dup):
            problems.append("%s: chave repetida %r" % (label, d))

    unique("hunts.id", [h.get("id") for h in cat.hunts])
    unique("hunts.nome", [(h.get("nome") or "").lower() for h in cat.hunts])
    unique("criaturas.chave", [c.get("chave") for c in cat.creatures])
    unique("charms.key", [c.get("key") for c in cat.charms])
    unique("arvore.id", [n.get("id") for t in cat.trees for n in (t.get("nos") or [])])
    unique("itens.nome", [(i.get("nome") or "").lower() for i in cat.items])
    unique("vocacoes", [v.get("vocacao") for v in cat.vocations])

    for h in cat.hunts:
        if not _SLUG.match(h.get("id") or ""):
            problems.append("hunt %r: id nao serve de nome de ficheiro" % h.get("id"))
        for m in h.get("monstros") or []:
            if m.get("chave") not in cat.creature_by_key:
                problems.append("hunt %s: monstro %r nao esta no bestiario" % (h["id"], m.get("chave")))
        boss = h.get("boss_da_wave_10")
        if boss and boss.get("chave") not in cat.creature_by_key:
            problems.append("hunt %s: boss %r nao esta no bestiario" % (h["id"], boss.get("chave")))
    for b in cat.wave10_bosses:
        if b.get("hunt") not in cat.hunt_by_id:
            problems.append("boss de wave 10 %r: hunt %r desconhecida" % (b.get("nome"), b.get("hunt")))
    for c in cat.charms:
        for field in ("chance", "points"):
            vals = c.get(field)
            if not isinstance(vals, list) or len(vals) != 3:
                problems.append("charm %s: %s nao tem 3 tiers" % (c.get("key"), field))
        if c.get("category") not in ("major", "minor"):
            problems.append("charm %s: categoria %r" % (c.get("key"), c.get("category")))
    for t in cat.trees:
        if t.get("vocacao") not in VOCATIONS:
            problems.append("arvore: vocacao %r desconhecida" % t.get("vocacao"))
        for n in t.get("nos") or []:
            for req in n.get("requer") or []:
                if req not in cat.node_by_id:
                    problems.append("no %s requer %r que nao existe" % (n.get("id"), req))
    for v in cat.vocations:
        if v.get("vocacao") not in VOCATIONS:
            problems.append("vocacao %r desconhecida" % v.get("vocacao"))
    if cat.raw_charms is None:
        problems.append("falta bruto/charms.json")
    elif len((cat.raw_charms or {}).get("dados") or []) != len(cat.charms):
        problems.append("bruto/charms.json nao bate com os charms do bestiario")
    for name in RAW_FILES:
        if name == "charms":
            continue
        if name not in cat.raw_extra:
            problems.append("falta bruto/%s.json" % name)
        elif name.startswith("arvore_"):
            raw_ids = {n.get("id") for n in (cat.raw_extra[name].get("dados") or {}).get("nodes") or []}
            derived_ids = {n["id"] for n in (cat.tree_by_vocation.get(name[7:]) or {}).get("nos") or []}
            if raw_ids != derived_ids:
                problems.append("bruto/%s.json nao bate com a arvore derivada" % name)
        elif name == "feiticos":
            raw_words = {s.get("words") for s in (cat.raw_extra[name].get("dados") or [])}
            derived_words = {s.get("palavras") for v in cat.vocations for s in (v.get("feiticos") or [])}
            if not derived_words <= raw_words:
                problems.append("bruto/feiticos.json nao cobre os feiticos derivados: %s"
                                % sorted(derived_words - raw_words)[:5])
    return problems
