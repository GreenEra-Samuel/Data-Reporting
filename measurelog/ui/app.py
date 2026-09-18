"""The main window: menus, tabs, shortcuts and the small event bus."""

from __future__ import annotations

import tkinter as tk
from collections import defaultdict
from datetime import date
from tkinter import messagebox, ttk

from .. import APP_NAME, APP_VERSION, config
from ..db import Database
from . import theme, widgets
from .entry_tab import EntryTab
from .export_tab import ExportTab
from .files_tab import FilesTab
from .review_tab import ReviewTab
from .runs_tab import RunsTab
from .setup_tab import SetupTab

QUICK_START = """\
1. Setup tab - click "Add from SOP library" and tick the tests you run. They
   arrive with the units, replicate counts and method notes from your SOPs,
   and you can edit any of it afterwards. Anything not in the SOPs goes in
   through "New test". The sampling points from the SOPs (Influent, Digester 1,
   Digester 2, Effluent) are already listed - rename or add to them freely.

2. Entry tab - click "New run" for each round of measurements. Pick a location,
   then type your readings. Enter or the down arrow moves down the column, Tab
   moves across the row. Mean, SD and %RSD appear as you type, and anything
   outside the acceptable range turns red.

   Ctrl+1 to Ctrl+6 jump between locations. Every value is saved the moment you
   move off the cell - there is no save button to forget.

3. Repeat run - starting the next round of the day takes one click. It reuses
   the operator and notes and gives you a fresh, empty grid.

4. Review tab - see one whole run as a tests-by-locations grid, and copy it
   straight into Excel.

5. Files tab - the app's own file browser. Find a photo, a meter printout or a
   certificate and click "Add to this run": MeasureLog keeps its own copy, so
   the paperwork stays with the readings. The same screen imports readings
   from a CSV or Excel file, showing you exactly what it understood before
   anything is written.

6. Export tab - write everything out as an Excel workbook or CSV files for a
   date range you choose.

Your data lives in a single file, so you can copy it to another computer or put
it on a network drive. Keep it out of OneDrive, Google Drive or Dropbox
though - sync tools can corrupt a database they copy behind your back. The
Export tab shows you where it is and warns you if it is somewhere risky.
"""


