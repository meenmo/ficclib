"""
Custom OIS curve bootstrap engine using pure Python.

This engine provides an alternative to QuantLib's PiecewiseLogLinearDiscount
for cases where QuantLib fails (e.g., deeply negative rate environments).
It follows the same pattern as the IBOR bootstrap engine.
"""

from __future__ import annotations

import logging
import math
from datetime import date
from typing import List, Optional

from ficclib.swap.business_calendar.date_calculator import (
    get_spot_date,
)
from ficclib.swap.conventions.daycount import get_day_count_convention
from ficclib.swap.curves.discount import OISDiscountCurve

logger = logging.getLogger(__name__)


class OISInstrument:
    """Represents an OIS swap instrument for bootstrapping."""

    def __init__(self, tenor: str, rate: float, maturity_date: date):
        self.tenor = tenor
        self.rate = rate
        self.maturity_date = maturity_date

    def __repr__(self):
        return f"OISInstrument({self.tenor}, {self.rate:.6f}, {self.maturity_date})"


class CustomOISBootstrapEngine:
    """Bootstrap OIS discount curve using custom Python implementation."""

    def __init__(
        self,
        reference_date: date,
        calendar=None,
        day_count_convention: str = "ACT/360"
    ):
        """
        Initialize custom OIS bootstrap engine.

        Args:
            reference_date: Curve valuation date
            calendar: Business day calendar (optional)
            day_count_convention: Day count convention for OIS swaps
        """
        self.reference_date = reference_date
        self.spot_date = get_spot_date(reference_date)
        self.day_count = get_day_count_convention(day_count_convention)
        self.time_axis = get_day_count_convention("ACT/365F")
        self.calendar = calendar

        # Storage for bootstrapped pillars
        self.pillar_dates: List[date] = []
        self.discount_factors: List[float] = []

    def bootstrap(
        self,
        instruments: List[OISInstrument],
        interpolation_method: str = "STEP_FORWARD_CONTINUOUS"
    ) -> OISDiscountCurve:
        """
        Bootstrap OIS discount curve from instruments.

        Args:
            instruments: List of OIS instruments (sorted by maturity)
            interpolation_method: Interpolation method for final curve

        Returns:
            Bootstrapped OIS discount curve
        """
        # Sort instruments by maturity
        sorted_instruments = sorted(instruments, key=lambda x: x.maturity_date)

        logger.info(f"Bootstrapping {len(sorted_instruments)} OIS instruments")

        # Bootstrap each instrument
        for inst in sorted_instruments:
            df = self._solve_discount_factor(inst)
            self.pillar_dates.append(inst.maturity_date)
            self.discount_factors.append(df)

            logger.debug(
                f"  {inst.tenor}: maturity={inst.maturity_date}, "
                f"rate={inst.rate:.6f}, DF={df:.8f}"
            )

        # Convert to pillar times
        pillar_times = [
            self.time_axis.year_fraction(self.reference_date, d)
            for d in self.pillar_dates
        ]

        # Create discount curve
        return OISDiscountCurve(
            reference_date=self.reference_date,
            pillar_times=pillar_times,
            discount_factors=self.discount_factors,
            interpolation_method=interpolation_method,
            name="EUR-OIS-CUSTOM"
        )

    def _solve_discount_factor(self, instrument: OISInstrument) -> float:
        """
        Solve for discount factor that makes the OIS swap have zero NPV.

        For an OIS swap:
        - Fixed leg: pays fixed rate on year fraction
        - Floating leg: pays compounded overnight rate

        The par swap condition is:
            Fixed Leg PV = Floating Leg PV

        For standard OIS (annual payments):
            rate × dcf × DF(T) = 1 - DF(T)  (for < 1Y)
            rate × Σ[dcf(ti) × DF(ti)] = 1 - DF(T)  (for ≥ 1Y)

        Args:
            instrument: OIS instrument to solve for

        Returns:
            Discount factor at instrument maturity
        """
        # Check if this is a short-term instrument (< 1Y)
        is_short_term = self._is_short_term(instrument.tenor)

        if is_short_term:
            return self._solve_short_term_df(instrument)
        else:
            return self._solve_long_term_df(instrument)

    def _is_short_term(self, tenor: str) -> bool:
        """Check if tenor is less than 1 year."""
        tenor_upper = tenor.upper()
        if tenor_upper.endswith('D') or tenor_upper.endswith('W'):
            return True
        if tenor_upper.endswith('M'):
            months = int(tenor_upper[:-1])
            return months < 12
        if tenor_upper.endswith('Y'):
            years = int(tenor_upper[:-1])
            return years < 1
        return False

    def _solve_short_term_df(self, instrument: OISInstrument) -> float:
        """
        Solve for discount factor using compounded formula.

        For short-term OIS with negative rates, use exponential form:
        DF(T) = exp(-rate × dcf)

        This handles negative rates correctly.

        Args:
            instrument: Short-term OIS instrument

        Returns:
            Discount factor
        """
        dcf = self.day_count.year_fraction(
            self.spot_date,
            instrument.maturity_date
        )

        # Use exponential form for robustness with negative rates
        df = math.exp(-instrument.rate * dcf)
        return df

    def _solve_long_term_df(self, instrument: OISInstrument) -> float:
        """
        Solve for discount factor for long-term OIS swap using numerical solver.

        For an OIS swap at par:
            Fixed Leg PV = Floating Leg PV
            rate × Σ[dcf(ti) × DF(ti)] = DF(start) - DF(end)

        For spot-starting swaps: DF(start) = 1
            rate × Σ[dcf(ti) × DF(ti)] = 1 - DF(end)

        We solve for DF(end) using bisection.

        Args:
            instrument: Long-term OIS instrument

        Returns:
            Discount factor at maturity
        """
        # Generate payment schedule (annual payments for OIS)
        payment_dates = self._generate_payment_schedule(instrument)

        if not payment_dates or len(payment_dates) < 2:
            # Fallback to simple interest if no schedule
            return self._solve_short_term_df(instrument)

        # Create residual function
        def residual(df_candidate: float) -> float:
            """Calculate NPV residual for candidate DF."""
            # Add candidate to temporary state for interpolation
            temp_pillars = self.pillar_dates + [instrument.maturity_date]
            temp_dfs = self.discount_factors + [df_candidate]

            # Calculate fixed leg PV
            fixed_pv = 0.0
            for i in range(len(payment_dates) - 1):
                period_start = payment_dates[i]
                period_end = payment_dates[i + 1]

                dcf = self.day_count.year_fraction(period_start, period_end)
                df = self._interpolate_df(period_end, temp_pillars, temp_dfs)

                if df is None:
                    logger.warning(
                        f"Cannot interpolate DF for {period_end}, using 1.0"
                    )
                    df = 1.0

                coupon_pv = instrument.rate * dcf * df
                fixed_pv += coupon_pv

            # Floating leg PV = 1 - DF(maturity) for spot-starting swap
            floating_pv = 1.0 - df_candidate

            return fixed_pv - floating_pv

        # Bracket solution
        try:
            lower, upper = self._bracket_ois_solution(residual)
        except ValueError as e:
            logger.error(
                f"Failed to bracket solution for {instrument.tenor} "
                f"(maturity: {instrument.maturity_date}, rate: {instrument.rate:.6f})"
            )
            logger.error(f"Payment schedule: {payment_dates}")
            logger.error(f"Current pillars: {len(self.pillar_dates)}")
            raise

        # Bisect to find solution
        df_final = self._bisect_ois_solution(residual, lower, upper)

        if df_final <= 0.0:
            raise ValueError(
                f"Negative discount factor solved for {instrument.tenor}"
            )

        return df_final

    def _generate_payment_schedule(
        self,
        instrument: OISInstrument
    ) -> List[date]:
        """
        Generate payment schedule for OIS swap.

        For standard EUR OIS: annual payments from spot date to maturity.

        Args:
            instrument: OIS instrument

        Returns:
            List of payment dates
        """
        schedule = [self.spot_date]

        # Parse tenor to get number of years
        tenor_upper = instrument.tenor.upper()
        if tenor_upper.endswith('Y'):
            years = int(tenor_upper[:-1])
        elif tenor_upper.endswith('M'):
            months = int(tenor_upper[:-1])
            years = months // 12
        else:
            # For very short tenors, just use maturity
            return [self.spot_date, instrument.maturity_date]

        # Generate annual payment dates
        current_date = self.spot_date
        for _ in range(years):
            # Add one year
            try:
                next_date = date(
                    current_date.year + 1,
                    current_date.month,
                    current_date.day
                )
            except ValueError:
                # Handle Feb 29 in non-leap years
                next_date = date(
                    current_date.year + 1,
                    current_date.month,
                    28
                )

            schedule.append(next_date)
            current_date = next_date

        # Ensure final date is the actual maturity
        if schedule[-1] != instrument.maturity_date:
            schedule[-1] = instrument.maturity_date

        return schedule

    def _get_discount_factor(self, target_date: date) -> Optional[float]:
        """
        Get discount factor for a date from already bootstrapped pillars.

        Args:
            target_date: Date to get discount factor for

        Returns:
            Discount factor if available, None if not yet bootstrapped
        """
        if not self.pillar_dates:
            return None
        return self._interpolate_df(target_date, self.pillar_dates, self.discount_factors)

    def _interpolate_df(
        self,
        target_date: date,
        pillar_dates: List[date],
        discount_factors: List[float]
    ) -> Optional[float]:
        """
        Interpolate discount factor using log-linear interpolation on time.

        Args:
            target_date: Date to interpolate DF for
            pillar_dates: List of pillar dates
            discount_factors: List of discount factors

        Returns:
            Interpolated discount factor, or None if cannot interpolate
        """
        if not pillar_dates:
            return None

        # Check if we have this exact date
        if target_date in pillar_dates:
            idx = pillar_dates.index(target_date)
            return discount_factors[idx]

        # Check if date is before spot date
        if target_date <= self.spot_date:
            return 1.0

        # Check if date is before our first pillar
        if target_date < pillar_dates[0]:
            # Flat extrapolation from spot to first pillar
            t0 = self.time_axis.year_fraction(self.reference_date, self.spot_date)
            t1 = self.time_axis.year_fraction(self.reference_date, pillar_dates[0])
            t_target = self.time_axis.year_fraction(self.reference_date, target_date)

            if t1 <= t0:
                return 1.0

            # Log-linear interpolation
            log_df1 = math.log(discount_factors[0])
            forward_rate = -log_df1 / (t1 - t0)
            return math.exp(-forward_rate * (t_target - t0))

        # Interpolate between pillars
        for i in range(len(pillar_dates) - 1):
            if pillar_dates[i] <= target_date < pillar_dates[i + 1]:
                t1 = self.time_axis.year_fraction(self.reference_date, pillar_dates[i])
                t2 = self.time_axis.year_fraction(self.reference_date, pillar_dates[i + 1])
                t_target = self.time_axis.year_fraction(self.reference_date, target_date)

                # Log-linear interpolation on discount factors
                log_df1 = math.log(discount_factors[i])
                log_df2 = math.log(discount_factors[i + 1])

                if abs(t2 - t1) < 1e-10:
                    return discount_factors[i]

                forward_rate = (log_df1 - log_df2) / (t2 - t1)
                return discount_factors[i] * math.exp(-forward_rate * (t_target - t1))

        # Date is beyond our pillars - flat extrapolation
        if target_date >= pillar_dates[-1]:
            return discount_factors[-1]

        return None

    def _bracket_ois_solution(self, residual) -> tuple:
        """
        Bracket the root for OIS bootstrap bisection.

        Args:
            residual: Residual function to bracket

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        # Start with reasonable bounds for discount factors
        # Negative rates can cause DF > 1, so allow wider range
        lower = 0.01  # Very steep discount
        upper = 1.5   # Allow for negative rates pushing DF above 1

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
                f"Unable to bracket OIS solution: "
                f"f({lower}) = {res_lower}, f({upper}) = {res_upper}"
            )

        return lower, upper

    def _bisect_ois_solution(self, residual, lower: float, upper: float) -> float:
        """
        Find solution using bisection method.

        Args:
            residual: Residual function
            lower: Lower bound
            upper: Upper bound

        Returns:
            Solution (discount factor)
        """
        res_lower = residual(lower)

        for _ in range(100):
            mid = 0.5 * (lower + upper)
            res_mid = residual(mid)

            if abs(res_mid) < 1e-12 or abs(upper - lower) < 1e-12:
                return mid

            if res_lower * res_mid <= 0:
                upper = mid
            else:
                lower = mid
                res_lower = res_mid

        return 0.5 * (lower + upper)
