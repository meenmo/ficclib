"""
Helper functions for curve calculations and conversions.
"""

import math
from typing import List


def df_to_zero_rate(df: float, time: float) -> float:
    """Convert discount factor to continuously compounded zero rate."""
    if df <= 0:
        raise ValueError("Discount factor must be positive")
    if time <= 0:
        raise ValueError("Time must be positive")

    return -math.log(df) / time


def zero_rate_to_df(rate: float, time: float) -> float:
    """Convert zero rate to discount factor."""
    return math.exp(-rate * time)


def simple_to_continuous(rate: float, time: float) -> float:
    """Convert simple rate to continuously compounded rate."""
    if time <= 0:
        return rate
    return math.log(1 + rate * time) / time


def continuous_to_simple(rate: float, time: float) -> float:
    """Convert continuously compounded rate to simple rate."""
    if time <= 0:
        return rate
    return (math.exp(rate * time) - 1) / time


def compound_frequency_convert(rate: float, from_freq: int, to_freq: int) -> float:
    """
    Convert rate between different compounding frequencies.

    Args:
        rate: Input rate
        from_freq: Original compounding frequency (0=continuous, 1=annual, 2=semi, etc.)
        to_freq: Target compounding frequency (0=continuous, 1=annual, 2=semi, etc.)

    Returns:
        Converted rate
    """
    if from_freq == to_freq:
        return rate

    # Convert to effective annual rate first
    if from_freq == 0:  # Continuous
        effective_annual = math.exp(rate) - 1
    else:
        effective_annual = (1 + rate / from_freq) ** from_freq - 1

    # Convert from effective annual to target frequency
    if to_freq == 0:  # Continuous
        return math.log(1 + effective_annual)
    else:
        return to_freq * ((1 + effective_annual) ** (1 / to_freq) - 1)


def calculate_dv01(curve, time: float, shift_bp: float = 1.0) -> float:
    """
    Calculate DV01 (dollar value of 01) for a curve at a specific time.

    Args:
        curve: Curve object with df() method
        time: Time point to calculate DV01
        shift_bp: Size of parallel shift in basis points

    Returns:
        DV01 value (change in PV for 1bp shift)
    """
    shift_decimal = shift_bp / 10000.0

    # Get base discount factor
    df_base = curve.df(time)

    # Create shifted curve (simplified - assumes we can shift zero rates)
    zero_base = df_to_zero_rate(df_base, time)
    zero_shifted = zero_base + shift_decimal
    df_shifted = zero_rate_to_df(zero_shifted, time)

    # DV01 is change in discount factor per basis point
    return (df_shifted - df_base) / shift_bp


def bootstrap_discount_factors(
    times: List[float], zero_rates: List[float]
) -> List[float]:
    """Bootstrap discount factors from zero rates."""
    if len(times) != len(zero_rates):
        raise ValueError("Times and rates must have same length")

    return [zero_rate_to_df(rate, time) for rate, time in zip(zero_rates, times, strict=False)]


def bootstrap_zero_rates(
    times: List[float], discount_factors: List[float]
) -> List[float]:
    """Bootstrap zero rates from discount factors."""
    if len(times) != len(discount_factors):
        raise ValueError("Times and discount factors must have same length")

    return [df_to_zero_rate(df, time) for df, time in zip(discount_factors, times, strict=False)]


def calculate_par_rate(
    times: List[float], discount_factors: List[float], frequency: int = 1
) -> float:
    """
    Calculate par swap rate for given discount factor curve.

    Args:
        times: Payment times
        discount_factors: Discount factors at payment times
        frequency: Coupon payment frequency per year

    Returns:
        Par swap rate
    """
    if len(times) != len(discount_factors):
        raise ValueError("Times and discount factors must have same length")

    if len(times) == 0:
        return 0.0

    # Calculate annuity (sum of discount factors * year fractions)
    annuity = 0.0
    for i, (t, df) in enumerate(zip(times, discount_factors, strict=False)):
        if i == 0:
            year_frac = t  # First period from 0 to t
        else:
            year_frac = t - times[i - 1]  # Period length

        # Adjust for frequency
        year_frac *= frequency
        annuity += df * year_frac

    if annuity == 0:
        return 0.0

    # Par rate = (1 - final DF) / annuity
    return (1.0 - discount_factors[-1]) / annuity


def create_flat_curve_dfs(times: List[float], flat_rate: float) -> List[float]:
    """Create discount factors for a flat yield curve."""
    return [zero_rate_to_df(flat_rate, t) for t in times]


def calculate_forward_rates(times: List[float], zero_rates: List[float]) -> List[float]:
    """
    Calculate instantaneous forward rates from zero rates.

    Uses finite difference approximation.
    """
    if len(times) != len(zero_rates):
        raise ValueError("Times and rates must have same length")

    if len(times) < 2:
        return zero_rates.copy()

    forward_rates = []

    for i in range(len(times)):
        if i == 0:
            # For first point, use zero rate
            forward_rates.append(zero_rates[0])
        else:
            # Forward rate calculation: f(t) ≈ [r(t+h)*t - r(t-h)*(t-h)] / h
            # Simplified to discrete forward between adjacent points
            t_prev, t_curr = times[i - 1], times[i]
            r_prev, r_curr = zero_rates[i - 1], zero_rates[i]

            # Calculate forward rate for period [t_prev, t_curr]
            df_prev = zero_rate_to_df(r_prev, t_prev)
            df_curr = zero_rate_to_df(r_curr, t_curr)

            period_length = t_curr - t_prev
            if period_length > 0:
                forward_rate = (df_prev / df_curr - 1) / period_length
            else:
                forward_rate = r_curr

            forward_rates.append(forward_rate)

    return forward_rates


# --- IRS-only bootstrapping utilities ---
def interpolate_curve_at_times(
    curve, times: List[float], method: str = "df"
) -> List[float]:
    """
    Interpolate curve values at specified times.

    Args:
        curve: Curve object
        times: Times to interpolate at
        method: 'df' for discount factors, 'zero' for zero rates

    Returns:
        Interpolated values
    """
    if method == "df":
        return [curve.df(t) for t in times]
    elif method == "zero":
        return [curve.zero(t) for t in times]
    else:
        raise ValueError("Method must be 'df' or 'zero'")


class CurveShifter:
    """Utility class for shifting curves for risk calculations."""

    @staticmethod
    def parallel_shift_zero_rates(
        zero_rates: List[float], shift_bp: float
    ) -> List[float]:
        """Apply parallel shift to zero rates."""
        shift_decimal = shift_bp / 10000.0
        return [rate + shift_decimal for rate in zero_rates]

    @staticmethod
    def steepen_curve(
        zero_rates: List[float], times: List[float], steepen_bp: float
    ) -> List[float]:
        """Apply steepening shift (longer rates increase more)."""
        if len(zero_rates) != len(times):
            raise ValueError("Rates and times must have same length")

        shift_decimal = steepen_bp / 10000.0
        max_time = max(times) if times else 1.0

        shifted_rates = []
        for rate, time in zip(zero_rates, times, strict=False):
            # Linear scaling: short end unchanged, long end gets full shift
            shift_factor = time / max_time
            shifted_rates.append(rate + shift_decimal * shift_factor)

        return shifted_rates

    @staticmethod
    def flatten_curve(
        zero_rates: List[float], times: List[float], flatten_bp: float
    ) -> List[float]:
        """Apply flattening shift (shorter rates increase more)."""
        return CurveShifter.steepen_curve(zero_rates, times, -flatten_bp)
