"""Modal dialogs for creating runs and editing locations, tests and notes."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .. import catalog
from ..models import Location, Run, Test
from . import theme, widgets


class BaseDialog(tk.Toplevel):
    """Modal dialog with OK / Cancel; ``result`` is None when cancelled."""

    def __init__(self, parent, title: str, width: int = 420, height: int = 320,
                 ok_text: str = "Save", resizable: bool = False):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.transient(parent.winfo_toplevel())
        self.resizable(resizable, resizable)
        self.configure(background=theme.BG)

        self.body_frame = ttk.Frame(self, padding=16)
        self.body_frame.pack(fill="both", expand=True)

        buttons = ttk.Frame(self, padding=(16, 0, 16, 14))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", command=self.cancel).pack(side="right")
        ttk.Button(buttons, text=ok_text, style="Accent.TButton",
                   command=self.ok).pack(side="right", padx=(0, 8))
        self.button_bar = buttons

        self.bind("<Return>", lambda _e: self.ok())
        self.bind("<Escape>", lambda _e: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.build(self.body_frame)
        widgets.center_window(self, width, height)

    # Subclasses override these two.
    def build(self, parent: ttk.Frame) -> None:  # pragma: no cover - UI layout
        raise NotImplementedError

    def collect(self):
        raise NotImplementedError

    def show(self):
        """Run the dialog modally and return its result."""
        self.grab_set()
        self.wait_window(self)
        return self.result

    def ok(self, _event=None) -> None:
        try:
            value = self.collect()
        except ValueError as error:
            messagebox.showwarning("Check the form", str(error), parent=self)
            return
        if value is None:
            return
        self.result = value
        self.destroy()

    def cancel(self, _event=None) -> None:
        self.result = None
        self.destroy()


class RunDialog(BaseDialog):
    """Create or edit a measurement round."""

    def __init__(self, parent, run: Run | None = None, default_operator: str = "",
                 suggest_label: str = ""):
        self._run = run
        self._default_operator = default_operator
        self._suggest_label = suggest_label
        super().__init__(parent, "Edit run" if run and run.id else "New run", 440, 420)

    def build(self, parent: ttk.Frame) -> None:
        run = self._run
        ttk.Label(
            parent,
            text="A run is one round of measurements - one pass over your locations.",
            style="Muted.TLabel", wraplength=390,
        ).pack(anchor="w", pady=(0, 12))

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 10))
        self.date = widgets.LabeledEntry(
            row, "Date", run.run_date if run else widgets.today_str(), width=14,
        )
        self.date.pack(side="left")
        ttk.Button(row, text="Today", width=7,
                   command=lambda: self.date.set(widgets.today_str())).pack(side="left", padx=(8, 20), pady=(18, 0))
        self.time = widgets.LabeledEntry(
            row, "Time", run.run_time if run else widgets.now_time_str(), width=10,
        )
        self.time.pack(side="left")
        ttk.Button(row, text="Now", width=6,
                   command=lambda: self.time.set(widgets.now_time_str())).pack(side="left", padx=8, pady=(18, 0))

        self.label = widgets.LabeledEntry(
            parent, "Label", run.label if run else self._suggest_label, width=38,
            hint="Which round of the day this is, e.g. Morning, Midday, Batch 3.",
        )
        self.label.pack(fill="x", pady=(0, 10))

        self.operator = widgets.LabeledEntry(
            parent, "Operator", run.operator if run else self._default_operator, width=38,
        )
        self.operator.pack(fill="x", pady=(0, 10))

        ttk.Label(parent, text="Notes", style="SubHeading.TLabel").pack(anchor="w")
        self.notes = tk.Text(parent, height=4, width=44, wrap="word", relief="solid",
                             borderwidth=1, highlightthickness=0)
        self.notes.pack(fill="x", pady=(2, 0))
        if run and run.notes:
            self.notes.insert("1.0", run.notes)
        self.date.focus()

    def collect(self) -> Run:
        run_date = widgets.normalise_date(self.date.get())
        if not run_date:
            raise ValueError("Enter a date as YYYY-MM-DD (or use the Today button).")
        run = self._run or Run()
        run.run_date = run_date
        run.run_time = widgets.normalise_time(self.time.get())
        run.label = self.label.get()
        run.operator = self.operator.get()
        run.notes = self.notes.get("1.0", "end").strip()
        return run


class LocationDialog(BaseDialog):
    """Create or edit a sampling location."""

    def __init__(self, parent, location: Location | None = None):
        self._location = location
        super().__init__(parent, "Edit location" if location and location.id else "New location",
                         420, 360)

    def build(self, parent: ttk.Frame) -> None:
        location = self._location
        self.name = widgets.LabeledEntry(
            parent, "Location name", location.name if location else "", width=36,
            hint="Shown on the entry screen, e.g. Tank A, Line 2, North well.",
        )
        self.name.pack(fill="x", pady=(0, 10))
        self.code = widgets.LabeledEntry(
            parent, "Short code", location.code if location else "", width=14,
            hint="Optional. Used in exports to keep columns narrow.",
        )
        self.code.pack(fill="x", pady=(0, 10))
        self.description = widgets.LabeledEntry(
            parent, "Description", location.description if location else "", width=36,
        )
        self.description.pack(fill="x", pady=(0, 10))

        self.active = tk.BooleanVar(value=location.active if location else True)
        ttk.Checkbutton(parent, text="Active (show on the entry screen)",
                        variable=self.active).pack(anchor="w", pady=(4, 0))
        self.name.focus()

    def collect(self) -> Location:
        name = self.name.get()
        if not name:
            raise ValueError("A location needs a name.")
        location = self._location or Location()
        location.name = name
        location.code = self.code.get()
        location.description = self.description.get()
        location.active = bool(self.active.get())
        return location


class TestDialog(BaseDialog):
    """Create or edit a test (a measurement type)."""

    def __init__(self, parent, test: Test | None = None, default_replicates: int = 3):
        self._test = test
        self._default_replicates = default_replicates
        super().__init__(parent, "Edit test" if test and test.id else "New test", 500, 700)

    def build(self, parent: ttk.Frame) -> None:
        test = self._test
        self.name = widgets.LabeledEntry(
            parent, "Test name", test.name if test else "", width=40,
            hint="e.g. pH, Conductivity, Moisture, Hardness.",
        )
        self.name.pack(fill="x", pady=(0, 8))

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 8))
        self.code = widgets.LabeledEntry(row, "Short code", test.code if test else "", width=12)
        self.code.pack(side="left", padx=(0, 12))
        self.unit = widgets.LabeledEntry(row, "Unit", test.unit if test else "", width=12)
        self.unit.pack(side="left", padx=(0, 12))
        self.decimals = widgets.LabeledEntry(
            row, "Decimals", str(test.decimals if test else 2), width=6, numeric=True,
        )
        self.decimals.pack(side="left")

        quality = ttk.Frame(parent)
        quality.pack(fill="x", pady=(0, 8))
        self.replicates = widgets.LabeledEntry(
            quality, "Replicates per location",
            str(test.replicates if test else self._default_replicates), width=6, numeric=True,
        )
        self.replicates.pack(side="left", padx=(0, 20))
        self.rsd = widgets.LabeledEntry(
            quality, "%RSD warning",
            "" if not test or test.rsd_limit is None else f"{test.rsd_limit:g}",
            width=6, numeric=True,
        )
        self.rsd.pack(side="left")
        ttk.Label(
            parent,
            text="Replicates: how many times you repeat this test at each location "
                 "(3 for triplicates). %RSD warning: flag the group when the replicates "
                 "disagree by more than this - leave blank to use the app-wide setting.",
            style="Muted.TLabel", wraplength=440, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        limits = ttk.Labelframe(parent, text="Acceptable range (optional)", padding=10)
        limits.pack(fill="x", pady=(4, 8))
        inner = ttk.Frame(limits)
        inner.pack(fill="x")
        self.lower = widgets.LabeledEntry(
            inner, "Lower limit",
            "" if not test or test.lower_limit is None else str(test.lower_limit),
            width=12, numeric=True,
        )
        self.lower.pack(side="left", padx=(0, 16))
        self.upper = widgets.LabeledEntry(
            inner, "Upper limit",
            "" if not test or test.upper_limit is None else str(test.upper_limit),
            width=12, numeric=True,
        )
        self.upper.pack(side="left")
        ttk.Label(limits, text="Values outside this range are highlighted in red as you type. "
                               "Leave blank if the test has no limits.",
                  style="Muted.TLabel", wraplength=400).pack(anchor="w", pady=(8, 0))

        ttk.Label(parent, text="Method and notes", style="SubHeading.TLabel").pack(anchor="w")
        self.notes = tk.Text(parent, height=6, width=48, wrap="word", relief="solid",
                             borderwidth=1, highlightthickness=0)
        self.notes.pack(fill="both", expand=True, pady=(2, 8))
        if test and test.notes:
            self.notes.insert("1.0", test.notes)

        self.active = tk.BooleanVar(value=test.active if test else True)
        ttk.Checkbutton(parent, text="Active (show on the entry screen)",
                        variable=self.active).pack(anchor="w", pady=(4, 0))
        self.name.focus()

    def collect(self) -> Test:
        name = self.name.get()
        if not name:
            raise ValueError("A test needs a name.")

        lower = self._number(self.lower.get(), "Lower limit")
        upper = self._number(self.upper.get(), "Upper limit")
        if lower is not None and upper is not None and lower > upper:
            raise ValueError("The lower limit must be smaller than the upper limit.")

        decimals = int(self._number(self.decimals.get(), "Decimals") or 2)
        replicates = int(self._number(self.replicates.get(), "Replicates") or 1)
        if not 0 <= decimals <= 8:
            raise ValueError("Decimals must be between 0 and 8.")
        if not 1 <= replicates <= 20:
            raise ValueError("Replicates must be between 1 and 20.")

        rsd_limit = self._number(self.rsd.get(), "%RSD warning")
        if rsd_limit is not None and rsd_limit <= 0:
            raise ValueError("The %RSD warning must be greater than zero, or blank.")

        test = self._test or Test()
        test.name = name
        test.code = self.code.get()
        test.unit = self.unit.get()
        test.decimals = decimals
        test.replicates = replicates
        test.lower_limit = lower
        test.upper_limit = upper
        test.rsd_limit = rsd_limit
        test.notes = self.notes.get("1.0", "end").strip()
        test.active = bool(self.active.get())
        return test

    @staticmethod
    def _number(text: str, field: str) -> float | None:
        ok, value = widgets.try_parse_number(text)
        if not ok:
            raise ValueError(f"{field} must be a number (or blank).")
        return value


class NoteDialog(BaseDialog):
    """Attach a short note to one replicate."""

    def __init__(self, parent, caption: str, note: str = ""):
        self._caption = caption
        self._note = note
        super().__init__(parent, "Note for this reading", 420, 260)

    def build(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text=self._caption, style="SubHeading.TLabel").pack(anchor="w")
        ttk.Label(parent, text="Notes travel with the value into every export.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        self.text = tk.Text(parent, height=5, width=44, wrap="word", relief="solid",
                            borderwidth=1, highlightthickness=0)
        self.text.pack(fill="both", expand=True)
        self.text.insert("1.0", self._note)
        self.text.focus_set()
        # Return inserts a newline here, so only Ctrl+Return confirms.
        self.unbind("<Return>")
        self.bind("<Control-Return>", lambda _e: self.ok())

    def collect(self) -> str:
        return self.text.get("1.0", "end").strip()


class TestLibraryDialog(BaseDialog):
    """Pick tests from the SOP catalogue instead of typing them in."""

    def __init__(self, parent, existing_names: set[str] | None = None):
        self._existing = {name.strip().lower() for name in (existing_names or set())}
        self._vars: dict[str, tk.BooleanVar] = {}
        self.custom_requested = False
        self.count_var = tk.StringVar(value="")
        super().__init__(parent, "Add tests from your SOPs", 720, 640,
                         ok_text="Add selected", resizable=True)

    def build(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Your laboratory SOPs", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(
            parent,
            text="Tick the tests you run. Each arrives with its units, replicate count and "
                 "method notes already filled in - all of it editable afterwards.",
            style="Muted.TLabel", wraplength=660, justify="left",
        ).pack(anchor="w", pady=(2, 10))

        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(0, 6))
        ttk.Button(toolbar, text="Select all", style="Compact.TButton",
                   command=lambda: self._set_all(True)).pack(side="left")
        ttk.Button(toolbar, text="Clear", style="Compact.TButton",
                   command=lambda: self._set_all(False)).pack(side="left", padx=6)
        ttk.Label(toolbar, textvariable=self.count_var,
                  style="SubHeading.TLabel").pack(side="right")

        holder = ttk.Frame(parent, relief="solid", borderwidth=1)
        holder.pack(fill="both", expand=True)
        self.scroller = widgets.ScrollFrame(holder, horizontal=False)
        self.scroller.pack(fill="both", expand=True)
        self._build_list(self.scroller.body)

        extra = ttk.Frame(self.button_bar)
        extra.pack(side="left")
        ttk.Button(extra, text="Add a different test\u2026",
                   command=self._request_custom).pack(side="left")
        self._update_count()

    def _build_list(self, body: ttk.Frame) -> None:
        body.columnconfigure(0, weight=1)
        row = 0
        for group_name, tests in catalog.grouped():
            heading = tk.Label(
                body, text=group_name, anchor="w", padx=10, pady=5,
                background=theme.ACCENT_LIGHT, foreground=theme.TEXT,
                font=("TkDefaultFont", 9, "bold"),
            )
            heading.grid(row=row, column=0, sticky="ew")
            row += 1

            for test in tests:
                row = self._build_row(body, test, row)

    def _build_row(self, body: ttk.Frame, test, row: int) -> int:
        already = test.name.lower() in self._existing
        frame = ttk.Frame(body, style="Surface.TFrame", padding=(10, 6))
        frame.grid(row=row, column=0, sticky="ew")
        frame.columnconfigure(1, weight=1)

        variable = tk.BooleanVar(value=False)
        self._vars[test.name] = variable
        check = ttk.Checkbutton(frame, variable=variable, command=self._update_count)
        check.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, 8))

        title = test.name if not already else f"{test.name}   \u2014 already in your list"
        label = tk.Label(frame, text=title, anchor="w", background=theme.SURFACE,
                         font=("TkDefaultFont", 9, "bold"),
                         foreground=theme.MUTED if already else theme.TEXT)
        label.grid(row=0, column=1, sticky="w")

        tk.Label(frame, text=f"{test.summary}\n{test.method}", anchor="w", justify="left",
                 background=theme.SURFACE, foreground=theme.MUTED, wraplength=560).grid(
            row=1, column=1, sticky="w")

        if already:
            check.state(["disabled"])
        self.scroller.bind_mousewheel(frame)
        self.scroller.bind_mousewheel(label)
        return row + 1

    def _set_all(self, value: bool) -> None:
        for name, variable in self._vars.items():
            if name.lower() not in self._existing:
                variable.set(value)
        self._update_count()

    def _update_count(self) -> None:
        chosen = len(self.selected())
        available = sum(1 for name in self._vars if name.lower() not in self._existing)
        self.count_var.set(f"{chosen} of {available} selected")

    def selected(self) -> list:
        return [
            test for test in catalog.TESTS
            if self._vars.get(test.name) is not None
            and self._vars[test.name].get()
            and test.name.lower() not in self._existing
        ]

    def _request_custom(self) -> None:
        self.custom_requested = True
        self.result = []
        self.destroy()

    def collect(self) -> list:
        chosen = self.selected()
        if not chosen:
            raise ValueError(
                "No tests are ticked yet. Tick the ones you run, or use "
                "\u201cAdd a different test\u201d for something not in the SOPs."
            )
        return chosen
