"""Tolerant readers for stored run records.

Runs come from a database and from older app versions, so any field may be
missing, ``None`` or oddly typed. These helpers turn such values into safe
defaults so one malformed record can never crash a dashboard or a report.
"""

import math
from typing import Any


def as_float(value: Any, default: float | None = None) -> float | None:
    """``value`` as a finite float, or ``default`` if it is not one."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def as_int(value: Any, default: int = 0) -> int:
    """``value`` as an int ("3", "3.0" and 3.0 all work), or ``default``."""
    result = as_float(value)
    return int(result) if result is not None else default


def as_list(value: Any) -> list:
    """``value`` if it is a list, otherwise an empty list."""
    return value if isinstance(value, list) else []


def as_records(value: Any) -> list[dict[str, Any]]:
    """The dictionaries inside ``value``; anything else is dropped."""
    return [item for item in as_list(value) if isinstance(item, dict)]
