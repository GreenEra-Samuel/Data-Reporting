"""Reading measurements out of CSV and Excel files."""

import tempfile
import unittest
from pathlib import Path

from measurelog import exporters, importers
from measurelog.db import Database
from measurelog.models import Location, Test

try:
    import openpyxl
except ImportError:  # pragma: no cover - a build without the Excel writer
    openpyxl = None


class ImportTestCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.db = Database(self.root / "test.db")
        for location in self.db.list_locations():
            self.db.delete_location(location.id)

        self.locations = [
            self.db.save_location(Location(name=name, code=code, sort_order=index))
            for index, (name, code) in enumerate(
                [("Influent", "INF"), ("Digester 1", "D1"), ("Effluent", "EFF")])
        ]
        self.tests = [
            self.db.save_test(Test(name=name, code=code, unit=unit, replicates=3,
                                   sort_order=index))
            for index, (name, code, unit) in enumerate(
                [("pH", "PH", ""), ("Total Solids", "TS", "%"),
                 ("Alkalinity", "ALK", "mg/L")])
        ]
        self.run = self.db.create_run("2026-09-14", "08:00", "Round 1", "Sam")

    def tearDown(self):
        self.db.close()
        self.folder.cleanup()

    def write(self, name: str, text: str) -> Path:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def plan_for(self, path):
        table = importers.read_table(path)
        mapping = importers.guess_mapping(table, self.tests, self.locations)
        return importers.build_plan(table, mapping, self.tests, self.locations)


class NumberTests(unittest.TestCase):
    def test_plain_numbers(self):
        self.assertEqual(importers.to_number("7.02")[0], 7.02)
        self.assertEqual(importers.to_number(" 8 ")[0], 8.0)
        self.assertEqual(importers.to_number(3.5)[0], 3.5)

    def test_a_comma_may_be_a_decimal_point_or_a_thousands_separator(self):
        self.assertEqual(importers.to_number("2,45")[0], 2.45)
        self.assertEqual(importers.to_number("2,450")[0], 2450.0)
        self.assertEqual(importers.to_number("1,234,567")[0], 1234567.0)
        self.assertEqual(importers.to_number("1.234,5")[0], 1234.5)
        self.assertEqual(importers.to_number("1,234.5")[0], 1234.5)

    def test_anything_else_is_refused_with_a_reason(self):
        value, problem = importers.to_number("abc")
        self.assertIsNone(value)
        self.assertIn("not a number", problem)

        value, problem = importers.to_number("")
        self.assertIsNone(value)
        self.assertIn("empty", problem)

    def test_a_less_than_result_is_not_quietly_turned_into_a_reading(self):
        value, problem = importers.to_number("<0.5")
        self.assertIsNone(value)
        self.assertIn("limit rather than a reading", problem)


class MatcherTests(ImportTestCase):
    def test_names_match_however_they_are_spelt(self):
        matcher = importers.Matcher(self.tests)
        for spelling in ("Total Solids", "total solids", "TotalSolids", "Total Solids (%)"):
            self.assertEqual(matcher.find(spelling).name, "Total Solids", spelling)

    def test_codes_match_too(self):
        self.assertEqual(importers.Matcher(self.tests).find("ALK").name, "Alkalinity")

    def test_an_unknown_name_matches_nothing(self):
        self.assertIsNone(importers.Matcher(self.tests).find("Unobtainium"))
        self.assertIsNone(importers.Matcher(self.tests).find(""))

    def test_a_short_code_does_not_swallow_a_longer_name(self):
        tests = [Test(id=1, name="pH", code="PH"), Test(id=2, name="Phosphate", code="PO4")]
        matcher = importers.Matcher(tests)
        self.assertEqual(matcher.find("Phosphate").name, "Phosphate")
        self.assertEqual(matcher.find("pH").name, "pH")


