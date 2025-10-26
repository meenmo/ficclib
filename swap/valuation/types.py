"""Data structures for swap pricing.

This module defines the core data types used throughout the swap pricing engine,
including curve containers, swap specifications, and cashflow representations.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from ficclib.swap.conventions.types import (
    BusinessDayAdjustment,
    CalendarType,
    RollConvention,
)
from ficclib.swap.curves.discount import OISDiscountCurve
from ficclib.swap.curves.projection import IborProjectionCurve
from ficclib.swap.instruments.swap import SwapLegConvention


@dataclass
class CurveSet:
    """Container for all curves needed for swap pricing.

    Attributes:
        ois_curve: OIS discount curve (ESTR for EUR)
        euribor3m_curve: EURIBOR 3M projection curve (optional)
        euribor6m_curve: EURIBOR 6M projection curve (optional)
    """

    ois_curve: OISDiscountCurve
    euribor3m_curve: IborProjectionCurve | None = None
    euribor6m_curve: IborProjectionCurve | None = None


@dataclass
class SwapSpec:
    """Complete specification for a swap instrument.

    This dataclass defines all parameters needed to price a swap, including
    both leg conventions, spreads, discounting methodology, and calendar conventions.

    Attributes:
        notional: Notional amount in currency units
        effective_date: Swap start date
        maturity_date: Swap end date
        pay_leg: Convention for the leg you pay
        rec_leg: Convention for the leg you receive
        pay_leg_spread: Spread added to pay leg rate (basis points)
        rec_leg_spread: Spread added to receive leg rate (basis points)
        discounting: Use OIS curve or each leg's projection curve for discounting
        calendar: Calendar for date adjustments
        business_day_adj: Business day adjustment convention
        roll_convention: Date roll convention
        include_principal_exchanges: Whether to include initial/final principal exchanges
    """

    notional: float
    effective_date: date
    maturity_date: date
    pay_leg: SwapLegConvention
    rec_leg: SwapLegConvention
    pay_leg_spread: float = 0.0
    rec_leg_spread: float = 0.0
    discounting: Literal["OIS", "PROJECTION"] = "OIS"
    calendar: CalendarType = CalendarType.TARGET
    business_day_adj: BusinessDayAdjustment = (
        BusinessDayAdjustment.MODIFIED_FOLLOWING
    )
    roll_convention: RollConvention = RollConvention.BACKWARD_EOM
    include_principal_exchanges: bool = False
    # When True, discount coupon cashflows from spot (effective) date to payment date
    # (presentation flag; principals account for ref->spot).
    discount_coupons_from_spot: bool = False

    # Backward‑compat alias properties (non‑breaking):
    # Some callers may still pass/read "*_spread_bp"; map them to the canonical fields.
    @property
    def pay_leg_spread_bp(self) -> float:  # pragma: no cover - compatibility shim
        return self.pay_leg_spread

    @pay_leg_spread_bp.setter
    def pay_leg_spread_bp(self, value: float) -> None:  # pragma: no cover
        self.pay_leg_spread = value

    @property
    def rec_leg_spread_bp(self) -> float:  # pragma: no cover - compatibility shim
        return self.rec_leg_spread

    @rec_leg_spread_bp.setter
    def rec_leg_spread_bp(self, value: float) -> None:  # pragma: no cover
        self.rec_leg_spread = value


@dataclass
class CouponCashflow:
    """Represents a single coupon payment in a swap leg.

    Attributes:
        idx: Period index (1-based)
        accrual_start: Accrual start date (adjusted)
        accrual_end: Accrual end date (adjusted)
        reset_date: Rate reset date (None for fixed legs)
        fixing_date: Rate fixing date (None for fixed legs)
        payment_date: Payment date
        accrual_fraction: Day count fraction for the period
        forward_rate: Forward rate for floating legs (None for fixed)
        fixed_rate: Fixed rate for fixed legs (None for floating)
        discount_factor: Discount factor at payment date
        pv: Present value of this cashflow
        notional: Notional amount for this period (default: 0 for interest-only)
        payment: Undiscounted payment amount (notional for principals, coupon for interest)
    """

    idx: int
    accrual_start: date
    accrual_end: date
    reset_date: date | None
    fixing_date: date | None
    payment_date: date
    accrual_fraction: float
    forward_rate: float | None
    fixed_rate: float | None
    discount_factor: float
    pv: float
    notional: float = 0.0
    payment: float = 0.0


@dataclass
class LegPV:
    """Present value and details for one leg of a swap.

    Attributes:
        spec: Leg convention specification
        direction: Whether this leg is PAY or RECEIVE
        pv: Total present value of the leg
        cashflows: List of individual coupon cashflows
    """

    spec: SwapLegConvention
    direction: Literal["PAY", "RECEIVE"]
    pv: float
    cashflows: list[CouponCashflow]


@dataclass
class SwapPV:
    """Complete present value breakdown for a swap.

    Attributes:
        pv_total: Net present value of the swap
        pay_leg_pv: Present value details for pay leg
        rec_leg_pv: Present value details for receive leg
    """

    pv_total: float
    pay_leg_pv: LegPV
    rec_leg_pv: LegPV
