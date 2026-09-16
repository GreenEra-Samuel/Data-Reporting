"""Interface tests for the file browser, the Files tab and the import dialog.

Skipped automatically when there is no display, like the other interface tests.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_gui import HAVE_DISPLAY, TK_IMPORT_ERROR


@unittest.skipUnless(HAVE_DISPLAY, f"no display available ({TK_IMPORT_ERROR or 'no X server'})")
class FileBrowserTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk

        from measurelog.ui import theme

        self.folder = tempfile.TemporaryDirectory()
        self.root_path = Path(self.folder.name)
        (self.root_path / "sub").mkdir()
        (self.root_path / "sub" / "deep.csv").write_text("a\n")
        (self.root_path / "readings.csv").write_text("Location,Test,Value\nInfluent,pH,7\n")
        (self.root_path / "photo.jpg").write_bytes(b"\xff\xd8\xff")
        (self.root_path / "notes.pdf").write_bytes(b"%PDF-1.4")

        self.window = tk.Tk()
        theme.apply(self.window)
        self.activated = []
        self.selected = []

    def tearDown(self):
        try:
            self.window.destroy()
        except Exception:
            pass
        self.folder.cleanup()

    def browser(self, **kwargs):
        from measurelog.ui.browser import FileBrowser

        widget = FileBrowser(self.window, start=self.root_path,
                             on_activate=self.activated.append,
                             on_selection=self.selected.append, **kwargs)
        widget.pack(fill="both", expand=True)
        self.window.update()
        return widget

    def names(self, widget):
        return [widget.tree.set(item, "name") for item in widget.tree.get_children()]

    def item_for(self, widget, name):
        return next(item for item in widget.tree.get_children()
                    if widget.tree.set(item, "name") == name)

    def test_it_opens_in_the_folder_it_was_given(self):
        widget = self.browser()
        self.assertEqual(widget.folder, self.root_path)
        self.assertEqual(widget.path_var.get(), str(self.root_path))

    def test_an_unreadable_start_falls_back_to_somewhere_that_exists(self):
        from measurelog.ui.browser import FileBrowser

        widget = FileBrowser(self.window, start=self.root_path / "not-here")
        self.assertTrue(widget.folder.is_dir())

    def test_it_shows_the_files_the_importer_can_read_first_of_all(self):
        widget = self.browser()
        self.assertEqual(self.names(widget), ["sub", "readings.csv"])
        self.assertIn("1 folder", widget.status_var.get())

    def test_the_filter_changes_what_is_listed_but_never_hides_folders(self):
        widget = self.browser()
        widget.filter_var.set("Photos and images")
        widget.refresh()
        self.assertEqual(self.names(widget), ["sub", "photo.jpg"])

        widget.filter_var.set("All files")
        widget.refresh()
        self.assertEqual(self.names(widget), ["sub", "notes.pdf", "photo.jpg", "readings.csv"])

    def test_typing_in_the_find_box_narrows_the_list(self):
        widget = self.browser()
        widget.filter_var.set("All files")
        widget.find_var.set("pho")
        self.window.update()
        self.assertEqual(self.names(widget), ["sub", "photo.jpg"])

    def test_types_are_spelt_out(self):
        widget = self.browser()
        widget.filter_var.set("All files")
        widget.refresh()
        kinds = {widget.tree.set(item, "name"): widget.tree.set(item, "kind")
                 for item in widget.tree.get_children()}
        self.assertEqual(kinds["sub"], "Folder")
        self.assertEqual(kinds["notes.pdf"], "PDF document")
        self.assertEqual(kinds["readings.csv"], "CSV file")

    def test_double_clicking_a_folder_walks_into_it(self):
        widget = self.browser()
        widget.tree.selection_set(self.item_for(widget, "sub"))
        widget._on_activate()
        self.assertEqual(widget.folder, self.root_path / "sub")
        self.assertEqual(self.names(widget), ["deep.csv"])
        self.assertEqual(self.activated, [])

    def test_double_clicking_a_file_hands_it_over(self):
        widget = self.browser()
        widget.tree.selection_set(self.item_for(widget, "readings.csv"))
        widget._on_activate()
        self.assertEqual([path.name for batch in self.activated for path in batch],
                         ["readings.csv"])

    def test_up_and_back_both_work(self):
        widget = self.browser()
        widget.go_to(self.root_path / "sub")
        widget.go_up()
        self.assertEqual(widget.folder, self.root_path)

        widget.go_to(self.root_path / "sub")
        widget.go_back()
        self.assertEqual(widget.folder, self.root_path)

    def test_a_folder_that_is_not_there_is_reported_and_nothing_moves(self):
        widget = self.browser()
        self.assertFalse(widget.go_to(self.root_path / "nowhere"))
        self.assertEqual(widget.folder, self.root_path)
        self.assertIn("no folder", widget.status_var.get())
        self.assertEqual(widget.path_var.get(), str(self.root_path))

    def test_typing_a_file_path_opens_the_folder_holding_it(self):
        widget = self.browser()
        self.assertTrue(widget.go_to(self.root_path / "sub" / "deep.csv"))
        self.assertEqual(widget.folder, self.root_path / "sub")

    def test_the_shortcuts_go_somewhere_real(self):
        widget = self.browser()
        self.assertTrue(widget._places)
        for path in widget._places.values():
            self.assertTrue(path.is_dir())

    def test_sorting_by_a_column_keeps_folders_at_the_top(self):
        widget = self.browser()
        widget.filter_var.set("All files")
        widget.refresh()
        self.assertEqual(self.names(widget),
                         ["sub", "notes.pdf", "photo.jpg", "readings.csv"])

        widget.sort_by("name")  # clicking the heading turns the order round
        self.assertEqual(self.names(widget),
                         ["sub", "readings.csv", "photo.jpg", "notes.pdf"])

        widget.sort_by("name")  # and back again
        self.assertEqual(self.names(widget)[0], "sub")
        self.assertEqual(self.names(widget)[-1], "readings.csv")

    def test_only_files_come_back_from_a_mixed_selection(self):
        widget = self.browser()
        widget.tree.selection_set(widget.tree.get_children())
        picked = widget.selected_paths()
        self.assertEqual([path.name for path in picked], ["readings.csv"])
        self.assertEqual(len(widget.selected_paths(folders=True)), 2)

    def test_the_folder_it_lands_in_is_reported(self):
        visited = []
        widget = self.browser(on_folder_change=visited.append)
        widget.go_to(self.root_path / "sub")
        self.assertEqual(visited, [self.root_path / "sub"])


@unittest.skipUnless(HAVE_DISPLAY, f"no display available ({TK_IMPORT_ERROR or 'no X server'})")
class FilesTabTests(unittest.TestCase):
    def setUp(self):
        from measurelog.models import Location, Test
        from measurelog.ui.app import MeasureLogApp

        self.data = tempfile.TemporaryDirectory()
        os.environ["MEASURELOG_DATA_DIR"] = self.data.name
        self.source = tempfile.TemporaryDirectory()
        self.source_path = Path(self.source.name)
        (self.source_path / "certificate.pdf").write_bytes(b"%PDF-1.4 cert")
        (self.source_path / "meter.csv").write_text(
            "Location,Test,Replicate,Value\n"
            "Influent,pH,1,7.02\nInfluent,pH,2,7.05\nEffluent,pH,1,7.26\n")

        self.app = MeasureLogApp()
        self.app.update()
        db = self.app.db
        for location in db.list_locations():
            db.delete_location(location.id)
        for test in db.list_tests():
            db.delete_test(test.id)
        self.locations = [
            db.save_location(Location(name=name, code=code, sort_order=index))
            for index, (name, code) in enumerate([("Influent", "INF"), ("Effluent", "EFF")])
        ]
        self.tests = [db.save_test(Test(name="pH", code="PH", replicates=3, sort_order=0))]
        self.run = db.create_run("2026-09-14", "08:00", "Round 1", "Sam")
        self.app.current_run_id = self.run.id
        self.app.notify("setup_changed")
        self.app.notify("runs_changed")
        self.app.update()

        self.tab = self.app.files_tab
        self.app.notebook.select(self.tab)
        self.app.update()
        self.tab.browser.go_to(self.source_path)
        self.tab.browser.filter_var.set("All files")
        self.tab.browser.refresh()
        self.app.update()

    def tearDown(self):
        try:
            self.app.on_close()
        except Exception:
            pass
        self.data.cleanup()
        self.source.cleanup()
        os.environ.pop("MEASURELOG_DATA_DIR", None)

    # -------------------------------------------------------------- helpers

    def pick(self, *names):
        browser = self.tab.browser
        items = [item for item in browser.tree.get_children()
                 if browser.tree.set(item, "name") in names]
        browser.tree.selection_set(items)
        self.app.update()

    def stored_files(self):
        from measurelog import config

        return sorted(path.name for path in config.files_dir().iterdir())

    def attachment_names(self):
        return [self.tab.tree.set(item, "name") for item in self.tab.tree.get_children()]

    # ------------------------------------------------------------- the tab

    def test_the_files_tab_is_in_the_window(self):
        self.assertIn("Files", [name for _tab, name in self.app.tab_order])
        self.assertEqual(self.app.notebook.index(self.tab), 3)

    def test_adding_a_file_copies_it_and_lists_it(self):
        self.pick("certificate.pdf")
        self.tab.attach()
        self.app.update()

        self.assertEqual(self.stored_files(), ["certificate.pdf"])
        self.assertEqual(self.attachment_names(), ["certificate.pdf"])
        self.assertEqual(self.app.db.count_attachments(self.run.id), 1)
        self.assertIn("1 file added", self.tab.status_var.get())

    def test_the_copy_outlives_the_original(self):
        self.pick("certificate.pdf")
        self.tab.attach()
        (self.source_path / "certificate.pdf").unlink()
        self.app.update()

        from measurelog import files

        [attachment] = self.app.db.list_attachments(self.run.id)
        self.assertEqual(files.path_for(attachment.stored_name).read_bytes(), b"%PDF-1.4 cert")

    def test_several_files_go_in_at_once(self):
        self.pick("certificate.pdf", "meter.csv")
        self.tab.attach()
        self.app.update()
        self.assertEqual(self.app.db.count_attachments(self.run.id), 2)
        self.assertIn("2 files added", self.tab.status_var.get())

    def test_double_clicking_a_file_adds_it(self):
        self.pick("certificate.pdf")
        self.tab.browser._on_activate()
        self.app.update()
        self.assertEqual(self.attachment_names(), ["certificate.pdf"])

    def test_the_buttons_wait_until_something_is_picked(self):
        self.tab.browser.tree.selection_set(())
        self.tab._update_buttons()
        self.assertEqual(str(self.tab.attach_button["state"]), "disabled")
        self.assertEqual(str(self.tab.import_button["state"]), "disabled")

        self.pick("certificate.pdf")
        self.assertEqual(str(self.tab.attach_button["state"]), "normal")
        self.assertEqual(str(self.tab.import_button["state"]), "disabled")

        self.pick("meter.csv")
        self.assertEqual(str(self.tab.import_button["state"]), "normal")

    def test_the_count_is_shown_on_the_tab_and_the_entry_screen(self):
        self.pick("certificate.pdf")
        self.tab.attach()
        self.app.update()
        self.assertEqual(self.tab.attached_count_var.get(), "1 file")
        self.assertEqual(self.app.entry_tab.files_var.get(), "Files (1)")

    def test_the_runs_list_shows_how_many_files_a_run_carries(self):
        self.pick("certificate.pdf")
        self.tab.attach()
        self.app.notebook.select(self.app.runs_tab)
        self.app.update()
        self.assertEqual(self.app.runs_tab.tree.set(str(self.run.id), "files"), "1")

    def test_removing_a_file_deletes_the_copy_as_well(self):
        self.pick("certificate.pdf")
        self.tab.attach()
        self.app.update()

        self.tab.tree.selection_set(self.tab.tree.get_children())
        with mock.patch("measurelog.ui.files_tab.messagebox") as box:
            box.askyesno.return_value = True
            self.tab.remove_selected()
        self.app.update()

        self.assertEqual(self.stored_files(), [])
        self.assertEqual(self.app.db.count_attachments(self.run.id), 0)
        self.assertTrue((self.source_path / "certificate.pdf").exists())

    def test_saying_no_to_the_removal_keeps_everything(self):
        self.pick("certificate.pdf")
        self.tab.attach()
        self.tab.tree.selection_set(self.tab.tree.get_children())
        with mock.patch("measurelog.ui.files_tab.messagebox") as box:
            box.askyesno.return_value = False
            self.tab.remove_selected()
        self.assertEqual(self.stored_files(), ["certificate.pdf"])

    def test_deleting_the_run_takes_its_files_with_it(self):
        self.pick("certificate.pdf")
        self.tab.attach()
        self.app.update()

        self.app.notebook.select(self.app.runs_tab)
        self.app.update()
        self.app.runs_tab.tree.selection_set(str(self.run.id))
        with mock.patch("measurelog.ui.runs_tab.messagebox") as box:
            box.askyesno.return_value = True
            self.app.runs_tab.delete_selected()
        self.app.update()

        self.assertEqual(self.stored_files(), [])
        self.assertEqual(self.app.db.count_attachments(), 0)

    def test_a_note_says_what_a_file_is_for(self):
        self.pick("certificate.pdf")
        self.tab.attach()
        self.tab.tree.selection_set(self.tab.tree.get_children())
        with mock.patch("measurelog.ui.files_tab.NoteDialog") as dialog:
            dialog.return_value.show.return_value = "calibration certificate"
            self.tab.edit_note()
        self.app.update()

        [attachment] = self.app.db.list_attachments(self.run.id)
        self.assertEqual(attachment.note, "calibration certificate")
        self.assertEqual(self.tab.tree.set(self.tab.tree.get_children()[0], "note"),
                         "calibration certificate")

    def test_showing_every_run_brings_in_the_run_column(self):
        self.pick("certificate.pdf")
        self.tab.attach()
        other = self.app.db.create_run("2026-09-15", "08:00", "Round 1", "Sam")
        self.app.current_run_id = other.id
        self.app.notify("runs_changed")
        self.app.update()

        self.assertEqual(self.attachment_names(), [])
        self.tab.every_run_var.set(True)
        self.tab.reload_attachments()
        self.app.update()

        self.assertEqual(self.attachment_names(), ["certificate.pdf"])
        self.assertIn("run", self.tab.tree.cget("displaycolumns"))

    def test_a_missing_copy_is_flagged_rather_than_hidden(self):
        from measurelog import files

        self.pick("certificate.pdf")
        self.tab.attach()
        [attachment] = self.app.db.list_attachments(self.run.id)
        files.discard(attachment.stored_name)
        self.tab.reload_attachments()
        self.app.update()

        self.assertIn("(missing)", self.attachment_names()[0])

    def test_the_browser_remembers_where_you_were(self):
        from measurelog.ui.files_tab import LAST_FOLDER_KEY

        self.assertEqual(self.app.db.get_setting(LAST_FOLDER_KEY), str(self.source_path))

    # ------------------------------------------------------------ importing

    def test_importing_fills_the_run_from_a_spreadsheet(self):
        from measurelog import importers
        from measurelog.ui.import_dialog import ImportChoice

        path = self.source_path / "meter.csv"
        table = importers.read_table(path)
        tests = self.app.db.list_tests(active_only=True)
        locations = self.app.db.list_locations(active_only=True)
        plan = importers.build_plan(
            table, importers.guess_mapping(table, tests, locations), tests, locations)

        self.pick("meter.csv")
        with mock.patch("measurelog.ui.files_tab.ImportDialog") as dialog, \
                mock.patch("measurelog.ui.files_tab.messagebox"):
            dialog.return_value.show.return_value = ImportChoice(
                plan=plan, overwrite=False, keep_copy=True, path=path)
            self.tab.import_readings()
        self.app.update()

        self.assertEqual(self.app.db.count_values(run_id=self.run.id), 3)
        self.assertIn("3 readings imported", self.tab.status_var.get())
        # keep_copy was on, so the spreadsheet is filed against the run as well.
        self.assertEqual(self.attachment_names(), ["meter.csv"])

    def test_importing_needs_one_readable_file_picked(self):
        self.pick("certificate.pdf")
        with mock.patch("measurelog.ui.files_tab.messagebox") as box:
            self.tab.import_readings()
        box.showinfo.assert_called_once()
        self.assertIn("Pick one file", box.showinfo.call_args[0][0])

    def test_importing_needs_tests_to_import_into(self):
        for test in self.app.db.list_tests():
            self.app.db.delete_test(test.id)
        self.pick("meter.csv")
        with mock.patch("measurelog.ui.files_tab.messagebox") as box:
            self.tab.import_readings()
        self.assertIn("Setup tab", box.showinfo.call_args[0][1])

    def test_with_no_run_at_all_the_tab_says_what_to_do_first(self):
        self.app.db.delete_run(self.run.id)
        self.app.current_run_id = None
        self.app.notify("runs_changed")
        self.app.update()

        self.pick("certificate.pdf")
        with mock.patch("measurelog.ui.files_tab.messagebox") as box:
            self.tab.attach()
        self.assertIn("Entry tab", box.showinfo.call_args[0][1])
        self.assertEqual(self.tab.attached_count_var.get(), "no files yet")


@unittest.skipUnless(HAVE_DISPLAY, f"no display available ({TK_IMPORT_ERROR or 'no X server'})")
class ImportDialogTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk

        from measurelog.db import Database
        from measurelog.models import Location, Test
        from measurelog.ui import theme

        self.folder = tempfile.TemporaryDirectory()
        self.root_path = Path(self.folder.name)
        self.db = Database(self.root_path / "test.db")
        for location in self.db.list_locations():
            self.db.delete_location(location.id)
        self.locations = [
            self.db.save_location(Location(name=name, sort_order=index))
            for index, name in enumerate(["Influent", "Effluent"])
        ]
        self.tests = [self.db.save_test(Test(name="pH", replicates=3, sort_order=0))]

        self.window = tk.Tk()
        theme.apply(self.window)

    def tearDown(self):
        try:
            self.window.destroy()
        except Exception:
            pass
        self.db.close()
        self.folder.cleanup()

    def dialog(self, name, text):
        from measurelog.ui.import_dialog import ImportDialog

        path = self.root_path / name
        path.write_text(text, encoding="utf-8")
        widget = ImportDialog(self.window, path, self.tests, self.locations, "Round 1")
        self.window.update()
        return widget

    def preview_rows(self, dialog):
        return [dialog.preview.item(item)["values"] for item in dialog.preview.get_children()]

    def test_it_opens_on_the_layout_it_worked_out(self):
        dialog = self.dialog("long.csv",
                             "Location,Test,Replicate,Value\nInfluent,pH,1,7.02\n")
        self.assertEqual(dialog.layout_var.get(), "long")
        self.assertEqual(dialog.column_vars["value"].get(), "4. Value")
        self.assertIn("1 reading ready", dialog.summary_var.get())
        dialog.destroy()

    def test_the_preview_shows_what_will_be_written(self):
        dialog = self.dialog("long.csv",
                             "Location,Test,Value\nInfluent,pH,7.02\nEffluent,pH,7.26\n")
        rows = self.preview_rows(dialog)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][1:5], ["Influent", "pH", 1, "7.02"])
        self.assertEqual(rows[0][5], "Will be imported")
        dialog.destroy()

    def test_rows_it_cannot_use_are_listed_first_with_the_reason(self):
        dialog = self.dialog("mixed.csv",
                             "Location,Test,Value\nInfluent,pH,7.02\nNowhere,pH,7.0\n")
        rows = self.preview_rows(dialog)
        self.assertIn("No location called", rows[0][5])
        self.assertEqual(rows[1][5], "Will be imported")
        dialog.destroy()

    def test_choosing_a_different_column_redraws_the_preview(self):
        dialog = self.dialog("swapped.csv",
                             "Test,Location,Value\npH,Influent,7.02\n")
        dialog.column_vars["location"].set("1. Test")
        dialog.column_vars["test"].set("2. Location")
        dialog.rebuild_plan()
        self.assertEqual(len(dialog.plan.ready), 0)

        dialog.column_vars["location"].set("2. Location")
        dialog.column_vars["test"].set("1. Test")
        dialog.rebuild_plan()
        self.assertEqual(len(dialog.plan.ready), 1)
        dialog.destroy()

    def test_switching_to_a_grid_rereads_the_same_file(self):
        dialog = self.dialog("grid.csv", "Test,Influent,Effluent\npH,7.02,7.26\n")
        self.assertEqual(dialog.layout_var.get(), "wide")
        self.assertEqual(len(dialog.plan.ready), 2)

        dialog.layout_var.set("long")
        dialog.rebuild_plan()
        self.assertIsNone(dialog.plan)
        self.assertIn("Choose which column", dialog.summary_var.get())
        dialog.destroy()

    def test_it_refuses_to_import_when_nothing_matched(self):
        dialog = self.dialog("bad.csv", "Location,Test,Value\nNowhere,Nothing,7.0\n")
        with self.assertRaises(ValueError) as caught:
            dialog.collect()
        self.assertIn("Setup tab", str(caught.exception))
        dialog.destroy()

    def test_what_it_hands_back_carries_the_choices(self):
        dialog = self.dialog("long.csv", "Location,Test,Value\nInfluent,pH,7.02\n")
        dialog.overwrite_var.set(True)
        dialog.keep_copy_var.set(False)
        choice = dialog.collect()

        self.assertTrue(choice.overwrite)
        self.assertFalse(choice.keep_copy)
        self.assertEqual(len(choice.plan.ready), 1)
        dialog.destroy()

    def test_a_file_it_cannot_read_is_reported_rather_than_crashing(self):
        path = self.root_path / "scan.pdf"
        path.write_bytes(b"%PDF-1.4")

        from measurelog.ui.import_dialog import ImportDialog

        dialog = ImportDialog(self.window, path, self.tests, self.locations, "Round 1")
        self.window.update()
        self.assertIn("cannot read", dialog.summary_var.get())
        with self.assertRaises(ValueError):
            dialog.collect()
        dialog.destroy()


if __name__ == "__main__":
    unittest.main()
