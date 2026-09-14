"""Browse, edit and delete past runs."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from . import widgets
from .dialogs import RunDialog


class RunsTab(widgets.DeferredRefresh, ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=(12, 10))
        self.app = app
        self.db = app.db
        self.runs = []
        self.search_var = tk.StringVar()
        self.count_var = tk.StringVar(value="")

        self._build_toolbar()
        self._build_table()
        app.subscribe("runs_changed", self.reload)
        app.subscribe("values_changed", self.reload)
        app.subscribe("setup_changed", self.reload)

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 10))

        ttk.Button(bar, text="New run", style="Accent.TButton",
                   command=self.new_run).pack(side="left")
        ttk.Button(bar, text="Open in Entry", command=self.open_selected).pack(side="left", padx=6)
        ttk.Button(bar, text="Edit", command=self.edit_selected).pack(side="left")
        ttk.Button(bar, text="Duplicate", command=self.duplicate_selected).pack(side="left", padx=6)
        ttk.Button(bar, text="Delete", command=self.delete_selected).pack(side="left")

        ttk.Label(bar, textvariable=self.count_var, style="Muted.TLabel").pack(side="right")
        search = ttk.Entry(bar, textvariable=self.search_var, width=22)
        search.pack(side="right", padx=(8, 16))
        ttk.Label(bar, text="Find").pack(side="right")
        self.search_var.trace_add("write", lambda *_: self._populate())

    def _build_table(self) -> None:
        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True)

        columns = ("date", "time", "label", "operator", "values", "notes")
        self.tree = ttk.Treeview(holder, columns=columns, show="headings", selectmode="browse")
        headings = {
            "date": ("Date", 110), "time": ("Time", 70), "label": ("Run", 150),
            "operator": ("Operator", 130), "values": ("Readings", 90), "notes": ("Notes", 320),
        }
        for key, (title, width) in headings.items():
            self.tree.heading(key, text=title)
            anchor = "center" if key in ("time", "values") else "w"
            self.tree.column(key, width=width, anchor=anchor,
                             stretch=key == "notes")

        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.tag_configure("empty", foreground="#9aa1ab")
        self.tree.bind("<Double-1>", lambda _e: self.open_selected())
        self.tree.bind("<Return>", lambda _e: self.open_selected())
        self.tree.bind("<Delete>", lambda _e: self.delete_selected())

    # ---------------------------------------------------------------- data

    def reload(self, *_args) -> None:
        if self.defer():
            return
        self.runs = self.db.list_runs()
        self._populate()

    def refresh_now(self) -> None:
        self.reload()

    def _populate(self) -> None:
        needle = self.search_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        shown = 0
        for run in self.runs:
            haystack = " ".join(
                [run.run_date, run.run_time, run.label, run.operator, run.notes]
            ).lower()
            if needle and needle not in haystack:
                continue
            shown += 1
            self.tree.insert(
                "", "end", iid=str(run.id),
                values=(run.run_date, run.run_time, run.label, run.operator,
                        run.value_count, run.notes.replace("\n", " ")),
                tags=() if run.value_count else ("empty",),
            )
        total = len(self.runs)
        self.count_var.set(
            f"{shown} of {total} runs" if needle else f"{total} run(s) recorded"
        )
        current = self.app.current_run_id
        if current is not None and self.tree.exists(str(current)):
            self.tree.selection_set(str(current))

    def selected_run_id(self) -> int | None:
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    # ------------------------------------------------------------- actions

    def new_run(self) -> None:
        run = RunDialog(
            self, None,
            default_operator=self.db.get_setting("last_operator") or "",
            suggest_label=self.app.suggest_run_label(),
        ).show()
        if run is None:
            return
        created = self.db.create_run(run.run_date, run.run_time, run.label,
                                     run.operator, run.notes)
        if run.operator:
            self.db.set_setting("last_operator", run.operator)
        self.app.current_run_id = created.id
        self.app.notify("runs_changed", source=self)
        self.app.show_entry_tab()

    def open_selected(self) -> None:
        run_id = self.selected_run_id()
        if run_id is None:
            return
        self.app.current_run_id = run_id
        self.app.notify("run_selected", source=self)
        self.app.show_entry_tab()

    def edit_selected(self) -> None:
        run_id = self.selected_run_id()
        if run_id is None:
            messagebox.showinfo("Pick a run", "Select a run in the list first.", parent=self)
            return
        run = self.db.get_run(run_id)
        updated = RunDialog(self, run).show()
        if updated is None:
            return
        self.db.update_run(updated)
        self.app.notify("runs_changed", source=self)

    def duplicate_selected(self) -> None:
        run_id = self.selected_run_id()
        if run_id is None:
            messagebox.showinfo("Pick a run", "Select a run in the list first.", parent=self)
            return
        source = self.db.get_run(run_id)
        template = RunDialog(self, None, default_operator=source.operator,
                             suggest_label=source.label)
        template.notes.insert("1.0", source.notes)
        run = template.show()
        if run is None:
            return
        created = self.db.create_run(run.run_date, run.run_time, run.label,
                                     run.operator, run.notes)
        self.app.current_run_id = created.id
        self.app.notify("runs_changed", source=self)

    def delete_selected(self) -> None:
        run_id = self.selected_run_id()
        if run_id is None:
            return
        run = self.db.get_run(run_id)
        count = self.db.count_values(run_id=run_id)
        if not messagebox.askyesno(
            "Delete run",
            f"Delete the run on {run.display}?\n\n"
            f"{count} reading(s) will be deleted. This cannot be undone.",
            parent=self,
        ):
            return
        self.db.delete_run(run_id)
        if self.app.current_run_id == run_id:
            self.app.current_run_id = None
        self.app.notify("runs_changed", source=self)
