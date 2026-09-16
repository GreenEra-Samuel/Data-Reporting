"""Selecting several rows at once to delete them.

The dialogs are stubbed out: these tests assert on what the confirmation says
and on what each answer actually does to the database.
"""

import os
import tempfile
import unittest
from unittest import mock

try:
    import tkinter as tk
except ImportError:  # pragma: no cover
    tk = None


def display_available() -> bool:
    if tk is None:
        return False
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


HAVE_DISPLAY = display_available()


@unittest.skipUnless(HAVE_DISPLAY, "no display available")
class MultiSelectTestCase(unittest.TestCase):
    def setUp(self):
        from measurelog.models import Location, Test
        from measurelog.ui.app import MeasureLogApp

        self.folder = tempfile.TemporaryDirectory()
        os.environ["MEASURELOG_DATA_DIR"] = self.folder.name
        self.app = MeasureLogApp()
        self.app.update()

        db = self.app.db
        for location in db.list_locations():
            db.delete_location(location.id)
        for test in db.list_tests():
            db.delete_test(test.id)

        self.locations = [
            db.save_location(Location(name=f"Point {i + 1}", sort_order=i)) for i in range(3)
        ]
        self.tests = [
            db.save_test(Test(name=f"Test {i + 1}", replicates=3, sort_order=i)) for i in range(5)
        ]
        self.run = db.create_run("2026-09-14", "08:00", "Round 1", "Sam")
        self.app.current_run_id = self.run.id
        self.app.notify("setup_changed")
        self.app.notify("runs_changed")

        self.app.notebook.select(self.app.setup_tab)
        self.app.update()
        self.setup = self.app.setup_tab
        self.runs = self.app.runs_tab

    def tearDown(self):
        try:
            self.app.on_close()
        except Exception:
            pass
        os.environ.pop("MEASURELOG_DATA_DIR", None)
        self.folder.cleanup()

    def record(self, test, location=None, values=(1.0, 1.1, 1.2)):
        location = location or self.locations[0]
        for replicate, value in enumerate(values, start=1):
            self.app.db.set_value(self.run.id, location.id, test.id, replicate, value)

    def select(self, tree, ids):
        tree.selection_set([str(i) for i in ids])
        self.app.update()

    def current_test_names(self):
        return [test.name for test in self.app.db.list_tests()]


class SelectionHelperTests(MultiSelectTestCase):
    def test_several_rows_can_be_selected(self):
        self.select(self.setup.test_tree, [t.id for t in self.tests[:3]])
        self.assertEqual(len(self.setup._selected_ids(self.setup.test_tree)), 3)

    def test_selection_comes_back_in_list_order(self):
        chosen = [self.tests[3].id, self.tests[0].id, self.tests[2].id]
        self.select(self.setup.test_tree, chosen)
        self.assertEqual(
            self.setup._selected_ids(self.setup.test_tree),
            [self.tests[0].id, self.tests[2].id, self.tests[3].id],
        )

    def test_ctrl_a_selects_everything(self):
        self.setup._select_all(self.setup.test_tree)
        self.assertEqual(len(self.setup._selected_ids(self.setup.test_tree)), 5)

    def test_single_row_actions_refuse_a_multiple_selection(self):
        self.select(self.setup.test_tree, [t.id for t in self.tests[:2]])
        with mock.patch("measurelog.ui.setup_tab.messagebox") as box:
            self.assertIsNone(self.setup._require_one(self.setup.test_tree, "test"))
            box.showinfo.assert_called_once()
            self.assertIn("2 tests are selected", box.showinfo.call_args[0][1])

    def test_single_row_actions_accept_one(self):
        self.select(self.setup.test_tree, [self.tests[1].id])
        with mock.patch("measurelog.ui.setup_tab.messagebox"):
            self.assertEqual(self.setup._require_one(self.setup.test_tree, "test"),
                             self.tests[1].id)

    def test_editing_with_several_selected_opens_no_dialog(self):
        self.select(self.setup.test_tree, [t.id for t in self.tests[:2]])
        with mock.patch("measurelog.ui.setup_tab.TestDialog") as dialog, \
                mock.patch("measurelog.ui.setup_tab.messagebox"):
            self.setup.edit_test()
            dialog.assert_not_called()


