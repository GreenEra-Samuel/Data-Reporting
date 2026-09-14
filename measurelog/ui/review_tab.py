"""Review one run as a tests-by-locations matrix, with copy-to-Excel."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..models import format_number
from ..stats import spec_status, summarize
from . import theme, widgets

VIEWS = [
    ("Mean", "mean"),
    ("Mean ± SD", "mean_sd"),
    ("%RSD", "rsd"),
    ("Replicates", "values"),
    ("Range", "span"),
]


class ReviewTab(widgets.DeferredRefresh, ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=(12, 10))
        self.app = app
        self.db = app.db
        self.runs = []
        self.run_var = tk.StringVar()
        self.view_var = tk.StringVar(value="mean")
        self.summary_var = tk.StringVar(value="")

        self._build_toolbar()
        self._build_matrix()

        app.subscribe("runs_changed", self.reload)
        app.subscribe("values_changed", self.reload)
        app.subscribe("setup_changed", self.reload)
        app.subscribe("run_selected", self.reload)

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x")

        ttk.Label(bar, text="Run", style="SubHeading.TLabel").pack(side="left", padx=(0, 6))
        self.run_combo = ttk.Combobox(bar, textvariable=self.run_var, state="readonly", width=42)
        self.run_combo.pack(side="left")
        self.run_combo.bind("<<ComboboxSelected>>", lambda _e: self.draw())

        ttk.Label(bar, text="Show").pack(side="left", padx=(16, 6))
        for text, value in VIEWS:
            ttk.Radiobutton(bar, text=text, value=value, variable=self.view_var,
                            command=self.draw).pack(side="left", padx=(0, 4))

        copy_button = ttk.Button(bar, text="Copy table", command=self.copy_table)
        copy_button.pack(side="right")
        widgets.ToolTip(copy_button,
                        "Copy this table to the clipboard, ready to paste into Excel.")

        ttk.Label(self, textvariable=self.summary_var, style="Muted.TLabel").pack(
            fill="x", pady=(8, 8))

    def _build_matrix(self) -> None:
        container = ttk.Frame(self, relief="solid", borderwidth=1)
        container.pack(fill="both", expand=True)
        self.scroller = widgets.ScrollFrame(container)
        self.scroller.pack(fill="both", expand=True)
        self.body = self.scroller.body

        legend = ttk.Frame(self)
        legend.pack(fill="x", pady=(8, 0))
        for text, colour in (("In spec", theme.OK_BG), ("Outside limits", theme.BAD_BG),
                             ("No reading", theme.DISABLED_BG)):
            swatch = tk.Label(legend, text="    ", background=colour, relief="solid",
                              borderwidth=1)
            swatch.pack(side="left", padx=(0, 4))
            ttk.Label(legend, text=text, style="Muted.TLabel").pack(side="left", padx=(0, 14))

    # ---------------------------------------------------------------- data

    def reload(self, *_args) -> None:
        if self.defer():
            return
        self.runs = self.db.list_runs(limit=400)
        self.run_combo.configure(values=[run.display for run in self.runs])
        current = self.app.current_run_id
        index = next((i for i, run in enumerate(self.runs) if run.id == current), 0)
        if self.runs:
            self.run_combo.current(index)
        else:
            self.run_var.set("")
        self.draw()

    def refresh_now(self) -> None:
        self.reload()

    def selected_run(self):
        index = self.run_combo.current()
        if 0 <= index < len(self.runs):
            return self.runs[index]
        return None

    def draw(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

        run = self.selected_run()
        locations = self.db.list_locations(active_only=True)
        tests = self.db.list_tests(active_only=True)
        if run is None or not locations or not tests:
            ttk.Label(self.body, text="Nothing to review yet.", style="Muted.TLabel",
                      background=theme.SURFACE, padding=40).grid(row=0, column=0)
            self.summary_var.set("")
            return

        stored = self.db.get_run_values(run.id)
        view = self.view_var.get()

        self._header_cell("Test", 0, 0, anchor="w")
        for column, location in enumerate(locations, start=1):
            self._header_cell(location.name, 0, column)

        readings = 0
        out_of_spec = 0
        for row, test in enumerate(tests, start=1):
            background = theme.SURFACE if row % 2 else theme.ROW_ALT
            label = tk.Label(self.body, text=test.label, anchor="w", padx=8, pady=4,
                             background=background)
            label.grid(row=row, column=0, sticky="nsew", padx=(0, 1), pady=(0, 1))

            for column, location in enumerate(locations, start=1):
                values = [
                    stored[(location.id, test.id, replicate)].value
                    for replicate in range(1, test.replicates + 1)
                    if (location.id, test.id, replicate) in stored
                ]
                stats = summarize(values)
                readings += stats.n
                status = spec_status(stats.mean, test.lower_limit, test.upper_limit)
                if status in ("low", "high"):
                    out_of_spec += 1

                text = self._cell_text(view, stats, test)
                if stats.n == 0:
                    cell_bg, cell_fg = theme.DISABLED_BG, theme.MUTED
                else:
                    cell_bg, cell_fg = theme.status_colours(status)
                    if status == "none":
                        cell_bg = background

                cell = tk.Label(self.body, text=text or "—", padx=8, pady=4, width=16,
                                background=cell_bg, foreground=cell_fg)
                cell.grid(row=row, column=column, sticky="nsew", padx=(0, 1), pady=(0, 1))
                if stats.n:
                    widgets.ToolTip(cell, self._tooltip(test, location, stats, values))

        self.body.columnconfigure(0, weight=1, minsize=200)
        self.scroller.scroll_to_top()
        self.summary_var.set(
            f"{run.display}   |   {readings} reading(s)   |   "
            f"{out_of_spec} test/location group(s) outside limits"
        )

    def _header_cell(self, text: str, row: int, column: int, anchor: str = "center") -> None:
        tk.Label(self.body, text=text, font=("TkDefaultFont", 9, "bold"),
                 background=theme.ACCENT_LIGHT, padx=8, pady=6, anchor=anchor).grid(
            row=row, column=column, sticky="nsew", padx=(0, 1), pady=(0, 1))

    @staticmethod
    def _cell_text(view: str, stats, test) -> str:
        if stats.n == 0:
            return ""
        if view == "mean":
            return format_number(stats.mean, test.decimals)
        if view == "mean_sd":
            mean = format_number(stats.mean, test.decimals)
            if stats.sd is None:
                return mean
            return f"{mean} ± {format_number(stats.sd, max(test.decimals, 3))}"
        if view == "rsd":
            return "" if stats.rsd is None else f"{stats.rsd:.2f}%"
        if view == "span":
            return format_number(stats.span, test.decimals)
        return f"{stats.n} of {test.replicates}"

    @staticmethod
    def _tooltip(test, location, stats, values) -> str:
        readings = ", ".join(format_number(value, test.decimals) for value in values)
        lines = [
            f"{test.name} at {location.name}",
            f"Readings: {readings}",
            f"Mean: {format_number(stats.mean, test.decimals)}",
        ]
        if stats.sd is not None:
            lines.append(f"SD: {format_number(stats.sd, max(test.decimals, 3))}")
        if stats.rsd is not None:
            lines.append(f"%RSD: {stats.rsd:.2f}%")
        if test.limit_text:
            lines.append(f"Limits: {test.limit_text}")
        return "\n".join(lines)

    def copy_table(self) -> None:
        """Put the visible matrix on the clipboard as tab-separated text."""
        run = self.selected_run()
        if run is None:
            return
        locations = self.db.list_locations(active_only=True)
        tests = self.db.list_tests(active_only=True)
        stored = self.db.get_run_values(run.id)
        view = self.view_var.get()

        lines = ["\t".join(["Test"] + [location.name for location in locations])]
        for test in tests:
            row = [test.label]
            for location in locations:
                values = [
                    stored[(location.id, test.id, replicate)].value
                    for replicate in range(1, test.replicates + 1)
                    if (location.id, test.id, replicate) in stored
                ]
                row.append(self._cell_text(view, summarize(values), test))
            lines.append("\t".join(row))

        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        messagebox.showinfo(
            "Copied",
            f"{len(tests)} row(s) copied.\n\nPaste straight into Excel with Ctrl+V.",
            parent=self,
        )
