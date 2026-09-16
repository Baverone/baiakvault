import sqlite3
import unittest

import helpers
from baiakvault import db

TABLES = {"characters", "character_tree", "character_equipment", "character_charms",
          "character_charm_points", "character_bestiary", "readings"}


class Schema(unittest.TestCase):
    def test_applies_to_a_fresh_db(self):
        conn, vault, path = helpers.temp_vault()
        self.assertTrue(path.is_file())
        self.assertEqual(db.schema_version(conn), db.SCHEMA_VERSION)
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue(TABLES <= names, names)
        conn.close()

    def test_reopening_is_a_no_op(self):
        conn, vault, path = helpers.temp_vault()
        conn.close()
        conn = db.connect(path)
        self.assertEqual(db.schema_version(conn), db.SCHEMA_VERSION)
        conn.close()

    def test_newer_db_than_code_fails_loud(self):
        conn, vault, path = helpers.temp_vault()
        conn.execute("PRAGMA user_version = %d" % (db.SCHEMA_VERSION + 5))
        conn.close()
        with self.assertRaises(db.VaultError):
            db.connect(path)

    def test_foreign_keys_cascade(self):
        conn, vault, path = helpers.temp_vault(with_fixture=True)
        cid = vault.character("teste-knight")["id"]
        vault.delete_character(cid)
        self.assertEqual(conn.execute("SELECT count(*) FROM character_tree").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT count(*) FROM readings").fetchone()[0], 0)
        conn.close()

    def test_v1_to_v2_keeps_children_and_maps_sustain(self):
        """Uma BD na v1 com um druid «sustain» e filhos (arvore, leituras) migra
        para a v2 sem perder os filhos e com o objectivo da vocacao."""
        path = helpers.temp_dir() / "v1.db"
        conn = sqlite3.connect(str(path))
        conn.executescript(db.MIGRATIONS[0])
        conn.execute("PRAGMA user_version = 1")
        conn.execute("INSERT INTO characters (id, name, slug, vocation, goal, updated_at) VALUES (1, 'D', 'd', 'druid', 'sustain', 'x')")
        conn.execute("INSERT INTO characters (id, name, slug, vocation, goal, updated_at) VALUES (2, 'S', 's', 'sorcerer', 'sustain', 'x')")
        conn.execute("INSERT INTO character_tree (character_id, node_key, rank) VALUES (1, 'd_nature', 2)")
        conn.execute("INSERT INTO readings (character_id, at, level) VALUES (1, '2026-09-16 10:00:00', 50)")
        conn.commit()
        conn.close()
        conn = db.connect(path)
        try:
            self.assertEqual(db.schema_version(conn), db.SCHEMA_VERSION)
            self.assertEqual(conn.execute("SELECT goal FROM characters WHERE id = 1").fetchone()[0], "heal")
            self.assertIsNone(conn.execute("SELECT goal FROM characters WHERE id = 2").fetchone()[0])
            self.assertEqual(conn.execute("SELECT count(*) FROM character_tree").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM readings").fetchone()[0], 1)
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO characters (name, slug, goal, updated_at) VALUES ('X', 'x', 'sustain', 'x')")
            # as chaves estrangeiras continuam a apontar para a tabela nova
            conn.execute("DELETE FROM characters WHERE id = 1")
            self.assertEqual(conn.execute("SELECT count(*) FROM character_tree").fetchone()[0], 0)
        finally:
            conn.close()

    def test_v2_to_v3_adds_charm_screen_columns_and_keeps_rows(self):
        path = helpers.temp_dir() / "v2.db"
        conn = sqlite3.connect(str(path))
        conn.executescript(db.MIGRATIONS[0])
        conn.executescript(db.MIGRATIONS[1])
        conn.execute("PRAGMA user_version = 2")
        conn.execute("INSERT INTO characters (id, name, slug, vocation, updated_at) VALUES (1, 'K', 'k', 'knight', 'x')")
        conn.execute("INSERT INTO character_charm_points (character_id, points_available, points_spent) VALUES (1, 350, 100)")
        conn.commit()
        conn.close()
        conn = db.connect(path)
        try:
            self.assertEqual(db.schema_version(conn), 3)
            row = conn.execute("SELECT * FROM character_charm_points WHERE character_id = 1").fetchone()
            self.assertEqual((row["points_available"], row["points_spent"]), (350, 100))
            self.assertIsNone(row["slot_limit"])
            self.assertIsNone(row["echoes"])
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE character_charm_points SET expansion = 2 WHERE character_id = 1")
        finally:
            conn.close()


class Characters(unittest.TestCase):
    def setUp(self):
        self.conn, self.vault, _ = helpers.temp_vault()

    def tearDown(self):
        self.conn.close()

    def test_upsert_creates_with_slug_and_normalized_vocation(self):
        cid = self.vault.upsert_character("Bluey The Cat", vocation="ED", source="manual")
        c = self.vault.character("bluey-the-cat")
        self.assertEqual(c["id"], cid)
        self.assertEqual(c["vocation"], "druid")
        self.assertIsNone(c["level"])
        self.assertIsNone(c["vip"])

    def test_unknown_stays_null_and_is_not_clobbered(self):
        cid = self.vault.upsert_character("X", level=100, vip=True)
        self.vault.upsert_character("X", current_hunt="Cobras")  # level nao vem: fica
        c = self.vault.character(cid)
        self.assertEqual(c["level"], 100)
        self.assertEqual(c["vip"], 1)
        self.assertEqual(c["current_hunt"], "cobra-cave")
        self.assertIsNone(c["goal"])
        self.vault.clear_character_field(cid, "level")
        self.assertIsNone(self.vault.character(cid)["level"])

    def test_rejects_bad_values(self):
        with self.assertRaises(db.VaultError):
            self.vault.upsert_character("X", vocation="paladino")
        with self.assertRaises(db.VaultError):
            self.vault.upsert_character("X", current_hunt="Hunt Que Nao Existe")
        with self.assertRaises(db.VaultError):
            self.vault.upsert_character("X", goal="xp")
        with self.assertRaises(db.VaultError):
            self.vault.upsert_character("X", source="wiki")
        with self.assertRaises(db.VaultError):
            self.vault.upsert_character("X", level="312")
        with self.assertRaises(db.VaultError):
            self.vault.upsert_character("   ")
        self.assertEqual(self.vault.characters(), [])

    def test_same_name_in_other_case_is_the_same_character(self):
        # o slug e UNIQUE: «Baverone» e «baverone» davam um IntegrityError cru (nao um VaultError)
        cid = self.vault.upsert_character("Baverone", vocation="knight", level=100)
        cid2 = self.vault.upsert_character("BAVERONE", level=101)
        self.assertEqual(cid, cid2)
        self.assertEqual(len(self.vault.characters()), 1)
        c = self.vault.character(cid)
        self.assertEqual((c["name"], c["level"], c["vocation"]), ("Baverone", 101, "knight"))

    def test_changing_vocation_over_a_registered_tree_is_an_error(self):
        cid = self.vault.upsert_character("K", vocation="knight")
        self.vault.set_tree_node(cid, "k_fury", 2)
        with self.assertRaises(db.VaultError):
            self.vault.upsert_character("K", vocation="druid")
        self.assertEqual(self.vault.character(cid)["vocation"], "knight")
        self.assertEqual(db.check(self.conn, helpers.real_catalog()), [])
        # sem arvore registada muda-se (e o objectivo repoe a omissao da nova vocacao)
        self.vault.clear_tree(cid)
        self.vault.upsert_character("K", vocation="druid")
        self.assertEqual(self.vault.character(cid)["vocation"], "druid")


class Tree(unittest.TestCase):
    def setUp(self):
        self.conn, self.vault, _ = helpers.temp_vault()
        self.cid = self.vault.upsert_character("K", vocation="knight")

    def tearDown(self):
        self.conn.close()

    def test_valid_node(self):
        self.vault.set_tree_node(self.cid, "k_fury", 3, source="captura", seen_at="2026-09-16")
        self.vault.set_tree_node(self.cid, "k_fury", 4)
        rows = self.vault.tree_of(self.cid)
        self.assertEqual([(r["node_key"], r["rank"]) for r in rows], [("k_fury", 4)])
        self.assertIsNone(rows[0]["source"])

    def test_unknown_node_is_an_error_not_a_row(self):
        with self.assertRaises(db.VaultError):
            self.vault.set_tree_node(self.cid, "k_inventado", 1)
        self.assertEqual(self.vault.tree_of(self.cid), [])

    def test_node_of_another_vocation_is_an_error(self):
        with self.assertRaises(db.VaultError):
            self.vault.set_tree_node(self.cid, "s_fury" if "s_fury" in self.vault.cat.node_by_id
                                     else next(k for k, v in self.vault.cat.node_vocation.items()
                                               if v == "sorcerer"), 1)

    def test_rank_above_max_is_an_error(self):
        with self.assertRaises(db.VaultError):
            self.vault.set_tree_node(self.cid, "k_fury", 11)


class Equipment(unittest.TestCase):
    def setUp(self):
        self.conn, self.vault, _ = helpers.temp_vault()
        self.cid = self.vault.upsert_character("D", vocation="druid")

    def tearDown(self):
        self.conn.close()

    def test_item_name_comes_from_catalog_and_json_fields_stay_null(self):
        self.vault.set_equipment(self.cid, "shield", "Eldritch Tome", upgrade_level=1)
        e = self.vault.equipment_of(self.cid)[0]
        self.assertEqual(e["item_key"], "eldritch tome")
        self.assertEqual(e["item_name"], "eldritch tome")
        self.assertIsNone(e["imbuements"])
        self.assertIsNone(e["attributes"])
        self.assertIsNone(e["imbuements_json"])

    def test_empty_list_means_known_none(self):
        self.vault.set_equipment(self.cid, "amulet", None, imbuements=[], attributes={"xp": 2})
        e = self.vault.equipment_of(self.cid)[0]
        self.assertIsNone(e["item_key"])
        self.assertEqual(e["imbuements"], [])
        self.assertEqual(e["attributes"], {"xp": 2})

    def test_unknown_item_and_wrong_slot_are_errors(self):
        with self.assertRaises(db.VaultError):
            self.vault.set_equipment(self.cid, "shield", "escudo inventado")
        with self.assertRaises(db.VaultError):
            self.vault.set_equipment(self.cid, "weapon", "eldritch tome")
        with self.assertRaises(db.VaultError):
            self.vault.set_equipment(self.cid, "chapeu", "eldritch tome")
        self.assertEqual(self.vault.equipment_of(self.cid), [])

    def test_backpack_slot_exists_even_without_catalog_slot(self):
        self.vault.set_equipment(self.cid, "backpack", "ghost backpack")
        self.assertEqual(self.vault.equipment_of(self.cid)[0]["slot"], "backpack")


class CharmsBestiaryReadings(unittest.TestCase):
    def setUp(self):
        self.conn, self.vault, _ = helpers.temp_vault()
        self.cid = self.vault.upsert_character("S", vocation="sorcerer")

    def tearDown(self):
        self.conn.close()

    def test_charm_with_creature_by_name(self):
        self.vault.set_charm(self.cid, "wound", 2, "Cobra Vizier", source="manual")
        c = self.vault.charms_of(self.cid)[0]
        self.assertEqual(c["assigned_creature_key"], "cobra_vizier")
        self.vault.set_charm(self.cid, "wound", 3, None)
        c = self.vault.charms_of(self.cid)[0]
        self.assertEqual((c["tier"], c["assigned_creature_key"]), (3, None))
        self.vault.remove_charm(self.cid, "wound")
        self.assertEqual(self.vault.charms_of(self.cid), [])

    def test_charm_errors(self):
        with self.assertRaises(db.VaultError):
            self.vault.set_charm(self.cid, "wound", 4)
        with self.assertRaises(db.VaultError):
            self.vault.set_charm(self.cid, "charm_falso", 1)
        with self.assertRaises(db.VaultError):
            self.vault.set_charm(self.cid, "wound", 1, "bicho inventado")

    def test_charm_points_null_is_null(self):
        self.vault.set_charm_points(self.cid, points_available=120)
        p = self.vault.charm_points_of(self.cid)
        self.assertEqual(p["points_available"], 120)
        self.assertIsNone(p["points_spent"])
        self.assertIsNone(p["slot_limit"])
        self.assertIsNone(p["expansion"])
        self.assertIsNone(p["echoes"])
        self.assertIsNone(self.vault.charm_points_of(999))

    def test_charm_points_partial_write_keeps_the_rest(self):
        # v3: uma leitura parcial nao limpa o resto (a regra do upsert_character); apagar e explicito
        self.vault.set_charm_points(self.cid, points_available=120, slot_limit=6, expansion=0, echoes=50)
        self.vault.set_charm_points(self.cid, points_spent=240)
        p = self.vault.charm_points_of(self.cid)
        self.assertEqual((p["points_available"], p["points_spent"], p["slot_limit"], p["expansion"], p["echoes"]),
                         (120, 240, 6, 0, 50))
        self.vault.clear_charm_points_field(self.cid, "slot_limit")
        self.assertIsNone(self.vault.charm_points_of(self.cid)["slot_limit"])
        with self.assertRaises(db.VaultError):
            self.vault.set_charm_points(self.cid, expansion="sim")
        with self.assertRaises(db.VaultError):
            self.vault.clear_charm_points_field(self.cid, "inventado")
        self.assertEqual(db.schema_version(self.conn), 3)

    def test_bestiary(self):
        self.vault.set_bestiary(self.cid, "cobra_vizier", 10)
        self.vault.set_bestiary(self.cid, "cobra_vizier", 12)
        self.assertEqual(self.vault.bestiary_of(self.cid)[0]["kills"], 12)
        with self.assertRaises(db.VaultError):
            self.vault.set_bestiary(self.cid, "cobra_vizier", -1)
        with self.assertRaises(db.VaultError):
            self.vault.set_bestiary(self.cid, "nao_existe", 1)

    def test_readings_append_and_keep_nulls(self):
        self.vault.add_reading(self.cid, at="2026-09-16 10:00:00", level=50, hunt="Cobras")
        self.vault.add_reading(self.cid, at="2026-09-16 11:00:00", level=None, xp=None)
        rows = self.vault.readings_of(self.cid)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["at"], "2026-09-16 11:00:00")
        self.assertIsNone(rows[0]["level"])
        self.assertEqual(rows[1]["hunt"], "cobra-cave")
        with self.assertRaises(db.VaultError):
            self.vault.add_reading(self.cid, hunt="inventada")

    def test_unknown_character_is_an_error(self):
        with self.assertRaises(db.VaultError):
            self.vault.set_charm(999, "wound", 1)


class Check(unittest.TestCase):
    def test_fixture_is_clean(self):
        conn, vault, _ = helpers.temp_vault(with_fixture=True)
        self.assertEqual(db.check(conn, vault.cat), [])
        conn.close()

    def test_detects_rows_that_bypassed_the_vault(self):
        conn, vault, _ = helpers.temp_vault(with_fixture=True)
        cid = vault.character("teste-knight")["id"]
        conn.execute("INSERT INTO character_tree (character_id, node_key, rank) VALUES (?, 'no_falso', 1)", (cid,))
        conn.execute("UPDATE characters SET current_hunt = 'hunt-falsa' WHERE id = ?", (cid,))
        conn.commit()
        problems = db.check(conn, vault.cat)
        self.assertEqual(len(problems), 2, problems)
        conn.close()

    def test_sqlite_constraints_hold(self):
        conn, vault, _ = helpers.temp_vault()
        cid = vault.upsert_character("Z")
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO character_charms (character_id, charm_key, tier) VALUES (?, 'wound', 9)", (cid,))
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE characters SET source = 'wiki' WHERE id = ?", (cid,))
        conn.close()


if __name__ == "__main__":
    unittest.main()
