"""Launch MeasureLog. This module is the entry point PyInstaller bundles.

Command line:
    MeasureLog.exe                 start the app
    MeasureLog.exe --version       print the version and exit
    MeasureLog.exe --selftest      check this build works, then exit (0 = good)
    MeasureLog.exe --data-dir DIR  use DIR for the database instead of the default
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="MeasureLog", add_help=True)
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    parser.add_argument("--selftest", action="store_true",
                        help="verify this build can store and export data, then exit")
    parser.add_argument("--data-dir", metavar="DIR",
                        help="folder to keep the database in (overrides the default)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.data_dir:
        os.environ["MEASURELOG_DATA_DIR"] = args.data_dir

    if args.version:
        from measurelog import APP_NAME, APP_VERSION

        print(f"{APP_NAME} {APP_VERSION}")
        return 0

    if args.selftest:
        return selftest()

    try:
        from measurelog.ui.app import run
    except ImportError as error:  # pragma: no cover - only on a broken build
        print(f"MeasureLog could not start: {error}", file=sys.stderr)
        return 1

    try:
        run()
    except Exception:  # pragma: no cover - last-resort crash report
        # A windowed .exe has no console: sys.stderr is None there, so printing
        # the traceback must not be allowed to swallow the crash dialog.
        try:
            traceback.print_exc()
        except Exception:
            pass
        _report_crash()
        return 1
    return 0


def selftest() -> int:
    """Exercise the parts of a packaged build that can silently go missing.

    Checks that the database layer, the statistics, the CSV writer, the bundled
    Excel writer and Tk itself all survived packaging. Prints a line per check;
    returns 0 only when every one passes.
    """
    import tempfile
    from pathlib import Path

    checks: list[tuple[str, bool, str]] = []

    def record(name: str, function) -> None:
        try:
            detail = function() or "ok"
            checks.append((name, True, str(detail)))
        except Exception as error:
            checks.append((name, False, f"{type(error).__name__}: {error}"))

    workspace = Path(tempfile.mkdtemp(prefix="measurelog-selftest-"))
    state: dict = {}

    def check_database():
        from measurelog.db import Database
        from measurelog.models import Location, Test

        db = Database(workspace / "selftest.db")
        state["db"] = db
        location = db.save_location(Location(name="Location 1"))
        test = db.save_test(Test(name="Test 1", unit="mg/L", replicates=3))
        run = db.create_run("2026-01-01", "08:00", "Round 1", "selftest")
        for replicate, value in enumerate((7.01, 7.03, 6.99), start=1):
            db.set_value(run.id, location.id, test.id, replicate, value)
        stored = db.count_values(run_id=run.id)
        assert stored == 3, f"expected 3 readings, stored {stored}"
        state["rows"] = db.fetch_long_rows()
        return f"{stored} readings stored"

    def check_statistics():
        from measurelog.stats import summarize

        stats = summarize([7.01, 7.03, 6.99])
        assert abs(stats.mean - 7.01) < 1e-9, stats.mean
        assert abs(stats.sd - 0.02) < 1e-9, stats.sd
        return f"mean {stats.mean:.4f}, SD {stats.sd:.4f}"

    def check_csv():
        from measurelog import exporters

        path = exporters.export_summary_csv(workspace / "selftest.csv", state["rows"])
        assert path.stat().st_size > 0, "empty CSV"
        return f"{path.stat().st_size} bytes"

    def check_excel():
        from measurelog import exporters

        if not exporters.excel_available():
            raise RuntimeError("openpyxl is missing from this build")
        path = exporters.export_excel(workspace / "selftest.xlsx", state["rows"])
        assert path.stat().st_size > 0, "empty workbook"
        return f"{path.stat().st_size} bytes"

    def check_tk():
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        version = root.tk.call("info", "patchlevel")
        root.destroy()
        return f"Tk {version}"

    def check_icon():
        """The icon is a bundled data file, so it can go missing on its own."""
        import tkinter as tk

        from measurelog import config

        ico = config.resource_path("icon.ico")
        png = config.resource_path("icon.png")
        if ico is None or not ico.exists():
            raise RuntimeError("icon.ico is missing from this build")
        if png is None or not png.exists():
            raise RuntimeError("icon.png is missing from this build")

        root = tk.Tk()
        root.withdraw()
        try:
            image = tk.PhotoImage(file=str(png))
            size = (image.width(), image.height())
        finally:
            root.destroy()
        if size != (256, 256):
            raise RuntimeError(f"icon.png is {size[0]}x{size[1]}, expected 256x256")
        return f"icon.ico {ico.stat().st_size} bytes, icon.png {size[0]}x{size[1]}"

    record("database", check_database)
    record("statistics", check_statistics)
    record("csv export", check_csv)
    record("excel export", check_excel)
    record("tk toolkit", check_tk)
    record("app icon", check_icon)

    if "db" in state:
        state["db"].close()

    for name, passed, detail in checks:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")

    failures = [name for name, passed, _ in checks if not passed]
    if failures:
        print(f"selftest FAILED: {', '.join(failures)}", file=sys.stderr)
        return 1
    print("selftest passed")
    return 0


def _report_crash() -> None:
    """Show the traceback in a dialog; a .exe has no console to print to."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "MeasureLog stopped unexpectedly",
            "Sorry - something went wrong:\n\n"
            f"{traceback.format_exc(limit=3)}\n"
            "Your saved data is untouched.",
        )
        root.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
