"""Coupon schedule helpers."""

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Iterable, List, Sequence, Tuple


def _to_date(value: date | datetime | str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Unsupported date-like value: {value!r}")


def _add_months(dt: date, months: int) -> date:
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def coupon_schedule(
    issue_date: date | datetime | str,
    maturity_date: date | datetime | str,
    payments_per_year: int,
) -> List[date]:
    """Generate coupon payment dates (strictly after issue, including maturity)."""
    start = _to_date(issue_date)
    maturity = _to_date(maturity_date)
    if payments_per_year <= 0:
        raise ValueError("payments_per_year must be positive")
    if maturity <= start:
        raise ValueError("maturity_date must be after issue_date")

    months = int(round(12 / payments_per_year))
    dates: List[date] = []
    current = _add_months(start, months)
    while current < maturity:
        dates.append(current)
        current = _add_months(current, months)
    dates.append(maturity)
    return dates


def previous_and_next_coupon(
    settlement_date: date | datetime | str,
    schedule: Sequence[date],
    issue_date: date | datetime | str,
) -> Tuple[date, date]:
    """Return the coupon dates immediately surrounding settlement."""
    settlement = _to_date(settlement_date)
    issue = _to_date(issue_date)
    if not schedule:
        raise ValueError("schedule must contain at least one payment date")
    if settlement <= schedule[0]:
        return issue, schedule[0]
    prev = schedule[0]
    for dt in schedule:
        if dt >= settlement:
            return prev, dt
        prev = dt
    return schedule[-1], schedule[-1]


def future_cashflow_dates(
    settlement_date: date | datetime | str, schedule: Iterable[date]
) -> List[date]:
    """Return coupon dates strictly after settlement."""
    settlement = _to_date(settlement_date)
    return [dt for dt in schedule if dt > settlement]
