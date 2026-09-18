"""Where the app keeps its data, and how it finds it on any computer.

Resolution order for the data folder:

1. ``MEASURELOG_DATA_DIR`` environment variable, if set.
2. A ``datadir.txt`` file next to the executable containing a folder path.
3. Portable mode: a ``portable.flag`` file next to the executable, in which
   case data lives in ``MeasureLog-Data`` beside the .exe (USB-stick friendly).
4. Default: ``<home>/Documents/MeasureLog`` (``<home>/MeasureLog`` if there is
   no Documents folder).
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from . import APP_NAME

DB_FILENAME = "measurelog.db"
BACKUP_KEEP = 15

# Folder names that mean a sync client owns everything underneath. The database
# must not live in one: sync tools copy the whole file and know nothing about
# the locks SQLite relies on, so a folder synced between two machines can be
# left corrupt. This is not a hypothetical - Windows often redirects Documents
# into OneDrive, which silently puts the default data folder inside a sync
# folder without anyone choosing it.
#
# Matched against each part of the path, case-insensitively. Entries ending in
# a space match by prefix, so "OneDrive - Green Era Campus" is caught too.
SYNC_FOLDERS: tuple[tuple[str, str], ...] = (
    ("onedrive", "OneDrive"),
    ("google drive", "Google Drive"),
    ("googledrive", "Google Drive"),
    ("my drive", "Google Drive"),
    ("shared drives", "Google Drive"),
    ("dropbox", "Dropbox"),
    ("box sync", "Box"),
    ("icloud drive", "iCloud Drive"),
    ("icloud~", "iCloud Drive"),
    ("creative cloud files", "Creative Cloud"),
    ("nextcloud", "Nextcloud"),
    ("pclouddrive", "pCloud"),
)


def is_frozen() -> bool:
    """True when running from a PyInstaller-built .exe."""
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Folder holding the .exe (or the project root when run from source)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(name: str) -> Path | None:
    """Locate a bundled read-only resource (icon, docs) in source or .exe form."""
    roots = []
    bundled = getattr(sys, "_MEIPASS", None)  # PyInstaller unpacks here at runtime
    if bundled:
        roots.append(Path(bundled))
    roots.append(Path(__file__).resolve().parent.parent / "packaging")
    roots.append(app_dir())
    for root in roots:
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def data_dir() -> Path:
    """Folder holding the database, backups and exports."""
    env = os.environ.get("MEASURELOG_DATA_DIR", "").strip()
    if env:
        return Path(env).expanduser()

    pointer = app_dir() / "datadir.txt"
    try:
        if pointer.is_file():
            target = pointer.read_text(encoding="utf-8").strip()
            if target:
                return Path(target).expanduser()
    except OSError:
        pass

    if (app_dir() / "portable.flag").is_file():
        return app_dir() / "MeasureLog-Data"

    home = Path.home()
    documents = home / "Documents"
    base = documents if documents.is_dir() else home
    return base / APP_NAME


def sync_service_for(path: Path | str | None = None) -> str | None:
    """Name the sync service holding ``path``, or None if nothing owns it.

    Used to warn before the database ends up somewhere a sync client will
    overwrite it behind the app's back. Exports are fine in a synced folder -
    they are written once and never held open - so this is only ever applied
    to the data folder.
    """
    target = Path(path) if path is not None else data_dir()
    # Split on both separators rather than trusting Path.parts: a Windows path
    # examined on any other platform comes back as a single component, which
    # would quietly match nothing.
    for part in re.split(r"[\\/]+", str(target)):
        cleaned = part.strip().lower()
        for marker, service in SYNC_FOLDERS:
            if cleaned == marker or cleaned.startswith(f"{marker} ") or \
                    cleaned.startswith(f"{marker}-") or cleaned.startswith(marker + "_"):
                return service
    return None


def ensure_data_dir() -> Path:
    target = data_dir()
    target.mkdir(parents=True, exist_ok=True)
    (target / "backups").mkdir(exist_ok=True)
    (target / "exports").mkdir(exist_ok=True)
    (target / "files").mkdir(exist_ok=True)
    return target


def db_path() -> Path:
    return ensure_data_dir() / DB_FILENAME


def exports_dir() -> Path:
    return ensure_data_dir() / "exports"


def backups_dir() -> Path:
    return ensure_data_dir() / "backups"


def make_backup(source: Path | None = None, keep: int = BACKUP_KEEP) -> Path | None:
    """Copy the database into the backups folder, at most once per day.

    Returns the backup path, or None when there is nothing to back up or a
    backup for today already exists.
    """
    source = Path(source) if source else db_path()
    if not source.is_file() or source.stat().st_size == 0:
        return None

    folder = backups_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    if any(folder.glob(f"measurelog-{stamp}-*.db")):
        return None

    target = folder / f"measurelog-{datetime.now():%Y%m%d-%H%M%S}.db"
    shutil.copy2(source, target)

    backups = sorted(folder.glob("measurelog-*.db"))
    for stale in backups[:-keep] if len(backups) > keep else []:
        try:
            stale.unlink()
        except OSError:
            pass
    return target


def files_dir() -> Path:
    """Folder holding the files attached to runs.

    They live beside the database rather than inside it, so a copied data
    folder brings the documents along and any file manager can still read them.
    """
    return ensure_data_dir() / "files"
