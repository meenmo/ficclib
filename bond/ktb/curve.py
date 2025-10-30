"""Zero curve utilities for KTB pricing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Iterable, Tuple

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


def _bootstrap_zero_rates_from_par(
    par_nodes: Dict[float, float],
    frequency: int,
) -> Dict[float, float]:
    """Bootstrap continuous zero rates (decimal) from par-yield nodes."""
    if frequency <= 0:
        raise ValueError("frequency must be positive")
    if not par_nodes:
        raise ValueError("par_nodes must not be empty")

    ytm_decimal: Dict[float, float] = {}
    for tenor, rate in par_nodes.items():
        val = float(rate)
        if abs(val) >= 1.0:
            val /= 100.0
        ytm_decimal[float(tenor)] = val
    zero_simple: Dict[float, float] = {}

    if 0.25 in ytm_decimal:
        zero_simple[0.25] = ytm_decimal[0.25]

    if 0.5 in ytm_decimal:
        c = ytm_decimal[0.5]
        zero_simple[0.5] = (1.0 + c / 2.0) ** 2 - 1.0

    tiny = 1e-9
    tenors = sorted(ytm_decimal.keys())

    for tenor in tenors:
        if tenor <= 0.5 + tiny:
            continue
        if abs((tenor / 0.5) - round(tenor / 0.5)) > 1e-9 and abs(tenor - 0.75) > 1e-9:
            continue

        coupon_rate = ytm_decimal[tenor]
        coupon_payment = coupon_rate / frequency

        known_ts = sorted(zero_simple.keys())
        if not known_ts:
            raise ValueError("Par curve bootstrap requires short-end anchors")
        t_lo = max(t for t in known_ts if t < tenor)
        df_lo = 1.0 / (1.0 + zero_simple[t_lo]) ** t_lo

        const_pv = 0.0
        coeffs: list[tuple[float, float]] = []

        periods = int((tenor - tiny) * frequency)
        for period in range(1, periods + 1):
            t = period / frequency
            if t >= tenor - tiny:
                break
            if t <= t_lo + tiny:
                z_t = zero_simple.get(t)
                if z_t is None:
                    z_t = _interpolate_simple_zero_rate(t, zero_simple)
                df_t = 1.0 / (1.0 + z_t) ** t
                const_pv += coupon_payment * df_t
            else:
                w = (t - t_lo) / (tenor - t_lo)
                K = coupon_payment * (df_lo ** (1.0 - w))
                coeffs.append((K, w))

        delta_last = tenor - (periods / frequency if periods > 0 else 0.0)
        if delta_last <= tiny:
            delta_last = 1.0 / frequency

        final_payment = coupon_payment * (delta_last * frequency) + 1.0

        def f(df_T: float) -> float:
            s = const_pv + final_payment * df_T
            for K, w in coeffs:
                s += K * (df_T**w)
            return s - 1.0

        lo, hi = 1e-12, 1.0
        f_lo, f_hi = f(lo), f(hi)
        if f_lo > 0 and f_hi > 0:
            df_T = lo
        elif f_lo < 0 and f_hi < 0:
            df_T = hi
        else:
            df_T = 0.5 * (lo + hi)
            for _ in range(80):
                fm = f(df_T)
                if abs(fm) < 1e-12:
                    break
                if f_lo * fm <= 0:
                    hi, f_hi = df_T, fm
                else:
                    lo, f_lo = df_T, fm
                df_T = 0.5 * (lo + hi)

        zero_simple[tenor] = df_T ** (-1.0 / tenor) - 1.0

    zero_cont = {
        tenor: -math.log(1.0 / (1.0 + rate) ** tenor) / tenor
        for tenor, rate in zero_simple.items()
    }
    return dict(sorted(zero_cont.items()))


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

    def zero(self, t: float) -> float:
        """Return interpolated zero rate (decimal) at tenor t."""
        if t <= 0:
            return self._zeros[0]
        idx = bisect.bisect_left(self._tenors, t)
        if idx == 0:
            return self._zeros[0]
        if idx >= len(self._tenors):
            return self._zeros[-1]
        t0 = self._tenors[idx - 1]
        t1 = self._tenors[idx]
        z0 = self._zeros[idx - 1]
        z1 = self._zeros[idx]
        weight = (t - t0) / (t1 - t0)
        return z0 + (z1 - z0) * weight

    def df(self, t: float) -> float:
        """Return discount factor for tenor t."""
        z = self.zero(t)
        if self.comp == "cont":
            return math.exp(-z * t)
        if self.comp == "simple":
            return 1.0 / (1.0 + z * t)
        if self.comp == "street":
            m = self._street_m or 2
            return (1.0 + z / m) ** (-m * t)
        raise ValueError(f"Unsupported comp mode: {self.comp}")

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
        *,
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
