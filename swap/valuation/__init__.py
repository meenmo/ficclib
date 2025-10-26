"""Swap valuation engine.

This package provides a complete swap valuation solution including:
- Multi-curve pricing with OIS discounting and IBOR projection
- Forward rate calculation for EURIBOR and ESTR legs
- Par rate calculation
- Spread solving for basis swaps
- Full cashflow breakdown
"""

# Core types
# Discounting (useful for advanced users)
from .discounting import get_discount_factor

# Forward rate calculation (useful for advanced users)
from .forwards import calculate_forward_rate

# Par rate calculation
from .par_rate import calculate_par_rate

# Main pricing functions
from .pv import price_leg, price_swap

# Schedule generation (useful for advanced users)
from .schedule import Period, build_schedule

# Spread solver
from .solver import (
    SolverConvergenceError,
    SpreadBracketError,
    solve_receive_leg_spread,
)
from .types import (
    CouponCashflow,
    CurveSet,
    LegPV,
    SwapPV,
    SwapSpec,
)

__all__ = [
    # Types
    "CurveSet",
    "SwapSpec",
    "CouponCashflow",
    "LegPV",
    "SwapPV",
    "Period",
    # Main functions
    "price_swap",
    "price_leg",
    "calculate_par_rate",
    "solve_receive_leg_spread",
    # Exceptions
    "SpreadBracketError",
    "SolverConvergenceError",
    # Advanced functions
    "build_schedule",
    "calculate_forward_rate",
    "get_discount_factor",
]
