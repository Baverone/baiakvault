"""A `vault.db`: esquema, migracoes por versao e o unico sitio que la escreve.

Duas regras que atravessam tudo:

- **Chave desconhecida e erro.** Um `node_key`, `item_key`, `charm_key`,
  `creature_key` ou `hunt` que nao esteja no catalogo levanta `VaultError`
  antes de tocar na BD. Nada entra «para depois ver».
- **Desconhecido nao e zero.** Os campos opcionais ficam `NULL` quando nao
  se sabem; a pagina mostra «?» e nenhuma conta os usa.

As migracoes sao uma lista de scripts SQL por versao, aplicadas por
`PRAGMA user_version`. A v1 e `schema.sql` inteiro; as seguintes acrescentam-se
a `MIGRATIONS` sem mexer nas anteriores.
"""
import json
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

from . import catalog as catalog_module

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "vault.db"
SOURCES = ("manual", "captura")
# Os objectivos que o Andre pediu, por vocacao (16/09/2026); o primeiro de cada
# lista e o que ele nomeou primeiro e serve de omissao quando o goal esta NULL.
GOALS_BY_VOCATION = {"knight": ("tank", "damage"), "druid": ("heal", "damage"),
                     "sorcerer": ("damage",), "paladin": ("damage",), "monk": ("support", "damage")}
GOALS = ("damage", "tank", "heal", "support")
# O catalogo so da slot aos itens que o cliente marca como equipaveis; mochila
# e municao nao tem slot la mas existem no boneco (decisao 16/09/2026).
EXTRA_SLOTS = ("backpack", "ammo")

_SCHEMA_V1 = (Path(__file__).resolve().parent / "schema.sql").read_text(encoding="utf-8")
# v2 (16/09/2026): o objectivo passa a ser por vocacao (heal/support em vez de
# «sustain»). O SQLite nao altera um CHECK, por isso a tabela reconstroi-se; o
# `sustain` antigo mapeia-se para o objectivo de omissao da vocacao.
_SCHEMA_V2 = """
CREATE TABLE characters_v2 (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    slug         TEXT NOT NULL UNIQUE,
    vocation     TEXT CHECK (vocation IN ('knight','monk','paladin','sorcerer','druid')),
    level        INTEGER CHECK (level IS NULL OR level >= 1),
    current_hunt TEXT,
    vip          INTEGER CHECK (vip IN (0, 1)),
    goal         TEXT CHECK (goal IN ('damage','tank','heal','support')),
    notes        TEXT,
    source       TEXT CHECK (source IN ('manual','captura')),
    seen_at      TEXT,
    updated_at   TEXT NOT NULL
);
INSERT INTO characters_v2 SELECT id, name, slug, vocation, level, current_hunt, vip,
    CASE goal WHEN 'sustain' THEN
        CASE vocation WHEN 'knight' THEN 'tank' WHEN 'druid' THEN 'heal' WHEN 'monk' THEN 'support' ELSE NULL END
    ELSE goal END,
    notes, source, seen_at, updated_at FROM characters;
DROP TABLE characters;
ALTER TABLE characters_v2 RENAME TO characters;
"""
MIGRATIONS = [_SCHEMA_V1, _SCHEMA_V2]
SCHEMA_VERSION = len(MIGRATIONS)


class VaultError(Exception):
    pass


def now_iso():
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def slugify(name):
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not text:
        raise VaultError("nome sem letras nem numeros: %r" % name)
    return text


def connect(path=None):
    """Abre (ou cria) a BD e aplica as migracoes que faltam."""
    path = Path(path or DEFAULT_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn)
    return conn


def schema_version(conn):
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn):
    current = schema_version(conn)
    if current > SCHEMA_VERSION:
        raise VaultError("a BD esta na versao %d e o codigo so conhece ate %d"
                         % (current, SCHEMA_VERSION))
    for version in range(current, SCHEMA_VERSION):
        # sem isto, o DROP de uma tabela reconstruida apagava em cascata os filhos
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            with conn:
                conn.executescript(MIGRATIONS[version])
                conn.execute("PRAGMA user_version = %d" % (version + 1))
        finally:
            conn.execute("PRAGMA foreign_keys = ON")
        broken = conn.execute("PRAGMA foreign_key_check").fetchall()
        if broken:
            raise VaultError("a migracao para a v%d deixou referencias partidas: %r" % (version + 1, broken[:5]))
    return schema_version(conn)


