"""State management for IBOR projection curve construction."""

from __future__ import annotations

import math
from datetime import date
from typing import Dict, List

from ficclib.swap.conventions.daycount import get_day_count_convention
from ficclib.swap.curves.projection import IborProjectionCurve


class ProjectionCurveState:
    """Incrementally builds and interpolates the projection curve."""

    def __init__(self, curve_date: date, spot_date: date):
        self.curve_date = curve_date
        self.spot_date = spot_date

        self._time_dcc = get_day_count_convention("ACT/365F")
        self._pillars: Dict[date, float] = {curve_date: 1.0}
        self.front_stub_df: float | None = None
        self._sorted_dates: List[date] | None = None
        self._sorted_times: List[float] | None = None
        self._sorted_pillars: List[float] | None = None

    # ------------------------------------------------------------------
    # Pillar management
    # ------------------------------------------------------------------
    def set_front_stub(self, front_stub_df: float) -> None:
        self.front_stub_df = front_stub_df
        self._pillars[self.spot_date] = front_stub_df
        self._invalidate_cache()

    def add_pillar(self, maturity: date, px: float) -> None:
        self._pillars[maturity] = px
        self._invalidate_cache()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def px(self, target_date: date) -> float:
        if target_date in self._pillars:
            return self._pillars[target_date]

        self._ensure_sorted()
        t = self._time(target_date)

        times = self._sorted_times
        values = self._sorted_pillars

        if t <= times[0]:
            return values[0]
        if t >= times[-1]:
            return values[-1]

        for i in range(len(times) - 1):
            t1, t2 = times[i], times[i + 1]
            if t1 <= t <= t2:
                p1, p2 = values[i], values[i + 1]
                forward = math.log(p1 / p2) / (t2 - t1)
                return p1 * math.exp(-forward * (t - t1))

        return values[-1]

    def build_curve(self, index_name: str) -> IborProjectionCurve:
        self._ensure_sorted()
        times = self._sorted_times
        values = self._sorted_pillars
        return IborProjectionCurve(
            reference_date=self.curve_date,
            index_name=index_name,
            pillar_times=times,
            pseudo_discount_factors=values,
            interpolation_method="STEP_FORWARD_CONTINUOUS",
        )

    def projection_map(self) -> Dict[date, float]:
        return dict(self._pillars)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _time(self, target_date: date) -> float:
        return self._time_dcc.year_fraction(self.curve_date, target_date)

    def _ensure_sorted(self) -> None:
        if self._sorted_dates is not None:
            return
        dates = sorted(self._pillars.keys())
        times = [self._time(d) for d in dates]
        values = [self._pillars[d] for d in dates]
        self._sorted_dates = dates
        self._sorted_times = times
        self._sorted_pillars = values

    def _invalidate_cache(self) -> None:
        self._sorted_dates = None
        self._sorted_times = None
        self._sorted_pillars = None
