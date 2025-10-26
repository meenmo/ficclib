"""Main swap pricing engine.

This module provides the core swap pricing functionality, calculating present values
for individual legs and complete swaps with full cashflow breakdowns.
"""

from datetime import date
from typing import Literal

from ficclib.swap.instruments.swap import LegType, SwapLegConvention

from .discounting import get_discount_factor
from .forwards import calculate_forward_rate
from .schedule import build_schedule
from .types import CouponCashflow, CurveSet, LegPV, SwapPV, SwapSpec


def price_swap(
    spec: SwapSpec,
    curves: CurveSet,
    valuation_date: date,
) -> SwapPV:
    """Price a swap and return complete cashflow breakdown.

    This is the main entry point for pricing swaps. It prices both legs separately
    and combines them to produce the total NPV along with detailed cashflow information.

    Args:
        spec: Complete swap specification including legs, spreads, and conventions
        curves: Curve set containing OIS and any required IBOR curves
        valuation_date: Valuation date (should match curve reference date)

    Returns:
        SwapPV object containing:
            - Total NPV of the swap
            - Detailed breakdown of pay leg (PV and cashflows)
            - Detailed breakdown of receive leg (PV and cashflows)

    Raises:
        ValueError: If required curves are not available or if conventions are invalid

    Examples:
        >>> # Price a 3M vs 6M basis swap
        >>> result = price_swap(
        ...     spec=swap_spec,
        ...     curves=curve_set,
        ...     valuation_date=date(2025, 8, 8)
        ... )
        >>> print(f"Total NPV: EUR {result.pv_total:,.2f}")
        >>> print(f"Pay leg (6M): EUR {result.pay_leg_pv.pv:,.2f}")
        >>> print(f"Receive leg (3M): EUR {result.rec_leg_pv.pv:,.2f}")
        Total NPV: EUR -343,601.60
        Pay leg (6M): EUR -11,042,319.95
        Receive leg (3M): EUR 10,698,718.35
    """
    # Price each leg separately
    # When include_principal_exchanges is True, include principals in leg PVs
    pay_leg_pv = price_leg(
        spec=spec,
        leg_convention=spec.pay_leg,
        curves=curves,
        valuation_date=valuation_date,
        direction="PAY",
        spread_bp=spec.pay_leg_spread,
        include_principals=spec.include_principal_exchanges,
    )

    rec_leg_pv = price_leg(
        spec=spec,
        leg_convention=spec.rec_leg,
        curves=curves,
        valuation_date=valuation_date,
        direction="RECEIVE",
        spread_bp=spec.rec_leg_spread,
        include_principals=spec.include_principal_exchanges,
    )

    # Calculate total NPV (sum of leg PVs)
    # Note: When include_principal_exchanges is True, principals are already in leg PVs
    # When False, principals are not included (as before)
    pv_total = rec_leg_pv.pv + pay_leg_pv.pv

    return SwapPV(
        pv_total=pv_total,
        pay_leg_pv=pay_leg_pv,
        rec_leg_pv=rec_leg_pv,
    )


def price_leg(
    spec: SwapSpec,
    leg_convention: SwapLegConvention,
    curves: CurveSet,
    valuation_date: date,
    direction: Literal["PAY", "RECEIVE"],
    spread_bp: float = 0.0,
    include_principals: bool = False,
) -> LegPV:
    """Price a single swap leg with full cashflow details.

    Args:
        spec: Swap specification for notional and discounting methodology
        leg_convention: Convention defining this leg's characteristics
        curves: Curve set for forward rates and discounting
        valuation_date: Valuation date for PV calculation
        direction: Whether this leg is PAY (negative PV) or RECEIVE (positive PV)
        spread_bp: Spread to add to floating rates, in basis points
        include_principals: Whether to include principal exchanges in leg PV

    Returns:
        LegPV object containing total PV and list of individual cashflows

    Raises:
        ValueError: If required curves are not available or conventions are invalid

    Examples:
        >>> # Price a floating leg
        >>> leg_pv = price_leg(
        ...     spec=swap_spec,
        ...     leg_convention=EURIBOR_6M_FLOATING,
        ...     curves=curve_set,
        ...     valuation_date=date(2025, 8, 8),
        ...     direction="PAY",
        ...     spread_bp=0.0
        ... )
        >>> print(f"Leg PV: EUR {leg_pv.pv:,.2f}")
        >>> print(f"Number of cashflows: {len(leg_pv.cashflows)}")
        Leg PV: EUR -11,042,319.95
        Number of cashflows: 10
    """
    # Build payment schedule
    periods = build_schedule(
        effective_date=spec.effective_date,
        maturity_date=spec.maturity_date,
        convention=leg_convention,
    )

    # Convert spread from basis points to decimal
    spread_decimal = spread_bp * 1e-4

    # Calculate cashflows for each period
    cashflows = []

    # Add initial principal exchange if requested and not in the past
    if include_principals and spec.effective_date >= valuation_date:
        initial_principal_cf = _price_principal_cashflow(
            payment_date=spec.effective_date,
            spec=spec,
            leg_convention=leg_convention,
            curves=curves,
            valuation_date=valuation_date,
            direction=direction,
            is_initial=True,
        )
        cashflows.append(initial_principal_cf)

    # Add coupon cashflows (only future cashflows)
    for period in periods:
        # Skip cashflows that have already occurred
        if period.payment_date < valuation_date:
            continue

        cashflow = _price_coupon(
            period=period,
            convention=leg_convention,
            spec=spec,
            curves=curves,
            valuation_date=valuation_date,
            direction=direction,
            spread_decimal=spread_decimal,
        )
        cashflows.append(cashflow)

    # Add final principal exchange if requested and not in the past
    if include_principals and spec.maturity_date >= valuation_date:
        final_principal_cf = _price_principal_cashflow(
            payment_date=spec.maturity_date,
            spec=spec,
            leg_convention=leg_convention,
            curves=curves,
            valuation_date=valuation_date,
            direction=direction,
            is_initial=False,
        )
        cashflows.append(final_principal_cf)

    # Sum up leg PV
    leg_pv = sum(cf.pv for cf in cashflows)

    return LegPV(
        spec=leg_convention,
        direction=direction,
        pv=leg_pv,
        cashflows=cashflows,
    )


