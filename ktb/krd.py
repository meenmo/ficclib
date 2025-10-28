"""Key rate delta calculations for KTB bonds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Iterable, List

import logging
import math

from .analytics import _price_from_curve
from .curve import ZeroCurve
from utils.cashflows import Cashflow, accrued_interest, coupon_cashflows
from utils.daycount import get_day_count

logger = logging.getLogger(__name__)


def _to_date(value: date | datetime | str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Unsupported date-like value: {value!r}")


def _pick(spec: Dict, keys: Iterable[str], default=None):
    for key in keys:
        if key in spec:
            return spec[key]
    return default


def _linear_interpolate(value: float, data: Dict[float, float]) -> float:
    items = sorted((float(k), float(v)) for k, v in data.items())
    if not items:
        raise ValueError("data must not be empty for interpolation")
    if value <= items[0][0]:
        return items[0][1]
    if value >= items[-1][0]:
        return items[-1][1]
    for idx in range(1, len(items)):
        x0, y0 = items[idx - 1]
        x1, y1 = items[idx]
        if x0 <= value <= x1:
            weight = (value - x0) / (x1 - x0)
            return y0 + weight * (y1 - y0)
    return items[-1][1]


@dataclass(frozen=True)
class BondSpec:
    issue_date: date
    maturity_date: date
    coupon: float
    payment_frequency: int
    face: float
    day_count: str
    settlement_date: date


def _normalize_bond_spec(bond_spec: Dict, curve: ZeroCurve) -> BondSpec:
    issue_raw = _pick(bond_spec, ("issue_date", "issue"))
    maturity_raw = _pick(bond_spec, ("maturity_date", "maturity"))
    if issue_raw is None or maturity_raw is None:
        raise ValueError("bond_spec must include issue_date and maturity_date")
    coupon = float(_pick(bond_spec, ("coupon", "coupon_rate"), 0.0))
    payment_frequency = int(_pick(bond_spec, ("payment_frequency", "frequency", "payments_per_year"), 2))
    face = float(_pick(bond_spec, ("face", "face_value"), 10_000.0))
    day_count = str(_pick(bond_spec, ("day_count", "daycount"), "ACT/365F"))

    settlement_raw = _pick(
        bond_spec,
        ("settlement_date", "valuation_date", "settlement", "curve_date"),
        curve.curve_date,
    )

    issue = _to_date(issue_raw)
    maturity = _to_date(maturity_raw)
    settlement = _to_date(settlement_raw)
    if settlement < issue:
        settlement = issue
    if settlement > maturity:
        settlement = maturity

    return BondSpec(
        issue_date=issue,
        maturity_date=maturity,
        coupon=coupon,
        payment_frequency=payment_frequency,
        face=face,
        day_count=day_count,
        settlement_date=settlement,
    )


def _build_discount_grid_from_par(
    par_curve_pct: Dict[float, float],
    frequency: int,
) -> Dict[float, float]:
    max_t = max(par_curve_pct.keys())
    grid = _build_halfyear_grid_local(par_curve_pct, max_t=max_t)
    if max_t not in grid:
        grid = sorted(set(grid + [max_t]))
    df_grid: Dict[float, float] = {}
    for tenor in grid:
        ytm_pct = _linear_interpolate(tenor, par_curve_pct)
        ytm_dec = ytm_pct / 100.0
        df_grid[tenor] = (1.0 + ytm_dec / frequency) ** (-frequency * tenor)
    return df_grid


def _discount_factor_from_grid(df_grid: Dict[float, float], t: float) -> float:
    keys = sorted(df_grid.keys())
    if not keys:
        return 1.0
    if t <= keys[0]:
        anchor = keys[0]
        if anchor <= 0:
            return 1.0
        z = -math.log(df_grid[anchor]) / anchor
        return math.exp(-z * t)
    if t >= keys[-1]:
        anchor = keys[-1]
        if anchor <= 0:
            return 1.0
        z = -math.log(df_grid[anchor]) / anchor
        return math.exp(-z * t)
    for idx in range(1, len(keys)):
        t0, t1 = keys[idx - 1], keys[idx]
        if t0 <= t <= t1:
            df0, df1 = df_grid[t0], df_grid[t1]
            z0 = -math.log(df0) / t0 if t0 > 0 else -math.log(df1) / t1
            z1 = -math.log(df1) / t1
            weight = (t - t0) / (t1 - t0)
            z_t = z0 + (z1 - z0) * weight
            return math.exp(-z_t * t)
    anchor = keys[-1]
    z = -math.log(df_grid[anchor]) / anchor
    return math.exp(-z * t)


def _price_bond_with_par_curve(
    spec: BondSpec,
    par_curve_pct: Dict[float, float],
    *,
    as_clean: bool,
) -> float:
    df_grid = _build_discount_grid_from_par(par_curve_pct, spec.payment_frequency)
    dc_func = get_day_count(spec.day_count)
    flows = coupon_cashflows(
        issue_date=spec.issue_date,
        maturity_date=spec.maturity_date,
        coupon_rate=spec.coupon,
        payments_per_year=spec.payment_frequency,
        face=spec.face,
    )
    dirty = 0.0
    for dt, amount in flows:
        if dt <= spec.settlement_date:
            continue
        t = dc_func(spec.settlement_date, dt)
        df = _discount_factor_from_grid(df_grid, t)
        dirty += amount * df
    if not as_clean:
        return dirty
    acc = accrued_interest(
        issue_date=spec.issue_date,
        maturity_date=spec.maturity_date,
        coupon_rate=spec.coupon,
        payments_per_year=spec.payment_frequency,
        settlement_date=spec.settlement_date,
        face=spec.face,
        day_count=spec.day_count,
    )
    return dirty - acc


def _shift_par_curve(
    par_curve_pct: Dict[float, float],
    tenor: float,
    shift_bp: float,
) -> Dict[float, float]:
    shift_pct = shift_bp / 100.0
    result = dict(par_curve_pct)
    if tenor in result:
        result[tenor] = result[tenor] + shift_pct
    else:
        base = _linear_interpolate(tenor, par_curve_pct)
        result[tenor] = base + shift_pct
    return dict(sorted(result.items()))


def _build_halfyear_grid_local(
    par_curve_pct: Dict[float, float], max_t: float | None = None
) -> List[float]:
    if not par_curve_pct:
        return []
    tenors = sorted(float(t) for t in par_curve_pct.keys())
    if max_t is None:
        max_t = tenors[-1]
    grid: set[float] = set()
    if max_t >= 0.25:
        grid.add(0.25)
    k = 1
    while True:
        tenor = 0.5 * k
        if tenor > max_t + 1e-12:
            break
        grid.add(round(tenor, 12))
        k += 1
    if max_t >= 0.75:
        grid.add(0.75)
    return sorted(grid)


def _curve_price(
    spec: BondSpec, curve: ZeroCurve, *, as_clean: bool
) -> float:
    flows = coupon_cashflows(
        issue_date=spec.issue_date,
        maturity_date=spec.maturity_date,
        coupon_rate=spec.coupon,
        payments_per_year=spec.payment_frequency,
        face=spec.face,
    )
    accrued = 0.0
    if as_clean:
        accrued = accrued_interest(
            issue_date=spec.issue_date,
            maturity_date=spec.maturity_date,
            coupon_rate=spec.coupon,
            payments_per_year=spec.payment_frequency,
            settlement_date=spec.settlement_date,
            face=spec.face,
            day_count=spec.day_count,
        )
    return _price_from_curve(
        flows,
        settlement_date=spec.settlement_date,
        discount_factor=curve.df,
        day_count=spec.day_count,
        as_clean=as_clean,
        accrued=accrued,
    )


def key_rate_delta(
    bond_spec: Dict,
    curve: ZeroCurve,
    key_tenor_years: float,
    as_clean: bool = True,
) -> float:
    """Return the price delta for a −1 bp shift at the specified tenor."""
    spec = _normalize_bond_spec(bond_spec, curve)
    if getattr(curve, "_par_nodes", None):
        par_curve_pct = {
            tenor: rate * 100.0 for tenor, rate in curve._par_nodes.items()
        }
        base_price = _price_bond_with_par_curve(
            spec,
            par_curve_pct,
            as_clean=as_clean,
        )
        shifted_pct = _shift_par_curve(par_curve_pct, key_tenor_years, -1.0)
        shifted_price = _price_bond_with_par_curve(
            spec,
            shifted_pct,
            as_clean=as_clean,
        )
        delta = (shifted_price - base_price) / spec.face
        logger.debug(
            "KRD(par) tenor=%sY base=%s shifted=%s delta=%s",
            key_tenor_years,
            base_price,
            shifted_price,
            delta,
        )
        return delta

    base_price = _curve_price(spec, curve, as_clean=as_clean)
    shifted_curve = curve.clone_with_shifted_node(key_tenor_years, -1.0)
    shifted_price = _curve_price(spec, shifted_curve, as_clean=as_clean)
    delta = (shifted_price - base_price) / spec.face
    logger.debug(
        "KRD tenor=%sY base=%s shifted=%s delta=%s",
        key_tenor_years,
        base_price,
        shifted_price,
        delta,
    )
    return delta


def batch_key_rate_delta(
    bonds: List[Dict],
    curve: ZeroCurve,
    key_tenors: List[float],
    as_clean: bool = True,
) -> Dict[str, Dict[float, float]]:
    """Compute KRD for a batch of bonds and key tenors."""
    results: Dict[str, Dict[float, float]] = {}
    for bond_spec in bonds:
        spec = _normalize_bond_spec(bond_spec, curve)
        isin = _pick(bond_spec, ("ISIN", "isin", "id"), "")
        tenors: Dict[float, float] = {}
        if getattr(curve, "_par_nodes", None):
            par_curve_pct = {
                tenor: rate * 100.0 for tenor, rate in curve._par_nodes.items()
            }
            base_price = _price_bond_with_par_curve(
                spec,
                par_curve_pct,
                as_clean=as_clean,
            )
            for tenor in key_tenors:
                shifted_pct = _shift_par_curve(par_curve_pct, float(tenor), -1.0)
                shifted_price = _price_bond_with_par_curve(
                    spec,
                    shifted_pct,
                    as_clean=as_clean,
                )
                tenors[float(tenor)] = (shifted_price - base_price) / spec.face
        else:
            base_price = _curve_price(spec, curve, as_clean=as_clean)
            for tenor in key_tenors:
                shifted_curve = curve.clone_with_shifted_node(float(tenor), -1.0)
                shifted_price = _curve_price(spec, shifted_curve, as_clean=as_clean)
                tenors[float(tenor)] = (shifted_price - base_price) / spec.face
        key = str(isin) if isin else f"{spec.issue_date}-{spec.maturity_date}"
        results[key] = tenors
    return results
