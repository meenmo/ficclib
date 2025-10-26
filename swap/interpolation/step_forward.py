"""
Step forward interpolation methods
"""
import math
from typing import List

import numpy as np

from .base import Interpolator


class StepForwardContinuousInterpolator(Interpolator):
    """Step Forward (continuous) interpolation

    Forward rates are piecewise constant (step function) between pillar points.
    Discount factors are derived using continuous compounding.
    This creates smooth zero rates with piecewise exponential discount factors.
    """

    def __init__(self, pillars: List[float], discount_factors: List[float]):
        """
        Initialize with discount factors.

        Args:
            pillars: Time to maturity points (in years)
            discount_factors: Discount factors at pillar points
        """
        super().__init__(pillars, discount_factors)

        # Calculate forward rates between pillars
        self.forward_rates = []
        for i in range(len(pillars) - 1):
            t1, t2 = pillars[i], pillars[i + 1]
            df1, df2 = discount_factors[i], discount_factors[i + 1]

            # Forward rate: f = ln(DF1/DF2) / (t2-t1)
            forward_rate = math.log(df1 / df2) / (t2 - t1)
            self.forward_rates.append(forward_rate)

    def interpolate(self, t: float) -> float:
        """Interpolate discount factor at time t using step forward rates."""
        return self.interpolate_discount_factor(t)

    def interpolate_discount_factor(self, t: float) -> float:
        """Interpolate discount factor using piecewise constant forward rates."""
        # Handle edge cases
        if t <= 0:
            return 1.0
        if t <= self.pillars[0]:
            # Step-forward extrapolation using first forward rate
            first_zero_rate = -math.log(self.values[0]) / self.pillars[0]
            return math.exp(-first_zero_rate * t)
        if t >= self.pillars[-1]:
            last_forward_rate = self.forward_rates[-1]
            dt = t - self.pillars[-1]
            return self.values[-1] * math.exp(-last_forward_rate * dt)

        # Find the interval containing t
        i = np.searchsorted(self.pillars, t) - 1

        # Start from the left pillar
        df = self.values[i]
        t_start = self.pillars[i]

        # Apply the constant forward rate for the remaining period
        if i < len(self.forward_rates):
            forward_rate = self.forward_rates[i]
            dt = t - t_start
            df = df * math.exp(-forward_rate * dt)

        return df

    def interpolate_zero_rate(self, t: float) -> float:
        """Interpolate zero rate at time t."""
        if t <= 0:
            return 0.0

        df = self.interpolate_discount_factor(t)
        return -math.log(df) / t