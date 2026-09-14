"""The SOP test library, and the schema migration that supports it."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from measurelog import catalog
from measurelog.db import SCHEMA_VERSION, Database
from measurelog.models import Test

V1_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE location (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
  code TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE test (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
  code TEXT NOT NULL DEFAULT '', unit TEXT NOT NULL DEFAULT '', decimals INTEGER NOT NULL DEFAULT 2,
  lower_limit REAL, upper_limit REAL, replicates INTEGER NOT NULL DEFAULT 3,
  sort_order INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE run (id INTEGER PRIMARY KEY AUTOINCREMENT, run_date TEXT NOT NULL,
  run_time TEXT NOT NULL DEFAULT '', label TEXT NOT NULL DEFAULT '',
  operator TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE measurement (id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES run(id) ON DELETE CASCADE,
  location_id INTEGER NOT NULL REFERENCES location(id) ON DELETE CASCADE,
  test_id INTEGER NOT NULL REFERENCES test(id) ON DELETE CASCADE,
  replicate INTEGER NOT NULL, value REAL, note TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL, UNIQUE (run_id, location_id, test_id, replicate));
INSERT INTO meta VALUES ('schema_version', '1');
INSERT INTO location (name) VALUES ('Digester 1');
INSERT INTO test (name, unit, decimals, replicates) VALUES ('pH', '', 2, 3);
INSERT INTO run (run_date, created_at, updated_at) VALUES ('2026-09-10', 'x', 'x');
INSERT INTO measurement (run_id, location_id, test_id, replicate, value, updated_at)
  VALUES (1, 1, 1, 1, 7.04, 'x'), (1, 1, 1, 2, 7.06, 'x'), (1, 1, 1, 3, 7.02, 'x');
"""


class CatalogContentTests(unittest.TestCase):
    def test_every_sop_test_is_present(self):
        names = [test.name for test in catalog.TESTS]
        for expected in ("pH", "Total Solids (TS)", "Total Volatile Solids (TVS)",
                         "Moisture Content", "Chemical Oxygen Demand (COD)", "Density",
                         "Total Organic Carbon (TOC)", "Total Inorganic Carbon (TIC)",
                         "Total Carbon (TC)", "Total Nitrogen (TN)", "Alkalinity",
                         "Volatile Fatty Acids (VFAs)", "Ammonia (NH3-N / TAN)",
                         "Conductivity (EC)"):
            self.assertIn(expected, names)

    def test_names_and_codes_are_unique(self):
        names = [test.name for test in catalog.TESTS]
        codes = [test.code for test in catalog.TESTS]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(codes), len(set(codes)))

    def test_units_match_the_sop_summary_matrix(self):
        units = {test.name: test.unit for test in catalog.TESTS}
        self.assertEqual(units["Chemical Oxygen Demand (COD)"], "mg/L")
        self.assertEqual(units["Alkalinity"], "mg CaCO3/L")
        self.assertEqual(units["Total Nitrogen (TN)"], "mg N/L")
        self.assertEqual(units["Ammonia (NH3-N / TAN)"], "mg NH3-N/L")
        self.assertEqual(units["Conductivity (EC)"], "mS/cm")
        self.assertEqual(units["Density"], "g/mL")
        # pH is dimensionless: a unit here would render as "pH (pH)" in the grid.
        self.assertEqual(units["pH"], "")

    def test_the_sops_call_for_triplicates_throughout(self):
        for test in catalog.TESTS:
            self.assertEqual(test.replicates, 3, test.name)

    def test_ph_carries_the_two_percent_rsd_rule_from_its_qc_section(self):
        self.assertEqual(catalog.by_name("pH").rsd_limit, 2.0)

    def test_every_entry_has_a_method_and_sensible_precision(self):
        for test in catalog.TESTS:
            self.assertTrue(test.method, test.name)
            self.assertGreaterEqual(test.decimals, 0)
            self.assertLessEqual(test.decimals, 8)

    def test_grouping_covers_every_test_exactly_once(self):
        grouped = [test for _, members in catalog.grouped() for test in members]
        self.assertEqual(len(grouped), len(catalog.TESTS))
        self.assertEqual({t.name for t in grouped}, {t.name for t in catalog.TESTS})

    def test_lookup_by_name_is_case_insensitive(self):
        self.assertIsNotNone(catalog.by_name("ph"))
        self.assertIsNotNone(catalog.by_name("  Alkalinity "))
        self.assertIsNone(catalog.by_name("Not a test"))

    def test_sampling_points_come_from_the_sops(self):
        self.assertEqual(
            [location.name for location in catalog.default_locations()],
            ["Influent", "Digester 1", "Digester 2", "Effluent"],
        )


class CatalogToTestTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.folder.name) / "t.db")

    def tearDown(self):
        self.db.close()
        self.folder.cleanup()

    def test_conversion_carries_the_sop_details(self):
        entry = catalog.by_name("pH")
        test = entry.to_test()
        self.assertEqual(test.name, "pH")
        self.assertEqual(test.replicates, 3)
        self.assertEqual(test.rsd_limit, 2.0)
        self.assertIn("Method:", test.notes)
        self.assertIsNone(test.id)

    def test_every_entry_saves_to_the_database(self):
        for entry in catalog.TESTS:
            self.db.save_test(entry.to_test())
        self.assertEqual(len(self.db.list_tests()), len(catalog.TESTS))

    def test_saved_entries_keep_their_rsd_limit_and_notes(self):
        self.db.save_test(catalog.by_name("pH").to_test())
        stored = self.db.list_tests()[0]
        self.assertEqual(stored.rsd_limit, 2.0)
        self.assertIn("4.01", stored.notes)

    def test_added_tests_stay_editable(self):
        test = self.db.save_test(catalog.by_name("Alkalinity").to_test())
        test.unit = "meq/L"
        test.rsd_limit = None
        self.db.save_test(test)
        stored = self.db.get_test(test.id)
        self.assertEqual(stored.unit, "meq/L")
        self.assertIsNone(stored.rsd_limit)

    def test_adding_the_same_test_twice_is_rejected(self):
        self.db.save_test(catalog.by_name("Density").to_test())
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.save_test(catalog.by_name("Density").to_test())


class MigrationTests(unittest.TestCase):
    """A database written by v1.0.0 must open without losing anything."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "old.db"
        connection = sqlite3.connect(self.path)
        connection.executescript(V1_SCHEMA)
        connection.commit()
        connection.close()

    def tearDown(self):
        self.folder.cleanup()

    def test_opening_an_old_database_upgrades_it(self):
        db = Database(self.path)
        self.assertEqual(db.get_setting("schema_version"), str(SCHEMA_VERSION))
        db.close()

    def test_existing_measurements_survive(self):
        db = Database(self.path)
        self.assertEqual(db.count_values(), 3)
        self.assertEqual(len(db.fetch_long_rows()), 3)
        self.assertEqual(db.list_tests()[0].name, "pH")
        db.close()

    def test_new_columns_default_to_empty(self):
        db = Database(self.path)
        test = db.list_tests()[0]
        self.assertIsNone(test.rsd_limit)
        self.assertEqual(test.notes, "")
        db.close()

    def test_new_columns_are_writable_after_migration(self):
        db = Database(self.path)
        test = db.list_tests()[0]
        test.rsd_limit = 2.0
        test.notes = "from the SOP"
        db.save_test(test)
        db.close()

        reopened = Database(self.path)
        stored = reopened.list_tests()[0]
        self.assertEqual(stored.rsd_limit, 2.0)
        self.assertEqual(stored.notes, "from the SOP")
        reopened.close()

    def test_migration_is_idempotent(self):
        for _ in range(3):
            db = Database(self.path)
            db.close()
        db = Database(self.path)
        self.assertEqual(db.count_values(), 3)
        self.assertEqual(len(db.list_tests()), 1)
        db.close()

    def test_an_old_database_can_take_catalogue_tests(self):
        db = Database(self.path)
        db.save_test(catalog.by_name("Alkalinity").to_test())
        self.assertEqual(len(db.list_tests()), 2)
        self.assertEqual(db.count_values(), 3)
        db.close()


class TestModelDefaults(unittest.TestCase):
    def test_a_plain_test_has_no_rsd_limit_or_notes(self):
        test = Test(name="Plain")
        self.assertIsNone(test.rsd_limit)
        self.assertEqual(test.notes, "")


if __name__ == "__main__":
    unittest.main()
