"""
Base classes for curve interpolation methods.
"""
from abc import ABC, abstractmethod
from typing import List

import numpy as np


class Interpolator(ABC):
    """Base class for curve interpolation methods."""

    def __init__(self, pillars: List[float], values: List[float]):
        """
        Initialize interpolator.

        Args:
            pillars: Time to maturity points (in years)
            values: Values to interpolate (discount factors, zero rates, etc.)
        """
        if len(pillars) != len(values):
            raise ValueError("Pillars and values must have same length")
        if len(pillars) < 2:
            raise ValueError("Need at least 2 points for interpolation")

        # Sort by pillars
        sorted_pairs = sorted(zip(pillars, values, strict=False))
        self.pillars = np.array([p[0] for p in sorted_pairs])
        self.values = np.array([p[1] for p in sorted_pairs])

        # Check for duplicates
        if len(np.unique(self.pillars)) != len(self.pillars):
            raise ValueError("Duplicate pillar dates not allowed")

    @abstractmethod
    def interpolate(self, t: float) -> float:
        """Interpolate value at time t."""
        pass

    def interpolate_many(self, times: List[float]) -> List[float]:
        """Interpolate values at multiple times."""
        return [self.interpolate(t) for t in times]

    def _extrapolate_flat(self, t: float) -> float:
        """Flat extrapolation beyond pillar range."""
        if t <= self.pillars[0]:
            return self.values[0]
        elif t >= self.pillars[-1]:
            return self.values[-1]
        else:
            raise ValueError("Time is within pillar range, use interpolation")