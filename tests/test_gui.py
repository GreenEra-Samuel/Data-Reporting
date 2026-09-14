"""End-to-end checks that drive the real Tk widgets.

Skipped automatically when there is no display (a plain CI shell), so the rest
of the suite still runs. On Linux, `xvfb-run python -m unittest` exercises these.
"""

import os
import tempfile
import unittest

try:
    import tkinter as tk
    TK_IMPORT_ERROR = None
except ImportError as error:  # pragma: no cover
    tk = None
    TK_IMPORT_ERROR = str(error)


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


@unittest.skipUnless(HAVE_DISPLAY, f"no display available ({TK_IMPORT_ERROR or 'no X server'})")
class AppTests(unittest.TestCase):
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
            db.save_location(Location(name=f"Location {i + 1}", code=f"L{i + 1}", sort_order=i))
            for i in range(6)
        ]
        self.tests = [
            db.save_test(Test(name=f"Test {i + 1}", unit="mg/L", decimals=2, replicates=3,
                              lower_limit=1.0, upper_limit=10.0, sort_order=i))
            for i in range(20)
        ]
        self.run = db.create_run("2026-09-14", "08:00", "Round 1", "Sam")
        self.app.current_run_id = self.run.id
        self.app.notify("setup_changed")
        self.app.notify("runs_changed")
        self.app.update()
        self.entry = self.app.entry_tab

    def tearDown(self):
        try:
            self.app.on_close()
        except Exception:
            pass
        os.environ.pop("MEASURELOG_DATA_DIR", None)
        self.folder.cleanup()

    def focused_widget(self):
        """Which widget holds the keyboard focus inside the app window.

        Tk's focus_get() returns None whenever the application does not own the
        operating system's input focus - which is the normal state for a CI
        desktop - so ask the toplevel instead, which reports the widget that
        holds focus either way.
        """
        return self.app.focus_lastfor()

    def type_into(self, test, replicate, text):
        cell = self.entry.cells[(test.id, replicate)]
        cell["var"].set(text)
        self.entry.commit(cell)
        return cell

    # ------------------------------------------------------------- the grid

    def test_grid_has_a_cell_for_every_test_and_replicate(self):
        self.assertEqual(len(self.entry.cells), 20 * 3)

    def test_grid_covers_six_locations(self):
        self.assertEqual(len(self.entry.locations), 6)

    def test_typing_a_value_saves_it_immediately(self):
        self.type_into(self.tests[0], 1, "7.01")
        self.assertEqual(self.app.db.count_values(run_id=self.run.id), 1)

    def test_values_are_stored_against_the_selected_location(self):
        self.entry.select_location(self.locations[2].id)
        self.app.update()
        self.type_into(self.tests[0], 1, "5")
        self.assertEqual(
            self.app.db.count_values(run_id=self.run.id, location_id=self.locations[2].id), 1)
        self.assertEqual(
            self.app.db.count_values(run_id=self.run.id, location_id=self.locations[0].id), 0)

    def test_statistics_appear_as_you_type(self):
        for replicate, value in enumerate(["7.01", "7.03", "6.99"], start=1):
            self.type_into(self.tests[0], replicate, value)
        labels = self.entry.rows[self.tests[0].id]["stats"]
        self.assertEqual(labels["mean"].cget("text"), "7.01")
        self.assertEqual(labels["sd"].cget("text"), "0.020")
        self.assertEqual(labels["rsd"].cget("text"), "0.29")

    def test_partial_entry_reports_progress(self):
        self.type_into(self.tests[0], 1, "5")
        self.assertEqual(self.entry.rows[self.tests[0].id]["stats"]["status"].cget("text"),
                         "1 of 3")

    def test_value_outside_the_limits_is_flagged(self):
        self.type_into(self.tests[0], 1, "99")
        self.assertEqual(self.entry.rows[self.tests[0].id]["stats"]["status"].cget("text"),
                         "Above limit")

    def test_value_below_the_limits_is_flagged(self):
        self.type_into(self.tests[0], 1, "0.2")
        self.assertEqual(self.entry.rows[self.tests[0].id]["stats"]["status"].cget("text"),
                         "Below limit")

    def test_noisy_replicates_are_flagged(self):
        for replicate, value in enumerate(["5", "5.01", "9"], start=1):
            self.type_into(self.tests[0], replicate, value)
        self.assertEqual(self.entry.rows[self.tests[0].id]["stats"]["status"].cget("text"),
                         "Check spread")

    def test_unreadable_input_restores_the_saved_value_without_a_dialog(self):
        self.type_into(self.tests[0], 1, "7.01")
        cell = self.entry.cells[(self.tests[0].id, 1)]
        cell["var"].set("-")
        self.assertFalse(self.entry.commit(cell))
        self.assertEqual(cell["var"].get(), "7.01")
        self.assertIn("not a number", self.entry.status_var.get())

    def test_clearing_a_cell_removes_the_reading(self):
        self.type_into(self.tests[0], 1, "7.01")
        self.entry._clear_cell(self.entry.cells[(self.tests[0].id, 1)])
        self.assertEqual(self.app.db.count_values(run_id=self.run.id), 0)

    def test_values_survive_a_location_round_trip(self):
        self.type_into(self.tests[0], 1, "7.01")
        self.entry.select_location(self.locations[1].id)
        self.entry.select_location(self.locations[0].id)
        self.app.update()
        self.assertEqual(self.entry.cells[(self.tests[0].id, 1)]["var"].get(), "7.01")

    def test_values_are_redisplayed_with_the_test_decimals(self):
        self.type_into(self.tests[0], 1, "7")
        self.assertEqual(self.entry.cells[(self.tests[0].id, 1)]["var"].get(), "7.00")

    # ------------------------------------------------------------ navigation

    def test_enter_moves_down_the_column(self):
        self.entry.focus_first_cell()
        self.app.update()
        self.entry._navigate(self.entry.cells[(self.tests[0].id, 1)], 1, 0)
        self.assertIs(self.focused_widget(), self.entry.cells[(self.tests[1].id, 1)]["entry"])

    def test_navigating_past_the_last_row_stays_put(self):
        last = self.entry.cells[(self.tests[-1].id, 1)]
        last["entry"].focus_set()
        self.app.update()
        self.entry._navigate(last, 1, 0)
        self.assertIs(self.focused_widget(), last["entry"])

    def test_navigation_skips_tests_with_fewer_replicates(self):
        from measurelog.models import Test

        short = self.app.db.save_test(Test(name="Two only", replicates=2, sort_order=1))
        self.app.notify("setup_changed")
        self.app.update()

        # Column 3 exists for test 1 but not for the two-replicate test below it,
        # so moving down from it must land on the next test that has a column 3.
        start = self.entry.cells[(self.tests[0].id, 3)]
        start["entry"].focus_set()
        self.app.update()
        self.entry._navigate(start, 1, 0)
        self.assertNotIn((short.id, 3), self.entry.cells)
        self.assertIs(self.focused_widget(), self.entry.cells[(self.tests[1].id, 3)]["entry"])

    def test_next_location_cycles_round(self):
        self.entry.select_location(self.locations[-1].id)
        self.entry.next_location()
        self.assertEqual(self.entry.location_id, self.locations[0].id)

    # ---------------------------------------------------------------- tabs

    def test_every_tab_renders(self):
        for index in range(5):
            self.app.notebook.select(index)
            self.app.update()
        self.assertEqual(len(self.app.notebook.tabs()), 5)

    def test_review_matrix_reports_the_readings(self):
        for replicate, value in enumerate(["7.01", "7.03", "6.99"], start=1):
            self.type_into(self.tests[0], replicate, value)
        self.app.notebook.select(2)
        self.app.update()
        self.assertIn("3 reading(s)", self.app.review_tab.summary_var.get())

    def test_review_views_all_draw(self):
        self.type_into(self.tests[0], 1, "7.01")
        self.app.notebook.select(2)
        for _, view in [("", "mean"), ("", "mean_sd"), ("", "rsd"), ("", "values"), ("", "span")]:
            self.app.review_tab.view_var.set(view)
            self.app.review_tab.draw()
            self.app.update()

    def test_runs_tab_lists_the_run(self):
        self.app.notebook.select(1)
        self.app.update()
        self.assertIn(str(self.run.id), self.app.runs_tab.tree.get_children())

    def test_export_tab_describes_the_data(self):
        self.type_into(self.tests[0], 1, "7.01")
        self.app.notebook.select(3)
        self.app.update()
        self.assertIn("1 measurements", self.app.export_tab.summary_var.get())

    def test_setup_tab_lists_locations_and_tests(self):
        self.app.notebook.select(4)
        self.app.update()
        self.assertEqual(len(self.app.setup_tab.location_tree.get_children()), 6)
        self.assertEqual(len(self.app.setup_tab.test_tree.get_children()), 20)

    def test_setup_tab_reading_counts_follow_new_data(self):
        self.app.notebook.select(4)
        self.app.update()
        readings = self.app.setup_tab.test_tree.item(str(self.tests[0].id))["values"][-1]
        self.assertEqual(int(readings), 0)

        self.app.notebook.select(0)
        self.type_into(self.tests[0], 1, "7.01")
        self.app.notebook.select(4)
        self.app.update()
        readings = self.app.setup_tab.test_tree.item(str(self.tests[0].id))["values"][-1]
        self.assertEqual(int(readings), 1)

    # -------------------------------------------------------------- actions

    def test_repeat_run_starts_an_empty_round(self):
        self.type_into(self.tests[0], 1, "7.01")
        self.entry.repeat_run()
        self.app.update()
        self.assertEqual(len(self.app.db.list_runs()), 2)
        self.assertEqual(self.app.db.count_values(run_id=self.app.current_run_id), 0)

    def test_repeat_run_keeps_the_operator(self):
        self.entry.repeat_run()
        self.assertEqual(self.app.db.get_run(self.app.current_run_id).operator, "Sam")

    def test_suggested_label_counts_todays_rounds(self):
        label = self.app.suggest_run_label()
        self.assertTrue(label.startswith("Round "))

    def test_setup_changes_rebuild_the_grid(self):
        from measurelog.models import Test

        self.app.db.save_test(Test(name="Extra test", replicates=2, sort_order=99))
        self.app.notify("setup_changed")
        self.app.update()
        self.assertEqual(len(self.entry.tests), 21)

    def test_deactivating_a_test_hides_it_from_entry(self):
        test = self.tests[0]
        test.active = False
        self.app.db.save_test(test)
        self.app.notify("setup_changed")
        self.app.update()
        self.assertNotIn(test.id, self.entry.rows)

    def test_preferences_persist(self):
        self.app.db.set_setting("rsd_warning", "2.5")
        self.app.refresh_settings()
        self.assertEqual(self.app.rsd_warning, 2.5)
        self.app.db.set_setting("rsd_warning", "")
        self.app.refresh_settings()
        self.assertIsNone(self.app.rsd_warning)


