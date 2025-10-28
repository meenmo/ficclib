from __future__ import annotations

from typing import Dict, List, Tuple, Union
import numpy as np
import math
from bisect import bisect_left
from datetime import date

from ficclib.ktb.bond import KTB
from ficclib.ktb.curve_types import DiscountFactorNode
from .utils import (
    build_df_zero_grid,  # not used here after refactor, but kept for API parity if needed
)


def bootstrap_dfs_from_bonds(
    bonds: List[Tuple[Union[str, date], Union[str, date], float, float]],
    valuation_date: date,
    coupon_term_months: int = 6,
) -> List[DiscountFactorNode]:
    items: List[
        Tuple[
            int,
            Tuple[Union[str, date], Union[str, date], float, float],
            List[Tuple[date, float]],
        ]
    ] = []
    for issue, maturity, coupon_pct, dirty in bonds:
        kb = KTB(issue, maturity, coupon_pct, coupon_term_months)
        flows = [(dt, amt) for dt, amt in kb.cash_flows() if dt > valuation_date]
        if not flows:
            continue
        last_day = (flows[-1][0] - valuation_date).days
        items.append((last_day, (issue, maturity, coupon_pct, dirty), flows))

    items.sort(key=lambda x: x[0])

    from collections import deque

    q = deque(items)
    df_by_date: Dict[date, float] = {}

    progressed = True
    while q and progressed:
        progressed = False
        for _ in range(len(q)):
            last_day, (issue, maturity, coupon_pct, dirty), flows = q.popleft()

            known_ok = True
            known_dates_sorted = sorted(df_by_date.keys())

            D_T = flows[-1][0]
            const_pv = 0.0
            coeffs: List[Tuple[float, float]] = []

            for dt, amt in flows[:-1]:
                if dt in df_by_date:
                    const_pv += amt * df_by_date[dt]
                    continue
                if not df_by_date:
                    known_ok = False
                    break
                pos = bisect_left(known_dates_sorted, dt)
                if pos == 0:
                    known_ok = False
                    break
                d_lo = known_dates_sorted[pos - 1]
                df_lo = df_by_date[d_lo]
                if pos < len(known_dates_sorted):
                    d_hi = known_dates_sorted[pos]
                    w = (dt - d_lo).days / (d_hi - d_lo).days
                    ln_df = math.log(df_lo) + w * (
                        math.log(df_by_date[d_hi]) - math.log(df_lo)
                    )
                    const_pv += amt * math.exp(ln_df)
                else:
                    if dt >= D_T:
                        known_ok = False
                        break
                    alpha = (dt - d_lo).days / (D_T - d_lo).days
                    K = amt * (df_lo ** ((D_T - dt).days / (D_T - d_lo).days))
                    coeffs.append((K, alpha))

            if not known_ok:
                q.append((last_day, (issue, maturity, coupon_pct, dirty), flows))
                continue

            last_amt = float(flows[-1][1])

            def f(df_t: float) -> float:
                s = const_pv + last_amt * df_t
                for K, a in coeffs:
                    s += K * (df_t**a)
                return s - float(dirty)

            lo, hi = 1e-10, 1.0
            f_lo, f_hi = f(lo), f(hi)
            if f_lo > 0 and f_hi > 0:
                df_t_star = lo
            elif f_lo < 0 and f_hi < 0:
                df_t_star = hi
            else:
                for _ in range(80):
                    mid = 0.5 * (lo + hi)
                    fm = f(mid)
                    if abs(fm) < 1e-10:
                        df_t_star = mid
                        break
                    if f_lo * fm <= 0:
                        hi, f_hi = mid, fm
                    else:
                        lo, f_lo = mid, fm
                else:
                    df_t_star = 0.5 * (lo + hi)

            df_by_date[D_T] = max(min(df_t_star, 1.0), 0.0)
            progressed = True

    if q:
        pending = [(issue, maturity) for _, (issue, maturity, *_), _ in q]
        raise RuntimeError(f"Failed to bootstrap, missing earlier DFs for: {pending}")

    dates_sorted = sorted(df_by_date.keys())
    dfs_sorted = [df_by_date[d] for d in dates_sorted]

    nodes: List[DiscountFactorNode] = []
    for d, df in zip(dates_sorted, dfs_sorted):
        years_from_val = (d - valuation_date).days / 365.0
        nodes.append(
            DiscountFactorNode(
                date=d, discount_factor=df, years_from_valuation=years_from_val
            )
        )

    return nodes


