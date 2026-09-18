"""Storing files alongside the data file, and the attachment records for them."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from measurelog import config, files
from measurelog.db import Database
from measurelog.models import Attachment


class FilesFolderTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.env = mock.patch.dict(os.environ, {"MEASURELOG_DATA_DIR": str(self.root)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.folder.cleanup()

    def test_the_files_folder_sits_beside_the_database(self):
        self.assertEqual(config.files_dir(), self.root / "files")
        self.assertTrue(config.files_dir().is_dir())

    def test_preparing_the_data_folder_makes_room_for_files(self):
        config.ensure_data_dir()
        self.assertTrue((self.root / "files").is_dir())

    def test_a_file_is_copied_not_linked(self):
        source = self.root / "certificate.pdf"
        source.write_bytes(b"%PDF-1.4 original")

        stored = files.store(source)
        source.unlink()  # the original goes; the record must not

        self.assertEqual(stored.filename, "certificate.pdf")
        self.assertEqual(stored.path.read_bytes(), b"%PDF-1.4 original")
        self.assertEqual(stored.size, len(b"%PDF-1.4 original"))

    def test_two_files_of_the_same_name_both_survive(self):
        first = self.root / "a" / "photo.jpg"
        second = self.root / "b" / "photo.jpg"
        for path, body in ((first, b"one"), (second, b"two")):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)

        stored_first = files.store(first)
        stored_second = files.store(second)

        self.assertNotEqual(stored_first.stored_name, stored_second.stored_name)
        self.assertEqual(stored_second.stored_name, "photo (2).jpg")
        self.assertEqual(stored_first.path.read_bytes(), b"one")
        self.assertEqual(stored_second.path.read_bytes(), b"two")

    def test_awkward_names_are_made_safe(self):
        self.assertEqual(files.safe_name("run 1: pH*.csv"), "run 1_ pH_.csv")
        self.assertEqual(files.safe_name("../../etc/passwd"), "passwd")
        self.assertEqual(files.safe_name(""), "file")

    def test_a_stored_name_cannot_point_outside_the_files_folder(self):
        self.assertEqual(files.path_for("../../escape.txt").parent, config.files_dir())

    def test_discarding_removes_the_copy(self):
        source = self.root / "note.txt"
        source.write_text("x")
        stored = files.store(source)

        self.assertTrue(files.discard(stored.stored_name))
        self.assertFalse(stored.path.exists())
        self.assertFalse(files.discard(stored.stored_name))  # already gone

    def test_a_stored_file_knows_which_folder_it_went_into(self):
        source = self.root / "note.txt"
        source.write_text("x")
        elsewhere = self.root / "elsewhere"

        stored = files.store(source, folder=elsewhere)
        self.assertEqual(stored.path, elsewhere / "note.txt")
        self.assertTrue(stored.path.is_file())

    def test_storing_something_that_is_not_a_file_is_refused(self):
        with self.assertRaises(OSError):
            files.store(self.root / "nothing-here.txt")


class DescribingTests(unittest.TestCase):
    def test_sizes_read_the_way_a_file_manager_shows_them(self):
        self.assertEqual(files.human_size(0), "0 B")
        self.assertEqual(files.human_size(512), "512 B")
        self.assertEqual(files.human_size(2048), "2 KB")
        self.assertEqual(files.human_size(5 * 1024 * 1024), "5 MB")
        self.assertEqual(files.human_size(None), "")

    def test_types_are_named_in_plain_words(self):
        self.assertEqual(files.describe_kind("report.xlsx"), "Excel workbook")
        self.assertEqual(files.describe_kind("scan.JPG"), "JPEG image")
        self.assertEqual(files.describe_kind("odd.qqq"), "QQQ file")
        self.assertEqual(files.describe_kind("README"), "File")

    def test_readable_files_are_the_ones_the_importer_handles(self):
        self.assertTrue(files.is_readable("readings.csv"))
        self.assertTrue(files.is_readable(Path("book.XLSX")))
        self.assertFalse(files.is_readable("photo.png"))

    def test_shortcuts_only_offer_folders_that_exist(self):
        for _label, path in files.places():
            self.assertTrue(path.is_dir(), path)


class ListingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        (self.root / "sub").mkdir()
        # Written as bytes, not text: on Windows write_text turns "\n" into
        # "\r\n", which would make this 5 bytes and break the size assertion.
        (self.root / "readings.csv").write_bytes(b"a,b\n")
        (self.root / "photo.jpg").write_bytes(b"\xff\xd8\xff")
        (self.root / ".hidden").write_text("secret")

    def tearDown(self):
        self.folder.cleanup()

    def names(self, **kwargs):
        return [entry.name for entry in files.listing(self.root, **kwargs)]

    def test_folders_come_first_then_files_alphabetically(self):
        self.assertEqual(self.names(), ["sub", "photo.jpg", "readings.csv"])

    def test_hidden_files_stay_out_of_the_way(self):
        self.assertNotIn(".hidden", self.names())
        self.assertIn(".hidden", self.names(show_hidden=True))

    def test_a_type_filter_never_hides_a_folder(self):
        listed = self.names(suffixes=(".csv",))
        self.assertEqual(listed, ["sub", "readings.csv"])

    def test_the_name_filter_matches_any_part_of_the_name(self):
        self.assertEqual(self.names(name_filter="read"), ["sub", "readings.csv"])
        self.assertEqual(self.names(name_filter="READ"), ["sub", "readings.csv"])

    def test_the_name_filter_leaves_folders_alone_so_you_can_still_navigate(self):
        self.assertIn("sub", self.names(name_filter="nothing matches this"))

    def test_entries_describe_themselves(self):
        entry = next(e for e in files.listing(self.root) if e.name == "readings.csv")
        self.assertFalse(entry.is_dir)
        self.assertEqual(entry.kind, "CSV file")
        self.assertEqual(entry.size_text, "4 B")
        self.assertTrue(entry.modified_text)

        folder = next(e for e in files.listing(self.root) if e.is_dir)
        self.assertEqual(folder.kind, "Folder")
        self.assertEqual(folder.size_text, "")


class AttachmentRecordTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.db = Database(self.root / "test.db")
        self.run = self.db.create_run("2026-09-14", "08:00", "Round 1", "Sam")

    def tearDown(self):
        self.db.close()
        self.folder.cleanup()

    def add(self, name="cert.pdf", run_id=None, size=10):
        return self.db.add_attachment(Attachment(
            run_id=self.run.id if run_id is None else run_id,
            filename=name, stored_name=name, size=size))

    def test_an_attachment_is_stored_and_read_back(self):
        added = self.add()
        self.assertIsNotNone(added.id)
        self.assertTrue(added.added_at)

        [found] = self.db.list_attachments(self.run.id)
        self.assertEqual(found.filename, "cert.pdf")
        self.assertEqual(found.run_id, self.run.id)
        self.assertEqual(self.db.get_attachment(added.id).stored_name, "cert.pdf")

    def test_counts_are_reported_per_run_and_overall(self):
        other = self.db.create_run("2026-09-15", "08:00", "Round 1")
        self.add("a.pdf")
        self.add("b.pdf")
        self.add("c.pdf", run_id=other.id)

        self.assertEqual(self.db.count_attachments(self.run.id), 2)
        self.assertEqual(self.db.count_attachments(), 3)
        self.assertEqual(self.db.attachment_counts(), {self.run.id: 2, other.id: 1})

    def test_listing_every_run_at_once(self):
        other = self.db.create_run("2026-09-15", "08:00", "Round 1")
        self.add("a.pdf")
        self.add("c.pdf", run_id=other.id)
        self.assertEqual(len(self.db.list_attachments(every_run=True)), 2)
        self.assertEqual(len(self.db.list_attachments(self.run.id)), 1)

    def test_a_note_can_be_edited(self):
        added = self.add()
        added.note = "calibration certificate"
        self.db.update_attachment(added)
        self.assertEqual(self.db.get_attachment(added.id).note, "calibration certificate")

    def test_deleting_reports_the_file_to_remove(self):
        added = self.add()
        self.assertEqual(self.db.delete_attachment(added.id), "cert.pdf")
        self.assertIsNone(self.db.get_attachment(added.id))
        self.assertIsNone(self.db.delete_attachment(added.id))

    def test_deleting_a_run_hands_back_the_files_it_orphaned(self):
        self.add("a.pdf")
        self.add("b.pdf")
        orphaned = self.db.delete_run(self.run.id)
        self.assertEqual(sorted(orphaned), ["a.pdf", "b.pdf"])
        self.assertEqual(self.db.count_attachments(), 0)

    def test_the_database_lists_the_files_it_expects_to_find(self):
        self.add("a.pdf")
        self.add("b.pdf")
        self.assertEqual(self.db.stored_names(), {"a.pdf", "b.pdf"})

    def test_an_older_data_file_gains_the_attachment_table(self):
        """A database written before attachments existed must still open."""
        path = self.root / "old.db"
        old = Database(path)
        old.conn.execute("DROP TABLE attachment")
        old.conn.commit()
        old.close()

        reopened = Database(path)
        try:
            self.assertEqual(reopened.list_attachments(every_run=True), [])
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