class LongLayoutTests(ImportTestCase):
    def setUp(self):
        super().setUp()
        self.path = self.write("long.csv", (
            "Location,Test,Replicate,Value,Note\n"
            "Influent,pH,1,7.02,\n"
            "Influent,pH,2,7.05,steady\n"
            "Digester 1,Alkalinity,1,2450,\n"
        ))

    def test_the_columns_are_recognised(self):
        table = importers.read_table(self.path)
        mapping = importers.guess_mapping(table, self.tests, self.locations)
        self.assertEqual(mapping.layout, importers.LAYOUT_LONG)
        self.assertEqual(
            [table.headers[index] for index in
             (mapping.location, mapping.test, mapping.value, mapping.replicate, mapping.note)],
            ["Location", "Test", "Value", "Replicate", "Note"],
        )

    def test_every_row_becomes_a_reading(self):
        plan = self.plan_for(self.path)
        self.assertEqual(len(plan.ready), 3)
        self.assertEqual(
            [(row.replicate, row.value) for row in plan.ready],
            [(1, 7.02), (2, 7.05), (1, 2450.0)],
        )
        self.assertEqual(plan.ready[1].note, "steady")

    def test_readings_land_in_the_run(self):
        result = importers.apply(self.db, self.run.id, self.plan_for(self.path))
        self.assertEqual(result.written, 3)
        self.assertEqual(self.db.count_values(run_id=self.run.id), 3)

        stored = self.db.get_run_values(self.run.id)
        self.assertEqual(stored[(self.locations[0].id, self.tests[0].id, 1)].value, 7.02)

    def test_without_a_replicate_column_repeats_are_numbered_in_order(self):
        path = self.write("norep.csv",
                          "Location,Test,Value\nInfluent,pH,7.02\nInfluent,pH,7.05\n"
                          "Effluent,pH,7.26\n")
        plan = self.plan_for(path)
        self.assertEqual([(row.location_name, row.replicate) for row in plan.ready],
                         [("Influent", 1), ("Influent", 2), ("Effluent", 1)])

    def test_unknown_names_are_reported_against_their_row(self):
        path = self.write("bad.csv",
                          "Location,Test,Value\nNowhere,pH,7.0\nInfluent,Unobtainium,5\n"
                          "Influent,pH,abc\n")
        plan = self.plan_for(path)

        self.assertEqual(plan.ready, [])
        statuses = {row.source_row: row.status for row in plan.problems}
        self.assertEqual(statuses[2], importers.UNKNOWN_LOCATION)
        self.assertEqual(statuses[3], importers.UNKNOWN_TEST)
        self.assertEqual(statuses[4], importers.NOT_A_NUMBER)
        self.assertIn("Nowhere", next(r for r in plan.problems if r.source_row == 2).detail)

    def test_more_replicates_than_the_test_allows_are_held_back(self):
        path = self.write("many.csv", "Location,Test,Replicate,Value\n" + "".join(
            f"Influent,pH,{n},7.0{n}\n" for n in range(1, 5)))
        plan = self.plan_for(path)

        self.assertEqual(len(plan.ready), 3)
        [held] = plan.problems
        self.assertEqual(held.status, importers.TOO_MANY_REPLICATES)
        self.assertIn("Setup tab", held.detail)

    def test_the_summary_counts_what_happened(self):
        path = self.write("mixed.csv", "Location,Test,Value\nInfluent,pH,7.0\nNowhere,pH,7.0\n")
        summary = self.plan_for(path).summary()
        self.assertIn("1 reading ready", summary)
        self.assertIn("1 skipped", summary)


