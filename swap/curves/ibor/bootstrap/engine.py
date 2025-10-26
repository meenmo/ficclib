"""Numerical engine for IBOR curve bootstrapping."""

from __future__ import annotations

import math
from datetime import date
from typing import Dict, Iterable, List

from ficclib.swap.business_calendar.date_calculator import get_spot_date
from ficclib.swap.conventions.daycount import get_day_count_convention
from ficclib.swap.curves.discount import OISDiscountCurve
from ficclib.swap.curves.projection import IborProjectionCurve

from .instruments import DepositInstrument, SwapInstrument
from .results import BootstrapResult
from .state import ProjectionCurveState


class BootstrapEngine:
    """Implements the dual-curve IBOR bootstrap."""

    def __init__(self, curve_date: date, ois_curve: OISDiscountCurve, index_name: str):
        self.curve_date = curve_date
        self.spot_date = get_spot_date(curve_date)
        self.ois_curve = ois_curve
        self.index_name = index_name

        self.state = ProjectionCurveState(curve_date, self.spot_date)
        self._results: List[BootstrapResult] = []

        self._zero_dcc = get_day_count_convention("ACT/365F")
        self._time_axis = get_day_count_convention("ACT/365F")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def bootstrap_deposits(self, deposits: Iterable[DepositInstrument]) -> None:
        deposits = sorted(deposits, key=lambda d: d.get_maturity())
        deposits = list(deposits)
        if not deposits:
            self.state.set_front_stub(1.0)
            return

        first = deposits[0]
        front_stub_df = self._compute_front_stub(first)
        self.state.set_front_stub(front_stub_df)

        for deposit in deposits:
            px = self._deposit_pseudo_df(deposit, front_stub_df)
            self.state.add_pillar(deposit.get_maturity(), px)
            self._results.append(
                self._result_entry(deposit.get_tenor(), deposit.get_maturity(), px)
            )

    def bootstrap_swap(self, swap: SwapInstrument) -> None:
        """Bootstrap a single swap instrument."""
        periods = swap.floating_periods()
        if not periods:
            raise ValueError(
                f"Floating schedule unavailable for tenor {swap.get_tenor()}"
            )

        # Setup bootstrap context
        context = self._setup_swap_context(swap, periods)

        # Solve for final pseudo-discount factor
        px_end = self._solve_for_pseudo_df(swap, periods, context)

        # Finalize bootstrap
        self._finalize_swap_bootstrap(swap, periods, px_end, context)

    def get_curve(self) -> IborProjectionCurve:
        return self.state.build_curve(self.index_name)

    def get_results(self) -> List[BootstrapResult]:
        return sorted(self._results, key=lambda r: r.maturity)

    def get_projection_map(self) -> Dict[date, float]:
        return self.state.projection_map()

    # ------------------------------------------------------------------
    # Swap bootstrap helpers
    # ------------------------------------------------------------------
    def _setup_swap_context(self, swap: SwapInstrument, periods: List) -> Dict:
        """Setup context for swap bootstrap."""
        fixed_pv = self._fixed_leg_pv(swap)
        projection_map = self.state.projection_map()
        final_end = periods[-1].accrual_end

        prev_anchor_date = self._get_prev_anchor(projection_map, final_end)

        return {
            'fixed_pv': fixed_pv,
            'projection_map': projection_map,
            'final_end': final_end,
            'prev_anchor_date': prev_anchor_date,
            'known_dates_sorted': sorted(projection_map.keys()),
            't_prev': self._time_axis.year_fraction(self.curve_date, prev_anchor_date),
            't_final': self._time_axis.year_fraction(self.curve_date, final_end),
            'px_prev': projection_map[prev_anchor_date],
        }

    def _get_prev_anchor(self, projection_map: Dict, final_end: date) -> date:
        """Get previous anchor date before final maturity."""
        try:
            return max(d for d in projection_map if d < final_end)
        except ValueError as exc:
            raise ValueError(
                f"No anchor pillar available before {final_end}"
            ) from exc

    def _solve_for_pseudo_df(
        self,
        swap: SwapInstrument,
        periods: List,
        context: Dict
    ) -> float:
        """Solve for pseudo-discount factor using root finding."""
        # Create residual function
        residual = self._create_residual_function(periods, context)

        # Bracket solution
        lower, upper = self._bracket_solution(swap, residual, context['px_prev'])

        # Bisect to find solution
        px_end = self._bisect_solution(residual, lower, upper)

        if px_end <= 0.0:
            raise ValueError(
                f"Negative pseudo-discount factor solved for {swap.get_tenor()}"
            )

        return px_end

    def _create_residual_function(self, periods: List, context: Dict):
        """Create residual function for root finding."""
        def residual(px_final: float) -> float:
            pv_float = self._calculate_floating_pv(periods, px_final, context)
            return context['fixed_pv'] - pv_float
        return residual

    def _calculate_floating_pv(
        self,
        periods: List,
        px_final: float,
        context: Dict
    ) -> float:
        """Calculate floating leg PV for given final pseudo-DF."""
        log_candidate = math.log(px_final)
        contributions = []

        for period in periods:
            px_start = self._project_df(
                period.accrual_start, px_final, log_candidate, context
            )
            px_end = self._project_df(
                period.accrual_end, px_final, log_candidate, context
            )
            forward = (px_start / px_end - 1.0) / period.year_fraction
            df = self._ois_df(period.accrual_end)
            contributions.append(period.year_fraction * forward * df)

        return math.fsum(contributions)

    def _project_df(
        self,
        target_date: date,
        candidate_px: float,
        log_candidate: float,
        context: Dict
    ) -> float:
        """Project pseudo-discount factor to target date."""
        projection_map = context['projection_map']
        prev_anchor_date = context['prev_anchor_date']

        if target_date in projection_map and target_date <= prev_anchor_date:
            return projection_map[target_date]

        t_target = self._time_axis.year_fraction(self.curve_date, target_date)
        t_prev = context['t_prev']
        t_final = context['t_final']

        if t_target <= t_prev:
            return self._interpolate_existing(target_date, context)
        if t_target >= t_final:
            return candidate_px

        # Step-forward interpolation between prev_anchor and final
        px_prev = context['px_prev']
        log_px_prev = math.log(px_prev)
        forward_rate = (log_px_prev - log_candidate) / (t_final - t_prev)
        return px_prev * math.exp(-forward_rate * (t_target - t_prev))

    def _interpolate_existing(self, target_date: date, context: Dict) -> float:
        """Interpolate using existing pillars."""
        projection_map = context['projection_map']
        known_dates_sorted = context['known_dates_sorted']

        if target_date in projection_map:
            return projection_map[target_date]

        times = [
            self._time_axis.year_fraction(self.curve_date, d)
            for d in known_dates_sorted
        ]
        t_target = self._time_axis.year_fraction(self.curve_date, target_date)

        if t_target <= times[0]:
            return projection_map[known_dates_sorted[0]]
        if t_target >= times[-1]:
            return projection_map[known_dates_sorted[-1]]

        return self._step_forward_interpolate(
            t_target, times, known_dates_sorted, projection_map
        )

    def _step_forward_interpolate(
        self,
        t_target: float,
        times: List[float],
        dates: List[date],
        projection_map: Dict
    ) -> float:
        """Perform step-forward interpolation."""
        for idx in range(len(times) - 1):
            t1, t2 = times[idx], times[idx + 1]
            if t1 <= t_target <= t2:
                df1 = projection_map[dates[idx]]
                df2 = projection_map[dates[idx + 1]]
                forward_rate = math.log(df1 / df2) / (t2 - t1)
                return df1 * math.exp(-forward_rate * (t_target - t1))

        return projection_map[dates[-1]]

    def _bracket_solution(
        self,
        swap: SwapInstrument,
        residual,
        px_prev: float
    ) -> tuple:
        """Bracket the root for bisection."""
        # Handle both positive and negative rates
        # For negative rates, pseudo-DF can be > 1.0
        lower = min(px_prev * 0.1, 0.01)
        upper = max(px_prev * 1.5, 1.5)  # Allow for negative rates
        res_lower = residual(lower)
        res_upper = residual(upper)

        attempts = 0
        while res_lower * res_upper > 0 and attempts < 20:
            if abs(res_lower) < abs(res_upper):
                lower *= 0.5
                res_lower = residual(lower)
            else:
                upper *= 1.2
                res_upper = residual(upper)
            attempts += 1

        if res_lower * res_upper > 0:
            raise ValueError(
                f"Unable to bracket solution for tenor {swap.get_tenor()}: "
                f"f({lower}) = {res_lower}, f({upper}) = {res_upper}"
            )

        return lower, upper

    def _bisect_solution(self, residual, lower: float, upper: float) -> float:
        """Find solution using bisection method."""
        res_lower = residual(lower)

        for _ in range(100):
            mid = 0.5 * (lower + upper)
            res_mid = residual(mid)

            if abs(res_mid) < 1e-14 or abs(upper - lower) < 1e-14:
                return mid

            if res_lower * res_mid <= 0:
                upper = mid
            else:
                lower = mid
                res_lower = res_mid

        return 0.5 * (lower + upper)

    def _finalize_swap_bootstrap(
        self,
        swap: SwapInstrument,
        periods: List,
        px_end: float,
        context: Dict
    ) -> None:
        """Finalize swap bootstrap by updating projection map and pillars."""
        projection_map = context['projection_map']
        log_px_end = math.log(px_end)

        # Update projection_map with all intermediate dates
        for period in periods:
            end = period.accrual_end
            df_val = self._project_df(end, px_end, log_px_end, context)
            projection_map[end] = df_val

        # Only add final maturity as pillar
        final_end = periods[-1].accrual_end
        self.state.add_pillar(final_end, px_end)

        self._results.append(
            self._result_entry(swap.get_tenor(), swap.get_maturity(), px_end)
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _compute_front_stub(self, deposit: DepositInstrument) -> float:
        # Use simple money-market convention: set spot pseudo-DF to 1.0, and
        # map the deposit quote entirely into the [spot, maturity] interval.
        # This aligns the front-stub projection with common market practice and
        # improves near-front forward alignment.
        return 1.0

    def _deposit_pseudo_df(
        self, deposit: DepositInstrument, front_stub_df: float
    ) -> float:
        return front_stub_df / (1.0 + deposit.rate * deposit.accrual_fraction())

    def _fixed_leg_pv(self, swap: SwapInstrument) -> float:
        contributions = [
            swap.fixed_rate * alpha * self._ois_df(end)
            for _, end, alpha in swap.fixed_cashflows()
        ]
        return math.fsum(contributions)

    def _ois_df(self, target_date: date) -> float:
        time_frac = self._zero_dcc.year_fraction(self.curve_date, target_date)
        return self.ois_curve.df(time_frac)

    def _result_entry(self, tenor: str, maturity: date, px: float) -> BootstrapResult:
        time_axis = self._time_axis.year_fraction(self.curve_date, maturity)
        zero_cc = self._zero_dcc.year_fraction(self.curve_date, maturity)
        zero_cc = -math.log(px) / zero_cc if zero_cc > 0 else 0.0
        return BootstrapResult(
            tenor=tenor,
            maturity=maturity,
            time_act360=time_axis,
            discount_factor=px,
            zero_rate=zero_cc,
        )
