"""
Factory functions and utilities for creating interpolators.
"""
import math
from typing import List

from .base import Interpolator
from .linear import (
    LinearDiscountFactorInterpolator,
    LogLinearZeroInterpolator,
    PiecewiseConstantInterpolator,
)
from .step_forward import StepForwardContinuousInterpolator


def create_interpolator(method: str,
                       pillars: List[float],
                       values: List[float]) -> Interpolator:
    """
    Create an interpolator based on method name.

    Args:
        method: Interpolation method name
        pillars: Time points
        values: Values to interpolate

    Returns:
        Configured interpolator
    """
    method_upper = method.upper()

    if method_upper == "LINEAR_DF":
        return LinearDiscountFactorInterpolator(pillars, values)
    elif method_upper == "LOGLINEAR_ZERO":
        return LogLinearZeroInterpolator(pillars, values)
    elif method_upper == "PIECEWISE_CONSTANT":
        return PiecewiseConstantInterpolator(pillars, values)
    elif method_upper in ["STEP_FORWARD", "STEP_FORWARD_CONTINUOUS"]:
        return StepForwardContinuousInterpolator(pillars, values)
    else:
        raise ValueError(f"Unknown interpolation method: {method}. "
                        f"Available: LINEAR_DF, LOGLINEAR_ZERO, MONOTONE_CONVEX, PIECEWISE_CONSTANT, STEP_FORWARD")


# Helper functions
def discount_factor_to_zero_rate(df: float, time: float) -> float:
    """Convert discount factor to continuously compounded zero rate."""
    if df <= 0:
        raise ValueError("Discount factor must be positive")
    if time <= 0:
        raise ValueError("Time must be positive")

    return -math.log(df) / time


def zero_rate_to_discount_factor(rate: float, time: float) -> float:
    """Convert zero rate to discount factor."""
    return math.exp(-rate * time)