class WideLayoutTests(ImportTestCase):
    def test_a_grid_of_tests_by_locations_is_understood(self):
        path = self.write("grid.csv",
                          "Test,Influent,Digester 1,Effluent\n"
                          "pH,7.02,7.11,7.26\n"
                          "Total Solids,3.4,2.9,0.4\n")
        table = importers.read_table(path)
        mapping = importers.guess_mapping(table, self.tests, self.locations)
        self.assertEqual(mapping.layout, importers.LAYOUT_WIDE)
        self.assertEqual(mapping.key_role, "test")

        plan = importers.build_plan(table, mapping, self.tests, self.locations)
        self.assertEqual(len(plan.ready), 6)
        self.assertEqual({row.replicate for row in plan.ready}, {1})

    def test_a_grid_the_other_way_round_is_understood_too(self):
        path = self.write("grid2.csv",
                          "Location,pH,Total Solids\n"
                          "Influent,7.02,3.4\n"
                          "Effluent,7.26,0.4\n")
        table = importers.read_table(path)
        mapping = importers.guess_mapping(table, self.tests, self.locations)
        self.assertEqual(mapping.key_role, "location")

        plan = importers.build_plan(table, mapping, self.tests, self.locations)
        self.assertEqual({(row.location_name, row.test_name) for row in plan.ready}, {
            ("Influent", "pH"), ("Influent", "Total Solids"),
            ("Effluent", "pH"), ("Effluent", "Total Solids"),
        })

    def test_blank_squares_are_simply_not_readings(self):
        path = self.write("gaps.csv",
                          "Test,Influent,Effluent\npH,7.02,\nTotal Solids,,0.4\n")
        plan = self.plan_for(path)
        self.assertEqual(len(plan.rows), 2)
        self.assertEqual(len(plan.ready), 2)


class RoundTripTests(ImportTestCase):
    """What MeasureLog writes out, MeasureLog can read back in."""

    def setUp(self):
        super().setUp()
        for replicate, value in enumerate((7.01, 7.03, 6.99), start=1):
            self.db.set_value(self.run.id, self.locations[0].id, self.tests[0].id,
                              replicate, value)
        self.db.set_value(self.run.id, self.locations[2].id, self.tests[1].id, 1, 0.4)
        self.rows = self.db.fetch_long_rows()
        self.target = self.db.create_run("2026-09-15", "08:00", "Round 1", "Sam")

    def test_the_every_reading_export_comes_back_whole(self):
        path = exporters.export_raw_csv(self.root / "raw.csv", self.rows)
        plan = self.plan_for(path)

        self.assertEqual(len(plan.problems), 0, [r.detail for r in plan.problems])
        self.assertEqual(len(plan.ready), 4)
        importers.apply(self.db, self.target.id, plan)
        self.assertEqual(self.db.get_run_values(self.target.id),
                         self.db.get_run_values(self.run.id))

    def test_the_one_row_per_location_export_is_read_as_a_grid(self):
        path = exporters.export_wide_csv(self.root / "wide.csv", self.rows)
        table = importers.read_table(path)
        mapping = importers.guess_mapping(table, self.tests, self.locations)

        self.assertEqual(mapping.layout, importers.LAYOUT_WIDE)
        self.assertEqual(mapping.key_role, "location")
        # Date, Time, Run and Operator sit in front of the Location column and
        # name neither a test nor a location, so they are stepped over.
        self.assertEqual([table.headers[index] for index in mapping.skip],
                         ["Date", "Time", "Run", "Operator"])

        plan = importers.build_plan(table, mapping, self.tests, self.locations)
        self.assertEqual(len(plan.problems), 0, [r.detail for r in plan.problems])
        self.assertEqual({(row.location_name, row.test_name, row.value)
                          for row in plan.ready},
                         {("Influent", "pH", 7.01), ("Effluent", "Total Solids (%)", 0.4)})


class ExistingReadingsTests(ImportTestCase):
    def setUp(self):
        super().setUp()
        self.db.set_value(self.run.id, self.locations[0].id, self.tests[0].id, 1, 6.50)
        self.path = self.write("long.csv",
                               "Location,Test,Replicate,Value\n"
                               "Influent,pH,1,7.02\nInfluent,pH,2,7.05\n")

    def test_by_default_what_is_already_typed_is_left_alone(self):
        result = importers.apply(self.db, self.run.id, self.plan_for(self.path))
        self.assertEqual((result.written, result.kept), (1, 1))
        stored = self.db.get_run_values(self.run.id)
        self.assertEqual(stored[(self.locations[0].id, self.tests[0].id, 1)].value, 6.50)

    def test_overwriting_replaces_it_and_says_so(self):
        result = importers.apply(self.db, self.run.id, self.plan_for(self.path),
                                 overwrite=True)
        self.assertEqual((result.written, result.replaced, result.kept), (2, 1, 0))
        stored = self.db.get_run_values(self.run.id)
        self.assertEqual(stored[(self.locations[0].id, self.tests[0].id, 1)].value, 7.02)
        self.assertIn("replaced", result.summary())


