"""Schedule generation for swap legs.

This module handles the generation of payment schedules for swap legs, including
date adjustments, business day conventions, and calculation of reset/fixing dates.
"""

from dataclasses import dataclass
from datetime import date

from ficclib.swap.conventions.types import Frequency
from ficclib.swap.instruments.swap import ResetPosition, SwapLegConvention
from ficclib.swap.schedule.adjustments import (
    adjust_date,
    apply_end_of_month_rule,
    is_end_of_month,
)


@dataclass
class Period:
    """Represents a single payment period in a swap schedule.

    Attributes:
        period_index: Sequential period number (1-based)
        accrual_start: Unadjusted accrual start date
        accrual_end: Unadjusted accrual end date
        accrual_start_adj: Business day adjusted accrual start
        accrual_end_adj: Business day adjusted accrual end
        reset_date: Rate reset date (None for fixed legs)
        fixing_date: Rate fixing date (None for fixed legs)
        payment_date: Payment date (adjusted with pay delay if applicable)
    """

    period_index: int
    accrual_start: date
    accrual_end: date
    accrual_start_adj: date
    accrual_end_adj: date
    reset_date: date | None
    fixing_date: date | None
    payment_date: date


def build_schedule(
    effective_date: date,
    maturity_date: date,
    convention: SwapLegConvention,
) -> list[Period]:
    """Build complete payment schedule for a swap leg.

    Generates unadjusted dates based on payment frequency, then applies:
    - Business day adjustments to accrual dates
    - Payment delays
    - Reset and fixing date logic for floating legs

    Args:
        effective_date: Swap start date
        maturity_date: Swap end date
        convention: Leg convention specifying frequencies, adjustments, and calendar

    Returns:
        List of Period objects representing the full payment schedule

    Raises:
        ValueError: If the frequency is not supported for schedule generation

    Examples:
        >>> # Build schedule for a 6M floating leg
        >>> periods = build_schedule(
        ...     effective_date=date(2025, 8, 12),
        ...     maturity_date=date(2030, 8, 12),
        ...     convention=EURIBOR_6M_FLOATING
        ... )
        >>> print(f"Number of periods: {len(periods)}")
        >>> print(f"First payment: {periods[0].payment_date}")
        Number of periods: 10
        First payment: 2026-02-12
    """
    periods: list[Period] = []
    calendar = convention.calendar_obj

    # Determine period length from payment frequency
    payment_freq = convention.pay_frequency
    period_months = _frequency_to_months(payment_freq)

    # Two generation modes:
    # - BACKWARD_EOM: build schedule backwards anchored to maturity day (SWPM-style)
    # - otherwise: build forward from effective date
    build_backward = True  # default given available RollConvention

    try:
        # Import here to avoid circular import at module load time
        from ficclib.swap.conventions.types import RollConvention

        build_backward = (
            convention.roll_convention == RollConvention.BACKWARD_EOM
        )
    except Exception:
        # Fallback to backward generation if enum not available
        build_backward = True

    # For floating legs, prefer forward generation anchored to effective date
    # to match market (SWPM) quarterly/semiannual schedules.
    from ficclib.swap.instruments.swap import LegType
    if convention.leg_type == LegType.FLOATING:
        build_backward = False

    if build_backward:
        # Build list of unadjusted period boundaries anchored to maturity DOM
        unadj_pairs: list[tuple[date, date]] = []
        current_end_unadj = maturity_date
        first_end_after_start: date | None = None

        while current_end_unadj > effective_date:
            prev_start_unadj = apply_end_of_month_rule(
                current_end_unadj, -period_months, apply_eom_rule=True
            )

            if prev_start_unadj <= effective_date:
                # If the effective date lands exactly on an anchor start, use the current end.
                # Otherwise (effective in-between anchors), step to the next regular end to avoid a tiny stub.
                if prev_start_unadj == effective_date:
                    first_end_after_start = current_end_unadj
                else:
                    first_end_after_start = apply_end_of_month_rule(
                        current_end_unadj, period_months, apply_eom_rule=True
                    )
                break

            # Regular full period between anchors
            unadj_pairs.append((prev_start_unadj, current_end_unadj))
            current_end_unadj = prev_start_unadj

        # Add the initial period starting exactly at effective_date
        if first_end_after_start is not None:
            # Remove the regular pair that would duplicate this end (e.g., [1/5, 4/5])
            try:
                prior_start = apply_end_of_month_rule(
                    first_end_after_start, -period_months, apply_eom_rule=True
                )
                unadj_pairs = [
                    (s, e) for (s, e) in unadj_pairs if not (s == prior_start and e == first_end_after_start)
                ]
            except Exception:
                pass

            unadj_pairs.append((effective_date, first_end_after_start))

        # Now create Periods from earliest to latest
        unadj_pairs.sort(key=lambda x: x[0])
        for idx, (start_unadj, end_unadj) in enumerate(unadj_pairs, start=1):
            accrual_start_adj = adjust_date(
                start_unadj,
                adjustment=convention.business_day_adjustment,
                calendar=calendar,
            )
            accrual_end_adj = adjust_date(
                end_unadj,
                adjustment=convention.business_day_adjustment,
                calendar=calendar,
            )
            if accrual_start_adj >= accrual_end_adj:
                continue

            payment_date = accrual_end_adj
            if convention.pay_delay_days > 0:
                payment_date = calendar.add_business_days(
                    payment_date, convention.pay_delay_days
                )

            reset_date, fixing_date = _calculate_reset_and_fixing_dates(
                convention=convention,
                accrual_start_adj=accrual_start_adj,
                accrual_end_adj=accrual_end_adj,
                calendar=calendar,
            )

            periods.append(
                Period(
                    period_index=idx,
                    accrual_start=start_unadj,
                    accrual_end=end_unadj,
                    accrual_start_adj=accrual_start_adj,
                    accrual_end_adj=accrual_end_adj,
                    reset_date=reset_date,
                    fixing_date=fixing_date,
                    payment_date=payment_date,
                )
            )

        return periods

    # Forward generation (fallback)
    current_start = effective_date
    preserve_eom = is_end_of_month(effective_date)
    period_idx = 1
    while current_start < maturity_date:
        # Preserve the effective date's day-of-month across periods; only keep EOM
        # behavior if the effective date itself was EOM.
        current_end = apply_end_of_month_rule(
            current_start, period_months, apply_eom_rule=preserve_eom
        )
        if current_end > maturity_date:
            current_end = maturity_date
        if current_start >= current_end:
            break

        accrual_start_adj = adjust_date(
            current_start,
            adjustment=convention.business_day_adjustment,
            calendar=calendar,
        )
        accrual_end_adj = adjust_date(
            current_end,
            adjustment=convention.business_day_adjustment,
            calendar=calendar,
        )
        if accrual_start_adj >= accrual_end_adj:
            break

        payment_date = accrual_end_adj
        if convention.pay_delay_days > 0:
            payment_date = calendar.add_business_days(
                payment_date, convention.pay_delay_days
            )

        reset_date, fixing_date = _calculate_reset_and_fixing_dates(
            convention=convention,
            accrual_start_adj=accrual_start_adj,
            accrual_end_adj=accrual_end_adj,
            calendar=calendar,
        )

        periods.append(
            Period(
                period_index=period_idx,
                accrual_start=current_start,
                accrual_end=current_end,
                accrual_start_adj=accrual_start_adj,
                accrual_end_adj=accrual_end_adj,
                reset_date=reset_date,
                fixing_date=fixing_date,
                payment_date=payment_date,
            )
        )

        current_start = current_end
        period_idx += 1

    return periods


