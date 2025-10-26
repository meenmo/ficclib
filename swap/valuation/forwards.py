"""Forward rate calculation for different leg types.

This module calculates forward rates for both EURIBOR (simple, in advance)
and ESTR (compounded, in arrears) legs using the appropriate projection curves.
"""

from datetime import date

from ficclib.swap.business_calendar.date_calculator import add_tenor_months
from ficclib.swap.conventions.types import Frequency, RefereceRate
from ficclib.swap.curves.discount import DiscountCurve
from ficclib.swap.curves.projection import IborProjectionCurve
from ficclib.swap.instruments.swap import LegType, SwapLegConvention

from .discounting import _get_projection_curve
from .schedule import Period
from .types import CurveSet


def calculate_forward_rate(
    period: Period,
    convention: SwapLegConvention,
    curves: CurveSet,
    valuation_date: date,
) -> float:
    """Calculate forward rate for a payment period.

    This function handles both EURIBOR (simple forward, reset in advance)
    and ESTR (compounded in arrears with rate cutoff) conventions.

    Args:
        period: Payment period with accrual dates
        convention: Leg convention specifying rate type and day count
        curves: Container with available projection curves
        valuation_date: Valuation date (curve reference date)

    Returns:
        Forward rate as a decimal (e.g., 0.025 for 2.5%)

    Raises:
        ValueError: If forward rate calculation is requested for a fixed leg,
            or if the required projection curve is not available

    Examples:
        >>> forward_rate = calculate_forward_rate(
        ...     period=period,
        ...     convention=EURIBOR_6M_FLOATING,
        ...     curves=curve_set,
        ...     valuation_date=date(2025, 1, 15)
        ... )
        >>> print(f"Forward rate: {forward_rate * 100:.4f}%")
        Forward rate: 2.0830%
    """
    if convention.leg_type == LegType.FIXED:
        raise ValueError(
            "Forward rate calculation not applicable for fixed legs. "
            "Fixed legs use a predetermined fixed rate."
        )

    # Get the appropriate projection curve
    projection_curve = _get_projection_curve(convention, curves)

    # Calculate forward rate based on reference rate type
    if convention.reference_rate == RefereceRate.ESTR:
        return _calculate_estr_forward(
            period, convention, projection_curve, valuation_date
        )

    # EURIBOR 3M or 6M
    return _calculate_euribor_forward(
        period, convention, projection_curve, valuation_date
    )


def _calculate_simple_forward(
    period: Period,
    convention: SwapLegConvention,
    projection_curve: DiscountCurve | IborProjectionCurve,
) -> float:
    """Calculate simple forward rate from discount factors.

    This is the common calculation used for both EURIBOR and ESTR (approximation).

    Formula: F = (DF(start) / DF(end) - 1) / alpha

    where alpha is the day count fraction for the accrual period.

    Args:
        period: Payment period
        convention: Leg convention for day count
        projection_curve: Curve to extract discount factors from

    Returns:
        Simple forward rate as decimal
    """
    # Get discount factors at accrual boundaries
    df_start = projection_curve.df(period.accrual_start_adj)
    df_end = projection_curve.df(period.accrual_end_adj)

    # Calculate accrual fraction using leg's day count convention
    accrual_fraction = convention.day_count.year_fraction(
        period.accrual_start_adj, period.accrual_end_adj
    )

    # Simple forward rate formula
    forward_rate = (df_start / df_end - 1.0) / accrual_fraction

    return forward_rate


def _calculate_euribor_forward(
    period: Period,
    convention: SwapLegConvention,
    projection_curve: IborProjectionCurve,
    valuation_date: date,
) -> float:
    """Calculate EURIBOR forward rate (simple, reset in advance).

    EURIBOR legs use simple interest with reset at the beginning of the accrual period.
    The day count is typically ACT/360.

    Args:
        period: Payment period
        convention: Leg convention (should specify EURIBOR rate and ACT/360)
        projection_curve: IBOR projection curve (EURIBOR 3M or 6M)
        valuation_date: Valuation date

    Returns:
        EURIBOR forward rate as decimal
    """
    # For the first period, end date may shift by BDA (e.g., +1 day vs deposit tenor).
    # To better align with market practice, use the tenor end date when computing
    # the simple forward, then apply that rate over the actual accrual alpha.
    tenor_months = 6 if convention.reset_frequency == Frequency.SEMIANNUAL else 3
    # Compute tenor end from accrual start using leg conventions
    tenor_end = add_tenor_months(
        period.accrual_start_adj,
        tenor_months,
        calendar=convention.calendar_obj,
        business_day_adjustment=convention.business_day_adjustment,
        end_of_month_rule=True,
    )

    df_start = projection_curve.df(period.accrual_start_adj)
    df_end_tenor = projection_curve.df(tenor_end)
    alpha_tenor = convention.day_count.year_fraction(
        period.accrual_start_adj, tenor_end
    )
    # Use tenor-aligned forward rate (deposit-style) as the reset rate for the period.
    return (df_start / df_end_tenor - 1.0) / alpha_tenor


def _calculate_estr_forward(
    period: Period,
    convention: SwapLegConvention,
    projection_curve: DiscountCurve,
    valuation_date: date,
) -> float:
    """Calculate ESTR forward rate with daily compounding approximation.

    For ESTR legs, rates are compounded daily in arrears with a rate cutoff.
    This implementation uses a simplified approximation: a constant forward rate
    over the period derived from the discount factor ratio.

    For precise calculations with actual daily fixings and rate cutoff,
    a more sophisticated approach would be needed.

    Approximation formula: r ≈ (DF(start) / DF(end) - 1) / alpha

    where alpha uses ACT/365F (ESTR convention).

    Args:
        period: Payment period
        convention: Leg convention (should specify ESTR and ACT/365F)
        projection_curve: OIS discount curve
        valuation_date: Valuation date

    Returns:
        Approximated ESTR forward rate as decimal

    Note:
        This approximation is acceptable when daily fixing data is not available.
        For production systems with access to ESTR fixings, implement full
        daily compounding with rate cutoff.
    """
    return _calculate_simple_forward(period, convention, projection_curve)
