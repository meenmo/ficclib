"""
Core data structures for schedule generation.
"""

from dataclasses import dataclass
from datetime import date


@dataclass
class SchedulePeriod:
    """Represents a single period in a payment schedule."""

    start_date: date
    end_date: date
    payment_date: date
    accrual_start: date
    accrual_end: date
    year_fraction: float
    is_stub: bool = False

    @property
    def accrual_days(self) -> int:
        """Number of calendar days in accrual period."""
        return (self.accrual_end - self.accrual_start).days