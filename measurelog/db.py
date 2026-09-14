"""SQLite storage for locations, tests, runs and replicate measurements."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from . import catalog
from .models import Cell, Location, LongRow, Run, Test

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS location (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    code        TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    sort_order  INTEGER NOT NULL DEFAULT 0,
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS test (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    code        TEXT NOT NULL DEFAULT '',
    unit        TEXT NOT NULL DEFAULT '',
    decimals    INTEGER NOT NULL DEFAULT 2,
    lower_limit REAL,
    upper_limit REAL,
    replicates  INTEGER NOT NULL DEFAULT 3,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    active      INTEGER NOT NULL DEFAULT 1,
    rsd_limit   REAL,
    notes       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS run (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date   TEXT NOT NULL,
    run_time   TEXT NOT NULL DEFAULT '',
    label      TEXT NOT NULL DEFAULT '',
    operator   TEXT NOT NULL DEFAULT '',
    notes      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS measurement (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    location_id INTEGER NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    test_id     INTEGER NOT NULL REFERENCES test(id) ON DELETE CASCADE,
    replicate   INTEGER NOT NULL,
    value       REAL,
    note        TEXT NOT NULL DEFAULT '',
    updated_at  TEXT NOT NULL,
    UNIQUE (run_id, location_id, test_id, replicate)
);

CREATE INDEX IF NOT EXISTS idx_run_when ON run (run_date, run_time);
CREATE INDEX IF NOT EXISTS idx_meas_run ON measurement (run_id);
CREATE INDEX IF NOT EXISTS idx_meas_lookup ON measurement (test_id, location_id);
"""



