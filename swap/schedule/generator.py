"""
Main schedule generation logic.
"""

from datetime import date, datetime
from typing import List, Optional, Union

from ficclib.swap.conventions.daycount import DayCountConvention
from ficclib.swap.conventions.types import Frequency, StubType
from ficclib.swap.instruments.swap import SwapLegConvention

from .adjustments import adjust_date, apply_end_of_month_rule, get_month_end
from .core import SchedulePeriod


class ScheduleGenerator:
    """Generates payment schedules for swaps with full stub handling."""

    def __init__(self, conventions: SwapLegConvention):
        self.conventions = conventions

    def _adjust_date(self, dt: Union[date, datetime]) -> date:
        """Adjust date using conventions."""
        return adjust_date(
            dt, self.conventions.business_day_adjustment, self.conventions.calendar_obj
        )

    def _get_end_of_month_rule(self) -> bool:
        """Get end of month rule from conventions."""
        return True  # Default end of month rule

    def generate_schedule(
        self,
        effective_date: Union[date, datetime],
        maturity_date: Union[date, datetime],
        frequency: Frequency,
        day_count: DayCountConvention,
        stub_type: StubType = StubType.SHORT_FINAL,
        roll_day: Optional[int] = None,
    ) -> List[SchedulePeriod]:
        """
        Generate a payment schedule.

        Args:
            effective_date: Start date of the swap (unadjusted)
            maturity_date: End date of the swap (unadjusted)
            frequency: Payment frequency
            day_count: Day count convention for year fractions
            stub_type: How to handle stub periods
            roll_day: Specific day of month to roll to (None = use effective date)

        Returns:
            List of schedule periods
        """
        if isinstance(effective_date, datetime):
            effective_date = effective_date.date()
        if isinstance(maturity_date, datetime):
            maturity_date = maturity_date.date()

        # Adjust key dates
        adj_effective = self._adjust_date(effective_date)
        adj_maturity = self._adjust_date(maturity_date)

        if adj_effective >= adj_maturity:
            raise ValueError("Effective date must be before maturity date")

        # Generate unadjusted schedule dates
        unadj_dates = self._generate_unadjusted_dates(
            effective_date, maturity_date, frequency, stub_type, roll_day
        )

        # Adjust all dates and create periods
        periods = []
        prev_accrual_end_unadj = None

        for i in range(len(unadj_dates) - 1):
            start_unadj = unadj_dates[i]
            end_unadj = unadj_dates[i + 1]

            # Adjust dates
            start_adj = self._adjust_date(start_unadj)
            end_adj = self._adjust_date(end_unadj)
            pay_adj = end_adj  # Payment on period end (can be customized)

            if i == 0:
                accrual_start = start_adj
            else:
                accrual_start = prev_accrual_end_adj
            accrual_end = end_adj

            # Calculate year fraction using ADJUSTED dates
            year_frac = day_count.year_fraction(accrual_start, accrual_end)

            # Determine if this is a stub period
            is_stub = self._is_stub_period(
                i, len(unadj_dates) - 1, frequency, start_unadj, end_unadj
            )

            period = SchedulePeriod(
                start_date=start_adj,
                end_date=end_adj,
                payment_date=pay_adj,
                accrual_start=accrual_start,
                accrual_end=accrual_end,
                year_fraction=year_frac,
                is_stub=is_stub,
            )

            periods.append(period)
            prev_accrual_end_adj = accrual_end  # Update for next iteration (now using adjusted)

        return periods

    def _generate_unadjusted_dates(
        self,
        effective_date: date,
        maturity_date: date,
        frequency: Frequency,
        stub_type: StubType,
        roll_day: Optional[int],
    ) -> List[date]:
        """Generate unadjusted schedule dates."""
        if stub_type == StubType.NO_STUB:
            return self._generate_no_stub_schedule(
                effective_date, maturity_date, frequency, roll_day
            )
        elif stub_type in [StubType.SHORT_FINAL, StubType.LONG_FINAL]:
            return self._generate_final_stub_schedule(
                effective_date, maturity_date, frequency, stub_type, roll_day
            )
        elif stub_type in [StubType.SHORT_INITIAL, StubType.LONG_INITIAL]:
            return self._generate_initial_stub_schedule(
                effective_date, maturity_date, frequency, stub_type, roll_day
            )
        else:
            raise ValueError(f"Unsupported stub type: {stub_type}")

    def _generate_no_stub_schedule(
        self,
        effective_date: date,
        maturity_date: date,
        frequency: Frequency,
        roll_day: Optional[int],
    ) -> List[date]:
        """Generate schedule with no stub periods (exact fit required)."""
        dates = [effective_date]
        current = effective_date

        while current < maturity_date:
            next_date = self._add_period(current, frequency, roll_day)
            if next_date > maturity_date:
                # This would create a stub, which is not allowed
                raise ValueError("Cannot create no-stub schedule - dates don't align")
            dates.append(next_date)
            current = next_date

        if current != maturity_date:
            raise ValueError("Cannot create no-stub schedule - dates don't align")

        return dates

    def _generate_final_stub_schedule(
        self,
        effective_date: date,
        maturity_date: date,
        frequency: Frequency,
        stub_type: StubType,
        roll_day: Optional[int],
    ) -> List[date]:
        """Generate schedule with final stub."""
        dates = [effective_date]
        current = effective_date

        # Generate regular periods from start
        while True:
            next_date = self._add_period(current, frequency, roll_day)

            if stub_type == StubType.SHORT_FINAL:
                # Continue adding regular periods until the next period would overshoot maturity
                if next_date >= maturity_date:
                    # Exact hit -> include maturity, otherwise short stub to maturity
                    if next_date == maturity_date:
                        dates.append(next_date)
                    else:
                        dates.append(maturity_date)
                    break
                dates.append(next_date)
                current = next_date

            elif stub_type == StubType.LONG_FINAL:
                following_date = self._add_period(next_date, frequency, roll_day)
                # For a long final stub, skip the penultimate date if it would create a short stub
                if following_date > maturity_date:
                    dates.append(maturity_date)
                    break
                dates.append(next_date)
                current = next_date

        return dates

    def _generate_initial_stub_schedule(
        self,
        effective_date: date,
        maturity_date: date,
        frequency: Frequency,
        stub_type: StubType,
        roll_day: Optional[int],
    ) -> List[date]:
        """Generate schedule with initial stub."""
        # Work backwards from maturity to determine regular schedule
        regular_dates = []
        current = maturity_date

        # Generate regular periods backwards
        while current > effective_date:
            prev_date = self._subtract_period(current, frequency, roll_day)
            if prev_date <= effective_date:
                break
            regular_dates.insert(0, prev_date)
            current = prev_date

        # Now decide on initial stub
        if regular_dates:
            first_regular = regular_dates[0]

            if stub_type == StubType.SHORT_INITIAL:
                # Use effective date as start, first regular date as first period end
                dates = [effective_date] + regular_dates + [maturity_date]

            elif stub_type == StubType.LONG_INITIAL:
                # Skip first regular date if stub would be too short
                prev_prev = self._subtract_period(first_regular, frequency, roll_day)
                if prev_prev <= effective_date:
                    # Remove first regular date to create long stub
                    dates = [effective_date] + regular_dates[1:] + [maturity_date]
                else:
                    dates = [effective_date] + regular_dates + [maturity_date]
        else:
            # Only one period
            dates = [effective_date, maturity_date]

        return dates

    def _add_period(
        self,
        start_date: date,
        frequency: Frequency,
        roll_day: Optional[int],
        subtract: bool = False,
    ) -> date:
        """Add or subtract one period to/from a date."""
        months_delta = frequency.months() * (-1 if subtract else 1)

        if roll_day is not None:
            # Roll to specific day of month
            result_month = start_date.month + months_delta
            result_year = start_date.year

            while result_month > 12:
                result_month -= 12
                result_year += 1
            while result_month < 1:
                result_month += 12
                result_year -= 1

            try:
                return date(result_year, result_month, roll_day)
            except ValueError:
                # Day doesn't exist in target month, use month end
                return self._get_month_end(result_year, result_month)
        else:
            # Use end-of-month rule
            return apply_end_of_month_rule(
                start_date, months_delta, self._get_end_of_month_rule()
            )

    def _subtract_period(
        self, start_date: date, frequency: Frequency, roll_day: Optional[int]
    ) -> date:
        """Subtract one period from a date."""
        return self._add_period(start_date, frequency, roll_day, subtract=True)

    def _get_month_end(self, year: int, month: int) -> date:
        """Get last day of month."""
        return get_month_end(year, month)

    def _is_stub_period(
        self,
        period_index: int,
        total_periods: int,
        frequency: Frequency,
        start_date: date,
        end_date: date,
    ) -> bool:
        """Determine if a period is a stub."""
        # Calculate expected period length
        expected_months = frequency.months()

        # Calculate actual period length in months (approximate)
        actual_months = (
            (end_date.year - start_date.year) * 12 + end_date.month - start_date.month
        )

        # Allow some tolerance for month-end adjustments
        tolerance = 0.1
        return abs(actual_months - expected_months) > tolerance
