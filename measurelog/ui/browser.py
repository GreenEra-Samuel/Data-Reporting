"""A file explorer that lives inside the app.

Windows has a perfectly good Open dialog, and the export screen uses it. This
is here for the other half of the job: a browser that stays on screen while you
work, remembers where you were, shows what each file is in plain words, and
lets you pick several files without the dialog closing between them.

It is a plain widget with no idea what the files are for - the Files tab decides
that - so it can be dropped into any screen that needs one.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable

from .. import files
from . import theme, widgets

# Folders with tens of thousands of entries do exist; drawing them all would
# freeze the window for seconds, and nobody reads past the first screenful.
MAX_ENTRIES = 2000

COLUMNS = {
    "name": ("Name", 280, "w"),
    "kind": ("Type", 150, "w"),
    "size": ("Size", 80, "e"),
    "modified": ("Changed", 130, "w"),
}


class FileBrowser(ttk.Frame):
    """Browse the computer's folders and pick files out of them."""

    def __init__(
        self,
        parent,
        on_activate: Callable[[list[Path]], None] | None = None,
        on_selection: Callable[[list[Path]], None] | None = None,
        on_folder_change: Callable[[Path], None] | None = None,
        start: str | Path | None = None,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self.on_activate = on_activate
        self.on_selection = on_selection
        self.on_folder_change = on_folder_change

        self.folder: Path = self._opening_folder(start)
        self.entries: list[files.Entry] = []
        self._history: list[Path] = []
        self._sort_key = "name"
        self._sort_reverse = False

        self.path_var = tk.StringVar(value=str(self.folder))
        self.filter_var = tk.StringVar(value=files.FILTERS[0][0])
        self.find_var = tk.StringVar()
        self.status_var = tk.StringVar(value="")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self._build_toolbar()
        self._build_panes()
        self._build_footer()
        self.refresh()

    # ------------------------------------------------------------- building

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self.back_button = ttk.Button(bar, text="←", width=3, command=self.go_back)
        self.back_button.pack(side="left")
        widgets.ToolTip(self.back_button, "Back to the folder you were in before")

        up = ttk.Button(bar, text="↑", width=3, command=self.go_up)
        up.pack(side="left", padx=(4, 0))
        widgets.ToolTip(up, "Up to the folder above this one  (Backspace)")

        refresh = ttk.Button(bar, text="⟳", width=3, command=self.refresh)
        refresh.pack(side="left", padx=(4, 8))
        widgets.ToolTip(refresh, "Look again - use this after saving a file from another program")

        entry = ttk.Entry(bar, textvariable=self.path_var)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda _e: self.go_to(self.path_var.get()))
        widgets.ToolTip(entry, "The folder you are looking at. Type a path and press Enter to jump to it.")

        ttk.Button(bar, text="Go", style="Compact.TButton",
                   command=lambda: self.go_to(self.path_var.get())).pack(side="left", padx=(6, 0))

    def _build_panes(self) -> None:
        panes = ttk.Frame(self)
        panes.grid(row=1, column=0, sticky="nsew")
        panes.columnconfigure(1, weight=1)
        panes.rowconfigure(0, weight=1)

        shortcuts = ttk.Labelframe(panes, text="Go straight to", padding=(6, 4))
        shortcuts.grid(row=0, column=0, sticky="nsw", padx=(0, 8))
        self.places_tree = ttk.Treeview(shortcuts, show="tree", selectmode="browse",
                                        height=10, columns=())
        self.places_tree.column("#0", width=150, stretch=False)
        self.places_tree.pack(fill="both", expand=True)
        self.places_tree.bind("<<TreeviewSelect>>", self._on_place_picked)
        self._load_places()

        holder = ttk.Frame(panes)
        holder.grid(row=0, column=1, sticky="nsew")

        self.tree = ttk.Treeview(holder, columns=tuple(COLUMNS), show="headings",
                                 selectmode="extended")
        for key, (title, width, anchor) in COLUMNS.items():
            self.tree.heading(key, text=title, command=lambda k=key: self.sort_by(k))
            self.tree.column(key, width=width, anchor=anchor, stretch=(key == "name"),
                             minwidth=60)
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.tag_configure("folder", foreground=theme.ACCENT)
        self.tree.tag_configure("readable", foreground=theme.OK_FG)
        self.tree.bind("<Double-1>", self._on_activate)
        self.tree.bind("<Return>", self._on_activate)
        self.tree.bind("<BackSpace>", lambda _e: self.go_up())
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _build_footer(self) -> None:
        footer = ttk.Frame(self)
        footer.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        ttk.Label(footer, text="Show").pack(side="left")
        self.filter_box = ttk.Combobox(
            footer, textvariable=self.filter_var, state="readonly", width=26,
            values=[label for label, _ in files.FILTERS],
        )
        self.filter_box.pack(side="left", padx=(6, 12))
        self.filter_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        ttk.Label(footer, text="Find").pack(side="left")
        find = ttk.Entry(footer, textvariable=self.find_var, width=18)
        find.pack(side="left", padx=(6, 0))
        widgets.ToolTip(find, "Show only the files whose name contains what you type")
        self.find_var.trace_add("write", lambda *_: self.refresh())

        ttk.Label(footer, textvariable=self.status_var,
                  style="Muted.TLabel").pack(side="right")

    def _load_places(self) -> None:
        self._places: dict[str, Path] = {}
        for label, path in files.places():
            item = self.places_tree.insert("", "end", text=f"  {label}")
            self._places[item] = path

    # ----------------------------------------------------------- navigation

    @staticmethod
    def _opening_folder(start: str | Path | None) -> Path:
        for candidate in (start, Path.home() / "Documents", Path.home(), Path.cwd()):
            if candidate:
                path = Path(candidate).expanduser()
                try:
                    if path.is_dir():
                        return path
                except OSError:  # pragma: no cover - a dropped network drive
                    continue
        return Path.cwd()  # pragma: no cover - only if even home is unreadable

    def go_to(self, folder: str | Path, remember: bool = True) -> bool:
        """Show a folder. Returns False (and says why) if it cannot be opened."""
        target = Path(str(folder).strip()).expanduser()
        if target.is_file():           # a path typed straight at a file
            target = target.parent
        if not target.is_dir():
            self.status_var.set(f"There is no folder called {target}")
            self.path_var.set(str(self.folder))
            return False
        if remember and target != self.folder:
            self._history.append(self.folder)
        self.folder = target
        self.path_var.set(str(target))
        self.refresh()
        if self.on_folder_change:
            self.on_folder_change(target)
        return True

    def go_up(self) -> None:
        parent = self.folder.parent
        if parent != self.folder:
            self.go_to(parent)

    def go_back(self) -> None:
        if self._history:
            self.go_to(self._history.pop(), remember=False)

    def _on_place_picked(self, _event=None) -> None:
        selection = self.places_tree.selection()
        if selection and selection[0] in self._places:
            self.go_to(self._places[selection[0]])

    # -------------------------------------------------------------- listing

    def current_suffixes(self) -> tuple[str, ...]:
        label = self.filter_var.get()
        for name, suffixes in files.FILTERS:
            if name == label:
                return suffixes
        return ()

    def refresh(self) -> None:
        """Re-read the current folder and redraw the list."""
        try:
            entries = files.listing(self.folder, suffixes=self.current_suffixes(),
                                    name_filter=self.find_var.get())
        except PermissionError:
            self.entries = []
            self._populate()
            self.status_var.set("Windows will not let this program read that folder.")
            return
        except OSError as error:
            self.entries = []
            self._populate()
            self.status_var.set(f"That folder could not be read: {error.strerror or error}")
            return

        self.entries = entries
        self._populate()
        self._report_count()

    def _report_count(self) -> None:
        folders = sum(1 for entry in self.entries if entry.is_dir)
        shown = len(self.entries) - folders
        parts = []
        if folders:
            parts.append(f"{folders} folder{'s' if folders != 1 else ''}")
        parts.append(f"{shown} file{'s' if shown != 1 else ''}")
        text = ", ".join(parts)
        if len(self.entries) > MAX_ENTRIES:
            text += f" - showing the first {MAX_ENTRIES}"
        elif not self.entries:
            text = "Nothing here matching that filter"
        self.status_var.set(text)

    def _sorted_entries(self) -> list[files.Entry]:
        keys = {
            "name": lambda entry: entry.name.lower(),
            "kind": lambda entry: entry.kind.lower(),
            "size": lambda entry: entry.size,
            "modified": lambda entry: entry.modified,
        }
        key = keys.get(self._sort_key, keys["name"])
        ordered = sorted(self.entries, key=key, reverse=self._sort_reverse)
        # A second, stable pass: folders stay together at the top whichever
        # column is sorted and whichever way round it is.
        ordered.sort(key=lambda entry: not entry.is_dir)
        return ordered

    def _populate(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._rows: dict[str, files.Entry] = {}
        for entry in self._sorted_entries()[:MAX_ENTRIES]:
            if entry.is_dir:
                tags = ("folder",)
            else:
                tags = ("readable",) if files.is_readable(entry.path) else ()
            item = self.tree.insert(
                "", "end", tags=tags,
                values=(entry.name, entry.kind, entry.size_text, entry.modified_text),
            )
            self._rows[item] = entry
        if self.on_selection:
            self.on_selection([])

    def sort_by(self, column: str) -> None:
        self._sort_reverse = not self._sort_reverse if column == self._sort_key else False
        self._sort_key = column
        self._populate()

    # ------------------------------------------------------------ selection

    def selected_entries(self) -> list[files.Entry]:
        return [self._rows[item] for item in self.tree.selection() if item in self._rows]

    def selected_paths(self, folders: bool = False) -> list[Path]:
        """The files picked in the list; folders are left out unless asked for."""
        return [entry.path for entry in self.selected_entries()
                if folders or not entry.is_dir]

    def _on_select(self, _event=None) -> None:
        if self.on_selection:
            self.on_selection(self.selected_paths())

    def _on_activate(self, _event=None) -> str | None:
        """Double-click or Enter: walk into a folder, or hand the files over."""
        chosen = self.selected_entries()
        if len(chosen) == 1 and chosen[0].is_dir:
            self.go_to(chosen[0].path)
            return "break"
        picked = [entry.path for entry in chosen if not entry.is_dir]
        if picked and self.on_activate:
            self.on_activate(picked)
        return "break"