class ReadingFilesTests(ImportTestCase):
    def test_a_semicolon_separated_file_is_read(self):
        path = self.write("semi.csv", "Location;Test;Value\nInfluent;pH;7,02\n")
        plan = self.plan_for(path)
        self.assertEqual(plan.ready[0].value, 7.02)

    def test_blank_rows_above_the_headings_are_skipped(self):
        path = self.write("padded.csv", "\n\nLocation,Test,Value\nInfluent,pH,7.02\n")
        table = importers.read_table(path)
        self.assertEqual(table.headers, ["Location", "Test", "Value"])
        self.assertEqual(len(table.rows), 1)

    def test_a_file_saved_by_excel_with_a_byte_order_mark_is_read(self):
        path = self.root / "bom.csv"
        path.write_text("Location,Test,Value\nInfluent,pH,7.02\n", encoding="utf-8-sig")
        self.assertEqual(importers.read_table(path).headers, ["Location", "Test", "Value"])

    def test_an_empty_file_says_so(self):
        path = self.write("empty.csv", "\n\n")
        with self.assertRaises(importers.ImportFailed) as caught:
            importers.read_table(path)
        self.assertIn("empty", str(caught.exception))

    def test_a_format_that_cannot_hold_readings_is_refused_clearly(self):
        path = self.root / "scan.pdf"
        path.write_bytes(b"%PDF-1.4")
        with self.assertRaises(importers.ImportFailed) as caught:
            importers.read_table(path)
        self.assertIn("CSV", str(caught.exception))

    def test_a_missing_file_says_so(self):
        with self.assertRaises(importers.ImportFailed):
            importers.read_table(self.root / "nothing.csv")


@unittest.skipUnless(openpyxl, "openpyxl is not installed")
class ExcelTests(ImportTestCase):
    def workbook(self, rows, sheet="Readings", extra_sheet=None):
        book = openpyxl.Workbook()
        sheet_one = book.active
        sheet_one.title = sheet
        for row in rows:
            sheet_one.append(row)
        if extra_sheet:
            book.create_sheet(extra_sheet).append(["something else"])
        path = self.root / "book.xlsx"
        book.save(path)
        return path

    def test_a_workbook_grid_is_read_from_the_first_sheet(self):
        path = self.workbook([
            ["Test", "Influent", "Effluent"],
            ["pH", 7.02, 7.26],
            ["Total Solids", 3.4, 0.4],
        ], extra_sheet="Notes")

        table = importers.read_table(path)
        self.assertEqual(table.sheet, "Readings")
        plan = self.plan_for(path)
        self.assertEqual(len(plan.ready), 4)

    def test_the_sheets_can_be_listed_and_chosen_between(self):
        path = self.workbook([["Test", "Influent"], ["pH", 7.02]], extra_sheet="Second")
        self.assertEqual(importers.sheet_names(path), ["Readings", "Second"])
        self.assertEqual(importers.read_table(path, "Second").headers, ["something else"])

    def test_numbers_stay_numbers_rather_than_text(self):
        path = self.workbook([["Location", "Test", "Value"], ["Influent", "pH", 7.02]])
        plan = self.plan_for(path)
        self.assertEqual(plan.ready[0].value, 7.02)

    def test_a_csv_file_is_not_offered_a_sheet_list(self):
        self.assertEqual(importers.sheet_names(self.write("x.csv", "a\n1\n")), [])


if __name__ == "__main__":
    unittest.main()
