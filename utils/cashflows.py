"""Cash flow and accrued interest helpers for KTB bonds."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Sequence, Tuple

from .daycount import DayCountFunc, get_day_count
from .schedule import coupon_schedule, previous_and_next_coupon

Cashflow = Tuple[date, float]


def _to_date(value: date | datetime | str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Unsupported date-like value: {value!r}")


def coupon_amount(face: float, coupon_rate: float, payments_per_year: int) -> float:
    """Return the per-period coupon cash amount."""
    return float(face) * float(coupon_rate) / float(payments_per_year)


def coupon_cashflows(
    issue_date: date | datetime | str,
    maturity_date: date | datetime | str,
    coupon_rate: float,
    payments_per_year: int,
    face: float = 10_000.0,
) -> List[Cashflow]:
    """Return coupon (and redemption) cash flows as (date, amount)."""
    schedule = coupon_schedule(issue_date, maturity_date, payments_per_year)
    coupon = coupon_amount(face, coupon_rate, payments_per_year)
    flows: List[Cashflow] = [(dt, coupon) for dt in schedule[:-1]]
    flows.append((schedule[-1], coupon + face))
    return flows


def accrued_interest(
    issue_date: date | datetime | str,
    maturity_date: date | datetime | str,
    coupon_rate: float,
    payments_per_year: int,
    settlement_date: date | datetime | str,
    face: float = 10_000.0,
    day_count: str = "ACT/365F",
) -> float:
    """Return accrued interest at settlement using the ACT/365F convention."""
    schedule = coupon_schedule(issue_date, maturity_date, payments_per_year)
    settlement = _to_date(settlement_date)
    if settlement >= schedule[-1]:
        return 0.0
    prev_coupon, next_coupon = previous_and_next_coupon(
        settlement_date, schedule, issue_date
    )
    dc_func: DayCountFunc = get_day_count(day_count)
    accrual_period = dc_func(prev_coupon, next_coupon)
    if accrual_period <= 0:
        return 0.0
    elapsed = dc_func(prev_coupon, settlement)
    return coupon_amount(face, coupon_rate, payments_per_year) * elapsed / accrual_period


def dirty_from_clean(clean_price: float, accrued: float) -> float:
    """Dirty price = clean + accrued."""
    return float(clean_price) + float(accrued)


def clean_from_dirty(dirty_price: float, accrued: float) -> float:
    """Clean price = dirty − accrued."""
    return float(dirty_price) - float(accrued)


def future_cashflows(
    settlement_date: date | datetime | str, flows: Sequence[Cashflow]
) -> List[Cashflow]:
    """Filter cash flows strictly after settlement."""
    settlement = _to_date(settlement_date)
    return [(dt, amt) for dt, amt in flows if dt > settlement]
