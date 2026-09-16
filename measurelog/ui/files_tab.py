"""The Files tab: bring files in, keep them with the run, or read readings out.

Two jobs share one screen because they start the same way - find the file.
The browser on the left is the app's own file explorer; what you do with what
you pick is the pair of buttons underneath:

* **Add to this run** copies the file into the data folder and lists it against
  the run, which is what a photo, an instrument printout or a calibration
  certificate wants.
* **Import readings** reads a CSV or Excel file and fills the entry grid from
  it, after showing exactly what it understood.
"""

from __future__ import annotations

import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import config, files, importers
from ..models import Attachment
from . import widgets
from .browser import FileBrowser
from .dialogs import NoteDialog
from .import_dialog import ImportDialog

LAST_FOLDER_KEY = "last_browse_folder"

ATTACHMENT_COLUMNS = {
    "name": ("File", 210, "w"),
    "run": ("Run", 150, "w"),
    "kind": ("Type", 120, "w"),
    "size": ("Size", 70, "e"),
    "added": ("Added", 90, "w"),
    "note": ("What it is", 180, "w"),
}


class FilesTab(widgets.DeferredRefresh, ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=(12, 10))
        self.app = app
        self.db = app.db

        self.runs = []
        self.attachments = []
        self.run_var = tk.StringVar()
        self.every_run_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="")
        self.attached_count_var = tk.StringVar(value="")

        self._build_header()
        self._build_body()
        self._build_status()

        app.subscribe("runs_changed", self.reload)
        app.subscribe("run_selected", self.reload)
        app.subscribe("files_changed", self.reload_attachments)
        self.reload()

    # -------------------------------------------------------------- chrome

    def _build_header(self) -> None:
        ttk.Label(
            self,
            text="Find a file on the left, then add it to the run or read its readings in.  "
                 "Added files are copied into your MeasureLog folder, so they stay with your "
                 "records even if the original is moved or deleted.",
            style="Muted.TLabel", wraplength=1080, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Run", style="SubHeading.TLabel").pack(side="left", padx=(0, 6))
        self.run_combo = ttk.Combobox(bar, textvariable=self.run_var, state="readonly", width=44)
        self.run_combo.pack(side="left")
        self.run_combo.bind("<<ComboboxSelected>>", self._on_run_picked)
        ttk.Label(bar, textvariable=self.attached_count_var,
                  style="SubHeading.TLabel").pack(side="left", padx=(12, 0))

        open_folder = ttk.Button(bar, text="Open the files folder", command=self.open_files_folder)
        open_folder.pack(side="right")
        widgets.ToolTip(open_folder,
                        f"Everything added here is copied into:\n{config.files_dir()}")

    def _build_body(self) -> None:
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3, uniform="files")
        body.columnconfigure(1, weight=2, uniform="files")
        body.rowconfigure(0, weight=1)

        self._build_browser(body)
        self._build_attachments(body)

    def _build_browser(self, parent) -> None:
        box = ttk.Labelframe(parent, text="Your computer", padding=(10, 8))
        box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)

        # The buttons are made before the browser because the browser reports an
        # empty selection as soon as it draws itself, and that switches them off.
        actions = ttk.Frame(box)
        actions.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.attach_button = ttk.Button(actions, text="Add to this run", style="Accent.TButton",
                                        command=lambda: self.attach())
        self.attach_button.pack(side="left")
        widgets.ToolTip(self.attach_button,
                        "Copy the files you have picked into your MeasureLog folder and list\n"
                        "them against this run. Double-clicking a file does the same thing.")

        self.import_button = ttk.Button(actions, text="Import readings…",
                                        command=self.import_readings)
        self.import_button.pack(side="left", padx=(8, 0))
        widgets.ToolTip(self.import_button,
                        "Read a CSV or Excel file of measurements into this run. You see\n"
                        "exactly what was understood before anything is written.")

        ttk.Label(actions, text="CSV and Excel files are shown in green.",
                  style="Muted.TLabel").pack(side="right")

        self.browser = FileBrowser(
            box,
            start=self.db.get_setting(LAST_FOLDER_KEY) or None,
            on_activate=lambda paths: self.attach(paths),
            on_selection=self._on_files_selected,
            on_folder_change=lambda folder: self.db.set_setting(LAST_FOLDER_KEY, str(folder)),
        )
        self.browser.grid(row=0, column=0, sticky="nsew")

    def _build_attachments(self, parent) -> None:
        box = ttk.Labelframe(parent, text="Files kept with your records", padding=(10, 8))
        box.grid(row=0, column=1, sticky="nsew")
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)

        holder = ttk.Frame(box)
        holder.grid(row=0, column=0, sticky="nsew")
        self.tree = ttk.Treeview(holder, columns=tuple(ATTACHMENT_COLUMNS), show="headings",
                                 selectmode="extended")
        for key, (title, width, anchor) in ATTACHMENT_COLUMNS.items():
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor=anchor, stretch=(key == "name"),
                             minwidth=55)
        self._show_run_column(False)
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.tag_configure("missing", foreground="#9b1c1c")
        self.tree.bind("<Double-1>", lambda _e: self.open_selected())
        self.tree.bind("<Return>", lambda _e: self.open_selected())
        self.tree.bind("<Delete>", lambda _e: self.remove_selected())
        self.tree.bind("<Control-a>", lambda _e: self._select_all())
        self.tree.bind("<Control-A>", lambda _e: self._select_all())

        buttons = ttk.Frame(box)
        buttons.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(buttons, text="Open", style="Compact.TButton",
                   command=self.open_selected).pack(side="left")
        ttk.Button(buttons, text="Save a copy…", style="Compact.TButton",
                   command=self.save_copy).pack(side="left", padx=4)
        ttk.Button(buttons, text="What it is…", style="Compact.TButton",
                   command=self.edit_note).pack(side="left")
        ttk.Button(buttons, text="Remove", style="Compact.TButton",
                   command=self.remove_selected).pack(side="left", padx=4)

        ttk.Checkbutton(box, text="Show the files from every run",
                        variable=self.every_run_var,
                        command=self.reload_attachments).grid(row=2, column=0, sticky="w",
                                                              pady=(6, 0))

    def _build_status(self) -> None:
        ttk.Label(self, textvariable=self.status_var,
                  style="Status.TLabel").pack(fill="x", pady=(8, 0))

    def _show_run_column(self, show: bool) -> None:
        """The Run column only earns its width when several runs are listed."""
        columns = tuple(ATTACHMENT_COLUMNS)
        self.tree.configure(
            displaycolumns=columns if show else tuple(c for c in columns if c != "run"))

    # ---------------------------------------------------------------- data

    def reload(self, *_args) -> None:
        if self.defer():
            return
        self.refresh_now()

    def refresh_now(self) -> None:
        self.runs = self.db.list_runs(limit=400)
        self.run_combo.configure(values=[run.display for run in self.runs])
        current = self.app.current_run_id
        if current is None or current not in {run.id for run in self.runs}:
            current = self.runs[0].id if self.runs else None
            self.app.current_run_id = current
        if current is not None:
            index = next((i for i, run in enumerate(self.runs) if run.id == current), 0)
            self.run_combo.current(index)
        else:
            self.run_var.set("")
        self.reload_attachments()

    def reload_attachments(self, *_args) -> None:
        every = self.every_run_var.get()
        run_id = self.app.current_run_id
        self.attachments = self.db.list_attachments(run_id=run_id, every_run=every)
        self._show_run_column(every)
        self._populate_attachments()
        self._refresh_counts()
        self._update_buttons()

    def _populate_attachments(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._rows: dict[str, object] = {}
        labels = {run.id: (run.label or run.run_date) for run in self.runs}
        for attachment in self.attachments:
            path = files.path_for(attachment.stored_name)
            missing = not path.exists()
            name = attachment.display + ("  (missing)" if missing else "")
            item = self.tree.insert(
                "", "end", tags=("missing",) if missing else (),
                values=(name, labels.get(attachment.run_id, ""),
                        files.describe_kind(attachment.filename),
                        files.human_size(attachment.size),
                        (attachment.added_at or "")[:10], attachment.note),
            )
            self._rows[item] = attachment

    def _refresh_counts(self) -> None:
        run_id = self.app.current_run_id
        count = self.db.count_attachments(run_id) if run_id is not None else 0
        self.attached_count_var.set(
            "no files yet" if not count else f"{count} file{'s' if count != 1 else ''}")

    def _update_buttons(self) -> None:
        has_run = self.app.current_run_id is not None
        picked = self.browser.selected_paths() if hasattr(self, "browser") else []
        readable = [path for path in picked if files.is_readable(path)]
        self.attach_button.configure(state="normal" if has_run and picked else "disabled")
        self.import_button.configure(
            state="normal" if has_run and len(readable) == 1 else "disabled")

    def _on_files_selected(self, paths) -> None:
        self._update_buttons()
        if not paths:
            self.status_var.set("")
        elif len(paths) == 1:
            entry = paths[0]
            self.status_var.set(f"{entry.name} — {files.describe_kind(entry)}")
        else:
            self.status_var.set(f"{len(paths)} files picked")

    def _on_run_picked(self, _event=None) -> None:
        index = self.run_combo.current()
        if 0 <= index < len(self.runs):
            self.app.current_run_id = self.runs[index].id
            self.app.notify("run_selected", source=self)
            self.reload_attachments()

    def _select_all(self) -> str:
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def selected_attachments(self) -> list:
        return [self._rows[item] for item in self.tree.selection() if item in self._rows]

    # ------------------------------------------------------------ attaching

    def attach(self, paths=None) -> None:
        """Copy files into the data folder and list them against this run."""
        run_id = self.app.current_run_id
        if run_id is None:
            messagebox.showinfo(
                "No run yet",
                "Start a run on the Entry tab first - files are kept against a run.",
                parent=self)
            return

        chosen = [Path(path) for path in (paths or self.browser.selected_paths())]
        if not chosen:
            messagebox.showinfo("Nothing picked",
                                "Pick one or more files in the list on the left first.",
                                parent=self)
            return
        if not self._confirm_size(chosen):
            return

        added, failed = 0, []
        for path in chosen:
            try:
                stored = files.store(path)
            except OSError as error:
                failed.append(f"{path.name}: {error.strerror or error}")
                continue
            self.db.add_attachment(Attachment(
                run_id=run_id, filename=path.name, stored_name=stored.stored_name,
                size=stored.size, source_path=str(path),
            ))
            added += 1

        if failed:
            messagebox.showerror(
                "Some files could not be added", "\n".join(failed), parent=self)
        if added:
            self.status_var.set(
                f"{added} file{'s' if added != 1 else ''} added to this run.")
            self.app.notify("files_changed", source=self)
        self.reload_attachments()

    def _confirm_size(self, chosen: list[Path]) -> bool:
        """A big file is copied, not linked, so it is worth a word first."""
        total = 0
        for path in chosen:
            try:
                total += path.stat().st_size
            except OSError:
                continue
        if total <= files.LARGE_FILE_BYTES:
            return True
        return messagebox.askyesno(
            "That is a lot to copy",
            f"These files come to {files.human_size(total)}, and MeasureLog keeps its own "
            "copy of everything you add.\n\nYour data folder will grow by about that much. "
            "Add them anyway?",
            parent=self)

    # ------------------------------------------------------------ importing

    def import_readings(self) -> None:
        """Read a spreadsheet of measurements into the current run."""
        run_id = self.app.current_run_id
        if run_id is None:
            messagebox.showinfo(
                "No run yet",
                "Start a run on the Entry tab first - readings are imported into a run.",
                parent=self)
            return

        readable = [path for path in self.browser.selected_paths() if files.is_readable(path)]
        if len(readable) != 1:
            messagebox.showinfo(
                "Pick one file to import",
                "Choose a single CSV or Excel file on the left - they are the ones shown "
                "in green - and then click Import readings.",
                parent=self)
            return

        tests = self.db.list_tests(active_only=True)
        locations = self.db.list_locations(active_only=True)
        if not tests or not locations:
            messagebox.showinfo(
                "Nothing to import into",
                "Add your tests and locations on the Setup tab first - an import has to "
                "match what the file says against the tests you actually run.",
                parent=self)
            return

        run = self.db.get_run(run_id)
        choice = ImportDialog(self, readable[0], tests, locations,
                              run_label=run.display if run else "").show()
        if choice is None:
            return

        result = importers.apply(self.db, run_id, choice.plan, overwrite=choice.overwrite)
        if choice.keep_copy:
            self.attach([choice.path])
        self.app.notify("values_changed", source=self)
        self.app.notify("runs_changed", source=self)
        self.status_var.set(result.summary())
        messagebox.showinfo(
            "Import finished",
            f"{result.summary()}\n\nThe readings are on the Entry tab now.",
            parent=self)
        self.reload_attachments()

    # -------------------------------------------------------- attached files

    def open_selected(self) -> None:
        chosen = self.selected_attachments()
        if not chosen:
            return
        for attachment in chosen[:5]:  # opening twenty windows at once helps nobody
            path = files.path_for(attachment.stored_name)
            if not path.exists():
                messagebox.showwarning(
                    "That file is gone",
                    f"{attachment.display} is no longer in the MeasureLog files folder. "
                    "Remove it from the list, or restore it from a backup.",
                    parent=self)
                continue
            if not files.open_in_system(path):
                messagebox.showinfo("Cannot open this one",
                                    f"Windows had nothing to open {attachment.display} with.\n\n"
                                    f"It is here:\n{path}", parent=self)

    def save_copy(self) -> None:
        chosen = self.selected_attachments()
        if len(chosen) != 1:
            messagebox.showinfo("Pick one file",
                                "Choose a single file in the list to save a copy of.",
                                parent=self)
            return
        attachment = chosen[0]
        source = files.path_for(attachment.stored_name)
        if not source.exists():
            messagebox.showwarning("That file is gone",
                                   f"{attachment.display} is no longer in the files folder.",
                                   parent=self)
            return
        target = filedialog.asksaveasfilename(
            parent=self, title="Save a copy", initialfile=attachment.display,
            initialdir=str(Path.home()),
            defaultextension=Path(attachment.filename).suffix or "",
        )
        if not target:
            return
        try:
            shutil.copy2(source, target)
        except OSError as error:
            messagebox.showerror("Could not save the copy", str(error), parent=self)
            return
        self.status_var.set(f"Copy saved: {target}")

    def edit_note(self) -> None:
        chosen = self.selected_attachments()
        if len(chosen) != 1:
            messagebox.showinfo("Pick one file",
                                "Choose a single file in the list to describe.", parent=self)
            return
        attachment = chosen[0]
        note = NoteDialog(
            self, caption=attachment.display, note=attachment.note,
            title="What this file is",
            hint="A few words so the next person knows why it is here - "
                 "\"calibration certificate\", \"meter printout\".",
        ).show()
        if note is None:
            return
        attachment.note = note
        self.db.update_attachment(attachment)
        self.reload_attachments()

    def remove_selected(self) -> None:
        chosen = self.selected_attachments()
        if not chosen:
            return
        names = "\n".join(f"  • {attachment.display}" for attachment in chosen[:10])
        if len(chosen) > 10:
            names += f"\n  … and {len(chosen) - 10} more"
        if not messagebox.askyesno(
            "Remove these files?",
            f"MeasureLog's copy of {'these files' if len(chosen) > 1 else 'this file'} "
            f"will be deleted:\n\n{names}\n\nThe original on your computer is untouched. "
            "Your readings are not affected.",
            parent=self,
        ):
            return
        for attachment in chosen:
            stored = self.db.delete_attachment(attachment.id)
            if stored:
                files.discard(stored)
        self.status_var.set(f"{len(chosen)} file{'s' if len(chosen) != 1 else ''} removed.")
        self.app.notify("files_changed", source=self)
        self.reload_attachments()

    def open_files_folder(self) -> None:
        files.open_in_system(config.files_dir())
