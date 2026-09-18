import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from measurelog import config


class DataDirTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("MEASURELOG_DATA_DIR", None)

    def tearDown(self):
        self.env.stop()
        self.folder.cleanup()

    def test_environment_variable_wins(self):
        os.environ["MEASURELOG_DATA_DIR"] = str(self.root / "chosen")
        self.assertEqual(config.data_dir(), self.root / "chosen")

    def test_datadir_pointer_file_is_honoured(self):
        (self.root / "datadir.txt").write_text(str(self.root / "shared"), encoding="utf-8")
        with mock.patch.object(config, "app_dir", return_value=self.root):
            self.assertEqual(config.data_dir(), self.root / "shared")

    def test_blank_pointer_file_is_ignored(self):
        (self.root / "datadir.txt").write_text("   \n", encoding="utf-8")
        with mock.patch.object(config, "app_dir", return_value=self.root):
            self.assertNotEqual(config.data_dir(), self.root)

    def test_portable_flag_keeps_data_beside_the_exe(self):
        (self.root / "portable.flag").write_text("", encoding="utf-8")
        with mock.patch.object(config, "app_dir", return_value=self.root):
            self.assertEqual(config.data_dir(), self.root / "MeasureLog-Data")

    def test_default_is_under_the_home_folder(self):
        with mock.patch.object(config, "app_dir", return_value=self.root):
            self.assertTrue(str(config.data_dir()).startswith(str(Path.home())))

    def test_ensure_creates_the_sub_folders(self):
        os.environ["MEASURELOG_DATA_DIR"] = str(self.root / "new")
        created = config.ensure_data_dir()
        self.assertTrue((created / "backups").is_dir())
        self.assertTrue((created / "exports").is_dir())


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        os.environ["MEASURELOG_DATA_DIR"] = str(self.root)
        self.source = config.db_path()
        self.source.write_bytes(b"pretend database")

    def tearDown(self):
        os.environ.pop("MEASURELOG_DATA_DIR", None)
        self.folder.cleanup()

    def test_backup_copies_the_database(self):
        made = config.make_backup()
        self.assertIsNotNone(made)
        self.assertEqual(made.read_bytes(), b"pretend database")

    def test_only_one_backup_per_day(self):
        self.assertIsNotNone(config.make_backup())
        self.assertIsNone(config.make_backup())

    def test_nothing_to_back_up(self):
        self.source.unlink()
        self.assertIsNone(config.make_backup())

    def test_empty_database_is_skipped(self):
        self.source.write_bytes(b"")
        self.assertIsNone(config.make_backup())

    def test_old_backups_are_pruned(self):
        folder = config.backups_dir()
        for day in range(1, 21):
            (folder / f"measurelog-202601{day:02d}-000000.db").write_bytes(b"old")
        config.make_backup(keep=5)
        self.assertLessEqual(len(list(folder.glob("measurelog-*.db"))), 5)


class SyncFolderTests(unittest.TestCase):
    """Spotting a data folder a sync client would fight the app over."""

    def test_onedrive_is_recognised(self):
        self.assertEqual(
            config.sync_service_for(r"C:\Users\sam\OneDrive\Documents\MeasureLog"),
            "OneDrive")

    def test_a_workspace_named_onedrive_folder_is_recognised(self):
        # Redirected Documents usually look like this, and it is the most
        # common way to end up synced without choosing to be.
        self.assertEqual(
            config.sync_service_for(
                r"C:\Users\sam\OneDrive - Green Era Campus\Documents\MeasureLog"),
            "OneDrive")

    def test_google_drive_in_both_its_shapes(self):
        self.assertEqual(config.sync_service_for(r"G:\My Drive\MeasureLog"), "Google Drive")
        self.assertEqual(
            config.sync_service_for(r"C:\Users\sam\Google Drive\MeasureLog"), "Google Drive")

    def test_dropbox_on_either_platform(self):
        self.assertEqual(config.sync_service_for(r"C:\Users\sam\Dropbox\MeasureLog"),
                         "Dropbox")
        self.assertEqual(config.sync_service_for("/home/sam/Dropbox/MeasureLog"), "Dropbox")

    def test_an_ordinary_documents_folder_is_fine(self):
        self.assertIsNone(config.sync_service_for(r"C:\Users\sam\Documents\MeasureLog"))

    def test_a_network_share_is_fine(self):
        # A real network drive is a different thing entirely: it is allowed.
        self.assertIsNone(config.sync_service_for(r"\\fileserver\lab\measurelog"))

    def test_folders_that_merely_start_with_a_service_name_are_left_alone(self):
        for path in (r"C:\Users\sam\Documents\OneDriveNotes\MeasureLog",
                     r"C:\Users\sam\Documents\Driveway\MeasureLog",
                     r"C:\Users\sam\Documents\Boxes\MeasureLog"):
            with self.subTest(path=path):
                self.assertIsNone(config.sync_service_for(path))

    def test_matching_ignores_case(self):
        self.assertEqual(config.sync_service_for(r"C:\Users\sam\ONEDRIVE\MeasureLog"),
                         "OneDrive")

    def test_it_checks_the_live_data_folder_when_asked_for_nothing(self):
        import os
        os.environ["MEASURELOG_DATA_DIR"] = r"C:\Users\sam\Dropbox\MeasureLog"
        try:
            self.assertEqual(config.sync_service_for(), "Dropbox")
        finally:
            os.environ.pop("MEASURELOG_DATA_DIR", None)


class ResourceTests(unittest.TestCase):
    def test_missing_resource_returns_none(self):
        self.assertIsNone(config.resource_path("definitely-not-here.xyz"))


if __name__ == "__main__":
    unittest.main()
