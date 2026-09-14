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


class ResourceTests(unittest.TestCase):
    def test_missing_resource_returns_none(self):
        self.assertIsNone(config.resource_path("definitely-not-here.xyz"))


if __name__ == "__main__":
    unittest.main()
