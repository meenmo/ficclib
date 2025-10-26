"""
OIS discount curve implementation with interpolation support.
"""
import logging
import math
from datetime import date, datetime
from typing import List, Optional, Union

from ficclib.swap.interpolation import Interpolator, create_interpolator

from .base import DiscountCurve


class OISDiscountCurve(DiscountCurve):
    """
    OIS (Overnight Index Swap) discount curve for EUR using €STR.
    
    This curve is used for discounting EUR-denominated cashflows
    in the multi-curve framework.
    """
    
    def __init__(self, 
                 reference_date: date,
                 pillar_times: List[float],
                 discount_factors: List[float],
                 interpolator: Optional[Interpolator] = None,
                 interpolation_method: str = "LOGLINEAR_ZERO",
                 name: str = "EUR-OIS"):
        """
        Initialize OIS discount curve.
        
        Args:
            reference_date: Curve valuation date
            pillar_times: Pillar times in years from reference date
            discount_factors: Discount factors at pillar times
            interpolator: Custom interpolator (if None, created from method)
            interpolation_method: Method name if interpolator is None
            name: Curve name
        """
        super().__init__(reference_date, name, time_day_count="ACT/365F")
        
        if len(pillar_times) != len(discount_factors):
            raise ValueError("Pillar times and discount factors must have same length")
        
        if len(pillar_times) < 2:
            raise ValueError("Need at least 2 pillar points")
        
        # Validate discount factors
        for i, df in enumerate(discount_factors):
            if df <= 0:
                raise ValueError(f"Discount factor at pillar {i} must be positive: {df}")
        
        # Check monotonicity (discount factors should be decreasing)
        sorted_pairs = sorted(zip(pillar_times, discount_factors, strict=True))
        logger = logging.getLogger(__name__)
        for i in range(1, len(sorted_pairs)):
            if sorted_pairs[i][1] > sorted_pairs[i-1][1]:
                # Allow small increases for numerical stability, but warn about large ones
                increase = sorted_pairs[i][1] - sorted_pairs[i-1][1]
                if increase > 1e-6:
                    logger.warning(
                        "Discount factors increasing at pillar %s (increase = %.8f)",
                        i,
                        increase,
                    )
        
        self.pillar_times = pillar_times
        self.discount_factors = discount_factors
        
        # Create interpolator
        if interpolator is not None:
            self.interpolator = interpolator
        else:
            if interpolation_method in ["LINEAR_DF", "STEP_FORWARD_CONTINUOUS", "STEP_FORWARD"]:
                # These methods work directly on discount factors
                self.interpolator = create_interpolator(interpolation_method, pillar_times, discount_factors)
            else:
                # For other methods, convert to zero rates first
                zero_rates = []
                for t, df in zip(pillar_times, discount_factors, strict=True):
                    if t > 0:
                        zero_rates.append(-math.log(df) / t)
                    else:
                        zero_rates.append(0.0)
                
                self.interpolator = create_interpolator(interpolation_method, pillar_times, zero_rates)
        
        self.interpolation_method = interpolation_method
    
    def df(self, t: Union[datetime, date, float]) -> float:
        """Get discount factor at time t."""
        time_frac = self._to_year_fraction(t)
        
        # Handle edge cases
        if time_frac <= 0:
            return 1.0
        
        # For methods that work directly on discount factors
        if self.interpolation_method in ["LINEAR_DF", "STEP_FORWARD_CONTINUOUS", "STEP_FORWARD"]:
            return self.interpolator.interpolate(time_frac)
        else:
            # For methods that work on zero rates, convert back to DF
            if hasattr(self.interpolator, 'interpolate_discount_factor'):
                return self.interpolator.interpolate_discount_factor(time_frac)
            else:
                # Fallback: get zero rate and convert
                zero_rate = self.interpolator.interpolate(time_frac)
                return math.exp(-zero_rate * time_frac)
    
    def zero(self, t: Union[datetime, date, float]) -> float:
        """Get continuously compounded zero rate at time t."""
        time_frac = self._to_year_fraction(t)
        
        if time_frac <= 0:
            return 0.0
        
        # For methods that work directly on zero rates
        if self.interpolation_method not in ["LINEAR_DF", "STEP_FORWARD_CONTINUOUS", "STEP_FORWARD"]:
            return self.interpolator.interpolate(time_frac)
        else:
            # Convert from discount factor
            df_val = self.df(time_frac)
            return -math.log(df_val) / time_frac
    
    def get_pillar_info(self) -> List[tuple[float, float, float]]:
        """Get pillar information as (time, discount_factor, zero_rate) tuples."""
        info = []
        for t, df in zip(self.pillar_times, self.discount_factors, strict=True):
            zero_rate = -math.log(df) / t if t > 0 else 0.0
            info.append((t, df, zero_rate))
        return info
    
    def shift_parallel(self, shift_bp: float) -> 'OISDiscountCurve':
        """
        Create a parallel shifted version of the curve.
        
        Args:
            shift_bp: Parallel shift in basis points
            
        Returns:
            New shifted curve
        """
        shift_decimal = shift_bp / 10000.0
        
        # Shift zero rates and convert back to discount factors
        new_discount_factors = []
        for t, df in zip(self.pillar_times, self.discount_factors, strict=True):
            if t > 0:
                zero_rate = -math.log(df) / t
                shifted_zero = zero_rate + shift_decimal
                new_df = math.exp(-shifted_zero * t)
            else:
                new_df = df
            new_discount_factors.append(new_df)
        
        return OISDiscountCurve(
            reference_date=self.reference_date,
            pillar_times=self.pillar_times.copy(),
            discount_factors=new_discount_factors,
            interpolation_method=self.interpolation_method,
            name=f"{self.name}_shifted_{shift_bp}bp"
        )

    def with_spot_stub(self, stub_time: float, stub_discount: float) -> 'OISDiscountCurve':
        """Return a new curve with an explicit near-spot pillar."""
        if stub_time <= 0.0:
            return self
        if stub_time >= self.pillar_times[0]:
            return self
        if not (0.0 < stub_discount < 1.0):
            return self

        new_times = [stub_time] + self.pillar_times
        new_dfs = [stub_discount] + self.discount_factors

        return OISDiscountCurve(
            reference_date=self.reference_date,
            pillar_times=new_times,
            discount_factors=new_dfs,
            interpolation_method=self.interpolation_method,
            name=self.name,
        )
    
    def get_forward_rate_curve(self, bump_size: float = 1e-6) -> List[tuple[float, float]]:
        """
        Calculate instantaneous forward rates using numerical differentiation.
        
        Args:
            bump_size: Size of bump for numerical derivative
            
        Returns:
            List of (time, forward_rate) tuples
        """
        forward_rates = []
        
        for t in self.pillar_times:
            if t <= bump_size:
                # For very short times, use zero rate as approximation
                forward_rate = self.zero(t)
            else:
                # f(t) = -d(ln DF)/dt ≈ [ln DF(t-h) - ln DF(t+h)] / (2h)
                df_minus = self.df(t - bump_size)
                df_plus = self.df(t + bump_size)
                
                forward_rate = (math.log(df_minus) - math.log(df_plus)) / (2 * bump_size)
            
            forward_rates.append((t, forward_rate))
        
        return forward_rates
    
    def __str__(self) -> str:
        return f"OISDiscountCurve({self.name}, {len(self.pillar_times)} pillars, {self.interpolation_method})"
    
    def __repr__(self) -> str:
        return (f"OISDiscountCurve(reference_date={self.reference_date}, "
                f"pillar_times={self.pillar_times}, "
                f"discount_factors={self.discount_factors}, "
                f"interpolation_method='{self.interpolation_method}', "
                f"name='{self.name}')")


def create_flat_ois_curve(reference_date: date, 
                         flat_rate: float,
                         max_time: float = 30.0,
                         num_pillars: int = 10,
                         name: str = "EUR-OIS-FLAT") -> OISDiscountCurve:
    """
    Create a flat OIS discount curve for testing purposes.
    
    Args:
        reference_date: Curve reference date
        flat_rate: Flat zero rate (decimal)
        max_time: Maximum time in years
        num_pillars: Number of pillar points
        name: Curve name
        
    Returns:
        Flat OIS discount curve
    """
    times = [i * max_time / (num_pillars - 1) for i in range(num_pillars)]
    times[0] = 0.1  # Avoid zero time
    
    discount_factors = [math.exp(-flat_rate * t) for t in times]
    
    return OISDiscountCurve(
        reference_date=reference_date,
        pillar_times=times,
        discount_factors=discount_factors,
        interpolation_method="LINEAR_DF",
        name=name
    )
