"""Configure the locations, the tests, and a couple of app-wide preferences."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from . import widgets
from .dialogs import LocationDialog, TestDialog, TestLibraryDialog


class SetupTab(widgets.DeferredRefresh, ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=(12, 10))
        self.app = app
        self.db = app.db

        ttk.Label(
            self,
            text="Set up your locations and tests once - the entry screen is built from them.  "
                 "Ctrl-click or Shift-click to pick several at a time, then Delete.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 10))

        # Packed before the panels so it keeps its row on a short window; the
        # panels then expand into whatever is left rather than over the top of it.
        self._build_preferences()

        columns = ttk.Frame(self)
        columns.pack(fill="both", expand=True)
        # Location names are short; test names are long, so give tests the room.
        columns.columnconfigure(0, weight=2, uniform="setup")
        columns.columnconfigure(1, weight=4, uniform="setup")
        columns.rowconfigure(0, weight=1)

        self._build_locations(columns)
        self._build_tests(columns)
        self.reload()

        # Reading counts shown here change as data is entered on other tabs.
        app.subscribe("setup_changed", self.reload)
        app.subscribe("values_changed", self.reload)
        app.subscribe("runs_changed", self.reload)

    # ----------------------------------------------------------- locations

    def _build_locations(self, parent) -> None:
        box = ttk.Labelframe(parent, text="Locations", padding=10)
        box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.location_tree = ttk.Treeview(
            box, columns=("name", "code", "active", "readings"), show="headings",
            selectmode="extended", height=10,
        )
        for key, (title, width, anchor) in {
            "name": ("Location", 150, "w"), "code": ("Code", 60, "center"),
            "active": ("Active", 60, "center"), "readings": ("Readings", 70, "center"),
        }.items():
            self.location_tree.heading(key, text=title)
            self.location_tree.column(key, width=width, anchor=anchor)
        self.location_tree.pack(fill="both", expand=True)
        self.location_tree.bind("<Double-1>", lambda _e: self.edit_location())
        self.location_tree.bind("<Delete>", lambda _e: self.delete_location())
        self.location_tree.bind("<Control-a>", lambda _e: self._select_all(self.location_tree))
        self.location_tree.bind("<Control-A>", lambda _e: self._select_all(self.location_tree))

        primary = ttk.Frame(box)
        primary.pack(fill="x", pady=(8, 0))
        ttk.Button(primary, text="Add location…", style="Accent.TButton",
                   command=self.add_location).pack(side="left")

        bar = ttk.Frame(box)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Button(bar, text="Edit", style="Compact.TButton",
                   command=self.edit_location).pack(side="left")
        ttk.Button(bar, text="▲", width=3,
                   command=lambda: self.move_location(-1)).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="▼", width=3,
                   command=lambda: self.move_location(1)).pack(side="left", padx=(2, 4))
        ttk.Button(bar, text="Delete", style="Compact.TButton",
                   command=self.delete_location).pack(side="left")

    # --------------------------------------------------------------- tests

    def _build_tests(self, parent) -> None:
        box = ttk.Labelframe(parent, text="Tests", padding=10)
        box.grid(row=0, column=1, sticky="nsew")

        columns = ("name", "unit", "reps", "rsd", "limits", "active", "readings")
        self.test_tree = ttk.Treeview(box, columns=columns, show="headings",
                                      selectmode="extended", height=10)
        for key, (title, width, anchor) in {
            "name": ("Test", 175, "w"), "unit": ("Unit", 102, "center"),
            "reps": ("Reps", 50, "center"), "rsd": ("%RSD", 55, "center"),
            "limits": ("Limits", 82, "center"), "active": ("Active", 55, "center"),
            "readings": ("Readings", 70, "center"),
        }.items():
            self.test_tree.heading(key, text=title)
            # Only the name column grows, so long test names stay readable.
            self.test_tree.column(key, width=width, anchor=anchor,
                                  stretch=(key == "name"), minwidth=width)
        self.test_tree.pack(fill="both", expand=True)
        self.test_tree.bind("<Double-1>", lambda _e: self.edit_test())
        self.test_tree.bind("<Delete>", lambda _e: self.delete_test())
        self.test_tree.bind("<Control-a>", lambda _e: self._select_all(self.test_tree))
        self.test_tree.bind("<Control-A>", lambda _e: self._select_all(self.test_tree))

        primary = ttk.Frame(box)
        primary.pack(fill="x", pady=(8, 0))
        library = ttk.Button(primary, text="Add from SOP library…",
                             style="Accent.TButton", command=self.add_from_library)
        library.pack(side="left")
        widgets.ToolTip(
            library,
            "Pick the tests straight from your laboratory SOPs, with their units,\n"
            "replicate counts and method notes already filled in.",
        )
        ttk.Button(primary, text="New test…", style="Compact.TButton",
                   command=self.add_test).pack(side="left", padx=6)

        bar = ttk.Frame(box)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Button(bar, text="Edit", style="Compact.TButton",
                   command=self.edit_test).pack(side="left")
        ttk.Button(bar, text="▲", width=3,
                   command=lambda: self.move_test(-1)).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="▼", width=3,
                   command=lambda: self.move_test(1)).pack(side="left", padx=(2, 4))
        ttk.Button(bar, text="Delete", style="Compact.TButton",
                   command=self.delete_test).pack(side="left")
        ttk.Button(bar, text="Duplicate", style="Compact.TButton",
                   command=self.duplicate_test).pack(side="left", padx=4)

    # --------------------------------------------------------- preferences

    def _build_preferences(self) -> None:
        box = ttk.Labelframe(self, text="Preferences", padding=10)
        box.pack(side="bottom", fill="x", pady=(12, 0))

        row = ttk.Frame(box)
        row.pack(fill="x")

        self.replicates_var = tk.StringVar(value=str(self.app.default_replicates))
        ttk.Label(row, text="Default replicates for new tests").pack(side="left")
        spin = ttk.Spinbox(row, from_=1, to=20, width=4, textvariable=self.replicates_var,
                           command=self.save_preferences)
        spin.pack(side="left", padx=(8, 24))
        spin.bind("<FocusOut>", lambda _e: self.save_preferences())

        self.rsd_var = tk.StringVar(
            value="" if self.app.rsd_warning is None else str(self.app.rsd_warning))
        ttk.Label(row, text="Warn when %RSD of a group exceeds").pack(side="left")
        rsd = widgets.NumberEntry(row, width=6, textvariable=self.rsd_var)
        rsd.pack(side="left", padx=(8, 4))
        rsd.bind("<FocusOut>", lambda _e: self.save_preferences())
        rsd.bind("<Return>", lambda _e: self.save_preferences())
        ttk.Label(row, text="%  (blank turns the check off)",
                  style="Muted.TLabel").pack(side="left")

    def save_preferences(self) -> None:
        try:
            replicates = max(1, min(20, int(float(self.replicates_var.get() or 3))))
        except ValueError:
            replicates = 3
        self.replicates_var.set(str(replicates))
        self.db.set_setting("default_replicates", str(replicates))

        ok, value = widgets.try_parse_number(self.rsd_var.get())
        if not ok or (value is not None and value <= 0):
            value = None
            self.rsd_var.set("")
        self.db.set_setting("rsd_warning", "" if value is None else str(value))
        self.app.refresh_settings()
        self.app.notify("setup_changed", source=self)

    # ---------------------------------------------------------------- data

    def reload(self, *_args) -> None:
        if self.defer():
            return
        self.locations = self.db.list_locations()
        self.location_tree.delete(*self.location_tree.get_children())
        for location in self.locations:
            self.location_tree.insert(
                "", "end", iid=str(location.id),
                values=(location.name, location.code, "Yes" if location.active else "No",
                        self.db.count_values(location_id=location.id)),
            )

        self.tests = self.db.list_tests()
        self.test_tree.delete(*self.test_tree.get_children())
        for test in self.tests:
            self.test_tree.insert(
                "", "end", iid=str(test.id),
                values=(test.name, test.unit, test.replicates,
                        "—" if test.rsd_limit is None else f"{test.rsd_limit:g}",
                        test.limit_text or "—",
                        "Yes" if test.active else "No",
                        self.db.count_values(test_id=test.id)),
            )

    def refresh_now(self) -> None:
        self.reload()

    def _selected_ids(self, tree: ttk.Treeview) -> list[int]:
        """Every selected row, in the order the list shows them."""
        selected = {int(item) for item in tree.selection()}
        return [int(item) for item in tree.get_children() if int(item) in selected]

    def _require_one(self, tree: ttk.Treeview, noun: str) -> int | None:
        """For actions that only make sense on a single row."""
        ids = self._selected_ids(tree)
        if not ids:
            messagebox.showinfo(f"Pick a {noun}", f"Select a {noun} in the list first.",
                                parent=self)
            return None
        if len(ids) > 1:
            messagebox.showinfo(
                "One at a time",
                f"{len(ids)} {noun}s are selected. This works on one {noun} at a time - "
                f"click a single {noun} and try again.",
                parent=self,
            )
            return None
        return ids[0]

    def _select_all(self, tree: ttk.Treeview) -> str:
        tree.selection_set(tree.get_children())
        return "break"

    @staticmethod
    def _bullets(names: list[str], limit: int = 12) -> str:
        shown = [f"\u2022 {name}" for name in names[:limit]]
        if len(names) > limit:
            shown.append(f"\u2022 ...and {len(names) - limit} more")
        return "\n".join(shown)

    def _delete_selection(self, tree: ttk.Treeview, noun: str, fetch, count_for,
                          save, delete) -> None:
        """Delete every selected row, protecting anything that holds readings.

        Rows with readings can be hidden from the entry screen instead of
        deleted, which keeps their measurements in the exports.
        """
        ids = self._selected_ids(tree)
        if not ids:
            messagebox.showinfo(f"Pick a {noun}", f"Select one or more {noun}s first.",
                                parent=self)
            return

        items = [fetch(item_id) for item_id in ids]
        counts = {item.id: count_for(item.id) for item in items}
        with_data = [item for item in items if counts[item.id]]
        empty = [item for item in items if not counts[item.id]]
        total = sum(counts.values())

        if not with_data:
            listing = self._bullets([item.name for item in items])
            if not messagebox.askyesno(
                f"Delete {noun}s" if len(items) > 1 else f"Delete {noun}",
                f"Delete {self._count_phrase(len(items), noun)}?\n\n{listing}\n\n"
                "No readings have been recorded against "
                f"{'them' if len(items) > 1 else 'it'}.",
                parent=self,
            ):
                return
            for item in items:
                delete(item.id)
            self._announce()
            return

        listing = self._bullets(
            [f"{item.name} ({counts[item.id]} reading(s))" for item in with_data])
        keep_clause = (
            f"Yes - hide {'them' if len(with_data) > 1 else 'it'} from the entry screen "
            "and keep the readings (recommended)"
        )
        if empty:
            keep_clause += f", and delete the {self._count_phrase(len(empty), noun)} with none"
        message = (
            f"{self._count_phrase(len(with_data), noun)} of the {len(items)} selected "
            f"hold readings - {total} in total:\n\n{listing}\n\n"
            f"{keep_clause}.\n"
            f"No - delete everything selected, readings included. This cannot be undone.\n"
            "Cancel - leave things as they are."
        )

        choice = messagebox.askyesnocancel(f"{noun.capitalize()}s hold readings", message,
                                           parent=self)
        if choice is None:
            return
        if choice:
            for item in with_data:
                item.active = False
                save(item)
            for item in empty:
                delete(item.id)
        else:
            for item in items:
                delete(item.id)
        self._announce()

    @staticmethod
    def _count_phrase(count: int, noun: str) -> str:
        return f"1 {noun}" if count == 1 else f"{count} {noun}s"

    def _announce(self) -> None:
        """Tell the rest of the app; our own subscription refreshes this tab."""
        self.app.notify("setup_changed", source=self)

    # ------------------------------------------------------ location actions

    def add_location(self) -> None:
        location = LocationDialog(self).show()
        if location is None:
            return
        try:
            self.db.save_location(location)
        except Exception as error:  # sqlite3.IntegrityError for a duplicate name
            messagebox.showwarning("Could not save", self._friendly(error, location.name),
                                   parent=self)
            return
        self._announce()

    def edit_location(self) -> None:
        location_id = self._require_one(self.location_tree, "location")
        if location_id is None:
            return
        location = LocationDialog(self, self.db.get_location(location_id)).show()
        if location is None:
            return
        try:
            self.db.save_location(location)
        except Exception as error:
            messagebox.showwarning("Could not save", self._friendly(error, location.name),
                                   parent=self)
            return
        self._announce()

    def move_location(self, delta: int) -> None:
        location_id = self._require_one(self.location_tree, "location")
        if location_id is None:
            return
        self.db.move_location(location_id, delta)
        self._announce()
        self.location_tree.selection_set(str(location_id))

    def delete_location(self) -> None:
        self._delete_selection(
            self.location_tree, "location",
            fetch=self.db.get_location,
            count_for=lambda location_id: self.db.count_values(location_id=location_id),
            save=self.db.save_location,
            delete=self.db.delete_location,
        )

    # ---------------------------------------------------------- test actions

    def add_from_library(self) -> None:
        """Add tests straight from the SOP catalogue."""
        existing = {test.name for test in self.db.list_tests()}
        dialog = TestLibraryDialog(self, existing)
        chosen = dialog.show()

        if dialog.custom_requested:
            self.add_test()
            return
        if not chosen:
            return

        added, skipped = [], []
        for entry in chosen:
            try:
                self.db.save_test(entry.to_test())
                added.append(entry.name)
            except Exception:       # a name that slipped past the existing-name filter
                skipped.append(entry.name)

        self._announce()
        message = f"Added {len(added)} test(s):\n\n" + "\n".join(f"\u2022 {n}" for n in added)
        if skipped:
            message += "\n\nAlready present, so left alone:\n" + "\n".join(
                f"\u2022 {n}" for n in skipped)
        messagebox.showinfo("Tests added", message, parent=self)

    def add_test(self) -> None:
        test = TestDialog(self, None, self.app.default_replicates).show()
        if test is None:
            return
        try:
            self.db.save_test(test)
        except Exception as error:
            messagebox.showwarning("Could not save", self._friendly(error, test.name), parent=self)
            return
        self._announce()

    def edit_test(self) -> None:
        test_id = self._require_one(self.test_tree, "test")
        if test_id is None:
            return
        test = TestDialog(self, self.db.get_test(test_id), self.app.default_replicates).show()
        if test is None:
            return
        try:
            self.db.save_test(test)
        except Exception as error:
            messagebox.showwarning("Could not save", self._friendly(error, test.name), parent=self)
            return
        self._announce()

    def duplicate_test(self) -> None:
        test_id = self._require_one(self.test_tree, "test")
        if test_id is None:
            return
        source = self.db.get_test(test_id)
        source.id = None
        source.name = self._unique_name(f"{source.name} copy")
        source.sort_order = 0
        test = TestDialog(self, source, self.app.default_replicates).show()
        if test is None:
            return
        test.id = None
        try:
            self.db.save_test(test)
        except Exception as error:
            messagebox.showwarning("Could not save", self._friendly(error, test.name), parent=self)
            return
        self._announce()

    def move_test(self, delta: int) -> None:
        test_id = self._require_one(self.test_tree, "test")
        if test_id is None:
            return
        self.db.move_test(test_id, delta)
        self._announce()
        self.test_tree.selection_set(str(test_id))

    def delete_test(self) -> None:
        self._delete_selection(
            self.test_tree, "test",
            fetch=self.db.get_test,
            count_for=lambda test_id: self.db.count_values(test_id=test_id),
            save=self.db.save_test,
            delete=self.db.delete_test,
        )

    # -------------------------------------------------------------- helpers

    def _unique_name(self, base: str) -> str:
        existing = {test.name for test in self.db.list_tests()}
        if base not in existing:
            return base
        index = 2
        while f"{base} {index}" in existing:
            index += 1
        return f"{base} {index}"

    @staticmethod
    def _friendly(error: Exception, name: str) -> str:
        if "UNIQUE" in str(error):
            return f"There is already an entry called “{name}”. Pick a different name."
        return str(error)
