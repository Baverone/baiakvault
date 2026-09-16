-- vault.db: os dados DELE (personagens, builds, charms). Versao 1 (16/09/2026).
-- A v2 (db.py, _SCHEMA_V2) reconstroi `characters` com goal IN (damage, tank, heal, support).
--
-- So o proprio BaiakVault escreve aqui (`db.py`). As chaves de hunt, criatura,
-- charm, no da arvore e item sao as dos catalogos e validam-se em `db.py`
-- antes de entrar: chave desconhecida e erro, nao insercao silenciosa.
--
-- NULL quer dizer «nao se sabe» e sai «?» na pagina. Nunca se poe 0 por
-- omissao num campo que ele nao preencheu.
--
-- `source` e sempre 'manual' (formulario local) ou 'captura' (imagem lida por
-- visao pelo Claude local). `seen_at` e quando o dado era verdade no jogo
-- (a data da captura); `updated_at` e quando a linha foi escrita.

CREATE TABLE characters (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    slug         TEXT NOT NULL UNIQUE,
    vocation     TEXT CHECK (vocation IN ('knight','monk','paladin','sorcerer','druid')),
    level        INTEGER CHECK (level IS NULL OR level >= 1),
    current_hunt TEXT,                                  -- hunts.id do catalogo
    vip          INTEGER CHECK (vip IN (0, 1)),          -- NULL = nao se sabe
    goal         TEXT CHECK (goal IN ('damage','tank','sustain')),
    notes        TEXT,
    source       TEXT CHECK (source IN ('manual','captura')),
    seen_at      TEXT,
    updated_at   TEXT NOT NULL
);

CREATE TABLE character_tree (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    node_key     TEXT NOT NULL,                          -- arvore.id (ex. k_fury)
    rank         INTEGER NOT NULL CHECK (rank >= 0),
    source       TEXT CHECK (source IN ('manual','captura')),
    seen_at      TEXT,
    PRIMARY KEY (character_id, node_key)
);

CREATE TABLE character_equipment (
    character_id    INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    slot            TEXT NOT NULL,                       -- amulet, armor, ..., mais backpack/ammo
    item_key        TEXT,                                -- itens.nome em minusculas; NULL = slot vazio ou desconhecido
    item_name       TEXT,                                -- o nome como o jogo o mostra
    upgrade_level   INTEGER CHECK (upgrade_level IS NULL OR upgrade_level >= 0),
    imbuements_json TEXT,                                -- lista JSON, tal como lida; NULL = nao se sabe
    attributes_json TEXT,                                -- dicionario JSON dos atributos da forja; NULL = nao se sabe
    source          TEXT CHECK (source IN ('manual','captura')),
    seen_at         TEXT,
    PRIMARY KEY (character_id, slot)
);

CREATE TABLE character_charms (
    character_id          INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    charm_key             TEXT NOT NULL,                 -- charms.key (ex. wound)
    tier                  INTEGER NOT NULL CHECK (tier BETWEEN 1 AND 3),
    assigned_creature_key TEXT,                          -- bestiario.chave; NULL = sem criatura
    source                TEXT CHECK (source IN ('manual','captura')),
    seen_at               TEXT,
    PRIMARY KEY (character_id, charm_key)
);

CREATE TABLE character_charm_points (
    character_id     INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    points_available INTEGER CHECK (points_available IS NULL OR points_available >= 0),
    points_spent     INTEGER CHECK (points_spent IS NULL OR points_spent >= 0),
    source           TEXT CHECK (source IN ('manual','captura')),
    seen_at          TEXT
);

CREATE TABLE character_bestiary (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    creature_key TEXT NOT NULL,                          -- bestiario.chave
    kills        INTEGER NOT NULL CHECK (kills >= 0),
    source       TEXT CHECK (source IN ('manual','captura')),
    seen_at      TEXT,
    PRIMARY KEY (character_id, creature_key)
);

-- Historico de leituras de estado, para o XP/h futuro. Uma linha por leitura;
-- nunca se actualiza, so se acrescenta.
CREATE TABLE readings (
    id           INTEGER PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    at           TEXT NOT NULL,                          -- ISO 8601, hora local
    level        INTEGER,
    xp           INTEGER,
    gold         INTEGER,
    stamina      INTEGER,                                -- minutos
    hunt         TEXT,                                   -- hunts.id
    source       TEXT CHECK (source IN ('manual','captura'))
);

CREATE INDEX readings_by_character ON readings (character_id, at);
