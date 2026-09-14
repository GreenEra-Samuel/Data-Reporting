"""Colours, fonts and ttk styling shared by every screen."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

BG = "#f4f5f7"
SURFACE = "#ffffff"
BORDER = "#d6dae0"
TEXT = "#1f2430"
MUTED = "#6b7280"
ACCENT = "#2f5597"
ACCENT_LIGHT = "#dce6f7"

OK_BG = "#e7f6ec"
OK_FG = "#1b6b3a"
WARN_BG = "#fff5e0"
WARN_FG = "#8a5b00"
BAD_BG = "#fde4e4"
BAD_FG = "#9b1c1c"
EMPTY_BG = "#ffffff"
DISABLED_BG = "#eceef1"
ROW_ALT = "#fafbfc"


def apply(root: tk.Misc) -> ttk.Style:
    """Apply the app-wide ttk theme and return the style object."""
    style = ttk.Style(root)
    for candidate in ("vista", "clam", "default"):
        if candidate in style.theme_names():
            style.theme_use(candidate)
            break

    base = tkfont.nametofont("TkDefaultFont")
    try:
        base.configure(size=max(9, base.cget("size")))
    except tk.TclError:
        pass

    root.option_add("*Font", base)
    try:
        root.configure(background=BG)
    except tk.TclError:
        pass

    style.configure(".", background=BG, foreground=TEXT)
    style.configure("TFrame", background=BG)
    style.configure("Surface.TFrame", background=SURFACE)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Surface.TLabel", background=SURFACE)
    style.configure("Heading.TLabel", font=(base.cget("family"), 13, "bold"), foreground=ACCENT)
    style.configure("SubHeading.TLabel", font=(base.cget("family"), 10, "bold"))
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Status.TLabel", foreground=MUTED, background=BG)
    style.configure("Good.TLabel", foreground=OK_FG)
    style.configure("Bad.TLabel", foreground=BAD_FG)
    style.configure("TLabelframe", background=BG)
    style.configure("TLabelframe.Label", background=BG, foreground=ACCENT,
                    font=(base.cget("family"), 10, "bold"))
    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", padding=(16, 8))
    style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, rowheight=24)
    style.configure("Treeview.Heading", font=(base.cget("family"), 9, "bold"))
    style.configure("TButton", padding=(10, 5))
    style.configure("Accent.TButton", padding=(12, 6))
    style.configure("Location.TButton", padding=(14, 7))
    # ttk buttons default to a minimum width of 11 characters, which overflows
    # the narrow Setup panels. A NEGATIVE width is a minimum rather than a fixed
    # size, so short labels stay compact and long ones are never clipped.
    style.configure("Compact.TButton", padding=(6, 4), width=-6)
    style.map("Accent.TButton", background=[("active", ACCENT_LIGHT)])
    return style


def status_colours(status: str) -> tuple[str, str]:
    """Background/foreground pair for a spec status."""
    return {
        "ok": (OK_BG, OK_FG),
        "low": (BAD_BG, BAD_FG),
        "high": (BAD_BG, BAD_FG),
    }.get(status, (EMPTY_BG, TEXT))
