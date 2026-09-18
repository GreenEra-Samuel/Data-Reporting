"""The warning shown when the data folder sits inside a sync service.

Note the teardown order: the app is closed before the temporary folder is
removed. Windows will not delete a file another process still holds open, so
leaving the database open here fails the build even though Linux allows it.
"""

import os
import tempfile
import unittest

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
class SyncWarningTestCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.app = None

    def tearDown(self):
        if self.app is not None:
            try:
                self.app.on_close()      # closes the database first ...
            except Exception:
                pass
        os.environ.pop("MEASURELOG_DATA_DIR", None)
        self.folder.cleanup()            # ... so this can delete the file

    def open_in(self, *parts: str):
        """Start the app with its data folder at the given sub-path."""
        from measurelog.ui.app import MeasureLogApp

        data_dir = os.path.join(self.folder.name, *parts)
        os.makedirs(data_dir, exist_ok=True)
        os.environ["MEASURELOG_DATA_DIR"] = data_dir
        self.app = MeasureLogApp()
        self.app.update()
        self.app.notebook.select(self.app.export_tab)
        self.app.update()
        return self.app

    def storage_text(self) -> str:
        """Every piece of text on the export tab."""
        found = []

        def walk(widget):
            for child in widget.winfo_children():
                try:
                    text = child.cget("text")
                except Exception:
                    text = ""
                if text:
                    found.append(str(text))
                walk(child)

        walk(self.app.export_tab)
        return "\n".join(found)


class SyncWarningTests(SyncWarningTestCase):
    def test_an_ordinary_folder_shows_no_warning(self):
        self.open_in("MeasureLog")
        self.assertNotIn("⚠", self.storage_text())

    def test_a_dropbox_folder_is_called_out_by_name(self):
        self.open_in("Dropbox", "MeasureLog")
        text = self.storage_text()
        self.assertIn("⚠", text)
        self.assertIn("Dropbox", text)

    def test_a_workspace_onedrive_folder_is_caught_too(self):
        self.open_in("OneDrive - Green Era Campus", "Documents", "MeasureLog")
        self.assertIn("OneDrive", self.storage_text())

    def test_the_warning_explains_the_risk_and_the_way_out(self):
        self.open_in("OneDrive", "Documents", "MeasureLog")
        text = self.storage_text()
        self.assertIn("corrupted", text)                 # the risk
        self.assertIn("datadir.txt", text)               # how to move it
        self.assertIn("Exports are unaffected", text)    # what stays safe

    def test_the_app_still_works_normally_in_a_synced_folder(self):
        # The warning is advice, not a block: nothing is prevented.
        app = self.open_in("Dropbox", "MeasureLog")
        run = app.db.create_run("2026-09-18", "08:00", "Round 1", "Sam")
        self.assertIsNotNone(run.id)
        self.assertEqual(len(app.db.list_runs()), 1)


if __name__ == "__main__":
    unittest.main()
