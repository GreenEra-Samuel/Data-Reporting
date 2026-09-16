"""Show what a spreadsheet is about to put into a run, before it goes in.

An import that silently drops the rows it did not understand is worse than no
import at all, so this dialog always answers three questions first: which
column means what, what will be written, and what will not be - and why.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .. import importers
from . import theme, widgets
from .dialogs import BaseDialog

NONE_LABEL = "(not in this file)"

PREVIEW_COLUMNS = {
    "row": ("Row", 50, "center"),
    "location": ("Location", 130, "w"),
    "test": ("Test", 150, "w"),
    "replicate": ("Rep", 45, "center"),
    "value": ("Value", 80, "e"),
    "outcome": ("What happens", 340, "w"),
}


class ImportDialog(BaseDialog):
    """Map a file's columns onto tests and locations, then import it."""

    def __init__(self, parent, path: str | Path, tests, locations, run_label: str = ""):
        self.path = Path(path)
        self.tests = list(tests)
        self.locations = list(locations)
        self.run_label = run_label

        self.table: importers.Table | None = None
        self.plan: importers.ImportPlan | None = None
        self.error = ""
        self._building = True

        self.sheet_var = tk.StringVar()
        self.layout_var = tk.StringVar(value=importers.LAYOUT_LONG)
        self.key_role_var = tk.StringVar(value="Tests")
        self.key_column_var = tk.StringVar()
        self.column_vars = {role: tk.StringVar()
                            for role in ("location", "test", "value", "replicate", "note")}
        self.overwrite_var = tk.BooleanVar(value=False)
        self.keep_copy_var = tk.BooleanVar(value=True)
        self.summary_var = tk.StringVar(value="")

        self.sheets = self._sheet_names()
        super().__init__(parent, f"Import readings from {self.path.name}",
                         width=920, height=660, ok_text="Import", resizable=True)

    def _sheet_names(self) -> list[str]:
        try:
            return importers.sheet_names(self.path)
        except importers.ImportFailed:
            return []

    # --------------------------------------------------------------- layout

    def build(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)

        self._build_source(parent)
        self._build_shape(parent)
        self._build_mapping(parent)
        self._build_preview(parent)
        self._build_choices(parent)

        self._building = False
        self.reload_file()

    def _build_source(self, parent) -> None:
        box = ttk.Frame(parent)
        box.grid(row=0, column=0, sticky="ew")

        ttk.Label(box, text=self.path.name, style="Heading.TLabel").pack(side="left")
        if self.run_label:
            ttk.Label(box, text=f"  →  {self.run_label}",
                      style="SubHeading.TLabel").pack(side="left")

        if len(self.sheets) > 1:
            ttk.Label(box, text="Sheet").pack(side="left", padx=(16, 6))
            picker = ttk.Combobox(box, textvariable=self.sheet_var, state="readonly",
                                  values=self.sheets, width=22)
            picker.pack(side="left")
            picker.current(0)
            picker.bind("<<ComboboxSelected>>", lambda _e: self.reload_file())

    def _build_shape(self, parent) -> None:
        box = ttk.Labelframe(parent, text="How the file is laid out", padding=(12, 8))
        box.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        ttk.Radiobutton(
            box, text="One row per reading  (columns for the location, the test and the value)",
            variable=self.layout_var, value=importers.LAYOUT_LONG,
            command=self.rebuild_plan,
        ).pack(anchor="w")
        ttk.Radiobutton(
            box, text="A grid  (tests down one side, locations across the top)",
            variable=self.layout_var, value=importers.LAYOUT_WIDE,
            command=self.rebuild_plan,
        ).pack(anchor="w", pady=(2, 0))

    def _build_mapping(self, parent) -> None:
        self.mapping_box = ttk.Labelframe(parent, text="Which column is which", padding=(12, 8))
        self.mapping_box.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        self.long_frame = ttk.Frame(self.mapping_box)
        self.column_boxes: dict[str, ttk.Combobox] = {}
        for index, (role, label) in enumerate((
            ("location", "Location"), ("test", "Test"), ("value", "Value"),
            ("replicate", "Replicate"), ("note", "Note"),
        )):
            cell = ttk.Frame(self.long_frame)
            cell.grid(row=0, column=index, sticky="w", padx=(0, 10))
            ttk.Label(cell, text=label, style="SubHeading.TLabel").pack(anchor="w")
            box = ttk.Combobox(cell, textvariable=self.column_vars[role], state="readonly",
                               width=18)
            box.pack(anchor="w")
            box.bind("<<ComboboxSelected>>", lambda _e: self.rebuild_plan())
            self.column_boxes[role] = box
        ttk.Label(self.long_frame,
                  text="Replicate and Note are optional. Without a replicate column, repeated "
                       "rows for the same test become replicate 1, 2, 3 …",
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=5, sticky="w",
                                             pady=(6, 0))

        self.wide_frame = ttk.Frame(self.mapping_box)
        ttk.Label(self.wide_frame, text="The names down the side are",
                  style="SubHeading.TLabel").grid(row=0, column=0, sticky="w")
        role_box = ttk.Combobox(self.wide_frame, textvariable=self.key_role_var,
                                state="readonly", values=["Tests", "Locations"], width=12)
        role_box.grid(row=0, column=1, sticky="w", padx=(8, 20))
        role_box.bind("<<ComboboxSelected>>", lambda _e: self.rebuild_plan())

        ttk.Label(self.wide_frame, text="and they are in column",
                  style="SubHeading.TLabel").grid(row=0, column=2, sticky="w")
        self.key_box = ttk.Combobox(self.wide_frame, textvariable=self.key_column_var,
                                    state="readonly", width=22)
        self.key_box.grid(row=0, column=3, sticky="w", padx=(8, 0))
        self.key_box.bind("<<ComboboxSelected>>", lambda _e: self.rebuild_plan())
        ttk.Label(self.wide_frame,
                  text="Every other column is read as the opposite: one reading per square.",
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=4, sticky="w",
                                             pady=(6, 0))

    def _build_preview(self, parent) -> None:
        box = ttk.Labelframe(parent, text="What will be imported", padding=(10, 8))
        box.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)

        holder = ttk.Frame(box)
        holder.grid(row=0, column=0, sticky="nsew")
        self.preview = ttk.Treeview(holder, columns=tuple(PREVIEW_COLUMNS), show="headings",
                                    selectmode="browse", height=9)
        for key, (title, width, anchor) in PREVIEW_COLUMNS.items():
            self.preview.heading(key, text=title)
            self.preview.column(key, width=width, anchor=anchor, stretch=(key == "outcome"),
                                minwidth=45)
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.preview.yview)
        self.preview.configure(yscrollcommand=scrollbar.set)
        self.preview.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.preview.tag_configure("problem", background=theme.BAD_BG, foreground=theme.BAD_FG)
        self.preview.tag_configure("ready", foreground=theme.TEXT)

        ttk.Label(box, textvariable=self.summary_var,
                  style="SubHeading.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))

    def _build_choices(self, parent) -> None:
        box = ttk.Frame(parent)
        box.grid(row=4, column=0, sticky="ew", pady=(8, 0))

        overwrite = ttk.Checkbutton(
            box, text="Replace readings already recorded in this run",
            variable=self.overwrite_var)
        overwrite.pack(anchor="w")
        widgets.ToolTip(
            overwrite,
            "Off: anything already typed into the run is left exactly as it is,\n"
            "and only the empty cells are filled.",
        )
        ttk.Checkbutton(
            box, text="Keep a copy of this file with the run as well",
            variable=self.keep_copy_var).pack(anchor="w", pady=(2, 0))

    # ----------------------------------------------------------------- data

    def reload_file(self) -> None:
        """Read the file (or the chosen sheet) and guess what it holds."""
        self.error = ""
        try:
            self.table = importers.read_table(self.path, self.sheet_var.get() or None)
        except importers.ImportFailed as failure:
            self.table, self.plan = None, None
            self.error = str(failure)
            self.summary_var.set(self.error)
            self.preview.delete(*self.preview.get_children())
            return

        guess = importers.guess_mapping(self.table, self.tests, self.locations)
        self._show_mapping(guess)
        self.rebuild_plan()

    def _show_mapping(self, mapping: importers.Mapping) -> None:
        """Push a guessed mapping into the controls without retriggering a rebuild."""
        self._building = True
        headers = self._header_labels()
        for role, box in self.column_boxes.items():
            optional = role in ("replicate", "note")
            box.configure(values=([NONE_LABEL] + headers) if optional else headers)
            index = getattr(mapping, role)
            if index is not None and index < len(headers):
                self.column_vars[role].set(headers[index])
            else:
                # Left blank rather than pointed at the first column: an unasked
                # question is better than a confidently wrong answer.
                self.column_vars[role].set(NONE_LABEL if optional else "")
        self.key_box.configure(values=headers)
        self.key_column_var.set(
            headers[mapping.key_column] if mapping.key_column < len(headers)
            else (headers[0] if headers else "")
        )
        self.key_role_var.set("Tests" if mapping.key_role == "test" else "Locations")
        self.layout_var.set(mapping.layout)
        self._skip = mapping.skip
        self._building = False

    def _header_labels(self) -> list[str]:
        """Number the columns, so two identically named ones can still be told apart."""
        if self.table is None:
            return []
        return [f"{index + 1}. {header or '(no heading)'}"
                for index, header in enumerate(self.table.headers)]

    def _index_of(self, role: str) -> int | None:
        label = self.column_vars[role].get()
        if not label or label == NONE_LABEL:
            return None
        labels = self._header_labels()
        return labels.index(label) if label in labels else None

    def current_mapping(self) -> importers.Mapping:
        if self.layout_var.get() == importers.LAYOUT_WIDE:
            labels = self._header_labels()
            key_label = self.key_column_var.get()
            return importers.Mapping(
                layout=importers.LAYOUT_WIDE,
                key_column=labels.index(key_label) if key_label in labels else 0,
                key_role="test" if self.key_role_var.get() == "Tests" else "location",
                skip=getattr(self, "_skip", ()),
            )
        return importers.Mapping(
            layout=importers.LAYOUT_LONG,
            location=self._index_of("location"),
            test=self._index_of("test"),
            value=self._index_of("value"),
            replicate=self._index_of("replicate"),
            note=self._index_of("note"),
        )

    def rebuild_plan(self, *_args) -> None:
        """Re-read the table through the current mapping and redraw the preview."""
        if self._building or self.table is None:
            return
        self._show_relevant_mapping()
        mapping = self.current_mapping()
        if not mapping.complete:
            self.plan = None
            self.summary_var.set("Choose which column holds the location, the test and the value.")
            self.preview.delete(*self.preview.get_children())
            return
        self.plan = importers.build_plan(self.table, mapping, self.tests, self.locations)
        self._populate_preview()
        self.summary_var.set(self.plan.summary())

    def _show_relevant_mapping(self) -> None:
        wide = self.layout_var.get() == importers.LAYOUT_WIDE
        self.long_frame.pack_forget()
        self.wide_frame.pack_forget()
        (self.wide_frame if wide else self.long_frame).pack(fill="x")

    def _populate_preview(self) -> None:
        self.preview.delete(*self.preview.get_children())
        if self.plan is None:
            return
        # Problems first: they are the rows worth reading before pressing Import.
        rows = sorted(self.plan.rows, key=lambda row: (row.ok, row.source_row))
        for row in rows[:importers.MAX_PREVIEW_ROWS]:
            value = "" if row.value is None else f"{row.value:g}"
            outcome = "Will be imported" if row.ok else row.detail
            self.preview.insert(
                "", "end", tags=("ready" if row.ok else "problem",),
                values=(row.source_row, row.location_name, row.test_name,
                        row.replicate, value, outcome),
            )

    # ------------------------------------------------------------- finishing

    def collect(self):
        if self.error:
            raise ValueError(self.error)
        if self.plan is None:
            raise ValueError("Tell MeasureLog which column holds the location, the test "
                             "and the value, then try again.")
        if not self.plan.ready:
            raise ValueError(
                "None of the rows in that file could be matched to your tests and locations.\n\n"
                "Check the spelling against the Setup tab, or add the missing tests there first."
            )
        return ImportChoice(plan=self.plan, overwrite=self.overwrite_var.get(),
                            keep_copy=self.keep_copy_var.get(), path=self.path)


class ImportChoice:
    """What the user settled on: the plan, and what to do with it."""

    def __init__(self, plan, overwrite: bool, keep_copy: bool, path: Path):
        self.plan = plan
        self.overwrite = overwrite
        self.keep_copy = keep_copy
        self.path = path