def default_goal(vocation):
    """O objectivo de omissao de uma vocacao (o primeiro que o Andre listou)."""
    goals = GOALS_BY_VOCATION.get(vocation)
    return goals[0] if goals else None


def _check_source(source):
    if source is not None and source not in SOURCES:
        raise VaultError("source tem de ser 'manual' ou 'captura', nao %r" % source)


def _opt_int(value, label):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise VaultError("%s tem de ser inteiro ou NULL, nao %r" % (label, value))
    return value


class Vault:
    """Escrita e leitura da `vault.db`, com o catalogo ao lado para validar."""

    def __init__(self, conn, cat):
        self.conn = conn
        self.cat = cat

    # --- validacao ------------------------------------------------------------
    def _hunt(self, hunt):
        if hunt is None:
            return None
        if self.cat.has_hunt(hunt):
            return hunt
        by_name = self.cat.hunt_by_name.get(str(hunt).lower())
        if by_name:
            return by_name["id"]
        raise VaultError("hunt desconhecida: %r" % hunt)

    def _creature(self, key):
        if key is None:
            return None
        if self.cat.has_creature(key):
            return key
        by_name = self.cat.creature_by_name.get(str(key).lower())
        if by_name:
            return by_name["chave"]
        raise VaultError("criatura desconhecida: %r" % key)

    def _charm(self, key):
        if not self.cat.has_charm(key):
            raise VaultError("charm desconhecido: %r" % key)
        return key

    def _node(self, key, vocation):
        if not self.cat.has_node(key):
            raise VaultError("no da arvore desconhecido: %r" % key)
        if vocation and not self.cat.has_node(key, vocation):
            raise VaultError("o no %r e da arvore de %s, nao de %s"
                             % (key, self.cat.node_vocation[key], vocation))
        return key

    def _item(self, key, slot):
        if key is None:
            return None
        key = str(key).lower()
        if not self.cat.has_item(key):
            raise VaultError("item desconhecido: %r" % key)
        item_slot = self.cat.item_by_key[key].get("slot")
        if item_slot and item_slot != slot:
            raise VaultError("o item %r e de %s, nao de %s" % (key, item_slot, slot))
        return key

    def _slot(self, slot):
        if not (self.cat.has_slot(slot) or slot in EXTRA_SLOTS):
            raise VaultError("slot desconhecido: %r" % slot)
        return slot

    def _character_id(self, character_id):
        row = self.conn.execute("SELECT id, vocation FROM characters WHERE id = ?",
                                (character_id,)).fetchone()
        if row is None:
            raise VaultError("personagem %r nao existe" % character_id)
        return row

    # --- personagens ------------------------------------------------------------
    def upsert_character(self, name, vocation=None, level=None, current_hunt=None,
                         vip=None, goal=None, notes=None, source=None, seen_at=None):
        """Cria ou actualiza pelo nome. So os campos passados mudam; o que vem a
        `None` NAO apaga o que la estava (para uma captura parcial nao limpar
        o resto). Para apagar um campo de proposito ha `clear_character_field`."""
        name = str(name or "").strip()
        if not name:
            raise VaultError("personagem sem nome")
        if vocation is not None:
            normalized = catalog_module.normalize_vocation(vocation)
            if normalized is None:
                raise VaultError("vocacao desconhecida: %r" % vocation)
            vocation = normalized
        if goal is not None and goal not in GOALS:
            raise VaultError("goal tem de ser damage/tank/heal/support, nao %r" % goal)
        if vip is not None:
            if isinstance(vip, bool):
                vip = int(vip)
            if vip not in (0, 1):
                raise VaultError("vip tem de ser 0/1/NULL, nao %r" % vip)
        level = _opt_int(level, "level")
        current_hunt = self._hunt(current_hunt)
        _check_source(source)

        fields = {"vocation": vocation, "level": level, "current_hunt": current_hunt,
                  "vip": vip, "goal": goal, "notes": notes, "source": source,
                  "seen_at": seen_at}
        row = self.conn.execute("SELECT id, vocation, goal FROM characters WHERE name = ?", (name,)).fetchone()
        # o objectivo tem de ser um dos da vocacao (a que vem agora ou a que ja la esta)
        final_vocation = vocation or (row["vocation"] if row else None)
        final_goal = goal or (row["goal"] if row else None)
        if final_vocation and final_goal and final_goal not in GOALS_BY_VOCATION[final_vocation]:
            if goal is None:
                fields["goal"] = default_goal(final_vocation)  # a vocacao mudou: o goal antigo deixou de valer
            else:
                raise VaultError("o objectivo %r nao e de %s (so %s)"
                                 % (goal, final_vocation, "/".join(GOALS_BY_VOCATION[final_vocation])))
        with self.conn:
            if row is None:
                cols = ["name", "slug", "updated_at"] + list(fields)
                vals = [name, slugify(name), now_iso()] + list(fields.values())
                cur = self.conn.execute(
                    "INSERT INTO characters (%s) VALUES (%s)"
                    % (", ".join(cols), ", ".join("?" * len(cols))), vals)
                return cur.lastrowid
            sets = {k: v for k, v in fields.items() if v is not None}
            sets["updated_at"] = now_iso()
            self.conn.execute(
                "UPDATE characters SET %s WHERE id = ?"
                % ", ".join("%s = ?" % k for k in sets),
                list(sets.values()) + [row["id"]])
            return row["id"]

    def clear_character_field(self, character_id, field):
        if field not in ("vocation", "level", "current_hunt", "vip", "goal", "notes", "seen_at"):
            raise VaultError("campo nao apagavel: %r" % field)
        self._character_id(character_id)
        with self.conn:
            self.conn.execute("UPDATE characters SET %s = NULL, updated_at = ? WHERE id = ?"
                              % field, (now_iso(), character_id))

    def delete_character(self, character_id):
        self._character_id(character_id)
        with self.conn:
            self.conn.execute("DELETE FROM characters WHERE id = ?", (character_id,))

    def characters(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM characters ORDER BY name")]

    def character(self, slug_or_id):
        if isinstance(slug_or_id, int):
            row = self.conn.execute("SELECT * FROM characters WHERE id = ?", (slug_or_id,)).fetchone()
        else:
            row = self.conn.execute("SELECT * FROM characters WHERE slug = ?", (slug_or_id,)).fetchone()
        return dict(row) if row else None

    # --- arvore -----------------------------------------------------------------
    def set_tree_node(self, character_id, node_key, rank, source=None, seen_at=None):
        ch = self._character_id(character_id)
        self._node(node_key, ch["vocation"])
        if not isinstance(rank, int) or isinstance(rank, bool) or rank < 0:
            raise VaultError("rank tem de ser inteiro >= 0, nao %r" % rank)
        max_rank = self.cat.node_by_id[node_key].get("rank_maximo")
        if max_rank is not None and rank > max_rank:
            raise VaultError("o no %r tem rank maximo %d, nao %d" % (node_key, max_rank, rank))
        _check_source(source)
        with self.conn:
            self.conn.execute(
                "INSERT INTO character_tree (character_id, node_key, rank, source, seen_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT (character_id, node_key) DO UPDATE SET "
                "rank = excluded.rank, source = excluded.source, seen_at = excluded.seen_at",
                (character_id, node_key, rank, source, seen_at))

    def tree_of(self, character_id):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM character_tree WHERE character_id = ? ORDER BY node_key",
            (character_id,))]

    # --- equipamento ------------------------------------------------------------
    def set_equipment(self, character_id, slot, item_key=None, item_name=None,
                      upgrade_level=None, imbuements=None, attributes=None,
                      source=None, seen_at=None):
        """`imbuements` e uma lista e `attributes` um dicionario, guardados em
        JSON tal como vieram; `None` fica NULL (nao se sabe), `[]`/`{}` fica
        «sabe-se que nao tem»."""
        self._character_id(character_id)
        slot = self._slot(slot)
        item_key = self._item(item_key, slot)
        if item_key and not item_name:
            item_name = self.cat.item_name(item_key)
        upgrade_level = _opt_int(upgrade_level, "upgrade_level")
        if imbuements is not None and not isinstance(imbuements, list):
            raise VaultError("imbuements tem de ser lista ou None")
        if attributes is not None and not isinstance(attributes, dict):
            raise VaultError("attributes tem de ser dicionario ou None")
        _check_source(source)
        with self.conn:
            self.conn.execute(
                "INSERT INTO character_equipment (character_id, slot, item_key, item_name, "
                "upgrade_level, imbuements_json, attributes_json, source, seen_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (character_id, slot) DO UPDATE SET "
                "item_key = excluded.item_key, item_name = excluded.item_name, "
                "upgrade_level = excluded.upgrade_level, imbuements_json = excluded.imbuements_json, "
                "attributes_json = excluded.attributes_json, source = excluded.source, "
                "seen_at = excluded.seen_at",
                (character_id, slot, item_key, item_name, upgrade_level,
                 None if imbuements is None else json.dumps(imbuements, ensure_ascii=False),
                 None if attributes is None else json.dumps(attributes, ensure_ascii=False),
                 source, seen_at))

    def equipment_of(self, character_id):
        rows = []
        for r in self.conn.execute(
                "SELECT * FROM character_equipment WHERE character_id = ? ORDER BY slot",
                (character_id,)):
            d = dict(r)
            d["imbuements"] = json.loads(d["imbuements_json"]) if d["imbuements_json"] else None
            d["attributes"] = json.loads(d["attributes_json"]) if d["attributes_json"] else None
            rows.append(d)
        return rows

    # --- charms -----------------------------------------------------------------
    def set_charm(self, character_id, charm_key, tier, assigned_creature_key=None,
                  source=None, seen_at=None):
        self._character_id(character_id)
        self._charm(charm_key)
        if tier not in (1, 2, 3):
            raise VaultError("tier tem de ser 1, 2 ou 3, nao %r" % tier)
        creature = self._creature(assigned_creature_key)
        _check_source(source)
        with self.conn:
            self.conn.execute(
                "INSERT INTO character_charms (character_id, charm_key, tier, "
                "assigned_creature_key, source, seen_at) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (character_id, charm_key) DO UPDATE SET tier = excluded.tier, "
                "assigned_creature_key = excluded.assigned_creature_key, "
                "source = excluded.source, seen_at = excluded.seen_at",
                (character_id, charm_key, tier, creature, source, seen_at))

    def remove_charm(self, character_id, charm_key):
        with self.conn:
            self.conn.execute("DELETE FROM character_charms WHERE character_id = ? AND charm_key = ?",
                              (character_id, charm_key))

    def charms_of(self, character_id):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM character_charms WHERE character_id = ? ORDER BY charm_key",
            (character_id,))]

    def set_charm_points(self, character_id, points_available=None, points_spent=None,
                         source=None, seen_at=None):
        self._character_id(character_id)
        points_available = _opt_int(points_available, "points_available")
        points_spent = _opt_int(points_spent, "points_spent")
        _check_source(source)
        with self.conn:
            self.conn.execute(
                "INSERT INTO character_charm_points (character_id, points_available, "
                "points_spent, source, seen_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT (character_id) DO UPDATE SET "
                "points_available = excluded.points_available, points_spent = excluded.points_spent, "
                "source = excluded.source, seen_at = excluded.seen_at",
                (character_id, points_available, points_spent, source, seen_at))

    def charm_points_of(self, character_id):
        row = self.conn.execute("SELECT * FROM character_charm_points WHERE character_id = ?",
                                (character_id,)).fetchone()
        return dict(row) if row else None

    # --- bestiario --------------------------------------------------------------
    def set_bestiary(self, character_id, creature_key, kills, source=None, seen_at=None):
        self._character_id(character_id)
        creature = self._creature(creature_key)
        if creature is None:
            raise VaultError("criatura em falta")
        if not isinstance(kills, int) or isinstance(kills, bool) or kills < 0:
            raise VaultError("kills tem de ser inteiro >= 0, nao %r" % kills)
        _check_source(source)
        with self.conn:
            self.conn.execute(
                "INSERT INTO character_bestiary (character_id, creature_key, kills, source, seen_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT (character_id, creature_key) DO UPDATE SET "
                "kills = excluded.kills, source = excluded.source, seen_at = excluded.seen_at",
                (character_id, creature, kills, source, seen_at))

    def bestiary_of(self, character_id):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM character_bestiary WHERE character_id = ? ORDER BY creature_key",
            (character_id,))]

    # --- leituras ---------------------------------------------------------------
    def add_reading(self, character_id, at=None, level=None, xp=None, gold=None,
                    stamina=None, hunt=None, source=None):
        self._character_id(character_id)
        hunt = self._hunt(hunt)
        for label, v in (("level", level), ("xp", xp), ("gold", gold), ("stamina", stamina)):
            _opt_int(v, label)
        _check_source(source)
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO readings (character_id, at, level, xp, gold, stamina, hunt, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (character_id, at or now_iso(), level, xp, gold, stamina, hunt, source))
            return cur.lastrowid

    def readings_of(self, character_id, limit=50):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM readings WHERE character_id = ? ORDER BY at DESC LIMIT ?",
            (character_id, limit))]


