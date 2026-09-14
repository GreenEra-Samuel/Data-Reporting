"""Replicate statistics: mean, standard deviation, %RSD and spec checks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

OK = "ok"
LOW = "low"
HIGH = "high"
NO_LIMIT = "none"


@dataclass
class Summary:
    """Descriptive statistics for one set of replicates."""

    n: int = 0
    mean: float | None = None
    sd: float | None = None
    rsd: float | None = None
    minimum: float | None = None
    maximum: float | None = None

    @property
    def span(self) -> float | None:
        """Range (max - min) across the replicates."""
        if self.minimum is None or self.maximum is None:
            return None
        return self.maximum - self.minimum

    @property
    def has_data(self) -> bool:
        return self.n > 0


def clean_values(values: Iterable[float | None]) -> list[float]:
    """Drop blanks and anything that is not a finite number."""
    result: list[float] = []
    for value in values:
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            result.append(number)
    return result


def summarize(values: Iterable[float | None]) -> Summary:
    """Mean, sample SD (n-1) and %RSD for a set of replicates.

    SD and %RSD need at least two values; %RSD additionally needs a non-zero
    mean, and is left as None otherwise rather than raising.
    """
    numbers = clean_values(values)
    if not numbers:
        return Summary()

    count = len(numbers)
    mean = sum(numbers) / count
    summary = Summary(
        n=count, mean=mean, minimum=min(numbers), maximum=max(numbers)
    )
    if count >= 2:
        variance = sum((number - mean) ** 2 for number in numbers) / (count - 1)
        summary.sd = math.sqrt(variance)
        if mean != 0:
            summary.rsd = abs(summary.sd / mean) * 100.0
    return summary


def spec_status(
    value: float | None,
    lower: float | None = None,
    upper: float | None = None,
) -> str:
    """Compare a value against its limits: ok / low / high / none."""
    if value is None or (lower is None and upper is None):
        return NO_LIMIT
    try:
        number = float(value)
    except (TypeError, ValueError):
        return NO_LIMIT
    if lower is not None and number < float(lower):
        return LOW
    if upper is not None and number > float(upper):
        return HIGH
    return OK


def out_of_spec(value: float | None, lower: float | None = None,
                upper: float | None = None) -> bool:
    return spec_status(value, lower, upper) in (LOW, HIGH)


def flag_outliers(values: Sequence[float | None], rsd_limit: float | None = None) -> list[int]:
    """Indices of replicates that look like the odd one out in their group.

    A z-score test is useless here: with three replicates the largest possible
    z-score is (n-1)/sqrt(n) = 1.155, so any threshold near 2 never fires. This
    uses the rule a bench analyst would apply instead - if the group's spread is
    worse than ``rsd_limit`` percent, the replicate furthest from the group
    median is the one to look at again.

    Returns an empty list when ``rsd_limit`` is None (the check is off), when
    there are fewer than three replicates, or when the spread is acceptable.
    """
    if rsd_limit is None:
        return []
    numbers = clean_values(values)
    if len(numbers) < 3:
        return []

    summary = summarize(numbers)
    spread = summary.rsd
    if spread is None:
        # Mean of zero: fall back to absolute spread so the group is still checked.
        spread = None if summary.span in (None, 0) else float("inf")
    if spread is None or spread <= float(rsd_limit):
        return []

    middle = median(numbers)
    deviations = {
        index: abs(float(value) - middle)
        for index, value in enumerate(values)
        if value is not None and _is_number(value)
    }
    if not deviations:
        return []
    worst = max(deviations.values())
    if worst == 0:
        return []
    return [index for index, deviation in deviations.items() if deviation == worst]


def median(numbers: Sequence[float]) -> float:
    ordered = sorted(numbers)
    count = len(ordered)
    middle = count // 2
    if count % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _is_number(value: object) -> bool:
    try:
        return math.isfinite(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
