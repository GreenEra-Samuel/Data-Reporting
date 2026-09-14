"""The data entry screen: one location at a time, one row per test."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..models import format_number
from ..stats import flag_outliers, spec_status, summarize
from . import theme, widgets
from .dialogs import NoteDialog, RunDialog

MAX_REPLICATE_COLUMNS = 20


class EntryTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=(12, 10))
        self.app = app
        self.db = app.db

        self.locations = []
        self.tests = []
        self.location_id: int | None = None
        self.cells: dict[tuple[int, int], dict] = {}
        self.rows: dict[int, dict] = {}
        self.order: list[tuple[int, int]] = []
        self._loc_buttons: dict[int, ttk.Radiobutton] = {}

        self.run_var = tk.StringVar()
        self.loc_var = tk.IntVar(value=0)
        self.status_var = tk.StringVar(value="")
        self.progress_var = tk.StringVar(value="")

        self._build_header()
        self._build_location_bar()
        self._build_grid_area()
        self._build_footer()

        app.subscribe("setup_changed", self.reload)
        app.subscribe("runs_changed", self.reload_runs)
        app.subscribe("run_selected", self._on_run_selected_externally)

    # ------------------------------------------------------------ chrome

    def _build_header(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x")

        ttk.Label(bar, text="Run", style="SubHeading.TLabel").pack(side="left", padx=(0, 6))
        self.run_combo = ttk.Combobox(bar, textvariable=self.run_var, state="readonly", width=44)
        self.run_combo.pack(side="left")
        self.run_combo.bind("<<ComboboxSelected>>", self._on_run_picked)

        ttk.Button(bar, text="New run", style="Accent.TButton",
                   command=self.new_run).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="Edit", width=6, command=self.edit_run).pack(side="left", padx=4)
        repeat = ttk.Button(bar, text="Repeat run", command=self.repeat_run)
        repeat.pack(side="left")
        widgets.ToolTip(
            repeat,
            "Start a new empty run now, reusing this run's operator and notes - "
            "for the next round of the day.",
        )

        info = ttk.Frame(self)
        info.pack(fill="x", pady=(6, 0))
        self.run_info = ttk.Label(info, text="", style="Muted.TLabel")
        self.run_info.pack(side="left")
        # On the info line rather than the button row: at narrow window widths
        # the buttons would otherwise squeeze this off the edge.
        self.saved_label = ttk.Label(info, textvariable=self.status_var, style="Status.TLabel")
        self.saved_label.pack(side="right")

    def _build_location_bar(self) -> None:
        frame = ttk.Labelframe(self, text="Location", padding=(10, 8))
        frame.pack(fill="x", pady=(10, 8))
        self.loc_bar = ttk.Frame(frame)
        self.loc_bar.pack(side="left", fill="x", expand=True)
        ttk.Label(frame, textvariable=self.progress_var,
                  style="SubHeading.TLabel").pack(side="right", padx=(10, 0))

    def _build_grid_area(self) -> None:
        container = ttk.Frame(self, relief="solid", borderwidth=1)
        container.pack(fill="both", expand=True)
        self.scroller = widgets.ScrollFrame(container)
        self.scroller.pack(fill="both", expand=True)
        self.grid_body = self.scroller.body

    def _build_footer(self) -> None:
        footer = ttk.Frame(self)
        footer.pack(fill="x", pady=(8, 0))

        ttk.Button(footer, text="Copy previous run to this location",
                   command=self.copy_previous).pack(side="left")
        ttk.Button(footer, text="Clear this location",
                   command=self.clear_location).pack(side="left", padx=6)
        ttk.Button(footer, text="Next location →", style="Accent.TButton",
                   command=self.next_location).pack(side="right")
        ttk.Label(
            self,
            text="Enter or ↓ moves down the column  •  Tab moves across the row  •  "
                 "right-click a cell to add a note  •  every value saves as you type",
            style="Muted.TLabel",
        ).pack(fill="x", pady=(6, 0))

    # ------------------------------------------------------------- loading

    def reload(self, *_args) -> None:
        """Re-read setup and rebuild everything."""
        self.locations = self.db.list_locations(active_only=True)
        self.tests = self.db.list_tests(active_only=True)
        self._build_location_buttons()
        if self.location_id not in {loc.id for loc in self.locations}:
            self.location_id = self.locations[0].id if self.locations else None
            self.loc_var.set(self.location_id or 0)
        self.reload_runs()

    def reload_runs(self, *_args) -> None:
        self.runs = self.db.list_runs(limit=400)
        labels = [run.display for run in self.runs]
        self.run_combo.configure(values=labels)
        current = self.app.current_run_id
        if current is None or current not in {run.id for run in self.runs}:
            current = self.runs[0].id if self.runs else None
            self.app.current_run_id = current
        if current is not None:
            index = next((i for i, run in enumerate(self.runs) if run.id == current), 0)
            self.run_combo.current(index)
        else:
            self.run_var.set("")
        self._refresh_run_info()
        self.rebuild_grid()

    def _on_run_selected_externally(self, *_args) -> None:
        self.reload_runs()

    def _on_run_picked(self, _event=None) -> None:
        index = self.run_combo.current()
        if 0 <= index < len(self.runs):
            self.app.current_run_id = self.runs[index].id
            self._refresh_run_info()
            self.rebuild_grid()

    def _refresh_run_info(self) -> None:
        run = self.current_run()
        if run is None:
            self.run_info.configure(text="No run selected - click New run to start one.")
            return
        bits = []
        if run.operator:
            bits.append(f"Operator: {run.operator}")
        if run.notes:
            bits.append(f"Notes: {run.notes}")
        bits.append(f"{self.db.count_values(run_id=run.id)} values recorded")
        self.run_info.configure(text="   |   ".join(bits))

    def current_run(self):
        run_id = self.app.current_run_id
        return self.db.get_run(run_id) if run_id else None

    # ---------------------------------------------------- location buttons

    def _build_location_buttons(self) -> None:
        for child in self.loc_bar.winfo_children():
            child.destroy()
        self._loc_buttons.clear()

        if not self.locations:
            ttk.Label(self.loc_bar, text="No locations yet - add them on the Setup tab.",
                      style="Muted.TLabel").pack(side="left")
            return

        for index, location in enumerate(self.locations):
            button = ttk.Radiobutton(
                self.loc_bar, text=location.name, value=location.id, variable=self.loc_var,
                style="Toolbutton", width=max(12, len(location.name) + 6),
                command=lambda loc_id=location.id: self.select_location(loc_id),
            )
            button.pack(side="left", padx=(0, 6))
            hint = location.description or location.name
            if index < 9:
                hint = f"{hint}\nShortcut: Ctrl+{index + 1}"
            widgets.ToolTip(button, hint)
            self._loc_buttons[location.id] = button

    def select_location(self, location_id: int) -> None:
        if location_id == self.location_id:
            return
        self.commit_focused()
        self.location_id = location_id
        self.loc_var.set(location_id)
        self.rebuild_grid()

    def select_location_index(self, index: int) -> None:
        if 0 <= index < len(self.locations):
            self.select_location(self.locations[index].id)

    def next_location(self) -> None:
        if not self.locations:
            return
        ids = [loc.id for loc in self.locations]
        try:
            position = ids.index(self.location_id)
        except ValueError:
            position = -1
        self.select_location(ids[(position + 1) % len(ids)])
        self.focus_first_cell()

    # ------------------------------------------------------------- the grid

    def rebuild_grid(self) -> None:
        for child in self.grid_body.winfo_children():
            child.destroy()
        self.cells.clear()
        self.rows.clear()
        self.order.clear()

        run = self.current_run()
        if not self.locations or not self.tests:
            self._placeholder(
                "Add at least one location and one test on the Setup tab,\n"
                "then come back here to enter readings."
            )
            return
        if run is None:
            self._placeholder("Click “New run” above to start a round of measurements.")
            return
        if self.location_id is None:
            self.location_id = self.locations[0].id
            self.loc_var.set(self.location_id)

        max_reps = min(MAX_REPLICATE_COLUMNS, max(test.replicates for test in self.tests))
        self._build_grid_header(max_reps)

        stored = self.db.get_run_values(run.id)
        for row_index, test in enumerate(self.tests):
            self._build_test_row(row_index, test, max_reps, stored)

        self.grid_body.columnconfigure(0, weight=1, minsize=165)
        self.scroller.scroll_to_top()
        self._refresh_progress()
        self._set_status("All changes saved" if stored else "Ready")

    def _placeholder(self, message: str) -> None:
        holder = ttk.Frame(self.grid_body, style="Surface.TFrame", padding=40)
        holder.grid(row=0, column=0, sticky="nsew")
        ttk.Label(holder, text=message, style="Muted.TLabel", justify="center",
                  background=theme.SURFACE).pack(expand=True)
        self.progress_var.set("")

    def _build_grid_header(self, max_reps: int) -> None:
        headers = ["Test"] + [f"R{n}" for n in range(1, max_reps + 1)] + \
                  ["Mean", "SD", "%RSD", "Status"]
        for column, text in enumerate(headers):
            label = tk.Label(
                self.grid_body, text=text, font=("TkDefaultFont", 9, "bold"),
                background=theme.ACCENT_LIGHT, foreground=theme.TEXT,
                padx=8, pady=6, anchor="w" if column == 0 else "center",
            )
            label.grid(row=0, column=column, sticky="nsew", padx=(0, 1), pady=(0, 1))

    def _build_test_row(self, row_index: int, test, max_reps: int, stored: dict) -> None:
        grid_row = row_index + 1
        background = theme.SURFACE if row_index % 2 == 0 else theme.ROW_ALT

        name = tk.Label(
            self.grid_body, text=test.label, anchor="w", background=background,
            padx=8, pady=3, foreground=theme.TEXT,
        )
        name.grid(row=grid_row, column=0, sticky="nsew", padx=(0, 1), pady=(0, 1))
        tip = []
        if test.limit_text:
            tip.append(f"Acceptable range: {test.limit_text} {test.unit}".strip())
        if test.rsd_limit is not None:
            tip.append(f"Replicates should agree within {test.rsd_limit:g}% RSD")
        if test.notes:
            tip.append(test.notes)
        if tip:
            widgets.ToolTip(name, "\n".join(tip))

        for replicate in range(1, max_reps + 1):
            column = replicate
            if replicate > test.replicates:
                filler = tk.Label(self.grid_body, background=theme.DISABLED_BG, text="")
                filler.grid(row=grid_row, column=column, sticky="nsew", padx=(0, 1), pady=(0, 1))
                continue

            cell = self._make_cell(test, replicate, grid_row, column, stored)
            self.order.append((test.id, replicate))
            self.cells[(test.id, replicate)] = cell

        stat_labels = {}
        for offset, key in enumerate(("mean", "sd", "rsd", "status")):
            label = tk.Label(
                self.grid_body, text="", background=background, padx=6, pady=3,
                width=9 if key != "status" else 12, anchor="center", foreground=theme.MUTED,
            )
            label.grid(row=grid_row, column=max_reps + 1 + offset, sticky="nsew",
                       padx=(0, 1), pady=(0, 1))
            stat_labels[key] = label

        self.rows[test.id] = {"test": test, "stats": stat_labels, "background": background}
        self._refresh_row(test.id)

    def _make_cell(self, test, replicate: int, grid_row: int, column: int, stored: dict) -> dict:
        key = (self.location_id, test.id, replicate)
        saved = stored.get(key)
        var = tk.StringVar(value=format_number(saved.value, test.decimals) if saved else "")

        entry = widgets.NumberEntry(
            self.grid_body, width=10, textvariable=var, justify="center",
            relief="flat", highlightthickness=1, highlightbackground=theme.BORDER,
            highlightcolor=theme.ACCENT, background=theme.EMPTY_BG,
        )
        entry.grid(row=grid_row, column=column, sticky="nsew", padx=(0, 1), pady=(0, 1))

        cell = {
            "entry": entry, "var": var, "test": test, "replicate": replicate,
            "stored": saved.value if saved else None, "note": saved.note if saved else "",
        }

        entry.bind("<FocusOut>", lambda _e, c=cell: self.commit(c))
        entry.bind("<FocusIn>", lambda _e, c=cell: self._on_cell_focus(c))
        entry.bind("<Return>", lambda _e, c=cell: self._navigate(c, 1, 0))
        entry.bind("<KP_Enter>", lambda _e, c=cell: self._navigate(c, 1, 0))
        entry.bind("<Shift-Return>", lambda _e, c=cell: self._navigate(c, -1, 0))
        entry.bind("<Down>", lambda _e, c=cell: self._navigate(c, 1, 0))
        entry.bind("<Up>", lambda _e, c=cell: self._navigate(c, -1, 0))
        entry.bind("<Escape>", lambda _e, c=cell: self._revert(c))
        entry.bind("<Button-3>", lambda e, c=cell: self._cell_menu(e, c))
        self.scroller.bind_mousewheel(entry)
        self._paint_cell(cell)
        return cell

    # ------------------------------------------------------- cell behaviour

    def _on_cell_focus(self, cell: dict) -> None:
        cell["entry"].select_range(0, "end")
        test = cell["test"]
        hint = f"{test.name} - replicate {cell['replicate']} of {test.replicates}"
        if test.limit_text:
            hint += f"   |   acceptable range {test.limit_text} {test.unit}".rstrip()
        if cell["note"]:
            hint += f"   |   note: {cell['note']}"
        self._set_status(hint, muted=True)

    def commit(self, cell: dict, force: bool = False) -> bool:
        """Write one cell to the database. Returns False when the text is invalid.

        This deliberately never opens a dialog: it runs from <FocusOut>, and a
        modal window raised while focus is moving traps focus in Tk. Incomplete
        input (a lone "-" or "1e") is restored to the saved value instead, with
        an explanation in the status line.
        """
        run = self.current_run()
        if run is None:
            return True
        text = cell["var"].get()
        ok, value = widgets.try_parse_number(text)
        if not ok:
            self._revert(cell)
            self._set_status(f"“{text}” is not a number - previous value restored",
                             muted=True)
            return False

        if value == cell["stored"] and not force:
            self._paint_cell(cell)
            return True

        self.db.set_value(run.id, self.location_id, cell["test"].id, cell["replicate"],
                          value, cell["note"])
        cell["stored"] = value
        if value is not None:
            cell["var"].set(format_number(value, cell["test"].decimals))
        self._paint_cell(cell)
        self._refresh_row(cell["test"].id)
        self._refresh_progress()
        self._set_status("Saved")
        self.app.notify("values_changed", source=self)
        return True

    def commit_focused(self) -> None:
        """Flush whichever cell currently has focus (before switching context)."""
        try:
            focused = self.focus_get()
        except (KeyError, tk.TclError):
            return
        for cell in self.cells.values():
            if cell["entry"] is focused:
                self.commit(cell)
                return

    def _revert(self, cell: dict) -> None:
        cell["var"].set(format_number(cell["stored"], cell["test"].decimals))
        self._paint_cell(cell)

    def _navigate(self, cell: dict, row_delta: int, column_delta: int) -> str:
        if not self.commit(cell):
            return "break"
        key = (cell["test"].id, cell["replicate"])
        if key not in self.cells:
            return "break"

        test_ids = [test.id for test in self.tests if test.id in self.rows]
        try:
            row_index = test_ids.index(cell["test"].id)
        except ValueError:
            return "break"

        target_row = row_index + row_delta
        replicate = cell["replicate"] + column_delta
        while 0 <= target_row < len(test_ids):
            candidate = (test_ids[target_row], replicate)
            if candidate in self.cells:
                self.cells[candidate]["entry"].focus_set()
                return "break"
            # Skip tests that have fewer replicates than this column.
            target_row += row_delta if row_delta else 1
        return "break"

    def focus_first_cell(self) -> None:
        if self.order:
            self.cells[self.order[0]]["entry"].focus_set()

    def _cell_menu(self, event, cell: dict) -> None:
        menu = tk.Menu(self, tearoff=0)
        label = "Edit note…" if cell["note"] else "Add note…"
        menu.add_command(label=label, command=lambda: self._edit_note(cell))
        menu.add_command(label="Clear this cell", command=lambda: self._clear_cell(cell))
        menu.add_separator()
        menu.add_command(label="Clear this whole row",
                         command=lambda: self._clear_row(cell["test"]))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _edit_note(self, cell: dict) -> None:
        caption = f"{cell['test'].name} - replicate {cell['replicate']}"
        note = NoteDialog(self, caption, cell["note"]).show()
        if note is None:
            return
        run = self.current_run()
        if run is None:
            return
        cell["note"] = note
        self.db.set_value(run.id, self.location_id, cell["test"].id, cell["replicate"],
                          cell["stored"], note)
        self._paint_cell(cell)
        self._set_status("Note saved")
        self.app.notify("values_changed", source=self)

    def _clear_cell(self, cell: dict) -> None:
        cell["note"] = ""
        cell["var"].set("")
        self.commit(cell, force=True)

    def _clear_row(self, test) -> None:
        for replicate in range(1, test.replicates + 1):
            cell = self.cells.get((test.id, replicate))
            if cell:
                self._clear_cell(cell)

    # ----------------------------------------------------------- repainting

    def _paint_cell(self, cell: dict) -> None:
        test = cell["test"]
        status = spec_status(cell["stored"], test.lower_limit, test.upper_limit)
        background, foreground = theme.status_colours(status)
        border = theme.WARN_FG if cell["note"] else theme.BORDER
        cell["entry"].configure(background=background, foreground=foreground,
                                highlightbackground=border)

    def _refresh_row(self, test_id: int) -> None:
        row = self.rows.get(test_id)
        if not row:
            return
        test = row["test"]
        values = [
            self.cells[(test_id, replicate)]["stored"]
            for replicate in range(1, test.replicates + 1)
            if (test_id, replicate) in self.cells
        ]
        stats = summarize(values)
        labels = row["stats"]
        labels["mean"].configure(text=format_number(stats.mean, test.decimals))
        labels["sd"].configure(text=format_number(stats.sd, max(test.decimals, 3)))
        labels["rsd"].configure(text="" if stats.rsd is None else f"{stats.rsd:.2f}")

        text, colour = self._row_status(test, stats, values)
        labels["status"].configure(text=text, foreground=colour)

    def _row_status(self, test, stats, values) -> tuple[str, str]:
        expected = test.replicates
        if stats.n == 0:
            return "—", theme.MUTED

        status = spec_status(stats.mean, test.lower_limit, test.upper_limit)
        if status == "low":
            return "Below limit", theme.BAD_FG
        if status == "high":
            return "Above limit", theme.BAD_FG

        # A test from the SOPs can carry its own QC limit (pH must be under 2%);
        # anything without one falls back to the app-wide setting.
        limit = test.rsd_limit if test.rsd_limit is not None else self.app.rsd_warning
        if flag_outliers(values, limit):
            return "Check spread", theme.WARN_FG
        if stats.n < expected:
            return f"{stats.n} of {expected}", theme.MUTED
        return "Complete" if status == "none" else "In spec", theme.OK_FG

    def _refresh_progress(self) -> None:
        if not self.tests or self.location_id is None:
            self.progress_var.set("")
            return
        done = sum(
            1 for test in self.tests
            if any(
                self.cells.get((test.id, replicate), {}).get("stored") is not None
                for replicate in range(1, test.replicates + 1)
            )
        )
        self.progress_var.set(f"{done} of {len(self.tests)} tests started")
        self._refresh_run_info()

        run = self.current_run()
        if run is None:
            return
        for location in self.locations:
            button = self._loc_buttons.get(location.id)
            if not button:
                continue
            count = self.db.count_values(run_id=run.id, location_id=location.id)
            button.configure(text=location.name if count == 0 else f"{location.name}  ({count})")

    def _set_status(self, text: str, muted: bool = False) -> None:
        self.status_var.set(text)
        self.saved_label.configure(style="Status.TLabel" if muted else "Good.TLabel")

    # --------------------------------------------------------------- actions

    def new_run(self) -> None:
        self.commit_focused()
        previous = self.db.list_runs(limit=1)
        suggested = self.app.suggest_run_label()
        run = RunDialog(
            self, None,
            default_operator=previous[0].operator if previous else
            (self.db.get_setting("last_operator") or ""),
            suggest_label=suggested,
        ).show()
        if run is None:
            return
        created = self.db.create_run(run.run_date, run.run_time, run.label,
                                     run.operator, run.notes)
        if run.operator:
            self.db.set_setting("last_operator", run.operator)
        self.app.current_run_id = created.id
        self.app.notify("runs_changed", source=self)
        self.focus_first_cell()

    def edit_run(self) -> None:
        run = self.current_run()
        if run is None:
            messagebox.showinfo("No run", "Create a run first.", parent=self)
            return
        self.commit_focused()
        updated = RunDialog(self, run).show()
        if updated is None:
            return
        self.db.update_run(updated)
        self.app.notify("runs_changed", source=self)

    def repeat_run(self) -> None:
        """Start the next round of the day from the current run's details."""
        run = self.current_run()
        if run is None:
            messagebox.showinfo("No run", "Create a run first.", parent=self)
            return
        self.commit_focused()
        new_run = self.db.duplicate_run(
            run.id, run_date=widgets.today_str(), run_time=widgets.now_time_str(),
            label=self.app.suggest_run_label(), copy_values=False,
        )
        if new_run:
            self.app.current_run_id = new_run.id
            self.app.notify("runs_changed", source=self)
            self.focus_first_cell()

    def copy_previous(self) -> None:
        run = self.current_run()
        if run is None or self.location_id is None:
            return
        previous_id = self.db.previous_run_id(run.id)
        if previous_id is None:
            messagebox.showinfo("Nothing to copy", "There is no earlier run to copy from.",
                                parent=self)
            return
        previous = self.db.get_run(previous_id)
        location = self.db.get_location(self.location_id)
        if not messagebox.askyesno(
            "Copy previous readings",
            f"Copy the readings for {location.name} from the run on "
            f"{previous.display}?\n\nAnything already entered for this location in the "
            "current run will be overwritten.",
            parent=self,
        ):
            return
        copied = self.db.copy_values_from_run(previous_id, run.id, self.location_id)
        self.rebuild_grid()
        self.app.notify("values_changed", source=self)
        self._set_status(f"Copied {copied} readings")

    def clear_location(self) -> None:
        run = self.current_run()
        if run is None or self.location_id is None:
            return
        location = self.db.get_location(self.location_id)
        count = self.db.count_values(run_id=run.id, location_id=self.location_id)
        if count == 0:
            messagebox.showinfo("Nothing to clear",
                                f"No readings recorded for {location.name} in this run.",
                                parent=self)
            return
        if not messagebox.askyesno(
            "Clear readings",
            f"Delete all {count} readings for {location.name} in this run?\n\n"
            "This cannot be undone.",
            parent=self,
        ):
            return
        self.db.clear_location_values(run.id, self.location_id)
        self.rebuild_grid()
        self.app.notify("values_changed", source=self)
        self._set_status("Location cleared")
