from __future__ import annotations

from typing import Dict, Iterable, Tuple
from datetime import date

from ficclib.bond.ktb.greeks import (
    krd_bond_via_bootstrap,
    ytm_by_price_newton_raphson,
    CurveNode,
)


def _price_from_par_curve(
    issue_date: date,
    maturity_date: date,
    coupon_rate_percent: float,
    valuation_date: date,
    ytm_curve: Dict[float, float],
    coupons_per_year: int,
    max_t: float | None,
) -> float:
    """Price using the same routine as KRD baseline (via greeks module)."""
    # Lazily import to avoid circulars
    from ficclib.bond.ktb.greeks import price_bond_by_par_curve

    return float(
        price_bond_by_par_curve(
            issue_date,
            maturity_date,
            coupon_rate_percent,
            valuation_date,
            ytm_curve,
            coupons_per_year,
            max_t,
        )
    )


def equivalent_ytm_shifts_for_bond(
    *,
    issue_date: date,
    maturity_date: date,
    coupon_rate_percent: float,
    valuation_date: date,
    ytm_curve: Dict[float, float],  # tenor_years -> ytm_percent
    key_tenors: Iterable[float],
    bump_bp: float = 1.0,
    coupons_per_year: int = 2,
    max_t: float | None = None,
) -> Dict[float, float]:
    """Return equivalent YTM shifts (in percent points) per key tenor for one bond.

    For each tenor i, find Δy_eq such that plain YTM pricer reproduces the
    same price change as the KRD local −bump_bp bp move at tenor i.

    Returns mapping tenor -> Δy_eq_percent (percent points).
    """
    # Base price from the current curve
    base_price = _price_from_par_curve(
        issue_date,
        maturity_date,
        coupon_rate_percent,
        valuation_date,
        ytm_curve,
        coupons_per_year,
        max_t,
    )

    # Base YTM from base price
    y0_decimal = ytm_by_price_newton_raphson(
        bond_type=0,
        price=base_price,
        issue=issue_date,
        maturity=maturity_date,
        valuation=valuation_date,
        coupon_decimal=float(coupon_rate_percent) / 100.0,
        coupons_per_year=int(coupons_per_year),
    )

    result: Dict[float, float] = {}

    for tenor in key_tenors:
        # Curve-based price change for −bump_bp at this tenor
        dP_curve = krd_bond_via_bootstrap(
            issue_date=issue_date,
            maturity_date=maturity_date,
            coupon_rate_percent=coupon_rate_percent,
            valuation_date=valuation_date,
            ytm_curve=ytm_curve,
            key_tenor=float(tenor),
            bump_bp=float(bump_bp),
            coupons_per_year=int(coupons_per_year),
            max_t=max_t,
        )

        target_price = base_price + float(dP_curve)

        # Invert YTM at base and bumped prices using the same conventions
        y1_decimal = ytm_by_price_newton_raphson(
            bond_type=0,
            price=target_price,
            issue=issue_date,
            maturity=maturity_date,
            valuation=valuation_date,
            coupon_decimal=float(coupon_rate_percent) / 100.0,
            coupons_per_year=int(coupons_per_year),
        )

        dy_decimal = float(y1_decimal) - float(y0_decimal)
        result[float(tenor)] = dy_decimal * 100.0  # percent points

    return result


def equivalent_ytm_levels_for_bond(
    *,
    observed_ytm_percent: float,
    shifts_percent: Dict[float, float],
) -> Dict[float, float]:
    """Convert shifts to equivalent YTM levels (percent) by adding the observed YTM.

    observed_ytm_percent: the market YTM for the bond
    shifts_percent: tenor -> Δy_eq in percent points
    """
    base = float(observed_ytm_percent)
    return {tenor: base + float(shift) for tenor, shift in shifts_percent.items()}


def equivalent_ytm_for_bonds(
    *,
    ktb_records: Iterable[
        Tuple[str, str, str, float]
    ],  # (isin, issue_s, maturity_s, coupon_pct)
    observed_ytm_map: Dict[str, float],  # ISIN -> observed YTM percent
    ytm_curve: Dict[float, float],  # tenor -> ytm percent (par curve used for KRD)
    key_tenors: Iterable[float],
    valuation_date: date,
    bump_bp: float = 1.0,
    coupons_per_year: int = 2,
    max_t: float | None = None,
) -> Dict[str, Dict[str, Dict[float, float]]]:
    """Compute equivalent YTM shifts and levels for a list of bonds.

    Returns mapping:
      ISIN -> { 'shifts': {tenor: dY_percent}, 'levels': {tenor: y_equiv_percent} }
    """
    out: Dict[str, Dict[str, Dict[float, float]]] = {}

    for isin, issue_s, maturity_s, coupon_pct in ktb_records:
        issue = date.fromisoformat(issue_s)
        maturity = date.fromisoformat(maturity_s)

        shifts = equivalent_ytm_shifts_for_bond(
            issue_date=issue,
            maturity_date=maturity,
            coupon_rate_percent=coupon_pct,
            valuation_date=valuation_date,
            ytm_curve=ytm_curve,
            key_tenors=key_tenors,
            bump_bp=bump_bp,
            coupons_per_year=coupons_per_year,
            max_t=max_t,
        )
        observed = float(observed_ytm_map.get(isin, 0.0))
        levels = equivalent_ytm_levels_for_bond(
            observed_ytm_percent=observed, shifts_percent=shifts
        )
        out[isin] = {"shifts": shifts, "levels": levels}

    return out