def build_zero_curve_from_bonds(
    bonds: List[Tuple[Union[str, date], Union[str, date], float, float]],
    valuation_date: date,
    coupon_term_months: int = 6,
    max_tenor: float | None = None,
) -> Dict[float, float]:
    discount_nodes = bootstrap_dfs_from_bonds(bonds, valuation_date, coupon_term_months)
    return dfs_to_zero_curve_grid(discount_nodes, max_tenor)


def nodes_to_time_arrays(
    nodes: List[DiscountFactorNode],
) -> Tuple[np.ndarray, np.ndarray]:
    times = np.array([node.years_from_valuation for node in nodes], dtype=float)
    dfs = np.array([node.discount_factor for node in nodes], dtype=float)
    return times, dfs


def _halfyear_grid_from_max(max_tenor: float) -> List[float]:
    n = int(np.floor(float(max_tenor) / 0.5))
    return [0.5 * i for i in range(1, n + 1)]


def _interpolate_ln_df(times: np.ndarray, ln_dfs: np.ndarray, t: float) -> float:
    if t <= times[0]:
        return float(ln_dfs[0])
    if t >= times[-1]:
        return float(ln_dfs[-1])
    return float(np.interp(t, times, ln_dfs))


def dfs_to_zero_curve_grid(
    discount_nodes: List[DiscountFactorNode], max_tenor: float | None = None
) -> Dict[float, float]:
    times, dfs = nodes_to_time_arrays(discount_nodes)
    if len(times) == 0:
        return {}
    if max_tenor is None:
        max_tenor = float(np.max(times))

    ln_dfs = np.log(dfs)
    grid = _halfyear_grid_from_max(max_tenor)
    out: Dict[float, float] = {}
    for t in grid:
        ln_df_t = _interpolate_ln_df(times, ln_dfs, t)
        df_t = float(np.exp(ln_df_t))
        z_t = df_t ** (-1.0 / t) - 1.0 if t > 0 else 0.0
        out[t] = z_t * 100.0
    return out


def par_curve_from_discount_factors(
    discount_nodes: List[DiscountFactorNode],
    max_tenor: float = 50,
) -> Dict[float, float]:
    times, dfs = nodes_to_time_arrays(discount_nodes)
    actual_max_tenor = min(max_tenor, max(times))
    grid_tenors = _halfyear_grid_from_max(actual_max_tenor)

    grid_ytms = []
    for tenor in grid_tenors:
        coupon_times = np.arange(0.5, tenor + 0.5, 0.5)
        coupon_dfs = np.interp(coupon_times, times, dfs)
        df_maturity = np.interp(tenor, times, dfs)
        sum_coupon_dfs = np.sum(coupon_dfs[:-1])
        if sum_coupon_dfs > 0:
            ytm = 2.0 * (1.0 - df_maturity) / sum_coupon_dfs
        else:
            ytm = 2.0 * (df_maturity ** (-1.0 / (2.0 * tenor)) - 1.0)
        grid_ytms.append(ytm * 100.0)
    return dict(zip(grid_tenors, grid_ytms))


class BondsZeroCurveBuilder:
    def __init__(
        self,
        bonds: List[Tuple[Union[str, date], Union[str, date], float, float]],
        valuation_date: date,
        coupon_term_months: int = 6,
    ):
        self.bonds = bonds
        self.valuation_date = valuation_date
        self.coupon_term_months = coupon_term_months

    def bootstrap_discount_factors(self) -> List[DiscountFactorNode]:
        return bootstrap_dfs_from_bonds(
            self.bonds, self.valuation_date, self.coupon_term_months
        )

    def build_zero_curve(self, max_tenor: float | None = None) -> Dict[float, float]:
        nodes = self.bootstrap_discount_factors()
        return dfs_to_zero_curve_grid(nodes, max_tenor)

    def par_curve(self, max_tenor: float = 50) -> Dict[float, float]:
        nodes = self.bootstrap_discount_factors()
        return par_curve_from_discount_factors(nodes, max_tenor)
