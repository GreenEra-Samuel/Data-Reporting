"""Plain data holders passed between the database layer and the UI."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Location:
    id: int | None = None
    name: str = ""
    code: str = ""
    description: str = ""
    sort_order: int = 0
    active: bool = True

    @property
    def label(self) -> str:
        return f"{self.name} ({self.code})" if self.code else self.name


@dataclass
class Test:
    id: int | None = None
    name: str = ""
    code: str = ""
    unit: str = ""
    decimals: int = 2
    lower_limit: float | None = None
    upper_limit: float | None = None
    replicates: int = 3
    sort_order: int = 0
    active: bool = True
    # None means "fall back to the app-wide %RSD warning".
    rsd_limit: float | None = None
    notes: str = ""

    @property
    def label(self) -> str:
        return f"{self.name} ({self.unit})" if self.unit else self.name

    @property
    def limit_text(self) -> str:
        lo, hi = self.lower_limit, self.upper_limit
        if lo is None and hi is None:
            return ""
        if lo is not None and hi is not None:
            return f"{format_number(lo, self.decimals)} - {format_number(hi, self.decimals)}"
        if lo is not None:
            return f"min {format_number(lo, self.decimals)}"
        return f"max {format_number(hi, self.decimals)}"

    def format(self, value: float | None) -> str:
        return format_number(value, self.decimals)


@dataclass
class Run:
    id: int | None = None
    run_date: str = ""
    run_time: str = ""
    label: str = ""
    operator: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
    value_count: int = 0

    @property
    def display(self) -> str:
        parts = [self.run_date]
        if self.run_time:
            parts.append(self.run_time)
        if self.label:
            parts.append(self.label)
        if self.operator:
            parts.append(f"- {self.operator}")
        return "  ".join(parts)


@dataclass
class Cell:
    """One replicate value for a run/location/test."""

    value: float | None = None
    note: str = ""


@dataclass
class Attachment:
    """A file kept alongside the data file and tied to a run."""

    id: int | None = None
    run_id: int | None = None
    filename: str = ""        # the name it had when it was added
    stored_name: str = ""     # the name it has inside the files folder
    size: int = 0
    source_path: str = ""     # where it came from, for the tooltip
    note: str = ""
    added_at: str = ""

    @property
    def display(self) -> str:
        return self.filename or self.stored_name


@dataclass
class LongRow:
    """One exported replicate row."""

    run_id: int
    run_date: str
    run_time: str
    run_label: str
    operator: str
    location: str
    location_code: str
    test: str
    test_code: str
    unit: str
    replicate: int
    value: float | None
    note: str
    lower_limit: float | None = None
    upper_limit: float | None = None
    run_notes: str = ""
    flags: list[str] = field(default_factory=list)


def format_number(value: float | None, decimals: int = 2) -> str:
    """Render a number for display, trimming float noise."""
    if value is None:
        return ""
    try:
        decimals = max(0, min(8, int(decimals)))
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)
