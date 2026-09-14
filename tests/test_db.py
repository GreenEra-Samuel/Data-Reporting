import tempfile
import unittest
from pathlib import Path

from measurelog.db import Database
from measurelog.models import Location, Test


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.folder.name) / "test.db")

    def tearDown(self):
        self.db.close()
        self.folder.cleanup()

    def make_setup(self, locations=2, tests=2, replicates=3):
        self.locations = [
            self.db.save_location(Location(name=f"Loc {i}", code=f"L{i}", sort_order=i))
            for i in range(locations)
        ]
        self.tests = [
            self.db.save_test(Test(name=f"Test {i}", unit="mg/L", replicates=replicates,
                                   sort_order=i))
            for i in range(tests)
        ]


class SetupTests(DatabaseTestCase):
    def test_seed_defaults_only_runs_on_an_empty_database(self):
        self.assertTrue(self.db.seed_defaults())
        self.assertFalse(self.db.seed_defaults())
        self.assertEqual(len(self.db.list_locations()), 4)

    def test_seed_uses_the_sampling_points_from_the_sops(self):
        self.db.seed_defaults()
        self.assertEqual(
            [location.name for location in self.db.list_locations()],
            ["Influent", "Digester 1", "Digester 2", "Effluent"],
        )

    def test_seed_creates_no_placeholder_tests(self):
        # The SOP library is a better first step than deleting invented tests.
        self.db.seed_defaults()
        self.assertEqual(self.db.list_tests(), [])

    def test_seed_is_skipped_when_tests_already_exist(self):
        self.db.save_test(Test(name="Only test"))
        self.assertFalse(self.db.seed_defaults())
        self.assertEqual(self.db.list_locations(), [])

    def test_duplicate_names_are_rejected(self):
        self.db.save_location(Location(name="Tank A"))
        with self.assertRaises(Exception):
            self.db.save_location(Location(name="Tank A"))

    def test_active_only_filter(self):
        self.db.save_location(Location(name="On"))
        self.db.save_location(Location(name="Off", active=False))
        self.assertEqual(len(self.db.list_locations()), 2)
        self.assertEqual(len(self.db.list_locations(active_only=True)), 1)

    def test_reordering_swaps_neighbours(self):
        self.make_setup(locations=3, tests=0)
        third = self.locations[2]
        self.db.move_location(third.id, -1)
        self.assertEqual([l.name for l in self.db.list_locations()], ["Loc 0", "Loc 2", "Loc 1"])
        self.db.move_location(third.id, -1)
        self.assertEqual([l.name for l in self.db.list_locations()], ["Loc 2", "Loc 0", "Loc 1"])

    def test_reordering_past_the_end_does_nothing(self):
        self.make_setup(locations=2, tests=0)
        self.db.move_location(self.locations[0].id, -1)
        self.assertEqual([l.name for l in self.db.list_locations()], ["Loc 0", "Loc 1"])

    def test_settings_round_trip(self):
        self.db.set_setting("default_replicates", "4")
        self.assertEqual(self.db.get_int_setting("default_replicates", 3), 4)
        self.db.set_setting("default_replicates", "not a number")
        self.assertEqual(self.db.get_int_setting("default_replicates", 3), 3)


class MeasurementTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.make_setup()
        self.run = self.db.create_run("2026-09-14", "08:00", "Round 1", "Sam")

    def test_store_and_read_back(self):
        location, test = self.locations[0], self.tests[0]
        for replicate, value in enumerate([7.01, 7.03, 6.99], start=1):
            self.db.set_value(self.run.id, location.id, test.id, replicate, value)
        values = self.db.get_run_values(self.run.id)
        self.assertEqual(len(values), 3)
        self.assertAlmostEqual(values[(location.id, test.id, 2)].value, 7.03)

    def test_writing_the_same_cell_twice_updates_it(self):
        location, test = self.locations[0], self.tests[0]
        self.db.set_value(self.run.id, location.id, test.id, 1, 1.0)
        self.db.set_value(self.run.id, location.id, test.id, 1, 2.0)
        self.assertEqual(self.db.count_values(run_id=self.run.id), 1)
        self.assertEqual(self.db.get_run_values(self.run.id)[(location.id, test.id, 1)].value, 2.0)

    def test_blanking_a_cell_removes_it(self):
        location, test = self.locations[0], self.tests[0]
        self.db.set_value(self.run.id, location.id, test.id, 1, 5.0)
        self.db.set_value(self.run.id, location.id, test.id, 1, None)
        self.assertEqual(self.db.count_values(run_id=self.run.id), 0)

    def test_a_note_survives_a_blank_value(self):
        location, test = self.locations[0], self.tests[0]
        self.db.set_value(self.run.id, location.id, test.id, 1, None, "sample lost")
        stored = self.db.get_run_values(self.run.id)[(location.id, test.id, 1)]
        self.assertIsNone(stored.value)
        self.assertEqual(stored.note, "sample lost")

    def test_counts_by_scope(self):
        for location in self.locations:
            for test in self.tests:
                self.db.set_value(self.run.id, location.id, test.id, 1, 1.0)
        self.assertEqual(self.db.count_values(run_id=self.run.id), 4)
        self.assertEqual(self.db.count_values(location_id=self.locations[0].id), 2)
        self.assertEqual(self.db.count_values(test_id=self.tests[0].id), 2)

    def test_clear_location_leaves_other_locations_alone(self):
        for location in self.locations:
            self.db.set_value(self.run.id, location.id, self.tests[0].id, 1, 1.0)
        self.db.clear_location_values(self.run.id, self.locations[0].id)
        self.assertEqual(self.db.count_values(run_id=self.run.id), 1)

    def test_deleting_a_run_deletes_its_measurements(self):
        self.db.set_value(self.run.id, self.locations[0].id, self.tests[0].id, 1, 1.0)
        self.db.delete_run(self.run.id)
        self.assertEqual(self.db.count_values(), 0)

    def test_deleting_a_test_deletes_its_measurements(self):
        self.db.set_value(self.run.id, self.locations[0].id, self.tests[0].id, 1, 1.0)
        self.db.delete_test(self.tests[0].id)
        self.assertEqual(self.db.count_values(), 0)


class RunTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.make_setup()

    def test_runs_come_back_newest_first(self):
        self.db.create_run("2026-09-10", "08:00")
        self.db.create_run("2026-09-14", "08:00")
        self.db.create_run("2026-09-14", "13:00")
        self.assertEqual(
            [(r.run_date, r.run_time) for r in self.db.list_runs()],
            [("2026-09-14", "13:00"), ("2026-09-14", "08:00"), ("2026-09-10", "08:00")],
        )

    def test_value_count_is_reported_per_run(self):
        run = self.db.create_run("2026-09-14")
        self.db.set_value(run.id, self.locations[0].id, self.tests[0].id, 1, 1.0)
        self.assertEqual(self.db.list_runs()[0].value_count, 1)

    def test_date_filtering(self):
        self.db.create_run("2026-09-01")
        self.db.create_run("2026-09-14")
        self.assertEqual(len(self.db.list_runs(date_from="2026-09-10")), 1)
        self.assertEqual(len(self.db.list_runs(date_to="2026-09-10")), 1)

    def test_previous_run_walks_backwards_in_time(self):
        first = self.db.create_run("2026-09-14", "08:00")
        second = self.db.create_run("2026-09-14", "13:00")
        self.assertEqual(self.db.previous_run_id(second.id), first.id)
        self.assertIsNone(self.db.previous_run_id(first.id))

    def test_duplicate_run_without_values(self):
        source = self.db.create_run("2026-09-14", "08:00", "Round 1", "Sam", "notes")
        self.db.set_value(source.id, self.locations[0].id, self.tests[0].id, 1, 1.0)
        copy = self.db.duplicate_run(source.id, "2026-09-15")
        self.assertEqual(copy.operator, "Sam")
        self.assertEqual(copy.notes, "notes")
        self.assertEqual(self.db.count_values(run_id=copy.id), 0)

    def test_duplicate_run_with_values(self):
        source = self.db.create_run("2026-09-14")
        self.db.set_value(source.id, self.locations[0].id, self.tests[0].id, 1, 1.0)
        copy = self.db.duplicate_run(source.id, "2026-09-15", copy_values=True)
        self.assertEqual(self.db.count_values(run_id=copy.id), 1)

    def test_copy_values_overwrites_the_target_cells(self):
        source = self.db.create_run("2026-09-14")
        target = self.db.create_run("2026-09-15")
        location, test = self.locations[0], self.tests[0]
        self.db.set_value(source.id, location.id, test.id, 1, 1.0)
        self.db.set_value(target.id, location.id, test.id, 1, 99.0)
        self.db.copy_values_from_run(source.id, target.id)
        self.assertEqual(self.db.get_run_values(target.id)[(location.id, test.id, 1)].value, 1.0)
        self.assertEqual(self.db.count_values(run_id=target.id), 1)

    def test_copy_values_can_be_limited_to_one_location(self):
        source = self.db.create_run("2026-09-14")
        target = self.db.create_run("2026-09-15")
        for location in self.locations:
            self.db.set_value(source.id, location.id, self.tests[0].id, 1, 1.0)
        self.db.copy_values_from_run(source.id, target.id, self.locations[0].id)
        self.assertEqual(self.db.count_values(run_id=target.id), 1)

    def test_date_bounds(self):
        self.assertEqual(self.db.date_bounds(), (None, None))
        self.db.create_run("2026-09-01")
        self.db.create_run("2026-09-14")
        self.assertEqual(self.db.date_bounds(), ("2026-09-01", "2026-09-14"))


class LongRowTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.make_setup(locations=2, tests=2)
        self.run = self.db.create_run("2026-09-14", "08:00", "Round 1", "Sam")
        for location in self.locations:
            for test in self.tests:
                for replicate in (1, 2, 3):
                    self.db.set_value(self.run.id, location.id, test.id, replicate, 5.0)

    def test_every_replicate_becomes_a_row(self):
        self.assertEqual(len(self.db.fetch_long_rows()), 2 * 2 * 3)

    def test_blank_cells_are_excluded_unless_asked_for(self):
        self.db.set_value(self.run.id, self.locations[0].id, self.tests[0].id, 1, None, "spill")
        self.assertEqual(len(self.db.fetch_long_rows()), 11)
        self.assertEqual(len(self.db.fetch_long_rows(include_blank=True)), 12)

    def test_rows_carry_context_for_export(self):
        row = self.db.fetch_long_rows()[0]
        self.assertEqual(row.run_date, "2026-09-14")
        self.assertEqual(row.operator, "Sam")
        self.assertEqual(row.unit, "mg/L")
        self.assertTrue(row.location.startswith("Loc"))

    def test_run_id_filter(self):
        other = self.db.create_run("2026-09-15")
        self.db.set_value(other.id, self.locations[0].id, self.tests[0].id, 1, 1.0)
        self.assertEqual(len(self.db.fetch_long_rows(run_ids=[other.id])), 1)


if __name__ == "__main__":
    unittest.main()
