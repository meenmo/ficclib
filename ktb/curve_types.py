"""Data structures for financial calculations."""

from dataclasses import dataclass
from datetime import date


@dataclass
class CurveNode:
    """Represents a point on a yield curve."""

    tenor_years: float  # e.g., 0.25, 0.5, 0.75, 1, 2, 3, ...
    ytm: float  # decimal, e.g., 0.0365


@dataclass
class DiscountFactorNode:
    """Represents a discount factor at a specific date."""

    date: date  # The date for this discount factor
    discount_factor: float  # The discount factor value
    years_from_valuation: float  # Years from valuation date (for convenience)
