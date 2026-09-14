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
        ttk.Label(
            self,
            text="Double-click a run to open it for entry.  Ctrl-click or Shift-click to pick "
                 "several at a time, then Delete.",
            style="Muted.TLabel",
        ).pack(fill="x", pady=(0, 6))

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True)

        columns = ("date", "time", "label", "operator", "values", "notes")
        self.tree = ttk.Treeview(holder, columns=columns, show="headings",
                                 selectmode="extended")
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
        self.tree.bind("<Control-a>", lambda _e: self._select_all())
        self.tree.bind("<Control-A>", lambda _e: self._select_all())

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

    def selected_run_ids(self) -> list[int]:
        """Every selected run, in the order the list shows them."""
        selected = {int(item) for item in self.tree.selection()}
        return [int(item) for item in self.tree.get_children() if int(item) in selected]

    def selected_run_id(self) -> int | None:
        """The selected run, when exactly one is selected."""
        ids = self.selected_run_ids()
        return ids[0] if len(ids) == 1 else None

    def _require_one(self) -> int | None:
        ids = self.selected_run_ids()
        if not ids:
            messagebox.showinfo("Pick a run", "Select a run in the list first.", parent=self)
            return None
        if len(ids) > 1:
            messagebox.showinfo(
                "One at a time",
                f"{len(ids)} runs are selected. This works on one run at a time - "
                "click a single run and try again.",
                parent=self,
            )
            return None
        return ids[0]

    def _select_all(self) -> str:
        self.tree.selection_set(self.tree.get_children())
        return "break"

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
        run_id = self._require_one()
        if run_id is None:
            return
        self.app.current_run_id = run_id
        self.app.notify("run_selected", source=self)
        self.app.show_entry_tab()

    def edit_selected(self) -> None:
        run_id = self._require_one()
        if run_id is None:
            return
        run = self.db.get_run(run_id)
        updated = RunDialog(self, run).show()
        if updated is None:
            return
        self.db.update_run(updated)
        self.app.notify("runs_changed", source=self)

    def duplicate_selected(self) -> None:
        run_id = self._require_one()
        if run_id is None:
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
        """Delete every selected run, and the readings recorded against them."""
        run_ids = self.selected_run_ids()
        if not run_ids:
            messagebox.showinfo("Pick a run", "Select one or more runs first.", parent=self)
            return

        runs = [self.db.get_run(run_id) for run_id in run_ids]
        total = sum(self.db.count_values(run_id=run_id) for run_id in run_ids)

        if len(runs) == 1:
            question = f"Delete the run on {runs[0].display}?"
        else:
            listing = [f"\u2022 {run.display}" for run in runs[:12]]
            if len(runs) > 12:
                listing.append(f"\u2022 ...and {len(runs) - 12} more")
            question = f"Delete these {len(runs)} runs?\n\n" + "\n".join(listing)

        if not messagebox.askyesno(
            "Delete run" if len(runs) == 1 else "Delete runs",
            f"{question}\n\n"
            f"{total} reading(s) will be deleted. This cannot be undone.",
            parent=self,
        ):
            return

        for run_id in run_ids:
            self.db.delete_run(run_id)
        if self.app.current_run_id in run_ids:
            self.app.current_run_id = None
        self.app.notify("runs_changed", source=self)
