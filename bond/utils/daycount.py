"""Day count conventions for KTB analytics."""

from __future__ import annotations

from datetime import date
from typing import Callable, Dict

import logging

logger = logging.getLogger(__name__)

DayCountFunc = Callable[[date, date], float]


def _act_365f(start: date, end: date) -> float:
    """Return the ACT/365F year fraction between two dates.

    Follows the convention:
        yearfrac(d1, d2) = ActualDays(d1, d2) / 365
    """
    if end < start:
        logger.debug("Swapping start/end for ACT/365F: %s, %s", start, end)
        start, end = end, start
    days = (end - start).days
    return float(days) / 365.0


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _act_act(start: date, end: date) -> float:
    """Return the ACT/ACT (ISDA-style) year fraction."""
    if end < start:
        logger.debug("Swapping start/end for ACT/ACT: %s, %s", start, end)
        start, end = end, start
    current = start
    frac = 0.0
    while current < end:
        year = current.year
        year_end = date(year + 1, 1, 1)
        period_end = min(year_end, end)
        days = (period_end - current).days
        year_length = 366 if _is_leap(year) else 365
        frac += float(days) / year_length
        current = period_end
    return frac


_REGISTRY: Dict[str, DayCountFunc] = {
    "ACT/365F": _act_365f,
    "ACT/ACT": _act_act,
}


def get_day_count(name: str) -> DayCountFunc:
    """Return a callable implementing the requested day-count convention."""
    key = name.upper()
    try:
        return _REGISTRY[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported day count convention: {name}") from exc


def register_day_count(name: str, func: DayCountFunc) -> None:
    """Register a custom day-count convention."""
    key = name.upper()
    if key in _REGISTRY:
        raise ValueError(f"Day count '{name}' already registered")
    _REGISTRY[key] = func