class MeasureLogApp(tk.Tk):
    def __init__(self, db_path=None):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1180x760")
        self.minsize(900, 600)
        theme.apply(self)
        self._set_icon()

        self.db = Database(db_path or config.db_path())
        self.first_run = self.db.seed_defaults()
        config.make_backup()

        self._subscribers: dict[str, list] = defaultdict(list)
        self.current_run_id: int | None = None
        self.default_replicates = 3
        self.rsd_warning: float | None = 5.0
        self.refresh_settings()

        self._build_tabs()
        self._build_menu()
        self._bind_shortcuts()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        # Held so it can be cancelled: closing the window inside this delay
        # would otherwise run the callback against destroyed widgets.
        self._startup_job = self.after(50, self._startup)

    # ----------------------------------------------------------- lifecycle

    def _startup(self) -> None:
        self._startup_job = None
        last_run = self.db.list_runs(limit=1)
        self.current_run_id = last_run[0].id if last_run else None
        self.entry_tab.reload()
        self.runs_tab.reload()
        self.review_tab.reload()
        self.files_tab.reload()
        self.export_tab.reload()
        if self.first_run:
            self.show_welcome()

    def on_close(self) -> None:
        if self._startup_job is not None:
            try:
                self.after_cancel(self._startup_job)
            except tk.TclError:
                pass
            self._startup_job = None
        try:
            self.entry_tab.commit_focused()
        except Exception:
            pass
        self.db.close()
        self.destroy()

    def refresh_settings(self) -> None:
        self.default_replicates = self.db.get_int_setting("default_replicates", 3)
        raw = self.db.get_setting("rsd_warning", "5")
        try:
            self.rsd_warning = float(raw) if raw not in (None, "") else None
        except (TypeError, ValueError):
            self.rsd_warning = None

    # --------------------------------------------------------------- chrome

    def _set_icon(self) -> None:
        """Put the Green Era Campus mark on the window and taskbar button.

        Both routes are attempted because neither is universal: iconbitmap
        wants a .ico and is Windows-only, while Tk's reading of
        PNG-compressed .ico files is unreliable - so the PNG is applied
        second and wins where it loads.
        """
        ico = config.resource_path("icon.ico")
        if ico and ico.exists():
            try:
                self.iconbitmap(default=str(ico))
            except tk.TclError:
                pass  # Not supported on this platform; harmless.

        png = config.resource_path("icon.png")
        if png and png.exists():
            try:
                self._icon_image = tk.PhotoImage(file=str(png))
                self.iconphoto(True, self._icon_image)
            except tk.TclError:
                pass

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New run\tCtrl+N", command=lambda: self.entry_tab.new_run())
        file_menu.add_separator()
        file_menu.add_command(label="Add a file to this run…", command=self.show_files_tab)
        file_menu.add_command(label="Import readings from a file…",
                              command=self.start_import)
        file_menu.add_separator()
        file_menu.add_command(label="Open data folder",
                              command=lambda: self.export_tab.open_folder())
        file_menu.add_command(label="Back up data now", command=lambda: self.export_tab.backup())
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        go_menu = tk.Menu(menubar, tearoff=0)
        for index, (_tab, name) in enumerate(self.tab_order):
            go_menu.add_command(label=name, command=lambda i=index: self.notebook.select(i))
        menubar.add_cascade(label="Go", menu=go_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Quick start\tF1", command=self.show_welcome)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=menubar)

    def _build_tabs(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(8, 10))

        self.entry_tab = EntryTab(self.notebook, self)
        self.runs_tab = RunsTab(self.notebook, self)
        self.review_tab = ReviewTab(self.notebook, self)
        self.files_tab = FilesTab(self.notebook, self)
        self.export_tab = ExportTab(self.notebook, self)
        self.setup_tab = SetupTab(self.notebook, self)

        self.tab_order = (
            (self.entry_tab, "Entry"),
            (self.runs_tab, "Runs"),
            (self.review_tab, "Review"),
            (self.files_tab, "Files"),
            (self.export_tab, "Export"),
            (self.setup_tab, "Setup"),
        )
        for tab, title in self.tab_order:
            self.notebook.add(tab, text=f"  {title}  ")

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, _event=None) -> None:
        """Let a tab catch up on changes it skipped while it was hidden."""
        try:
            current = self.notebook.nametowidget(self.notebook.select())
        except (tk.TclError, KeyError):
            return
        if current is not self.entry_tab:
            self.entry_tab.commit_focused()
        handler = getattr(current, "on_shown", None)
        if callable(handler):
            handler()

    def _bind_shortcuts(self) -> None:
        self.bind_all("<Control-n>", lambda _e: self.entry_tab.new_run())
        self.bind_all("<Control-N>", lambda _e: self.entry_tab.new_run())
        self.bind_all("<Control-s>", lambda _e: self.entry_tab.commit_focused())
        self.bind_all("<F1>", lambda _e: self.show_welcome())
        for index in range(9):
            self.bind_all(
                f"<Control-Key-{index + 1}>",
                lambda _e, i=index: self._jump_to_location(i),
            )

    def _jump_to_location(self, index: int) -> None:
        self.show_entry_tab()
        self.entry_tab.select_location_index(index)
        self.entry_tab.focus_first_cell()

    def show_entry_tab(self) -> None:
        self.select_tab(self.entry_tab)

    def show_files_tab(self) -> None:
        self.select_tab(self.files_tab)

    def show_setup_tab(self) -> None:
        self.select_tab(self.setup_tab)

    def select_tab(self, tab) -> None:
        self.notebook.select(self.notebook.index(tab))

    def start_import(self) -> None:
        """Take the user to the Files tab with the importer already open."""
        self.show_files_tab()
        self.files_tab.import_readings()

    # ------------------------------------------------------------ event bus

    def subscribe(self, event: str, callback) -> None:
        self._subscribers[event].append(callback)

    def notify(self, event: str, source=None) -> None:
        for callback in list(self._subscribers.get(event, [])):
            try:
                callback()
            except Exception as error:  # pragma: no cover - keep the UI alive
                print(f"{event} handler failed: {error}")

    # --------------------------------------------------------------- helpers

    def suggest_run_label(self) -> str:
        """Name the next round of the day: Round 1, Round 2, ..."""
        today = date.today().isoformat()
        todays_runs = [run for run in self.db.list_runs(date_from=today, date_to=today)]
        return f"Round {len(todays_runs) + 1}"

    # ----------------------------------------------------------------- help

    def show_welcome(self) -> None:
        window = tk.Toplevel(self)
        window.title(f"{APP_NAME} - quick start")
        window.configure(background=theme.BG)
        window.transient(self)

        frame = ttk.Frame(window, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"Welcome to {APP_NAME}", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Log replicate measurements across your locations, then export them.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 12))

        text = tk.Text(frame, wrap="word", width=78, height=22, relief="flat",
                       background=theme.SURFACE, padx=12, pady=10)
        text.pack(fill="both", expand=True)
        text.insert("1.0", QUICK_START)
        text.configure(state="disabled")

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Go to Setup", style="Accent.TButton",
                   command=lambda: (window.destroy(), self.show_setup_tab())).pack(side="left")
        ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")

        widgets.center_window(window, 660, 620)
        window.grab_set()

    def show_about(self) -> None:
        messagebox.showinfo(
            f"About {APP_NAME}",
            f"{APP_NAME} {APP_VERSION}\n\n"
            "Replicate measurement logging for repeated rounds across multiple locations.\n\n"
            f"Data file:\n{config.db_path()}\n\n"
            f"Backups:\n{config.backups_dir()}",
            parent=self,
        )


def run(db_path=None) -> None:
    app = MeasureLogApp(db_path)
    app.mainloop()