class DeleteTestsTests(MultiSelectTestCase):
    def test_deleting_several_empty_tests_at_once(self):
        self.select(self.setup.test_tree, [t.id for t in self.tests[:3]])
        with mock.patch("measurelog.ui.setup_tab.messagebox") as box:
            box.askyesno.return_value = True
            self.setup.delete_test()
        self.assertEqual(self.current_test_names(), ["Test 4", "Test 5"])

    def test_the_confirmation_lists_what_goes(self):
        self.select(self.setup.test_tree, [t.id for t in self.tests[:2]])
        with mock.patch("measurelog.ui.setup_tab.messagebox") as box:
            box.askyesno.return_value = False
            self.setup.delete_test()
            message = box.askyesno.call_args[0][1]
        self.assertIn("Delete 2 tests?", message)
        self.assertIn("Test 1", message)
        self.assertIn("Test 2", message)
        self.assertEqual(len(self.current_test_names()), 5)      # answered no: nothing deleted

    def test_declining_keeps_everything(self):
        self.select(self.setup.test_tree, [t.id for t in self.tests])
        with mock.patch("measurelog.ui.setup_tab.messagebox") as box:
            box.askyesno.return_value = False
            self.setup.delete_test()
        self.assertEqual(len(self.current_test_names()), 5)

    def test_tests_holding_readings_are_reported_before_anything_happens(self):
        self.record(self.tests[0])
        self.record(self.tests[1], values=(2.0, 2.1))
        self.select(self.setup.test_tree, [t.id for t in self.tests[:3]])
        with mock.patch("measurelog.ui.setup_tab.messagebox") as box:
            box.askyesnocancel.return_value = None        # cancel
            self.setup.delete_test()
            message = box.askyesnocancel.call_args[0][1]
        self.assertIn("2 tests of the 3 selected hold readings", message)
        self.assertIn("5 in total", message)
        self.assertEqual(len(self.current_test_names()), 5)
        self.assertEqual(self.app.db.count_values(), 5)

    def test_keeping_readings_hides_those_tests_and_deletes_the_empty_ones(self):
        self.record(self.tests[0])
        self.select(self.setup.test_tree, [t.id for t in self.tests[:3]])
        with mock.patch("measurelog.ui.setup_tab.messagebox") as box:
            box.askyesnocancel.return_value = True        # yes: keep the readings
            self.setup.delete_test()

        remaining = {test.name: test for test in self.app.db.list_tests()}
        self.assertIn("Test 1", remaining)                # kept, but hidden
        self.assertFalse(remaining["Test 1"].active)
        self.assertNotIn("Test 2", remaining)             # empty, so removed
        self.assertNotIn("Test 3", remaining)
        self.assertEqual(self.app.db.count_values(), 3)   # readings untouched

    def test_deleting_outright_removes_the_readings_too(self):
        self.record(self.tests[0])
        self.select(self.setup.test_tree, [t.id for t in self.tests[:2]])
        with mock.patch("measurelog.ui.setup_tab.messagebox") as box:
            box.askyesnocancel.return_value = False       # no: delete everything
            self.setup.delete_test()
        self.assertEqual(self.current_test_names(), ["Test 3", "Test 4", "Test 5"])
        self.assertEqual(self.app.db.count_values(), 0)

    def test_deleting_with_nothing_selected_says_so(self):
        self.setup.test_tree.selection_remove(self.setup.test_tree.get_children())
        with mock.patch("measurelog.ui.setup_tab.messagebox") as box:
            self.setup.delete_test()
            box.showinfo.assert_called_once()
            box.askyesno.assert_not_called()

    def test_the_entry_grid_follows_the_deletion(self):
        self.select(self.setup.test_tree, [t.id for t in self.tests[:2]])
        with mock.patch("measurelog.ui.setup_tab.messagebox") as box:
            box.askyesno.return_value = True
            self.setup.delete_test()
        self.app.notebook.select(self.app.entry_tab)
        self.app.update()
        self.assertEqual(len(self.app.entry_tab.tests), 3)


