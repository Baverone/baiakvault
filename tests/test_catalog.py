import unittest

import helpers
from baiakvault import catalog, notes


class CatalogLoads(unittest.TestCase):
    def setUp(self):
        self.cat = helpers.real_catalog()

    def test_counts_are_the_expected_ones(self):
        counts = self.cat.counts()
        self.assertEqual(counts["hunts"], 79)
        self.assertEqual(counts["charms"], 24)
        self.assertEqual(counts["tree_nodes"], 203)
        self.assertEqual(counts["vocations"], 5)
        self.assertEqual(counts["creatures"], 356)
        self.assertEqual(counts["items"], 2902)
        self.assertEqual(counts["room_bosses"], 386)
        self.assertEqual(counts["wave10_bosses"], 61)

    def test_validate_passes_on_the_real_catalog(self):
        self.assertEqual(catalog.validate(self.cat), [])

    def test_keys_are_unique(self):
        self.assertEqual(len(self.cat.hunt_by_id), len(self.cat.hunts))
        self.assertEqual(len(self.cat.creature_by_key), len(self.cat.creatures))
        self.assertEqual(len(self.cat.charm_by_key), len(self.cat.charms))
        self.assertEqual(len(self.cat.item_by_key), len(self.cat.items))
        self.assertEqual(len(self.cat.node_by_id), 203)

    def test_hunt_ids_are_file_safe_slugs(self):
        for hunt in self.cat.hunts:
            self.assertRegex(hunt["id"], r"^[a-z0-9]+(-[a-z0-9]+)*$")

    def test_every_hunt_monster_is_in_the_bestiary(self):
        for hunt in self.cat.hunts:
            for m in hunt["monstros"]:
                self.assertTrue(self.cat.has_creature(m["chave"]), (hunt["id"], m["chave"]))

    def test_wave10_bosses_point_to_hunts(self):
        for boss in self.cat.wave10_bosses:
            self.assertTrue(self.cat.has_hunt(boss["hunt"]), boss)

    def test_charms_have_three_tiers_and_a_category(self):
        for c in self.cat.charms:
            self.assertEqual(len(c["chance"]), 3, c["key"])
            self.assertEqual(len(c["points"]), 3, c["key"])
            self.assertIn(c["category"], ("major", "minor"))
            self.assertTrue(c["desc"])

    def test_slots_come_from_the_catalog(self):
        self.assertEqual(self.cat.slots,
                         ["amulet", "armor", "boots", "helmet", "legs", "ring", "shield", "weapon"])

    def test_source_and_seen_at_are_declared(self):
        self.assertIn("baiakidle.com", self.cat.source_of("hunts"))
        self.assertEqual(self.cat.seen_at("hunts"), "2026-09-09")

    def test_raw_charms_match(self):
        self.assertEqual(len(self.cat.raw_charms["dados"]), 24)


class CatalogFailsLoud(unittest.TestCase):
    def test_missing_directory_raises(self):
        with self.assertRaises(catalog.CatalogError):
            catalog.load(helpers.temp_dir() / "nao-existe")

    def test_missing_file_raises(self):
        d = helpers.temp_dir()
        (d / "hunts.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(catalog.CatalogError):
            catalog.load(d)

    def test_validate_reports_wrong_counts(self):
        cat = helpers.real_catalog()
        fake = catalog.Catalog(cat.raw, cat.raw_charms, cat.directory)
        fake.hunts = fake.hunts[:-1]
        problems = catalog.validate(fake)
        self.assertTrue(any("hunts" in p for p in problems), problems)


class Vocations(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(catalog.normalize_vocation("EK"), "knight")
        self.assertEqual(catalog.normalize_vocation(" Elder Druid "), "druid")
        self.assertEqual(catalog.normalize_vocation("monge"), "monk")

    def test_unknown_is_none_not_a_guess(self):
        self.assertIsNone(catalog.normalize_vocation("paladino"))
        self.assertIsNone(catalog.normalize_vocation(""))
        self.assertIsNone(catalog.normalize_vocation(None))


class ChannelNotes(unittest.TestCase):
    def test_every_note_points_to_a_real_hunt(self):
        cat = helpers.real_catalog()
        for hunt_id in notes.HUNT_NOTES:
            self.assertTrue(cat.has_hunt(hunt_id), hunt_id)

    def test_note_carries_its_source(self):
        n = notes.for_hunt("cobra-cave")
        self.assertIn("ICzhKPFcZWE", n["source"])
        self.assertIsNone(notes.for_hunt("troll-cave"))


if __name__ == "__main__":
    unittest.main()
