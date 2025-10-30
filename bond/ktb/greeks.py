from __future__ import annotations
from dataclasses import dataclass
from typing import List, Literal, Optional, Union
from datetime import date, timedelta
import numpy as np
import pandas as pd
from sympy import Symbol, nsolve

from ficclib.bond.ktb.bond import KTB, DAYS_IN_YEAR
from ficclib.bond.ktb.curve import (
    build_halfyear_grid,
    nodes_to_time_arrays,
)
from ficclib.bond.ktb.curve_types import CurveNode


@dataclass
class BasketBond:
    issue_date: date
    maturity_date: date
    coupon_rate: float  # percent, e.g., 3.5
    face_value: float = 10000.0
    pymt_freq_months: int = 6


def _years(d0: date, d1: date) -> float:
    """Convert date difference to years."""
    return (d1 - d0).days / DAYS_IN_YEAR


# =========================
# Spot Key-Rate Sensitivity
# =========================


def _adjacent_payment_dates_like_futures(kb: KTB, as_of: date) -> tuple[date, date]:
    """Replicate KTB_Futures._adjacent_payment_dates logic using KTB cash flows.
    Returns (previous_coupon_date, next_coupon_date)."""
    flows = kb.cash_flows()
    if not flows:
        return kb.issue, kb.maturity
    if as_of < flows[0][0]:
        return kb.issue, flows[0][0]
    prev_dt = flows[0][0]
    for dt, _ in flows:
        if dt <= as_of:
            prev_dt = dt
        else:
            return prev_dt, dt
    return flows[-1][0], flows[-1][0]


def _bond_price_and_derivative(
    y_decimal: float,
    coupon_rate_decimal: float,
    coupons_per_year: int,
    num_payments_remaining: int,
    prev_coupon_date: date,
    next_coupon_date: date,
    valuation_date: date,
    face_value: float = 10000.0,
) -> tuple[float, float]:
    """Return (price, dPrice/dy) using the same convention as above.

    Analytic derivative for Newton step to improve robustness.
    """
    m = float(coupons_per_year)
    if num_payments_remaining <= 0:
        return 0.0, 0.0

    discount_ratio = 1.0 + y_decimal / m
    coupon_amount = face_value * coupon_rate_decimal / m

    # Precompute powers and sums
    # S0 = sum_{i=0}^{N-1} discount^{-i}
    # S1 = sum_{i=0}^{N-1} i * discount^{-(i+1)}
    inv = 1.0 / discount_ratio
    pow_inv_i = 1.0  # discount^{-0}
    S0 = 0.0
    S1 = 0.0
    for i in range(num_payments_remaining):
        S0 += pow_inv_i
        if i > 0:
            S1 += i * (pow_inv_i * inv)  # discount^{-(i+1)}
        pow_inv_i *= inv

    # After loop, pow_inv_i == discount^{-N}
    disc_pow_N_minus_1 = pow_inv_i / inv  # discount^{-(N-1)}
    disc_pow_N = pow_inv_i  # discount^{-N}

    A = coupon_amount * S0 + face_value * disc_pow_N_minus_1

    # A' = -(1/m) * [coupon_amount * S1 + face * (N-1) * discount^{-N}]
    N = float(num_payments_remaining)
    A_prime = -(1.0 / m) * (coupon_amount * S1 + face_value * (N - 1.0) * disc_pow_N)

    d = (next_coupon_date - valuation_date).days
    t = max((next_coupon_date - prev_coupon_date).days, 1)
    k = (d / t) / m

    denom = 1.0 + k * y_decimal
    price = A / denom
    dprice = (A_prime * denom - A * k) / (denom * denom)
    return price, dprice


def ytm_by_price_newton_raphson(
    bond_type: int,  # ignored / placeholder for compatibility
    price: float,
    issue: date,
    maturity: date,
    valuation: date,
    coupon_decimal: float,
    coupons_per_year: int,
) -> float:
    """Invert dirty price -> annual YTM (decimal) using KTB_Futures.bond_market_price logic.

    Uses semiannual comp (generalized to coupons_per_year) and day-fraction adjustment
    back from next coupon date to valuation date.
    """
    # Build a KTB to obtain schedule details
    pymt_freq_months = int(round(12 / coupons_per_year))
    kb = KTB(issue, maturity, coupon_decimal * 100.0, pymt_freq_months, 10000.0)

    # Adjacent coupon dates and remaining payments (strictly after valuation)
    prev_dt, next_dt = _adjacent_payment_dates_like_futures(kb, valuation)
    remaining = sum(1 for dt, _ in kb.cash_flows() if dt > valuation)

    # Handle trivial edge case
    if remaining <= 0:
        return 0.0

    # Newton-Raphson with bracketing fallback
    target = price
    y = max(0.0, min(0.20, float(coupon_decimal)))  # initial guess near coupon

    # Try to bracket root in [yL, yH]
    def f(yv: float) -> tuple[float, float]:
        p, dp = _bond_price_and_derivative(
            yv, coupon_decimal, coupons_per_year, remaining, prev_dt, next_dt, valuation
        )
        return p - target, dp

    yL, yH = 1e-6, 1.0
    fL, _ = f(yL)
    fH, _ = f(yH)
    if fL * fH > 0:
        # Expand if necessary
        yH = 2.0
        fH, _ = f(yH)
        if fL * fH > 0:
            # Fall back to using Newton without a strict bracket
            yL, yH = 0.0, 2.0

    for _ in range(50):
        fv, dfv = f(y)
        if abs(fv) < 1e-8:
            return max(0.0, float(y))
        if dfv != 0:
            step = fv / dfv
            y_new = y - step
        else:
            y_new = (yL + yH) / 2.0

        # Keep within reasonable bounds
        if not (yL <= y_new <= yH):
            y_new = max(yL, min(yH, y_new))

        # Update bracket if sign change
        fv_new, _ = f(y_new)
        if fL * fv_new <= 0 and y_new < y:
            yH, fH = y, fv
        elif fH * fv_new <= 0 and y_new > y:
            yL, fL = y, fv

        y = y_new

    return max(0.0, float(y))


