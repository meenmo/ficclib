"""Projection curve implementation for IBOR indices."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import List, Optional, Union

from ficclib.swap.conventions.daycount import get_day_count_convention
from ficclib.swap.curves.base import ProjectionCurve
from ficclib.swap.interpolation import Interpolator, create_interpolator


class IborProjectionCurve(ProjectionCurve):
    """Projection curve used to derive IBOR forward rates."""

    def __init__(
        self,
        reference_date: date,
        index_name: str,
        pillar_times: List[float],
        pseudo_discount_factors: List[float],
        interpolator: Optional[Interpolator] = None,
        interpolation_method: str = "LOGLINEAR_ZERO",
        name: str = "",
    ):
        if not name:
            name = f"{index_name}-PROJECTION"

        super().__init__(reference_date, index_name, name, time_day_count="ACT/365F")

        if len(pillar_times) != len(pseudo_discount_factors):
            raise ValueError("Pillar times and pseudo discount factors must have same length")
        if len(pillar_times) < 2:
            raise ValueError("Need at least 2 pillar points")

        for idx, pdf in enumerate(pseudo_discount_factors):
            if pdf <= 0:
                raise ValueError(f"Pseudo discount factor at pillar {idx} must be positive: {pdf}")

        self.pillar_times = pillar_times
        self.pseudo_discount_factors = pseudo_discount_factors

        if interpolator is not None:
            self.interpolator = interpolator
        else:
            method = interpolation_method.upper()
            if method in {"LINEAR_DF"}:
                self.interpolator = create_interpolator(
                    "LINEAR_DF", pillar_times, pseudo_discount_factors
                )
            elif method in {"STEP_FORWARD", "STEP_FORWARD_CONTINUOUS"}:
                self.interpolator = create_interpolator(
                    "STEP_FORWARD_CONTINUOUS", pillar_times, pseudo_discount_factors
                )
            else:
                zero_rates = [
                    -math.log(pdf) / t if t > 0 else 0.0
                    for t, pdf in zip(pillar_times, pseudo_discount_factors, strict=False)
                ]
                self.interpolator = create_interpolator(
                    interpolation_method, pillar_times, zero_rates
                )

        self.interpolation_method = interpolation_method

    def px(self, t: Union[datetime, date, float]) -> float:
        time_frac = self._to_year_fraction(t)
        if time_frac <= 0:
            return 1.0

        method = self.interpolation_method.upper()
        if method in {"LINEAR_DF", "STEP_FORWARD", "STEP_FORWARD_CONTINUOUS"}:
            return self.interpolator.interpolate(time_frac)
        zero_rate = self.interpolator.interpolate(time_frac)
        return math.exp(-zero_rate * time_frac)

    def df(self, t: Union[datetime, date, float]) -> float:
        return self.px(t)

    def zero(self, t: Union[datetime, date, float]) -> float:
        pdf = self.px(t)
        if pdf <= 0:
            raise ValueError(f"Non-positive pseudo-discount factor: {pdf}")

        if isinstance(t, (int, float)):
            _time = float(t)
        else:
            target_date = t.date() if isinstance(t, datetime) else t
            _dcc = get_day_count_convention("ACT/365F")
            _time = _dcc.year_fraction(self.reference_date, target_date)

        if _time <= 0:
            return 0.0

        return -math.log(pdf) / _time

    def forward(
        self,
        u: Union[datetime, date, float],
        v: Union[datetime, date, float],
        dcc: str,  # pragma: no cover - maintained for API parity
    ) -> float:
        date_u = self._to_date(u)
        date_v = self._to_date(v)

        dcc_365f = get_day_count_convention("ACT/365F")
        T_u = dcc_365f.year_fraction(self.reference_date, date_u)
        T_v = dcc_365f.year_fraction(self.reference_date, date_v)
        if T_v <= T_u:
            raise ValueError("Forward period must be positive")

        r_u = self.zero(date_u)
        r_v = self.zero(date_v)
        return (r_v * T_v - r_u * T_u) / (T_v - T_u)

    def get_pillar_info(self) -> List[tuple[float, float, float]]:
        info = []
        for t, pdf in zip(self.pillar_times, self.pseudo_discount_factors, strict=False):
            zero_rate = -math.log(pdf) / t if t > 0 else 0.0
            info.append((t, pdf, zero_rate))
        return info

    def shift_parallel(self, shift_bp: float) -> "IborProjectionCurve":
        shift_decimal = shift_bp / 10000.0
        shifted = []
        for t, pdf in zip(self.pillar_times, self.pseudo_discount_factors, strict=False):
            if t > 0:
                zero = -math.log(pdf) / t
                shifted.append(math.exp(-(zero + shift_decimal) * t))
            else:
                shifted.append(pdf)
        return IborProjectionCurve(
            reference_date=self.reference_date,
            index_name=self.index_name,
            pillar_times=self.pillar_times.copy(),
            pseudo_discount_factors=shifted,
            interpolation_method=self.interpolation_method,
            name=f"{self.name}_shifted_{shift_bp}bp",
        )

    def get_index_tenor(self) -> str:
        upper = self.index_name.upper()
        for tenor in ("12M", "6M", "3M", "1M"):
            if tenor in upper:
                return tenor
        return "UNKNOWN"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"IborProjectionCurve({self.index_name}, "
            f"{len(self.pillar_times)} pillars, {self.interpolation_method})"
        )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"IborProjectionCurve(reference_date={self.reference_date}, "
            f"index_name='{self.index_name}', "
            f"pillar_times={self.pillar_times}, "
            f"pseudo_discount_factors={self.pseudo_discount_factors}, "
            f"interpolation_method='{self.interpolation_method}', "
            f"name='{self.name}')"
        )

    def _to_year_fraction(self, dt: Union[datetime, date, float]) -> float:
        if isinstance(dt, (int, float)):
            return float(dt)
        if isinstance(dt, datetime):
            dt = dt.date()
        dcc = get_day_count_convention("ACT/365F")
        return dcc.year_fraction(self.reference_date, dt)

    def _to_date(self, value: Union[datetime, date, float]) -> date:
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        days = int(value * 365.25)
        return self.reference_date + timedelta(days=days)


def create_flat_ibor_curve(
    reference_date: date,
    index_name: str,
    flat_rate: float,
    max_time: float = 30.0,
    num_pillars: int = 10,
    name: str = "",
) -> IborProjectionCurve:
    times = [i * max_time / (num_pillars - 1) for i in range(num_pillars)]
    if times[0] == 0:
        times[0] = max_time / (num_pillars - 1)

    pseudo_discount_factors = [math.exp(-flat_rate * t) for t in times]

    return IborProjectionCurve(
        reference_date=reference_date,
        index_name=index_name,
        pillar_times=times,
        pseudo_discount_factors=pseudo_discount_factors,
        interpolation_method="STEP_FORWARD_CONTINUOUS",
        name=name or f"{index_name}-FLAT-{flat_rate:.4f}",
    )