def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Database:
    """Every read and write the app performs goes through this class."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._create_schema()

    # ---------------------------------------------------------------- setup

    def _create_schema(self) -> None:
        with self.conn:
            self.conn.executescript(SCHEMA)
        self._migrate()
        self.set_setting("schema_version", str(SCHEMA_VERSION))

    def _migrate(self) -> None:
        """Bring an older database up to the current schema.

        Columns are added in place so that a file written by an earlier version
        keeps every measurement already recorded in it.
        """
        added = [
            ("test", "rsd_limit", "REAL"),
            ("test", "notes", "TEXT NOT NULL DEFAULT ''"),
        ]
        for table, column, definition in added:
            if not self._has_column(table, column):
                with self.conn:
                    self.conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                    )

    def _has_column(self, table: str, column: str) -> bool:
        rows = self.conn.execute(f"PRAGMA table_info({table})")
        return any(row["name"] == column for row in rows)

    def seed_defaults(self) -> bool:
        """Populate the sampling points from the SOPs on a brand new database.

        No tests are created: the Setup tab offers the SOP test library, so
        picking the real tests is a better first step than deleting placeholders.
        """
        if self.list_locations() or self.list_tests():
            return False
        for location in catalog.default_locations():
            self.save_location(location)
        return True

    def close(self) -> None:
        try:
            self.conn.close()
        except sqlite3.Error:
            pass

    # ------------------------------------------------------------- settings

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )

    def get_int_setting(self, key: str, default: int) -> int:
        try:
            return int(self.get_setting(key, str(default)) or default)
        except (TypeError, ValueError):
            return default

    # ------------------------------------------------------------ locations

    def list_locations(self, active_only: bool = False) -> list[Location]:
        sql = "SELECT * FROM location"
        if active_only:
            sql += " WHERE active = 1"
        sql += " ORDER BY sort_order, id"
        return [self._as_location(row) for row in self.conn.execute(sql)]

    def get_location(self, location_id: int) -> Location | None:
        row = self.conn.execute("SELECT * FROM location WHERE id = ?", (location_id,)).fetchone()
        return self._as_location(row) if row else None

    def save_location(self, location: Location) -> Location:
        if location.sort_order == 0 and location.id is None:
            location.sort_order = self._next_sort_order("location")
        with self.conn:
            if location.id is None:
                cursor = self.conn.execute(
                    "INSERT INTO location (name, code, description, sort_order, active) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (location.name.strip(), location.code.strip(), location.description.strip(),
                     location.sort_order, int(location.active)),
                )
                location.id = int(cursor.lastrowid)
            else:
                self.conn.execute(
                    "UPDATE location SET name = ?, code = ?, description = ?, "
                    "sort_order = ?, active = ? WHERE id = ?",
                    (location.name.strip(), location.code.strip(), location.description.strip(),
                     location.sort_order, int(location.active), location.id),
                )
        return location

    def delete_location(self, location_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM location WHERE id = ?", (location_id,))

    def move_location(self, location_id: int, delta: int) -> None:
        self._move_row("location", location_id, delta)

    # ---------------------------------------------------------------- tests

    def list_tests(self, active_only: bool = False) -> list[Test]:
        sql = "SELECT * FROM test"
        if active_only:
            sql += " WHERE active = 1"
        sql += " ORDER BY sort_order, id"
        return [self._as_test(row) for row in self.conn.execute(sql)]

    def get_test(self, test_id: int) -> Test | None:
        row = self.conn.execute("SELECT * FROM test WHERE id = ?", (test_id,)).fetchone()
        return self._as_test(row) if row else None

    def save_test(self, test: Test) -> Test:
        if test.sort_order == 0 and test.id is None:
            test.sort_order = self._next_sort_order("test")
        values = (
            test.name.strip(), test.code.strip(), test.unit.strip(), int(test.decimals),
            test.lower_limit, test.upper_limit, max(1, int(test.replicates)),
            test.sort_order, int(test.active), test.rsd_limit, test.notes.strip(),
        )
        with self.conn:
            if test.id is None:
                cursor = self.conn.execute(
                    "INSERT INTO test (name, code, unit, decimals, lower_limit, upper_limit, "
                    "replicates, sort_order, active, rsd_limit, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    values,
                )
                test.id = int(cursor.lastrowid)
            else:
                self.conn.execute(
                    "UPDATE test SET name = ?, code = ?, unit = ?, decimals = ?, lower_limit = ?, "
                    "upper_limit = ?, replicates = ?, sort_order = ?, active = ?, rsd_limit = ?, "
                    "notes = ? WHERE id = ?",
                    values + (test.id,),
                )
        return test

    def delete_test(self, test_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM test WHERE id = ?", (test_id,))

    def move_test(self, test_id: int, delta: int) -> None:
        self._move_row("test", test_id, delta)

    # ----------------------------------------------------------------- runs

    def list_runs(
        self,
        limit: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[Run]:
        sql = [
            "SELECT r.*, (SELECT COUNT(*) FROM measurement m "
            "WHERE m.run_id = r.id AND m.value IS NOT NULL) AS value_count FROM run r",
        ]
        where, params = [], []
        if date_from:
            where.append("r.run_date >= ?")
            params.append(date_from)
        if date_to:
            where.append("r.run_date <= ?")
            params.append(date_to)
        if where:
            sql.append("WHERE " + " AND ".join(where))
        sql.append("ORDER BY r.run_date DESC, r.run_time DESC, r.id DESC")
        if limit:
            sql.append("LIMIT ?")
            params.append(limit)
        rows = self.conn.execute(" ".join(sql), params)
        return [self._as_run(row) for row in rows]

    def get_run(self, run_id: int) -> Run | None:
        row = self.conn.execute("SELECT * FROM run WHERE id = ?", (run_id,)).fetchone()
        return self._as_run(row) if row else None

    def create_run(
        self,
        run_date: str,
        run_time: str = "",
        label: str = "",
        operator: str = "",
        notes: str = "",
    ) -> Run:
        stamp = _now()
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO run (run_date, run_time, label, operator, notes, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_date, run_time, label, operator, notes, stamp, stamp),
            )
        return Run(
            id=int(cursor.lastrowid), run_date=run_date, run_time=run_time, label=label,
            operator=operator, notes=notes, created_at=stamp, updated_at=stamp,
        )

    def update_run(self, run: Run) -> Run:
        run.updated_at = _now()
        with self.conn:
            self.conn.execute(
                "UPDATE run SET run_date = ?, run_time = ?, label = ?, operator = ?, "
                "notes = ?, updated_at = ? WHERE id = ?",
                (run.run_date, run.run_time, run.label, run.operator, run.notes,
                 run.updated_at, run.id),
            )
        return run

    def delete_run(self, run_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM run WHERE id = ?", (run_id,))

    def duplicate_run(self, run_id: int, run_date: str, run_time: str = "",
                      label: str = "", copy_values: bool = False) -> Run | None:
        source = self.get_run(run_id)
        if source is None:
            return None
        new_run = self.create_run(
            run_date=run_date,
            run_time=run_time or source.run_time,
            label=label or source.label,
            operator=source.operator,
            notes=source.notes,
        )
        if copy_values:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO measurement (run_id, location_id, test_id, replicate, value, "
                    "note, updated_at) SELECT ?, location_id, test_id, replicate, value, note, ? "
                    "FROM measurement WHERE run_id = ?",
                    (new_run.id, _now(), run_id),
                )
        return new_run

    # --------------------------------------------------------- measurements

    def get_run_values(self, run_id: int) -> dict[tuple[int, int, int], Cell]:
        """All measurements for a run, keyed by (location_id, test_id, replicate)."""
        rows = self.conn.execute(
            "SELECT location_id, test_id, replicate, value, note FROM measurement WHERE run_id = ?",
            (run_id,),
        )
        return {
            (row["location_id"], row["test_id"], row["replicate"]): Cell(row["value"], row["note"] or "")
            for row in rows
        }

    def set_value(
        self,
        run_id: int,
        location_id: int,
        test_id: int,
        replicate: int,
        value: float | None,
        note: str = "",
    ) -> None:
        """Store one replicate. Blank value with no note removes the row."""
        with self.conn:
            if value is None and not note:
                self.conn.execute(
                    "DELETE FROM measurement WHERE run_id = ? AND location_id = ? "
                    "AND test_id = ? AND replicate = ?",
                    (run_id, location_id, test_id, replicate),
                )
            else:
                self.conn.execute(
                    "INSERT INTO measurement (run_id, location_id, test_id, replicate, value, "
                    "note, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(run_id, location_id, test_id, replicate) DO UPDATE SET "
                    "value = excluded.value, note = excluded.note, updated_at = excluded.updated_at",
                    (run_id, location_id, test_id, replicate, value, note, _now()),
                )
            self.conn.execute("UPDATE run SET updated_at = ? WHERE id = ?", (_now(), run_id))

    def clear_location_values(self, run_id: int, location_id: int) -> int:
        with self.conn:
            cursor = self.conn.execute(
                "DELETE FROM measurement WHERE run_id = ? AND location_id = ?",
                (run_id, location_id),
            )
        return cursor.rowcount

    def previous_run_id(self, run_id: int) -> int | None:
        run = self.get_run(run_id)
        if run is None:
            return None
        row = self.conn.execute(
            "SELECT id FROM run WHERE (run_date, run_time, id) < (?, ?, ?) "
            "ORDER BY run_date DESC, run_time DESC, id DESC LIMIT 1",
            (run.run_date, run.run_time, run.id),
        ).fetchone()
        return int(row["id"]) if row else None

    def copy_values_from_run(self, source_run_id: int, target_run_id: int,
                             location_id: int | None = None) -> int:
        """Copy measurements between runs; used for 'repeat the previous round'."""
        params: list = [target_run_id, _now(), source_run_id]
        sql = (
            "INSERT INTO measurement (run_id, location_id, test_id, replicate, value, note, updated_at) "
            "SELECT ?, location_id, test_id, replicate, value, note, ? FROM measurement WHERE run_id = ?"
        )
        if location_id is not None:
            sql += " AND location_id = ?"
            params.append(location_id)
        sql += (
            " ON CONFLICT(run_id, location_id, test_id, replicate) DO UPDATE SET "
            "value = excluded.value, note = excluded.note, updated_at = excluded.updated_at"
        )
        with self.conn:
            cursor = self.conn.execute(sql, params)
        return cursor.rowcount

    def count_values(self, *, run_id: int | None = None, location_id: int | None = None,
                     test_id: int | None = None) -> int:
        where, params = ["value IS NOT NULL"], []
        for column, value in (("run_id", run_id), ("location_id", location_id), ("test_id", test_id)):
            if value is not None:
                where.append(f"{column} = ?")
                params.append(value)
        row = self.conn.execute(
            f"SELECT COUNT(*) AS n FROM measurement WHERE {' AND '.join(where)}", params
        ).fetchone()
        return int(row["n"])

    # -------------------------------------------------------------- reading

    def fetch_long_rows(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        run_ids: list[int] | None = None,
        include_blank: bool = False,
    ) -> list[LongRow]:
        """Flat replicate-level rows, ready for export or summarising."""
        sql = [
            "SELECT r.id AS run_id, r.run_date, r.run_time, r.label AS run_label, r.operator,",
            "       r.notes AS run_notes, l.name AS location, l.code AS location_code,",
            "       t.name AS test, t.code AS test_code, t.unit, t.lower_limit, t.upper_limit,",
            "       m.replicate, m.value, m.note",
            "FROM measurement m",
            "JOIN run r ON r.id = m.run_id",
            "JOIN location l ON l.id = m.location_id",
            "JOIN test t ON t.id = m.test_id",
        ]
        where, params = [], []
        if not include_blank:
            where.append("m.value IS NOT NULL")
        if date_from:
            where.append("r.run_date >= ?")
            params.append(date_from)
        if date_to:
            where.append("r.run_date <= ?")
            params.append(date_to)
        if run_ids:
            where.append(f"r.id IN ({','.join('?' * len(run_ids))})")
            params.extend(run_ids)
        if where:
            sql.append("WHERE " + " AND ".join(where))
        sql.append(
            "ORDER BY r.run_date, r.run_time, r.id, l.sort_order, l.id, t.sort_order, t.id, m.replicate"
        )
        rows = self.conn.execute(" ".join(sql), params)
        return [
            LongRow(
                run_id=row["run_id"], run_date=row["run_date"], run_time=row["run_time"],
                run_label=row["run_label"], operator=row["operator"], location=row["location"],
                location_code=row["location_code"], test=row["test"], test_code=row["test_code"],
                unit=row["unit"], replicate=row["replicate"], value=row["value"],
                note=row["note"] or "", lower_limit=row["lower_limit"],
                upper_limit=row["upper_limit"], run_notes=row["run_notes"] or "",
            )
            for row in rows
        ]

    def date_bounds(self) -> tuple[str | None, str | None]:
        row = self.conn.execute("SELECT MIN(run_date) AS lo, MAX(run_date) AS hi FROM run").fetchone()
        return (row["lo"], row["hi"]) if row else (None, None)

    # -------------------------------------------------------------- helpers

    def _next_sort_order(self, table: str) -> int:
        row = self.conn.execute(f"SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM {table}").fetchone()
        return int(row["n"])

    def _move_row(self, table: str, row_id: int, delta: int) -> None:
        """Swap a row with its neighbour to reorder the list."""
        rows = [dict(r) for r in self.conn.execute(
            f"SELECT id, sort_order FROM {table} ORDER BY sort_order, id")]
        index = next((i for i, r in enumerate(rows) if r["id"] == row_id), None)
        if index is None:
            return
        target = index + delta
        if not 0 <= target < len(rows):
            return
        rows[index], rows[target] = rows[target], rows[index]
        with self.conn:
            for position, row in enumerate(rows):
                self.conn.execute(
                    f"UPDATE {table} SET sort_order = ? WHERE id = ?", (position, row["id"])
                )

    @staticmethod
    def _as_location(row: sqlite3.Row) -> Location:
        return Location(
            id=row["id"], name=row["name"], code=row["code"], description=row["description"],
            sort_order=row["sort_order"], active=bool(row["active"]),
        )

    @staticmethod
    def _as_test(row: sqlite3.Row) -> Test:
        keys = row.keys()
        return Test(
            id=row["id"], name=row["name"], code=row["code"], unit=row["unit"],
            decimals=row["decimals"], lower_limit=row["lower_limit"], upper_limit=row["upper_limit"],
            replicates=row["replicates"], sort_order=row["sort_order"], active=bool(row["active"]),
            rsd_limit=row["rsd_limit"] if "rsd_limit" in keys else None,
            notes=(row["notes"] or "") if "notes" in keys else "",
        )

    @staticmethod
    def _as_run(row: sqlite3.Row) -> Run:
        keys = row.keys()
        return Run(
            id=row["id"], run_date=row["run_date"], run_time=row["run_time"], label=row["label"],
            operator=row["operator"], notes=row["notes"], created_at=row["created_at"],
            updated_at=row["updated_at"],
            value_count=row["value_count"] if "value_count" in keys else 0,
        )