@unittest.skipUnless(HAVE_DISPLAY, "no display available")
class ScrollFrameTests(unittest.TestCase):
    """The grids rely on scrollbars appearing only when they are needed."""

    def setUp(self):
        from measurelog.ui import theme, widgets

        self.root = tk.Tk()
        theme.apply(self.root)
        self.root.geometry("400x300")
        self.scroller = widgets.ScrollFrame(self.root)
        self.scroller.pack(fill="both", expand=True)
        self.settle()

    def tearDown(self):
        self.root.destroy()

    def settle(self):
        for _ in range(5):
            self.root.update()

    def fill(self, rows: int, columns: int) -> None:
        for child in self.scroller.body.winfo_children():
            child.destroy()
        for row in range(rows):
            for column in range(columns):
                tk.Label(self.scroller.body, text=f"r{row}c{column}", width=12).grid(
                    row=row, column=column)
        self.settle()

    def test_small_content_hides_both_scrollbars(self):
        self.fill(rows=2, columns=1)
        self.assertFalse(self.scroller.vbar.winfo_ismapped())
        self.assertFalse(self.scroller.hbar.winfo_ismapped())

    def test_tall_content_shows_the_vertical_scrollbar(self):
        self.fill(rows=80, columns=1)
        self.assertTrue(self.scroller.vbar.winfo_ismapped())

    def test_wide_content_shows_the_horizontal_scrollbar(self):
        self.fill(rows=2, columns=12)
        self.assertTrue(self.scroller.hbar.winfo_ismapped())

    def test_scrollbars_go_away_again(self):
        self.fill(rows=80, columns=12)
        self.assertTrue(self.scroller.vbar.winfo_ismapped())
        self.fill(rows=1, columns=1)
        self.assertFalse(self.scroller.vbar.winfo_ismapped())
        self.assertFalse(self.scroller.hbar.winfo_ismapped())


if __name__ == "__main__":
    unittest.main()
