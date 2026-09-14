"""Small reusable Tkinter building blocks."""

from __future__ import annotations

import re
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk
from typing import Callable

from . import theme

# Matches complete and partially typed numbers, so validation can run per keystroke.
PARTIAL_NUMBER = re.compile(r"^[+-]?(\d+\.?\d*|\.\d*)?([eE][+-]?\d*)?$")


def parse_number(text: str) -> float | None:
    """Parse user input into a float. Blank returns None; bad input raises."""
    text = (text or "").strip().replace(",", ".")
    if not text:
        return None
    return float(text)


def try_parse_number(text: str) -> tuple[bool, float | None]:
    try:
        return True, parse_number(text)
    except ValueError:
        return False, None


def today_str() -> str:
    return date.today().isoformat()


def now_time_str() -> str:
    return datetime.now().strftime("%H:%M")


def parse_date(text: str) -> date | None:
    text = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def normalise_date(text: str) -> str | None:
    parsed = parse_date(text)
    return parsed.isoformat() if parsed else None


def normalise_time(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    for fmt in ("%H:%M", "%H%M", "%I:%M %p", "%H:%M:%S"):
        try:
            return datetime.strptime(text.upper(), fmt).strftime("%H:%M")
        except ValueError:
            continue
    return text


class DeferredRefresh:
    """Skip expensive redraws while a notebook tab is hidden.

    A tab mixes this in, calls ``self.defer()`` at the top of its reload, and
    implements ``refresh_now``. The main window calls ``on_shown`` when the tab
    becomes visible, so the work happens once, when it can actually be seen.
    """

    _pending_refresh = False

    def defer(self) -> bool:
        if self.winfo_ismapped():  # type: ignore[attr-defined]
            return False
        self._pending_refresh = True
        return True

    def on_shown(self) -> None:
        if self._pending_refresh:
            self._pending_refresh = False
            self.refresh_now()

    def refresh_now(self) -> None:  # pragma: no cover - overridden by each tab
        raise NotImplementedError


class ScrollFrame(ttk.Frame):
    """A scrollable container whose scrollbars appear only when needed.

    Put content inside ``self.body``. Wide grids (many locations, many
    replicate columns) scroll sideways with Shift+wheel.
    """

    def __init__(self, parent, horizontal: bool = True, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas = tk.Canvas(self, background=theme.SURFACE, highlightthickness=0, bd=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.hbar = None
        if horizontal:
            self.hbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
            self.canvas.configure(xscrollcommand=self.hbar.set)
            self.hbar.grid(row=1, column=0, sticky="ew")

        self.body = ttk.Frame(self.canvas, style="Surface.TFrame")
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self._syncing = False

        self.body.bind("<Configure>", self._on_body_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind_mousewheel(self.canvas)
        self.bind_mousewheel(self.body)

    def _on_body_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._sync_scrollbars()

    def _on_canvas_configure(self, event) -> None:
        # Let narrow content stretch to fill the canvas, but never shrink below it.
        required = self.body.winfo_reqwidth()
        self.canvas.itemconfigure(self._window, width=max(required, event.width))
        self._sync_scrollbars()

    def _sync_scrollbars(self) -> None:
        """Show each scrollbar only while the content overflows that axis."""
        if self._syncing:
            return
        self._syncing = True
        try:
            slack = 2  # ignore sub-pixel rounding
            if self.body.winfo_reqheight() > self.canvas.winfo_height() + slack:
                self.vbar.grid()
            else:
                self.vbar.grid_remove()
            if self.hbar is not None:
                if self.body.winfo_reqwidth() > self.canvas.winfo_width() + slack:
                    self.hbar.grid()
                else:
                    self.hbar.grid_remove()
        except tk.TclError:  # pragma: no cover - window torn down mid-event
            pass
        finally:
            self._syncing = False

    def bind_mousewheel(self, widget: tk.Misc) -> None:
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")        # Windows / macOS
        widget.bind("<Shift-MouseWheel>", self._on_shift_mousewheel, add="+")
        widget.bind("<Button-4>", self._on_mousewheel, add="+")          # X11 scroll up
        widget.bind("<Button-5>", self._on_mousewheel, add="+")          # X11 scroll down
        widget.bind("<Shift-Button-4>", self._on_shift_mousewheel, add="+")
        widget.bind("<Shift-Button-5>", self._on_shift_mousewheel, add="+")

    @staticmethod
    def _wheel_direction(event) -> int:
        if getattr(event, "num", None) == 4:
            return -1
        if getattr(event, "num", None) == 5:
            return 1
        return -1 if event.delta > 0 else 1

    def _on_mousewheel(self, event) -> None:
        if self.vbar.winfo_ismapped():
            self.canvas.yview_scroll(self._wheel_direction(event), "units")

    def _on_shift_mousewheel(self, event) -> str:
        if self.hbar is not None and self.hbar.winfo_ismapped():
            self.canvas.xview_scroll(self._wheel_direction(event), "units")
        return "break"

    def scroll_to_top(self) -> None:
        self.canvas.yview_moveto(0.0)
        self.canvas.xview_moveto(0.0)

    def clear(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()


class NumberEntry(tk.Entry):
    """Entry that only accepts characters which can form a number."""

    def __init__(self, parent, width: int = 9, on_commit: Callable | None = None, **kwargs):
        self.var = kwargs.pop("textvariable", None) or tk.StringVar()
        super().__init__(parent, width=width, textvariable=self.var, **kwargs)
        self.on_commit = on_commit
        check = (self.register(self._validate), "%P")
        self.configure(validate="key", validatecommand=check)

    @staticmethod
    def _validate(proposed: str) -> bool:
        return proposed == "" or bool(PARTIAL_NUMBER.match(proposed.replace(",", ".")))

    @property
    def value(self) -> float | None:
        return try_parse_number(self.var.get())[1]


class LabeledEntry(ttk.Frame):
    """Label above an entry, used by the setup dialogs."""

    def __init__(self, parent, label: str, value: str = "", width: int = 24,
                 hint: str = "", numeric: bool = False):
        super().__init__(parent)
        self.var = tk.StringVar(value=value)
        ttk.Label(self, text=label, style="SubHeading.TLabel").pack(anchor="w")
        if numeric:
            self.entry: tk.Entry = NumberEntry(self, width=width, textvariable=self.var)
        else:
            self.entry = ttk.Entry(self, width=width, textvariable=self.var)
        self.entry.pack(anchor="w", fill="x", pady=(2, 0))
        if hint:
            ttk.Label(self, text=hint, style="Muted.TLabel", wraplength=280).pack(anchor="w")

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, value: str) -> None:
        self.var.set(value)

    def focus(self) -> None:
        self.entry.focus_set()


class ToolTip:
    """Lightweight hover tip - tkinter has no built-in one."""

    def __init__(self, widget: tk.Misc, text: str, delay: int = 500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._after_id: str | None = None
        self._window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        if self.text:
            self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self) -> None:
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self) -> None:
        if self._window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        except tk.TclError:
            return
        self._window = tk.Toplevel(self.widget)
        self._window.wm_overrideredirect(True)
        self._window.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self._window, text=self.text, justify="left", background="#333a45",
            foreground="white", relief="flat", padx=8, pady=4, wraplength=320,
        ).pack()

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._window:
            self._window.destroy()
            self._window = None

    def update_text(self, text: str) -> None:
        self.text = text


def separator(parent, pad: int = 8) -> ttk.Separator:
    line = ttk.Separator(parent, orient="horizontal")
    line.pack(fill="x", pady=pad)
    return line


def center_window(window: tk.Misc, width: int, height: int) -> None:
    window.update_idletasks()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 3)
    window.geometry(f"{width}x{height}+{x}+{y}")
