"""Numerical solvers for swap pricing problems.

This module provides solvers for finding swap parameters (like spreads) that
satisfy specific conditions, such as zero NPV or target present values.
"""

from dataclasses import replace
from datetime import date

from .types import CurveSet, SwapPV, SwapSpec


class SpreadBracketError(ValueError):
    """Raised when the provided spread bracket does not contain a solution."""

    pass


class SolverConvergenceError(RuntimeError):
    """Raised when the solver fails to converge within iteration limit."""

    pass


def solve_receive_leg_spread(
    spec: SwapSpec,
    curves: CurveSet,
    valuation_date: date,
    *,
    target: float = 0.0,
    tolerance: float = 1e-6,
    max_iterations: int = 100,
    lower_bound_bp: float = -500.0,
    upper_bound_bp: float = 500.0,
) -> tuple[float, SwapPV]:
    """Solve for the receive-leg spread that balances leg PVs.

    Uses bisection method to find the receive leg spread (in basis points) such that:
        PV(receive leg) + PV(pay leg) = target

    Typically target=0.0 to find the spread that makes the swap fair (zero NPV).

    Args:
        spec: Swap specification with initial configuration (rec_leg_spread will be overridden)
        curves: Curve set containing discounting and projection curves
        valuation_date: Valuation date (should match curve reference date)
        target: Desired sum of leg PVs (default 0.0 for zero NPV)
        tolerance: Absolute tolerance on the objective function in PV units
        max_iterations: Maximum number of bisection iterations
        lower_bound_bp: Lower bound of the spread search range (basis points)
        upper_bound_bp: Upper bound of the spread search range (basis points)

    Returns:
        Tuple of (solved_spread_bp, swap_pv_result):
            - solved_spread_bp: The spread in basis points that achieves the target
            - swap_pv_result: The SwapPV object at the solved spread

    Raises:
        SpreadBracketError: If the provided bounds don't bracket a solution
            (i.e., objective function has same sign at both bounds)
        SolverConvergenceError: If solver fails to converge within max_iterations

    Examples:
        >>> # Find the receive-leg spread for a basis swap to have zero NPV
        >>> spread_bp, result = solve_receive_leg_spread(
        ...     spec=swap_spec,
        ...     curves=curve_set,
        ...     valuation_date=date(2025, 8, 8),
        ...     tolerance=1e-3,  # 0.001 currency units
        ... )
        >>> print(f"Solved spread: {spread_bp:.6f} bp")
        >>> print(f"NPV: {result.pv_total:.2f}")
        Solved spread: -4.563583 bp
        NPV: 0.00
    """
    # Import here to avoid circular dependency
    from .pv import price_swap

    def objective(spread_bp: float) -> tuple[float, SwapPV]:
        """Objective function: leg balance minus target.

        Args:
            spread_bp: Receive leg spread in basis points

        Returns:
            Tuple of (objective_value, swap_pv_result)
        """
        spec_with_spread = replace(spec, rec_leg_spread=spread_bp)
        result = price_swap(
            spec=spec_with_spread,
            curves=curves,
            valuation_date=valuation_date,
        )
        leg_balance = result.rec_leg_pv.pv + result.pay_leg_pv.pv
        objective_value = leg_balance - target
        return objective_value, result

    # Evaluate at bounds
    lower_value, lower_result = objective(lower_bound_bp)
    upper_value, upper_result = objective(upper_bound_bp)

    # Check if we're already at solution at either bound
    if abs(lower_value) <= tolerance:
        return lower_bound_bp, lower_result
    if abs(upper_value) <= tolerance:
        return upper_bound_bp, upper_result

    # Verify bracket contains a root (opposite signs)
    if lower_value * upper_value > 0:
        raise SpreadBracketError(
            f"Spread bracket does not contain a solution. "
            f"Objective values have same sign: "
            f"f({lower_bound_bp:.2f})={lower_value:.6e}, "
            f"f({upper_bound_bp:.2f})={upper_value:.6e}. "
            f"Try widening the bracket or check if a solution exists."
        )

    # Bisection method
    for iteration in range(max_iterations):
        # Calculate midpoint
        midpoint_bp = 0.5 * (lower_bound_bp + upper_bound_bp)
        mid_value, mid_result = objective(midpoint_bp)

        # Check convergence
        if abs(mid_value) <= tolerance:
            return midpoint_bp, mid_result

        # Update bracket
        if lower_value * mid_value <= 0:
            # Root is in [lower, mid]
            upper_bound_bp = midpoint_bp
            upper_value = mid_value
        else:
            # Root is in [mid, upper]
            lower_bound_bp = midpoint_bp
            lower_value = mid_value

    # Failed to converge
    raise SolverConvergenceError(
        f"Solver failed to converge within {max_iterations} iterations. "
        f"Final bracket: [{lower_bound_bp:.6f}, {upper_bound_bp:.6f}] bp, "
        f"objective values: ({lower_value:.6e}, {upper_value:.6e}). "
        f"Consider increasing max_iterations or loosening tolerance."
    )