def _calculate_reset_and_fixing_dates(
    convention: SwapLegConvention,
    accrual_start_adj: date,
    accrual_end_adj: date,
    calendar,
) -> tuple[date | None, date | None]:
    """Calculate reset and fixing dates based on leg convention.

    Args:
        convention: Leg convention
        accrual_start_adj: Adjusted accrual start date
        accrual_end_adj: Adjusted accrual end date
        calendar: Calendar for business day calculations

    Returns:
        Tuple of (reset_date, fixing_date). Both None for fixed legs.
    """
    reset_date = None
    fixing_date = None

    # Only floating legs have reset/fixing dates
    if convention.reset_frequency is None:
        return None, None

    if convention.reset_position == ResetPosition.IN_ADVANCE:
        # EURIBOR-style: Reset at start of period
        reset_date = accrual_start_adj

        # Fixing is N business days before reset (fixing lag)
        if convention.fixing_lag_days and convention.fixing_lag_days > 0:
            fixing_date = calendar.add_business_days(
                reset_date, -convention.fixing_lag_days
            )
        else:
            fixing_date = reset_date

    elif convention.reset_position == ResetPosition.IN_ARREARS:
        # ESTR-style: Reset at end of period
        reset_date = accrual_end_adj
        fixing_date = reset_date

    return reset_date, fixing_date


def _frequency_to_months(frequency: Frequency) -> int:
    """Convert payment frequency enum to number of months.

    Args:
        frequency: Payment frequency

    Returns:
        Number of months for the frequency

    Raises:
        ValueError: If frequency is not supported for swap schedules
    """
    mapping = {
        Frequency.DAILY: 0,  # Special case - handled differently in compounding
        Frequency.MONTHLY: 1,
        Frequency.QUARTERLY: 3,
        Frequency.SEMIANNUAL: 6,
        Frequency.ANNUAL: 12,
    }

    months = mapping.get(frequency)
    if months is None:
        raise ValueError(
            f"Unsupported frequency for schedule generation: {frequency}"
        )

    if months == 0 and frequency != Frequency.DAILY:
        raise ValueError(
            f"Frequency {frequency} not supported for swap schedules. "
            f"Use MONTHLY, QUARTERLY, SEMIANNUAL, or ANNUAL."
        )

    return months
