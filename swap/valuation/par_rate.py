"""Par rate calculation for interest rate swaps.

This module calculates the fixed rate that makes a swap have zero NPV at inception,
commonly used for mark-to-market and fair value calculations.
"""

from datetime import date
from typing import Literal

from .discounting import get_discount_factor
from .forwards import calculate_forward_rate
from .schedule import build_schedule
from .types import CurveSet, SwapSpec


def calculate_par_rate(
    spec: SwapSpec,
    curves: CurveSet,
    valuation_date: date,
    fixed_leg: Literal["PAY", "RECEIVE"],
) -> float:
    """Calculate the par fixed rate that makes the swap NPV = 0.

    The par rate is the fixed rate where:
        PV(fixed leg) = PV(floating leg)

    It's calculated as:
        par_rate = PV(floating) / PV01(fixed)

    where PV01 is the present value of a 1% (or 0.01) fixed rate annuity.

    Args:
        spec: Swap specification (any fixed rate in spec will be ignored)
        curves: Container with OIS and IBOR curves
        valuation_date: Valuation date (should match curve reference date)
        fixed_leg: Which leg is the fixed leg - either "PAY" or "RECEIVE"

    Returns:
        Par fixed rate as a decimal (e.g., 0.0250 for 2.50%)

    Raises:
        ValueError: If the specified fixed leg doesn't match the conventions
            or if required curves are not available

    Examples:
        >>> par_rate = calculate_par_rate(
        ...     spec=swap_spec,
        ...     curves=curve_set,
        ...     valuation_date=date(2025, 8, 8),
        ...     fixed_leg="RECEIVE"
        ... )
        >>> print(f"Par rate: {par_rate * 100:.4f}%")
        Par rate: 2.5000%
    """
    # Identify fixed and floating legs
    if fixed_leg == "PAY":
        fixed_convention = spec.pay_leg
        floating_convention = spec.rec_leg
        floating_spread_bp = spec.rec_leg_spread
    else:  # "RECEIVE"
        fixed_convention = spec.rec_leg
        floating_convention = spec.pay_leg
        floating_spread_bp = spec.pay_leg_spread

    # Build schedules for both legs
    fixed_periods = build_schedule(
        effective_date=spec.effective_date,
        maturity_date=spec.maturity_date,
        convention=fixed_convention,
    )

    floating_periods = build_schedule(
        effective_date=spec.effective_date,
        maturity_date=spec.maturity_date,
        convention=floating_convention,
    )

    # Calculate PV01: Present value of 1 unit (not 1%) annuity on fixed leg
    # This represents the sensitivity of the fixed leg to a 1 unit change in rate
    annuity_pv = _calculate_annuity_pv(
        periods=fixed_periods,
        convention=fixed_convention,
        spec=spec,
        curves=curves,
        valuation_date=valuation_date,
    )

    # Calculate floating leg PV including any spread
    floating_pv = _calculate_floating_leg_pv(
        periods=floating_periods,
        convention=floating_convention,
        spread_bp=floating_spread_bp,
        spec=spec,
        curves=curves,
        valuation_date=valuation_date,
    )

    # Par rate: floating PV divided by the annuity PV
    par_rate = floating_pv / annuity_pv

    return par_rate


def _calculate_annuity_pv(
    periods: list,
    convention,
    spec: SwapSpec,
    curves: CurveSet,
    valuation_date: date,
) -> float:
    """Calculate the present value of a 1-unit annuity.

    This is the sum of (day count fraction × discount factor) for all periods.

    Args:
        periods: List of payment periods
        convention: Leg convention for day count
        spec: Swap specification for discounting methodology
        curves: Curve set
        valuation_date: Valuation date

    Returns:
        Annuity PV (dimensionless, represents PV of 1 unit rate)
    """
    annuity_pv = 0.0

    for period in periods:
        # Calculate day count fraction
        accrual_fraction = convention.day_count.year_fraction(
            period.accrual_start_adj, period.accrual_end_adj
        )

        # Get discount factor
        discount_factor = get_discount_factor(
            payment_date=period.payment_date,
            curves=curves,
            discounting=spec.discounting,
            leg_convention=convention,
            valuation_date=valuation_date,
        )

        # Accumulate: α_i × DF_i
        annuity_pv += accrual_fraction * discount_factor

    return annuity_pv


def _calculate_floating_leg_pv(
    periods: list,
    convention,
    spread_bp: float,
    spec: SwapSpec,
    curves: CurveSet,
    valuation_date: date,
) -> float:
    """Calculate the present value of the floating leg.

    PV = Σ (α_i × (F_i + spread) × DF_i × notional) / notional
       = Σ (α_i × (F_i + spread) × DF_i)

    where F_i is the forward rate and spread is in decimal.

    Args:
        periods: List of payment periods
        convention: Leg convention
        spread_bp: Spread in basis points
        spec: Swap specification
        curves: Curve set
        valuation_date: Valuation date

    Returns:
        Floating leg PV per unit notional (dimensionless)
    """
    spread_decimal = spread_bp * 1e-4  # Convert bp to decimal
    floating_pv = 0.0

    for period in periods:
        # Calculate forward rate for this period
        forward_rate = calculate_forward_rate(
            period, convention, curves, valuation_date
        )

        # Calculate day count fraction
        accrual_fraction = convention.day_count.year_fraction(
            period.accrual_start_adj, period.accrual_end_adj
        )

        # Get discount factor
        discount_factor = get_discount_factor(
            payment_date=period.payment_date,
            curves=curves,
            discounting=spec.discounting,
            leg_convention=convention,
            valuation_date=valuation_date,
        )

        # Accumulate: α_i × (F_i + spread) × DF_i
        floating_pv += accrual_fraction * (forward_rate + spread_decimal) * discount_factor

    return floating_pv
