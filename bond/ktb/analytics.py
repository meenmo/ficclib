"""Pricing routines for Korean Treasury Bonds (KTB)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable, Iterable, List, Tuple

import logging
import math

from ficclib.bond.utils.cashflows import Cashflow, accrued_interest, coupon_cashflows
from ficclib.bond.utils.daycount import get_day_count
from ficclib.bond.utils.rootfinding import RootFindingError, newton_with_bisect
from ficclib.bond.utils.date import to_date as _to_date

logger = logging.getLogger(__name__)

_VALUATION_DATE: date | None = None


def set_valuation_date(value: date | datetime | str | None) -> None:
    """Set the global valuation/settlement date for analytics."""
    global _VALUATION_DATE
    if value is None:
        _VALUATION_DATE = None
    else:
        _VALUATION_DATE = _to_date(value)


def _resolve_settlement(issue: date, maturity: date) -> date:
    settlement = _VALUATION_DATE or date.today()
    if settlement < issue:
        return issue
    if settlement > maturity:
        return maturity
    return settlement


def _validate_inputs(
    issue_date: date, maturity_date: date, coupon: float, payment_frequency: int, ytm: float
) -> None:
    if maturity_date <= issue_date:
        raise ValueError("maturity_date must be after issue_date")
    if payment_frequency <= 0:
        raise ValueError("payment_frequency must be positive")
    if coupon < 0:
        raise ValueError("coupon rate must be non-negative")
    if ytm <= -1.0:
        raise ValueError("ytm must be greater than -100%")


def _cashflows(
    issue_date: date,
    maturity_date: date,
    coupon: float,
    payment_frequency: int,
    face: float,
) -> List[Cashflow]:
    return coupon_cashflows(
        issue_date=issue_date,
        maturity_date=maturity_date,
        coupon_rate=coupon,
        payments_per_year=payment_frequency,
        face=face,
    )


def _price_from_curve(
    flows: Iterable[Cashflow],
    *,
    settlement_date: date | datetime | str,
    discount_factor: Callable[[float], float],
    day_count: str,
    as_clean: bool,
    accrued: float = 0.0,
) -> float:
    """Discount future flows using an externally supplied discount function."""
    settlement = _to_date(settlement_date)
    dc_func = get_day_count(day_count)
    dirty = 0.0
    for dt, amount in flows:
        if dt <= settlement:
            continue
        t = dc_func(settlement, dt)
        dirty += amount * discount_factor(t)
    return dirty - accrued if as_clean else dirty


def price_from_ytm(
    issue_date: date | datetime | str,
    maturity_date: date | datetime | str,
    coupon: float,
    payment_frequency: int,
    ytm: float,
    face: float = 10_000.0,
    day_count: str = "ACT/365F",
    as_clean: bool = False,
) -> float:
    """Return DIRTY price for a coupon bond given YTM (decimal).

    Parameters are expressed in decimals internally; pass coupon and ytm as decimals
    (e.g., 0.0275 for 2.75%).
    """
    issue = _to_date(issue_date)
    maturity = _to_date(maturity_date)
    _validate_inputs(issue, maturity, coupon, payment_frequency, ytm)
    settlement = _resolve_settlement(issue, maturity)
    if settlement >= maturity:
        return 0.0

    flows = _cashflows(issue, maturity, coupon, payment_frequency, face)
    dc_func = get_day_count(day_count)
    freq = float(payment_frequency)
    r = float(ytm) / freq
    base = 1.0 + r
    if base <= 0.0:
        raise ValueError("1 + ytm/payment_frequency must be positive")
    log_base = math.log(base)

    price = 0.0
    for dt, amount in flows:
        if dt <= settlement:
            continue
        t = dc_func(settlement, dt)
        discount = math.exp(-freq * t * log_base)
        price += amount * discount

    if as_clean:
        ai = accrued_interest(
            issue_date=issue,
            maturity_date=maturity,
            coupon_rate=coupon,
            payments_per_year=payment_frequency,
            settlement_date=settlement,
            face=face,
            day_count=day_count,
        )
        return price - ai
    return price


def ytm_from_price(
    issue_date: date | datetime | str,
    maturity_date: date | datetime | str,
    coupon: float,
    payment_frequency: int,
    price_dirty: float,
    face: float = 10_000.0,
    day_count: str = "ACT/365F",
    guess: float | None = None,
) -> float:
    """Solve YTM (decimal) from a DIRTY price."""
    issue = _to_date(issue_date)
    maturity = _to_date(maturity_date)
    _validate_inputs(issue, maturity, coupon, payment_frequency, 0.0)
    settlement = _resolve_settlement(issue, maturity)
    flows = _cashflows(issue, maturity, coupon, payment_frequency, face)
    if not flows or settlement >= flows[-1][0]:
        return 0.0

    dc_func = get_day_count(day_count)
    freq = float(payment_frequency)

    future_flows = [(dt, amt) for dt, amt in flows if dt > settlement]
    if not future_flows:
        return 0.0

    def func_and_deriv(y: float) -> Tuple[float, float]:
        if y <= -freq + 1e-12:
            y = -freq + 1e-12
        log_base = math.log1p(y / freq)
        price = 0.0
        deriv = 0.0
        for dt, amount in future_flows:
            t = dc_func(settlement, dt)
            expo = -freq * t * log_base
            discount = math.exp(expo)
            price += amount * discount
            deriv += amount * discount * (-freq * t) / (freq + y)
        return price - price_dirty, deriv

    initial = guess if guess is not None else max(coupon, 0.02)
    try:
        result = newton_with_bisect(
            func_and_deriv,
            initial,
            tol_value=1e-6,
            tol_step=1e-10,
            max_iter=50,
            clamp=0.01,
            bracket=(-0.02, 0.30),
        )
    except RootFindingError as exc:
        logger.error("Root finding failed: %s", exc)
        raise
    logger.debug("YTM solved after %s iterations via %s", result.iterations, result.method)
    return result.root
