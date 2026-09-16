"""Files attached to runs: where they are kept, and what they are.

An attachment is a copy, not a link. The moment a file is added it is copied
into ``<data folder>/files``, so the record survives the original being moved,
renamed, or deleted off somebody's desktop - and a copied data folder brings
every document with it. The database stores the paperwork; this module stores
the bytes.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import config

# Anything larger is unusual for lab paperwork, and copying it would bloat the
# data folder a shared drive has to carry. The UI asks before going ahead.
LARGE_FILE_BYTES = 25 * 1024 * 1024

# Extension -> what to call it in the Type column. A name in words beats an
# extension for anyone who has never had to think about what ".xlsm" is.
KINDS: dict[str, str] = {
    ".csv": "CSV file",
    ".tsv": "Tab-separated file",
    ".txt": "Text file",
    ".xlsx": "Excel workbook",
    ".xlsm": "Excel workbook",
    ".xls": "Excel 97-2003 workbook",
    ".pdf": "PDF document",
    ".doc": "Word document",
    ".docx": "Word document",
    ".rtf": "Rich text document",
    ".odt": "OpenDocument text",
    ".ods": "OpenDocument spreadsheet",
    ".jpg": "JPEG image",
    ".jpeg": "JPEG image",
    ".png": "PNG image",
    ".gif": "GIF image",
    ".bmp": "Bitmap image",
    ".tif": "TIFF image",
    ".tiff": "TIFF image",
    ".heic": "HEIC photo",
    ".db": "MeasureLog data file",
    ".zip": "Zip archive",
}

# Formats the importer can actually read readings out of.
READABLE_SUFFIXES = (".csv", ".tsv", ".txt", ".xlsx", ".xlsm")

# The named choices in the browser's "Show" box, in the order they appear.
FILTERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Files MeasureLog can read", READABLE_SUFFIXES),
    ("Spreadsheets and CSV", (".csv", ".tsv", ".xlsx", ".xlsm", ".xls", ".ods")),
    ("Photos and images", (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".heic")),
    ("Documents and PDFs", (".pdf", ".doc", ".docx", ".rtf", ".odt", ".txt")),
    ("All files", ()),
)

_UNSAFE = re.compile(r"[^A-Za-z0-9._ +()\[\]-]")


@dataclass
class StoredFile:
    """The result of copying a file into the data folder."""

    stored_name: str
    filename: str
    size: int
    folder: Path | None = None   # None means the app's own files folder

    @property
    def path(self) -> Path:
        return path_for(self.stored_name, self.folder)


# ------------------------------------------------------------------ describing

def describe_kind(name: str | Path) -> str:
    """A plain-English name for a file type, for the Type column."""
    suffix = Path(name).suffix.lower()
    if suffix in KINDS:
        return KINDS[suffix]
    if suffix:
        return f"{suffix.lstrip('.').upper()} file"
    return "File"


def is_readable(name: str | Path) -> bool:
    """True when the importer could try to read readings out of this file."""
    return Path(name).suffix.lower() in READABLE_SUFFIXES


def human_size(size: int | float | None) -> str:
    """Render a byte count the way a file manager does."""
    if size is None:
        return ""
    size = float(size)
    if size < 1024:
        return f"{int(size)} B"
    for unit in ("KB", "MB", "GB"):
        size /= 1024.0
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}".replace(".0 ", " ")
    return f"{size:.1f} GB"  # pragma: no cover - unreachable, kept for clarity


def human_time(stamp: float | None) -> str:
    if not stamp:
        return ""
    try:
        return datetime.fromtimestamp(stamp).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):  # pragma: no cover - odd clocks
        return ""


# -------------------------------------------------------------------- storing

def safe_name(name: str) -> str:
    """Strip a filename down to characters every filesystem accepts."""
    cleaned = _UNSAFE.sub("_", Path(name).name).strip(" .")
    return cleaned or "file"


def unique_name(folder: Path, name: str) -> str:
    """A filename not already taken in ``folder``: adds ' (2)', ' (3)', ..."""
    stem, suffix = Path(name).stem, Path(name).suffix
    candidate = f"{stem}{suffix}"
    counter = 2
    while (folder / candidate).exists():
        candidate = f"{stem} ({counter}){suffix}"
        counter += 1
    return candidate


def store(source: str | Path, folder: Path | None = None) -> StoredFile:
    """Copy a file into the data folder, keeping its name readable.

    Raises OSError if the source cannot be read or the copy cannot be written.
    """
    source = Path(source)
    if not source.is_file():
        raise OSError(f"{source} is not a file")

    folder = Path(folder) if folder else config.files_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stored_name = unique_name(folder, safe_name(source.name))
    shutil.copy2(source, folder / stored_name)
    return StoredFile(stored_name=stored_name, filename=source.name,
                      size=(folder / stored_name).stat().st_size, folder=folder)


def path_for(stored_name: str, folder: Path | None = None) -> Path:
    folder = Path(folder) if folder else config.files_dir()
    # Never let a stored name climb out of the files folder.
    return folder / Path(stored_name).name


def discard(stored_name: str, folder: Path | None = None) -> bool:
    """Delete one stored file. Returns True if something was removed."""
    target = path_for(stored_name, folder)
    try:
        target.unlink()
        return True
    except OSError:
        return False


# -------------------------------------------------------------------- opening

def open_in_system(path: str | Path) -> bool:
    """Hand a file or folder to whatever the computer opens it with."""
    path = Path(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True
    except Exception:  # pragma: no cover - platform dependent
        return False


# ------------------------------------------------------------------- browsing

def places() -> list[tuple[str, Path]]:
    """The shortcuts down the side of the file browser.

    Only folders that exist are offered, so the list stays honest on a machine
    with no Downloads folder or no USB stick plugged in.
    """
    home = Path.home()
    candidates: list[tuple[str, Path]] = [
        ("Desktop", home / "Desktop"),
        ("Documents", home / "Documents"),
        ("Downloads", home / "Downloads"),
        ("Pictures", home / "Pictures"),
        ("Home folder", home),
    ]
    found = [(label, path) for label, path in candidates if _is_dir(path)]
    found.extend(_removable_drives())

    data = config.data_dir()
    if _is_dir(data):
        found.append(("MeasureLog data", data))

    seen: set[str] = set()
    unique: list[tuple[str, Path]] = []
    for label, path in found:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append((label, path))
    return unique


def _removable_drives() -> list[tuple[str, Path]]:
    """Drive letters on Windows; mounted media elsewhere."""
    drives: list[tuple[str, Path]] = []
    if sys.platform.startswith("win"):
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:\\")
            if _is_dir(drive):
                drives.append((f"{letter}: drive", drive))
        return drives

    for root in (Path("/media"), Path("/Volumes"), Path("/mnt")):
        if not _is_dir(root):
            continue
        try:
            for child in sorted(root.iterdir()):
                if _is_dir(child):
                    drives.append((child.name, child))
        except OSError:  # pragma: no cover - unreadable mount point
            continue
    return drives


def _is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:  # pragma: no cover - a disconnected network drive
        return False


def is_hidden(path: Path) -> bool:
    """Hide dot-files everywhere, and hidden-flagged files on Windows."""
    if path.name.startswith("."):
        return True
    if sys.platform.startswith("win"):
        try:
            # 0x2 FILE_ATTRIBUTE_HIDDEN, 0x4 FILE_ATTRIBUTE_SYSTEM
            return bool(path.stat().st_file_attributes & 0x6)  # type: ignore[attr-defined]
        except (OSError, AttributeError):  # pragma: no cover - platform dependent
            return False
    return False


@dataclass
class Entry:
    """One row in the file browser."""

    path: Path
    is_dir: bool
    size: int
    modified: float

    @property
    def name(self) -> str:
        return self.path.name or str(self.path)

    @property
    def kind(self) -> str:
        return "Folder" if self.is_dir else describe_kind(self.path)

    @property
    def size_text(self) -> str:
        return "" if self.is_dir else human_size(self.size)

    @property
    def modified_text(self) -> str:
        return human_time(self.modified)


def listing(folder: str | Path, suffixes: tuple[str, ...] = (),
            name_filter: str = "", show_hidden: bool = False) -> list[Entry]:
    """Folders then files, each alphabetically, filtered as asked.

    Neither filter ever hides a folder: you have to be able to walk through a
    folder to reach the file inside it, and a list you cannot navigate out of
    is worse than one showing too much.
    """
    folder = Path(folder)
    wanted = tuple(suffix.lower() for suffix in suffixes)
    needle = name_filter.strip().lower()
    entries: list[Entry] = []

    for child in folder.iterdir():  # OSError is the caller's to report
        try:
            is_dir = child.is_dir()
            if not show_hidden and is_hidden(child):
                continue
            if not is_dir:
                if needle and needle not in child.name.lower():
                    continue
                if wanted and child.suffix.lower() not in wanted:
                    continue
            info = child.stat()
            entries.append(Entry(path=child, is_dir=is_dir,
                                 size=0 if is_dir else info.st_size,
                                 modified=info.st_mtime))
        except OSError:
            # A broken symlink or a file we may not stat: leave it out rather
            # than failing the whole folder.
            continue

    entries.sort(key=lambda entry: (not entry.is_dir, entry.name.lower()))
    return entries
