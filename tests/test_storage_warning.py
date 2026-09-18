"""The warning shown when the data folder sits inside a sync service."""

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
class SyncWarningTests(unittest.TestCase):
    def build(self, data_dir: str):
        from measurelog.ui.app import MeasureLogApp

        os.environ["MEASURELOG_DATA_DIR"] = data_dir
        app = MeasureLogApp()
        app.update()
        self.addCleanup(lambda: os.environ.pop("MEASURELOG_DATA_DIR", None))
        self.addCleanup(self.close, app)
        return app

    @staticmethod
    def close(app):
        try:
            app.on_close()
        except Exception:
            pass

    @staticmethod
    def warning_text(app) -> str:
        """Every bit of text inside the export tab's storage box."""
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

        walk(app.export_tab)
        return "\n".join(found)

    def test_an_ordinary_folder_shows_no_warning(self):
        with tempfile.TemporaryDirectory() as folder:
            app = self.build(folder)
            app.notebook.select(app.export_tab)
            app.update()
            self.assertNotIn("⚠", self.warning_text(app))

    def test_a_dropbox_folder_is_called_out_by_name(self):
        with tempfile.TemporaryDirectory() as parent:
            folder = os.path.join(parent, "Dropbox", "MeasureLog")
            os.makedirs(folder)
            app = self.build(folder)
            app.notebook.select(app.export_tab)
            app.update()

            text = self.warning_text(app)
            self.assertIn("⚠", text)
            self.assertIn("Dropbox", text)

    def test_the_warning_explains_the_risk_and_the_way_out(self):
        with tempfile.TemporaryDirectory() as parent:
            folder = os.path.join(parent, "OneDrive", "Documents", "MeasureLog")
            os.makedirs(folder)
            app = self.build(folder)
            app.notebook.select(app.export_tab)
            app.update()

            text = self.warning_text(app)
            self.assertIn("OneDrive", text)
            self.assertIn("corrupted", text)
            self.assertIn("datadir.txt", text)          # how to move it
            self.assertIn("Exports are unaffected", text)   # what is still safe

    def test_the_app_still_works_normally_in_a_synced_folder(self):
        # The warning is advice, not a block: nothing is prevented.
        with tempfile.TemporaryDirectory() as parent:
            folder = os.path.join(parent, "Dropbox", "MeasureLog")
            os.makedirs(folder)
            app = self.build(folder)
            run = app.db.create_run("2026-09-18", "08:00", "Round 1", "Sam")
            self.assertIsNotNone(run.id)
            self.assertEqual(len(app.db.list_runs()), 1)


if __name__ == "__main__":
    unittest.main()