class DeleteLocationsTests(MultiSelectTestCase):
    def test_deleting_several_locations(self):
        self.select(self.setup.location_tree, [l.id for l in self.locations[:2]])
        with mock.patch("measurelog.ui.setup_tab.messagebox") as box:
            box.askyesno.return_value = True
            self.setup.delete_location()
        self.assertEqual([l.name for l in self.app.db.list_locations()], ["Point 3"])

    def test_a_location_with_readings_can_be_hidden_instead(self):
        self.record(self.tests[0], location=self.locations[0])
        self.select(self.setup.location_tree, [l.id for l in self.locations[:2]])
        with mock.patch("measurelog.ui.setup_tab.messagebox") as box:
            box.askyesnocancel.return_value = True
            self.setup.delete_location()

        remaining = {l.name: l for l in self.app.db.list_locations()}
        self.assertFalse(remaining["Point 1"].active)
        self.assertNotIn("Point 2", remaining)
        self.assertEqual(self.app.db.count_values(), 3)


class DeleteRunsTests(MultiSelectTestCase):
    def make_runs(self, count=3):
        extra = [self.app.db.create_run(f"2026-09-{10 + i}", "08:00", f"Round {i}")
                 for i in range(count)]
        self.app.notify("runs_changed")
        self.app.notebook.select(self.app.runs_tab)
        self.app.update()
        return extra

    def test_deleting_several_runs_at_once(self):
        self.make_runs(3)
        ids = [run.id for run in self.app.db.list_runs()][:2]
        self.select(self.runs.tree, ids)
        with mock.patch("measurelog.ui.runs_tab.messagebox") as box:
            box.askyesno.return_value = True
            self.runs.delete_selected()
        remaining = {run.id for run in self.app.db.list_runs()}
        self.assertFalse(set(ids) & remaining)
        self.assertEqual(len(remaining), 2)

    def test_the_confirmation_counts_the_readings_at_risk(self):
        self.record(self.tests[0])
        self.make_runs(1)
        self.select(self.runs.tree, [run.id for run in self.app.db.list_runs()])
        with mock.patch("measurelog.ui.runs_tab.messagebox") as box:
            box.askyesno.return_value = False
            self.runs.delete_selected()
            message = box.askyesno.call_args[0][1]
        self.assertIn("Delete these 2 runs?", message)
        self.assertIn("3 reading(s) will be deleted", message)
        self.assertEqual(len(self.app.db.list_runs()), 2)

    def test_deleting_runs_removes_their_readings(self):
        self.record(self.tests[0])
        self.make_runs(1)
        self.select(self.runs.tree, [self.run.id])
        with mock.patch("measurelog.ui.runs_tab.messagebox") as box:
            box.askyesno.return_value = True
            self.runs.delete_selected()
        self.assertEqual(self.app.db.count_values(), 0)

    def test_deleting_the_open_run_clears_the_entry_screen(self):
        self.make_runs(1)
        self.select(self.runs.tree, [self.run.id])
        with mock.patch("measurelog.ui.runs_tab.messagebox") as box:
            box.askyesno.return_value = True
            self.runs.delete_selected()
        self.assertNotEqual(self.app.current_run_id, self.run.id)

    def test_single_run_wording_stays_singular(self):
        self.make_runs(1)
        self.select(self.runs.tree, [self.run.id])
        with mock.patch("measurelog.ui.runs_tab.messagebox") as box:
            box.askyesno.return_value = False
            self.runs.delete_selected()
            message = box.askyesno.call_args[0][1]
        self.assertIn("Delete the run on", message)

    def test_opening_refuses_a_multiple_selection(self):
        self.make_runs(2)
        self.select(self.runs.tree, [run.id for run in self.app.db.list_runs()][:2])
        with mock.patch("measurelog.ui.runs_tab.messagebox") as box:
            self.runs.open_selected()
            box.showinfo.assert_called_once()
            self.assertIn("2 runs are selected", box.showinfo.call_args[0][1])


if __name__ == "__main__":
    unittest.main()