# =========================
# Bond KRD via Re-Bootstrap
# =========================


def _bump_par_curve(
    ytm_curve: Union[List[CurveNode], dict],
    key_tenor: float,
    bump_bp: float = 1.0,
) -> Union[List[CurveNode], dict]:
    """Return a new curve bumped by −bp at the key tenor.

    - Dict input is assumed {tenor_years: ytm_percent}.
    - List[CurveNode] input is decimal yields.
    """
    if isinstance(ytm_curve, dict):
        bumped = dict(ytm_curve)
        # If no exact key, linearly interpolate to create it
        if key_tenor not in bumped:
            import numpy as _np

            ks = _np.array(sorted(bumped.keys()), dtype=float)
            vs = _np.array([bumped[k] for k in ks], dtype=float)
            bumped[key_tenor] = float(_np.interp(float(key_tenor), ks, vs))
        bumped[key_tenor] = float(bumped[key_tenor]) - float(bump_bp / 100)
        return bumped

    # List[CurveNode]
    nodes = list(ytm_curve)
    tenors = [float(n.tenor_years) for n in nodes]

    idx = tenors.index(float(key_tenor))
    dec_bump = float(bump_bp) / 100
    nodes[idx] = CurveNode(nodes[idx].tenor_years, float(nodes[idx].ytm) - dec_bump)
    return nodes


def price_bond_by_par_curve(
    issue_date: date,
    maturity_date: date,
    coupon_rate_percent: float,
    valuation_date: date,
    ytm_curve: Union[List[CurveNode], dict],
    coupons_per_year: int = 2,
    max_t: float | None = None,
) -> float:
    """Price a bond using the provided YTM curve."""
    # Convert dict to CurveNode list if needed
    if isinstance(ytm_curve, dict):
        curve_nodes = [
            CurveNode(tenor, ytm / 100.0) for tenor, ytm in ytm_curve.items()
        ]
    else:
        curve_nodes = ytm_curve

    # Build half-year grid from the curve
    grid_tenors = build_halfyear_grid(curve_nodes, max_t=max_t)

    # Interpolate YTMs at grid points and convert to discount factors
    from ficclib.bond.ktb.curve_types import DiscountFactorNode

    # Create a simple interpolation function
    def interpolate_ytm(tenor):
        # Find surrounding points
        for i, node in enumerate(curve_nodes):
            if i == 0 and tenor <= node.tenor_years:
                return node.ytm
            if i == len(curve_nodes) - 1:
                return node.ytm
            if curve_nodes[i].tenor_years <= tenor <= curve_nodes[i + 1].tenor_years:
                # Linear interpolation
                t1, y1 = curve_nodes[i].tenor_years, curve_nodes[i].ytm
                t2, y2 = curve_nodes[i + 1].tenor_years, curve_nodes[i + 1].ytm
                return y1 + (y2 - y1) * (tenor - t1) / (t2 - t1)
        return curve_nodes[-1].ytm

    # Convert grid tenors to discount factor nodes
    discount_nodes = []
    for tenor in grid_tenors:
        ytm = interpolate_ytm(tenor)
        # Convert YTM to discount factor (semi-annual compounding)
        df = (1 + ytm / 2) ** (-2 * tenor)
        df_date = valuation_date + timedelta(days=int(tenor * 365))
        discount_nodes.append(
            DiscountFactorNode(
                date=df_date, discount_factor=df, years_from_valuation=tenor
            )
        )

    # Convert to time arrays
    times, dfs = nodes_to_time_arrays(discount_nodes)
    kb = KTB(
        issue_date,
        maturity_date,
        coupon_rate_percent,
        int(round(12 / coupons_per_year)),
    )
    # Convert arrays to DiscountFactorNode list
    from ficclib.bond.ktb.curve_types import DiscountFactorNode

    discount_nodes = []
    for i, t in enumerate(times):
        df_date = valuation_date + timedelta(days=int(t * 365))
        discount_nodes.append(
            DiscountFactorNode(
                date=df_date, discount_factor=dfs[i], years_from_valuation=t
            )
        )
    return float(kb.price_from_zero_curve(valuation_date, discount_nodes))


def krd_bond_via_bootstrap(
    issue_date: date,
    maturity_date: date,
    coupon_rate_percent: float,
    valuation_date: date,
    ytm_curve: Union[List[CurveNode], dict],
    key_tenor: float,
    bump_bp: float = 1.0,
    coupons_per_year: int = 2,
    max_t: float | None = None,
) -> float:
    """KRD = Price(-bp at key tenor) − Price(base), via re-bootstrapping the curve."""
    base = price_bond_by_par_curve(
        issue_date,
        maturity_date,
        coupon_rate_percent,
        valuation_date,
        ytm_curve,
        coupons_per_year,
        max_t,
    )
    bumped_curve = _bump_par_curve(ytm_curve, key_tenor, bump_bp)
    bumped = price_bond_by_par_curve(
        issue_date,
        maturity_date,
        coupon_rate_percent,
        valuation_date,
        bumped_curve,
        coupons_per_year,
        max_t,
    )
    return float(bumped - base)
