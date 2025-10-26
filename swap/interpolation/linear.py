"""
Linear interpolation methods for yield curves.
"""
import math
from typing import List

import numpy as np

from .base import Interpolator


class LinearDiscountFactorInterpolator(Interpolator):
    """Linear interpolation on discount factors.

    Simple and commonly used for discount curves.
    Fast but may not preserve forward rate smoothness.
    """

    def interpolate(self, t: float) -> float:
        """Linear interpolation on discount factors."""
        # Extrapolation
        if t <= self.pillars[0]:
            return self.values[0]
        if t >= self.pillars[-1]:
            return self.values[-1]

        # Find surrounding points
        i = np.searchsorted(self.pillars, t) - 1

        # Linear interpolation
        t1, t2 = self.pillars[i], self.pillars[i + 1]
        df1, df2 = self.values[i], self.values[i + 1]

        weight = (t - t1) / (t2 - t1)
        return df1 + weight * (df2 - df1)


class LogLinearZeroInterpolator(Interpolator):
    """Log-linear interpolation on zero rates.

    Equivalent to linear interpolation on log discount factors.
    Very commonly used and provides smooth forward rates.
    """

    def __init__(self, pillars: List[float], zero_rates: List[float]):
        """
        Initialize with zero rates.

        Args:
            pillars: Time to maturity points (in years)
            zero_rates: Continuously compounded zero rates
        """
        super().__init__(pillars, zero_rates)
        self.log_dfs = np.array([-rate * pillar for rate, pillar in zip(zero_rates, pillars, strict=False)])

    def interpolate(self, t: float) -> float:
        """Interpolate zero rate at time t."""
        if t <= 0:
            return self.values[0]

        # Get log discount factor
        log_df = self._interpolate_log_df(t)

        # Convert back to zero rate
        return -log_df / t

    def interpolate_discount_factor(self, t: float) -> float:
        """Interpolate discount factor directly."""
        log_df = self._interpolate_log_df(t)
        return math.exp(log_df)

    def _interpolate_log_df(self, t: float) -> float:
        """Interpolate log discount factor."""
        # Extrapolation
        if t <= self.pillars[0]:
            return -self.values[0] * t
        if t >= self.pillars[-1]:
            return -self.values[-1] * t

        # Find surrounding points
        i = np.searchsorted(self.pillars, t) - 1

        # Linear interpolation on log DF
        t1, t2 = self.pillars[i], self.pillars[i + 1]
        log_df1, log_df2 = self.log_dfs[i], self.log_dfs[i + 1]

        weight = (t - t1) / (t2 - t1)
        return log_df1 + weight * (log_df2 - log_df1)


class PiecewiseConstantInterpolator(Interpolator):
    """Piecewise constant (step function) interpolation.

    Used for rates that are constant between pillar points.
    Simple but can create discontinuities.
    """

    def interpolate(self, t: float) -> float:
        """Step function interpolation."""
        # Extrapolation
        if t <= self.pillars[0]:
            return self.values[0]
        if t >= self.pillars[-1]:
            return self.values[-1]

        # Find the interval and return left endpoint value
        i = np.searchsorted(self.pillars, t, side='right') - 1
        return self.values[i]