def _price_coupon(
    period,
    convention: SwapLegConvention,
    spec: SwapSpec,
    curves: CurveSet,
    valuation_date: date,
    direction: Literal["PAY", "RECEIVE"],
    spread_decimal: float,
) -> CouponCashflow:
    """Price a single coupon payment.

    Args:
        period: Payment period from schedule
        convention: Leg convention
        spec: Swap specification
        curves: Curve set
        valuation_date: Valuation date
        direction: PAY or RECEIVE
        spread_decimal: Spread as decimal (not bp)

    Returns:
        CouponCashflow with all details
    """
    # Calculate accrual fraction
    accrual_fraction = convention.day_count.year_fraction(
        period.accrual_start_adj, period.accrual_end_adj
    )

    # Determine rate (forward or fixed)
    forward_rate = None
    fixed_rate = None
    effective_rate = 0.0

    if convention.leg_type == LegType.FLOATING:
        # Calculate forward rate from projection curve
        forward_rate = calculate_forward_rate(
            period, convention, curves, valuation_date
        )
        effective_rate = forward_rate + spread_decimal
    else:
        # Fixed leg - rate should be specified externally
        # For now, use 0.0 as placeholder (caller should set via spread or convention)
        fixed_rate = 0.0
        effective_rate = fixed_rate

    # Get discount factor for payment date. If spot-base presentation is enabled,
    # convert DF(ref->pay) to DF(spot->pay) by dividing by DF(ref->spot).
    discount_factor = get_discount_factor(
        payment_date=period.payment_date,
        curves=curves,
        discounting=spec.discounting,
        leg_convention=convention,
        valuation_date=valuation_date,
    )
    if (
        getattr(spec, "discount_coupons_from_spot", False)
        and spec.include_principal_exchanges
        and period.payment_date >= spec.effective_date
    ):
        df_spot = get_discount_factor(
            payment_date=spec.effective_date,
            curves=curves,
            discounting=spec.discounting,
            leg_convention=convention,
            valuation_date=valuation_date,
        )
        if df_spot != 0.0:
            discount_factor = discount_factor / df_spot

    # Calculate PV with appropriate sign convention
    # PAY leg is negative, RECEIVE leg is positive
    sign = -1.0 if direction == "PAY" else 1.0
    coupon_payment = sign * spec.notional * accrual_fraction * effective_rate
    coupon_pv = coupon_payment * discount_factor

    return CouponCashflow(
        idx=period.period_index,
        accrual_start=period.accrual_start_adj,
        accrual_end=period.accrual_end_adj,
        reset_date=period.reset_date,
        fixing_date=period.fixing_date,
        payment_date=period.payment_date,
        accrual_fraction=accrual_fraction,
        forward_rate=forward_rate,
        fixed_rate=fixed_rate,
        discount_factor=discount_factor,
        pv=coupon_pv,
        notional=spec.notional,
        payment=coupon_payment,
    )


def _price_principal_cashflow(
    payment_date: date,
    spec: SwapSpec,
    leg_convention: SwapLegConvention,
    curves: CurveSet,
    valuation_date: date,
    direction: Literal["PAY", "RECEIVE"],
    is_initial: bool,
) -> CouponCashflow:
    """Price a principal exchange cashflow.

    Args:
        payment_date: When the principal is exchanged
        spec: Swap specification
        leg_convention: Leg convention (for discount curve selection)
        curves: Curve set
        valuation_date: Valuation date
        direction: PAY or RECEIVE
        is_initial: True for initial exchange, False for final

    Returns:
        CouponCashflow representing the principal exchange
    """
    # Get discount factor for payment date
    discount_factor = get_discount_factor(
        payment_date=payment_date,
        curves=curves,
        discounting=spec.discounting,
        leg_convention=leg_convention,
        valuation_date=valuation_date,
    )

    # Sign convention for principal exchanges:
    # Initial exchange: RECEIVE leg receives notional (+N), PAY leg pays notional (-N)
    # Final exchange: RECEIVE leg pays back notional (-N), PAY leg receives back notional (+N)
    if is_initial:
        # Align with SWPM: RECEIVE leg posts notional at start (-N), PAY leg receives (+N)
        sign = -1.0 if direction == "RECEIVE" else 1.0
    else:
        # At maturity: RECEIVE leg receives back notional (+N), PAY leg pays back (-N)
        sign = 1.0 if direction == "RECEIVE" else -1.0

    principal_payment = sign * spec.notional
    principal_pv = principal_payment * discount_factor

    # Return as CouponCashflow with special marker (idx=0 for initial, idx=-1 for final)
    return CouponCashflow(
        idx=0 if is_initial else -1,
        accrual_start=payment_date,
        accrual_end=payment_date,
        reset_date=None,
        fixing_date=None,
        payment_date=payment_date,
        accrual_fraction=0.0,
        forward_rate=None,
        fixed_rate=None,
        discount_factor=discount_factor,
        pv=principal_pv,
        notional=spec.notional,
        payment=principal_payment,
    )
