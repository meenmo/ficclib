"""Zero curve utilities for KTB pricing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Iterable, Tuple, List

import bisect
import logging
import math

from ficclib.bond.utils.date import to_date as _to_date
from ficclib.bond.utils.mathutils import linear_interpolate as _linear_interpolate

logger = logging.getLogger(__name__)


def _normalize_nodes(nodes: Dict[float, float]) -> Dict[float, float]:
    if not nodes:
        raise ValueError("nodes must not be empty")
    converted: Dict[float, float] = {}
    max_abs = max(abs(float(v)) for v in nodes.values())
    scale = 0.01 if max_abs > 1.0 else 1.0
    for tenor, rate in nodes.items():
        tenor_f = float(tenor)
        if tenor_f <= 0:
            raise ValueError("tenor must be positive")
        converted[tenor_f] = float(rate) * scale
    return dict(sorted(converted.items()))




def _interpolate_simple_zero_rate(
    tenor: float, zero_rates: Dict[float, float]
) -> float:
    keys = sorted(zero_rates.keys())
    if not keys:
        raise ValueError("zero_rates must not be empty")
    if tenor <= keys[0]:
        return zero_rates[keys[0]]
    if tenor >= keys[-1]:
        return zero_rates[keys[-1]]
    for idx in range(1, len(keys)):
        t0, t1 = keys[idx - 1], keys[idx]
        if t0 <= tenor <= t1:
            z0, z1 = zero_rates[t0], zero_rates[t1]
            weight = (tenor - t0) / (t1 - t0)
            return z0 + weight * (z1 - z0)
    return zero_rates[keys[-1]]


def _coupon_schedule_times(tenor: float, frequency: int) -> List[float]:
    """Return coupon payment times (in years) up to tenor."""
    step = 1.0 / frequency
    times: List[float] = []
    t = step
    eps = 1e-12
    while t < tenor - eps:
        times.append(round(t, 12))
        t += step
    times.append(round(tenor, 12))
    return times


def _interpolate_log_df(
    t: float,
    known_times: List[float],
    known_dfs: Dict[float, float],
) -> float:
    if t <= known_times[0] + 1e-12:
        return known_dfs[known_times[0]]
    idx = bisect.bisect_right(known_times, t)
    if idx >= len(known_times):
        return known_dfs[known_times[-1]]
    t0 = known_times[idx - 1]
    t1 = known_times[idx]
    if abs(t1 - t0) < 1e-12:
        return known_dfs[t0]
    w = (t - t0) / (t1 - t0)
    ln_df0 = math.log(known_dfs[t0])
    ln_df1 = math.log(known_dfs[t1])
    return math.exp(ln_df0 + w * (ln_df1 - ln_df0))


def _bootstrap_zero_rates_from_par(
    par_nodes: Dict[float, float],
    frequency: int,
) -> Dict[float, float]:
    """Bootstrap continuous zero rates (decimal) from par-yield nodes."""
    if frequency <= 0:
        raise ValueError("frequency must be positive")
    if not par_nodes:
        raise ValueError("par_nodes must not be empty")

    ytm_nodes: Dict[float, float] = {}
    for tenor, rate in par_nodes.items():
        value = float(rate)
        if abs(value) >= 1.0:
            value /= 100.0
        ytm_nodes[float(tenor)] = value

    tenors = sorted(ytm_nodes.keys())
    if not tenors:
        raise ValueError("par_nodes must not be empty")

    known_times: List[float] = [0.0]
    known_dfs: Dict[float, float] = {0.0: 1.0}

    for tenor in tenors:
        coupon_rate = ytm_nodes[tenor]
        times = _coupon_schedule_times(tenor, frequency)
        const_pv = 0.0
        coeffs: List[Tuple[float, float, float, float]] = []  # amount, base, exponent, time
        prev = 0.0
        max_known = known_times[-1]

        for t in times[:-1]:
            delta = t - prev
            prev = t
            payment = coupon_rate * delta
            if t <= max_known + 1e-12:
                df_t = _interpolate_log_df(t, known_times, known_dfs)
                const_pv += payment * df_t
            else:
                t_lo = max_known
                if abs(tenor - t_lo) < 1e-12:
                    # Should not happen, but guard to avoid division by zero
                    coeffs.append((payment, 1.0, 1.0))
                    continue
                w = (t - t_lo) / (tenor - t_lo)
                base = known_dfs[t_lo] ** (1.0 - w)
                coeffs.append((payment, base, w, t))

        prev = times[-2] if len(times) > 1 else 0.0
        final_delta = tenor - prev
        final_payment = coupon_rate * final_delta + 1.0

        def f(df_T: float) -> float:
            s = const_pv + final_payment * df_T
            for amt, base, w, _ in coeffs:
                s += amt * base * (df_T**w)
            return s - 1.0

        lo, hi = 1e-12, 1.0
        f_lo, f_hi = f(lo), f(hi)
        if f_lo > 0 and f_hi > 0:
            df_T = lo
        elif f_lo < 0 and f_hi < 0:
            df_T = hi
        else:
            df_T = 0.5 * (lo + hi)
            for _ in range(120):
                fm = f(df_T)
                if abs(fm) < 1e-14:
                    break
                if f_lo * fm <= 0:
                    hi, f_hi = df_T, fm
                else:
                    lo, f_lo = df_T, fm
                df_T = 0.5 * (lo + hi)

        df_T = max(min(df_T, 1.0), 1e-12)

        for _, base, w, t in coeffs:
            df_t = base * (df_T**w)
            if t not in known_dfs:
                bisect.insort(known_times, t)
            known_dfs[t] = df_t

        if tenor not in known_dfs:
            bisect.insort(known_times, tenor)
        known_dfs[tenor] = df_T

    zero_rates = {
        tenor: -math.log(df) / tenor for tenor, df in known_dfs.items() if tenor > 0
    }
    return dict(sorted(zero_rates.items()))


class ZeroCurve:
    """Piecewise-linear zero curve with optional compounding modes."""

    def __init__(
        self,
        curve_date: date | datetime | str,
        nodes: Dict[float, float],
        *,
        comp: str = "cont",
        kind: str = "zero",
        frequency: int = 2,
    ):
        self.curve_date = _to_date(curve_date)
        self.comp = comp
        self._street_m = None
        if comp not in {"cont", "simple"}:
            if comp.startswith("street"):
                parts = comp.split(":")
                m = 2
                if len(parts) > 1:
                    try:
                        m = int(parts[1])
                    except ValueError:
                        if parts[1].startswith("m="):
                            m = int(parts[1][2:])
                        else:
                            raise ValueError(f"Invalid street comp specifier: {comp}")
                if m <= 0:
                    raise ValueError("street compounding frequency must be positive")
                self._street_m = m
                self.comp = "street"
            else:
                raise ValueError("comp must be 'cont', 'simple', or 'street'")

        self._kind = kind
        self._frequency = frequency
        if kind == "par":
            par_decimals: Dict[float, float] = {}
            for tenor, rate in nodes.items():
                value = float(rate)
                if abs(value) >= 1.0:
                    value /= 100.0
                par_decimals[float(tenor)] = value
            normalized = _bootstrap_zero_rates_from_par(par_decimals, frequency)
            self._par_nodes = dict(sorted(par_decimals.items()))
        elif kind == "zero":
            normalized = _normalize_nodes(nodes)
            self._par_nodes = None
        else:
            raise ValueError("kind must be 'zero' or 'par'")

        self._nodes = normalized
        self._tenors = list(self._nodes.keys())
        self._zeros = list(self._nodes.values())
        self._log_dfs = [
            math.log(self._df_from_zero_rate(z, t))
            for t, z in zip(self._tenors, self._zeros)
        ]

    def _df_from_zero_rate(self, zero_rate: float, tenor: float) -> float:
        if tenor <= 0:
            return 1.0
        if self.comp == "cont":
            return math.exp(-zero_rate * tenor)
        if self.comp == "simple":
            return 1.0 / (1.0 + zero_rate * tenor)
        if self.comp == "street":
            m = self._street_m or self._frequency
            return (1.0 + zero_rate / m) ** (-m * tenor)
        raise ValueError(f"Unsupported comp mode: {self.comp}")

    def zero(self, t: float) -> float:
        """Return interpolated zero rate (decimal) at tenor t."""
        if t <= 0:
            return self._zeros[0]
        df_t = self.df(t)
        if df_t <= 0:
            return self._zeros[0]
        if self.comp == "cont":
            return -math.log(df_t) / t
        if self.comp == "simple":
            return (1.0 / df_t - 1.0) / t
        if self.comp == "street":
            m = self._street_m or self._frequency
            return m * (df_t ** (-1.0 / (m * t)) - 1.0)
        raise ValueError(f"Unsupported comp mode: {self.comp}")

    def df(self, t: float) -> float:
        """Return discount factor for tenor t."""
        if t <= 0:
            return 1.0

        tenors = self._tenors
        log_dfs = self._log_dfs
        if not tenors:
            return 1.0

        if t <= tenors[0]:
            scale = t / tenors[0]
            return math.exp(log_dfs[0] * scale)
        if t >= tenors[-1]:
            scale = t / tenors[-1]
            return math.exp(log_dfs[-1] * scale)

        idx = bisect.bisect_right(tenors, t)
        t0 = tenors[idx - 1]
        t1 = tenors[idx]
        log_df0 = log_dfs[idx - 1]
        log_df1 = log_dfs[idx]
        weight = (t - t0) / (t1 - t0)
        log_df = log_df0 + weight * (log_df1 - log_df0)
        return math.exp(log_df)

    def clone_with_shifted_node(self, tenor: float, shift_bp: float) -> "ZeroCurve":
        """Return a new curve with the specified node shifted by shift_bp basis points."""
        tenor_f = float(tenor)
        shift = float(shift_bp) / 10_000.0
        frequency = self._street_m or self._frequency
        if self._kind == "par" and self._par_nodes is not None:
            par_nodes = dict(self._par_nodes)
            if tenor_f in par_nodes:
                base = par_nodes[tenor_f]
            else:
                base = _linear_interpolate(tenor_f, par_nodes)
            par_nodes[tenor_f] = base + shift
            return ZeroCurve(
                self.curve_date,
                par_nodes,
                comp=self.comp,
                kind="par",
                frequency=frequency,
            )

        nodes = dict(self._nodes)
        base = nodes.get(tenor_f, self.zero(tenor_f))
        nodes[tenor_f] = base + shift
        return ZeroCurve(
            self.curve_date,
            nodes,
            comp=self.comp,
            kind="zero",
            frequency=frequency,
        )

    @classmethod
    def from_par_yields(
        cls,
        curve_date: date | datetime | str,
        par_nodes: Dict[float, float],
        comp: str = "cont",
        frequency: int = 2,
    ) -> "ZeroCurve":
        """Construct a zero curve by bootstrapping from par-yield nodes."""
        return cls(
            curve_date,
            par_nodes,
            comp=comp,
            kind="par",
            frequency=frequency,
        )
