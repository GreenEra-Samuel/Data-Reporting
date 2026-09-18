"""Export measurements to CSV or Excel, and look after the data file."""

from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import config, exporters, files
from . import theme, widgets


class ExportTab(widgets.DeferredRefresh, ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=(12, 10))
        self.app = app
        self.db = app.db
        self.summary_var = tk.StringVar(value="")
        self.from_var = tk.StringVar()
        self.to_var = tk.StringVar()

        self._build_range()
        self._build_actions()
        self._build_storage()

        app.subscribe("values_changed", self.refresh_summary)
        app.subscribe("runs_changed", self.reload)
        app.subscribe("setup_changed", self.refresh_summary)
        self.reload()

    # --------------------------------------------------------------- range

    def _build_range(self) -> None:
        box = ttk.Labelframe(self, text="What to export", padding=12)
        box.pack(fill="x")

        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Label(row, text="From").pack(side="left")
        ttk.Entry(row, textvariable=self.from_var, width=13).pack(side="left", padx=(6, 12))
        ttk.Label(row, text="To").pack(side="left")
        ttk.Entry(row, textvariable=self.to_var, width=13).pack(side="left", padx=(6, 16))

        for text, days in (("Today", 0), ("Last 7 days", 6), ("Last 30 days", 29)):
            ttk.Button(row, text=text, command=lambda d=days: self.set_range(d)).pack(
                side="left", padx=(0, 4))
        ttk.Button(row, text="All data", command=self.set_all_range).pack(side="left", padx=(0, 4))

        self.from_var.trace_add("write", lambda *_: self.refresh_summary())
        self.to_var.trace_add("write", lambda *_: self.refresh_summary())

        ttk.Label(box, textvariable=self.summary_var, style="SubHeading.TLabel").pack(
            anchor="w", pady=(12, 0))
        ttk.Label(box, text="Dates are YYYY-MM-DD. Leave a box empty for no limit on that end.",
                  style="Muted.TLabel").pack(anchor="w")

    # ------------------------------------------------------------- actions

    def _build_actions(self) -> None:
        box = ttk.Labelframe(self, text="Export", padding=12)
        box.pack(fill="x", pady=(12, 0))

        buttons = [
            ("Excel workbook (.xlsx)", self.export_excel, True,
             "Every reading, the statistics, and a one-row-per-location sheet - "
             "four tabs in one file."),
            ("Every reading (.csv)", self.export_raw, False,
             "One row per replicate: the full record, including notes."),
            ("Statistics (.csv)", self.export_summary, False,
             "One row per run/location/test with n, mean, SD, %RSD, min, max and range."),
            ("One row per location (.csv)", self.export_wide, False,
             "Mean of each test across the columns - the layout to chart or pivot."),
        ]
        row = ttk.Frame(box)
        row.pack(fill="x")
        for text, command, accent, tip in buttons:
            button = ttk.Button(row, text=text, command=command,
                                style="Accent.TButton" if accent else "TButton")
            button.pack(side="left", padx=(0, 8))
            widgets.ToolTip(button, tip)

        self.excel_note = ttk.Label(box, text="", style="Muted.TLabel")
        self.excel_note.pack(anchor="w", pady=(10, 0))
        if not exporters.excel_available():
            self.excel_note.configure(
                text="Excel export is unavailable in this build - the CSV files open in Excel too."
            )
        else:
            self.excel_note.configure(
                text="Exports are saved to your MeasureLog folder unless you choose somewhere else."
            )

    # ------------------------------------------------------------- storage

    def _build_storage(self) -> None:
        box = ttk.Labelframe(self, text="Your data file", padding=12)
        box.pack(fill="both", expand=True, pady=(12, 0))

        path_text = str(config.db_path())
        entry = ttk.Entry(box, width=80)
        entry.insert(0, path_text)
        entry.configure(state="readonly")
        entry.pack(fill="x")

        ttk.Label(
            box,
            text="Everything you enter lives in this one file, alongside any documents "
                 "attached to your runs. Copy the folder to move your records to another "
                 "computer. It can sit on a network drive if only one person has the app "
                 "open at a time - but not in a sync folder; see below.",
            style="Muted.TLabel", wraplength=760, justify="left",
        ).pack(anchor="w", pady=(8, 10))

        self._build_sync_warning(box)

        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Button(row, text="Open data folder", command=self.open_folder).pack(side="left")
        ttk.Button(row, text="Back up now", command=self.backup).pack(side="left", padx=6)
        ttk.Button(row, text="Save a copy as…", command=self.save_copy).pack(side="left")

        self.storage_note = ttk.Label(box, text="", style="Muted.TLabel")
        self.storage_note.pack(anchor="w", pady=(10, 0))

    def _build_sync_warning(self, box: ttk.Labelframe) -> None:
        """Warn when the data folder sits inside OneDrive, Drive or Dropbox.

        Worth saying loudly: Windows often redirects Documents into OneDrive,
        so this can be true without anyone having chosen it.
        """
        service = config.sync_service_for()
        if service is None:
            return

        warning = tk.Frame(box, background=theme.BAD_BG, padx=12, pady=10,
                           highlightthickness=1, highlightbackground=theme.BAD_FG)
        warning.pack(fill="x", pady=(0, 10))
        tk.Label(
            warning, text=f"\u26a0  Your data folder is inside {service}",
            background=theme.BAD_BG, foreground=theme.BAD_FG, anchor="w",
            font=("TkDefaultFont", 9, "bold"),
        ).pack(fill="x")
        tk.Label(
            warning,
            text=f"{service} copies the whole database file and knows nothing about the "
                 "locks the app uses to keep it consistent. If two computers ever sync the "
                 "same folder, your readings can be lost or corrupted.\n\n"
                 "Safe on one computer that nobody else syncs to. To move it, put a file "
                 "called datadir.txt next to MeasureLog.exe containing a folder path "
                 "outside the synced area.\n\n"
                 "Exports are unaffected - saving a workbook into a synced folder is fine.",
            background=theme.BAD_BG, foreground=theme.TEXT, anchor="w", justify="left",
            wraplength=720,
        ).pack(fill="x", pady=(4, 0))

    # ---------------------------------------------------------------- data

    def reload(self, *_args) -> None:
        if self.defer():
            return
        if not self.from_var.get() and not self.to_var.get():
            self.set_all_range()
        else:
            self.refresh_summary()

    def set_range(self, days_back: int) -> None:
        today = date.today()
        self.from_var.set((today - timedelta(days=days_back)).isoformat())
        self.to_var.set(today.isoformat())

    def set_all_range(self) -> None:
        low, high = self.db.date_bounds()
        self.from_var.set(low or "")
        self.to_var.set(high or "")

    def current_rows(self):
        return self.db.fetch_long_rows(
            date_from=widgets.normalise_date(self.from_var.get()),
            date_to=widgets.normalise_date(self.to_var.get()),
        )

    def refresh_now(self) -> None:
        self.reload()

    def refresh_summary(self, *_args) -> None:
        if self.defer():
            return
        try:
            self.summary_var.set(exporters.describe(self.current_rows()))
        except Exception as error:  # pragma: no cover - defensive
            self.summary_var.set(str(error))

    # ------------------------------------------------------------- exports

    def _ask_path(self, prefix: str, extension: str, description: str) -> Path | None:
        rows_exist = bool(self.current_rows())
        if not rows_exist:
            messagebox.showinfo(
                "Nothing to export",
                "No readings fall in this date range. Widen the dates and try again.",
                parent=self,
            )
            return None
        filename = exporters.default_filename(
            prefix, extension, self.from_var.get().strip(), self.to_var.get().strip()
        )
        chosen = filedialog.asksaveasfilename(
            parent=self, title="Save export", initialdir=str(config.exports_dir()),
            initialfile=filename, defaultextension=f".{extension}",
            filetypes=[(description, f"*.{extension}"), ("All files", "*.*")],
        )
        return Path(chosen) if chosen else None

    def export_raw(self) -> None:
        self._run_export("measurelog_readings", "csv", "CSV file",
                         lambda path, rows: exporters.export_raw_csv(path, rows))

    def export_summary(self) -> None:
        self._run_export("measurelog_statistics", "csv", "CSV file",
                         lambda path, rows: exporters.export_summary_csv(path, rows))

    def export_wide(self) -> None:
        self._run_export("measurelog_by_location", "csv", "CSV file",
                         lambda path, rows: exporters.export_wide_csv(path, rows))

    def export_excel(self) -> None:
        if not exporters.excel_available():
            messagebox.showinfo(
                "Excel export unavailable",
                "This build cannot write .xlsx files. Use one of the CSV exports - "
                "Excel opens those directly.",
                parent=self,
            )
            return
        self._run_export(
            "measurelog", "xlsx", "Excel workbook",
            lambda path, rows: exporters.export_excel(
                path, rows, self.db.list_locations(), self.db.list_tests()
            ),
        )

    def _run_export(self, prefix: str, extension: str, description: str, writer) -> None:
        path = self._ask_path(prefix, extension, description)
        if path is None:
            return
        rows = self.current_rows()
        try:
            written = writer(path, rows)
        except exporters.ExportError as error:
            messagebox.showerror("Export failed", str(error), parent=self)
            return
        except OSError as error:
            messagebox.showerror("Export failed", f"Could not write the file:\n{error}",
                                 parent=self)
            return

        if messagebox.askyesno(
            "Export finished",
            f"{len(rows)} reading(s) written to:\n{written}\n\nOpen the folder now?",
            parent=self,
        ):
            self.open_path(written.parent)

    # ------------------------------------------------------------- storage

    def backup(self) -> None:
        made = config.make_backup(keep=config.BACKUP_KEEP)
        if made is None:
            made = self._forced_backup()
        self.storage_note.configure(text=f"Backup saved: {made}")
        messagebox.showinfo("Backup saved", f"A copy of your data was saved to:\n{made}",
                            parent=self)

    def _forced_backup(self) -> Path:
        """config.make_backup() skips if today's backup exists; this always writes one."""
        import shutil
        from datetime import datetime

        target = config.backups_dir() / f"measurelog-{datetime.now():%Y%m%d-%H%M%S}.db"
        shutil.copy2(config.db_path(), target)
        return target

    def save_copy(self) -> None:
        chosen = filedialog.asksaveasfilename(
            parent=self, title="Save a copy of the data file",
            initialdir=str(Path.home()), initialfile=config.DB_FILENAME,
            defaultextension=".db", filetypes=[("MeasureLog data", "*.db"), ("All files", "*.*")],
        )
        if not chosen:
            return
        import shutil

        try:
            shutil.copy2(config.db_path(), chosen)
        except OSError as error:
            messagebox.showerror("Could not copy", str(error), parent=self)
            return
        self.storage_note.configure(text=f"Copy saved: {chosen}")

    def open_folder(self) -> None:
        self.open_path(config.data_dir())

    @staticmethod
    def open_path(path: Path) -> None:
        """Open a folder in the system file browser."""
        if not files.open_in_system(path):  # pragma: no cover - platform dependent
            messagebox.showinfo("Folder", str(path))
