"""Modal dialogs for creating runs and editing locations, tests and notes."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..models import Location, Run, Test
from . import theme, widgets


class BaseDialog(tk.Toplevel):
    """Modal dialog with OK / Cancel; ``result`` is None when cancelled."""

    def __init__(self, parent, title: str, width: int = 420, height: int = 320):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.configure(background=theme.BG)

        self.body_frame = ttk.Frame(self, padding=16)
        self.body_frame.pack(fill="both", expand=True)

        buttons = ttk.Frame(self, padding=(16, 0, 16, 14))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", command=self.cancel).pack(side="right")
        ttk.Button(buttons, text="Save", style="Accent.TButton",
                   command=self.ok).pack(side="right", padx=(0, 8))

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
        super().__init__(parent, "Edit test" if test and test.id else "New test", 470, 560)

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

        self.replicates = widgets.LabeledEntry(
            parent, "Replicates per location",
            str(test.replicates if test else self._default_replicates), width=6, numeric=True,
            hint="How many times you repeat this test at each location (3 for triplicates).",
        )
        self.replicates.pack(fill="x", pady=(0, 8))

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

        test = self._test or Test()
        test.name = name
        test.code = self.code.get()
        test.unit = self.unit.get()
        test.decimals = decimals
        test.replicates = replicates
        test.lower_limit = lower
        test.upper_limit = upper
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