def check(conn, cat):
    """Problemas na BD face ao catalogo (lista vazia = tudo bem). Apanha o que
    entrou por fora do `Vault` ou o que uma actualizacao do jogo desfez."""
    problems = []
    version = schema_version(conn)
    if version != SCHEMA_VERSION:
        problems.append("esquema na versao %d, esperava %d" % (version, SCHEMA_VERSION))
        return problems
    q = conn.execute
    for r in q("SELECT name, current_hunt, vocation FROM characters"):
        if r["current_hunt"] is not None and not cat.has_hunt(r["current_hunt"]):
            problems.append("%s: hunt %r desconhecida" % (r["name"], r["current_hunt"]))
    for r in q("SELECT c.name, t.node_key, t.rank, c.vocation FROM character_tree t "
               "JOIN characters c ON c.id = t.character_id"):
        if not cat.has_node(r["node_key"]):
            problems.append("%s: no %r desconhecido" % (r["name"], r["node_key"]))
        elif r["vocation"] and not cat.has_node(r["node_key"], r["vocation"]):
            problems.append("%s: no %r nao e da vocacao %s" % (r["name"], r["node_key"], r["vocation"]))
    for r in q("SELECT c.name, e.slot, e.item_key FROM character_equipment e "
               "JOIN characters c ON c.id = e.character_id"):
        if not (cat.has_slot(r["slot"]) or r["slot"] in EXTRA_SLOTS):
            problems.append("%s: slot %r desconhecido" % (r["name"], r["slot"]))
        if r["item_key"] is not None and not cat.has_item(r["item_key"]):
            problems.append("%s: item %r desconhecido" % (r["name"], r["item_key"]))
    for r in q("SELECT c.name, h.charm_key, h.assigned_creature_key FROM character_charms h "
               "JOIN characters c ON c.id = h.character_id"):
        if not cat.has_charm(r["charm_key"]):
            problems.append("%s: charm %r desconhecido" % (r["name"], r["charm_key"]))
        if r["assigned_creature_key"] is not None and not cat.has_creature(r["assigned_creature_key"]):
            problems.append("%s: criatura %r desconhecida" % (r["name"], r["assigned_creature_key"]))
    for r in q("SELECT c.name, b.creature_key FROM character_bestiary b "
               "JOIN characters c ON c.id = b.character_id"):
        if not cat.has_creature(r["creature_key"]):
            problems.append("%s: criatura %r desconhecida no bestiario" % (r["name"], r["creature_key"]))
    for r in q("SELECT c.name, r.hunt FROM readings r JOIN characters c ON c.id = r.character_id "
               "WHERE r.hunt IS NOT NULL"):
        if not cat.has_hunt(r["hunt"]):
            problems.append("%s: leitura com hunt %r desconhecida" % (r["name"], r["hunt"]))
    return problems
