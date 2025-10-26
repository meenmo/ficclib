"""Discount factor calculation for swap pricing.

This module handles all discount factor lookups based on the specified
discounting methodology (OIS or projection curve).
"""

from datetime import date
from typing import Literal

from ficclib.swap.conventions.types import RefereceRate
from ficclib.swap.curves.discount import DiscountCurve
from ficclib.swap.curves.projection import IborProjectionCurve
from ficclib.swap.instruments.swap import LegType, SwapLegConvention

from .types import CurveSet


def get_discount_factor(
    payment_date: date,
    curves: CurveSet,
    discounting: Literal["OIS", "PROJECTION"],
    leg_convention: SwapLegConvention,
    valuation_date: date,
) -> float:
    """Get discount factor for a payment date.

    Args:
        payment_date: Date of the payment
        curves: Container with available curves
        discounting: Discounting methodology - either "OIS" (use OIS curve for all legs)
            or "PROJECTION" (use each leg's projection curve)
        leg_convention: Leg convention (used if discounting="PROJECTION")
        valuation_date: Valuation date for PV calculation

    Returns:
        Discount factor from valuation_date to payment_date

    Raises:
        ValueError: If required curve is not available in the curve set

    Examples:
        >>> df = get_discount_factor(
        ...     payment_date=date(2026, 1, 15),
        ...     curves=curve_set,
        ...     discounting="OIS",
        ...     leg_convention=EURIBOR_6M_FLOATING,
        ...     valuation_date=date(2025, 1, 15)
        ... )
    """
    # Determine which curve to use
    if discounting == "OIS":
        # Use OIS curve for all discounting (standard multi-curve approach)
        curve = curves.ois_curve
    elif leg_convention.leg_type == LegType.FLOATING:
        # PROJECTION discounting: use the leg's projection curve
        curve = _get_projection_curve(leg_convention, curves)
    else:
        # For fixed legs with PROJECTION discounting, fall back to OIS
        curve = curves.ois_curve

    # Get discount factor from curve reference date to payment date
    df_payment = curve.df(payment_date)

    # If valuation date differs from curve reference date, adjust the DF
    # DF(valuation -> payment) = DF(ref -> payment) / DF(ref -> valuation)
    if valuation_date != curve.reference_date:
        df_valuation = curve.df(valuation_date)
        return df_payment / df_valuation

    return df_payment


def _get_projection_curve(
    convention: SwapLegConvention,
    curves: CurveSet,
) -> DiscountCurve | IborProjectionCurve:
    """Get the appropriate projection curve for a leg convention.

    Args:
        convention: Leg convention specifying the reference rate
        curves: Container with available curves

    Returns:
        The projection curve corresponding to the reference rate

    Raises:
        ValueError: If the required curve is not available in the curve set
            or if the reference rate is not supported
    """
    ref_rate = convention.reference_rate

    if ref_rate == RefereceRate.ESTR:
        return curves.ois_curve

    if ref_rate == RefereceRate.EURIBOR3M:
        if curves.euribor3m_curve is None:
            raise ValueError(
                "EURIBOR 3M curve not available in curve set. "
                "Provide euribor3m_curve when creating CurveSet."
            )
        return curves.euribor3m_curve

    if ref_rate == RefereceRate.EURIBOR6M:
        if curves.euribor6m_curve is None:
            raise ValueError(
                "EURIBOR 6M curve not available in curve set. "
                "Provide euribor6m_curve when creating CurveSet."
            )
        return curves.euribor6m_curve

    raise ValueError(
        f"Unsupported reference rate: {ref_rate}. "
        f"Supported rates: ESTR, EURIBOR3M, EURIBOR6M"
    )
