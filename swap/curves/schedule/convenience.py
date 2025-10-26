"""
Convenience functions for common EUR schedules.
"""

from datetime import date, datetime
from typing import List, Union

from ficclib.swap.conventions.daycount import DayCountConvention
from ficclib.swap.conventions.types import Frequency
from ficclib.swap.instruments.swap import SwapLegConvention

from .core import SchedulePeriod
from .generator import ScheduleGenerator


def generate_euribor_3m_schedule(
    effective_date: Union[date, datetime],
    maturity_date: Union[date, datetime],
    day_count: DayCountConvention,
    conventions: SwapLegConvention,
) -> List[SchedulePeriod]:
    """Generate quarterly EURIBOR 3M schedule."""
    generator = ScheduleGenerator(conventions)
    return generator.generate_schedule(
        effective_date, maturity_date, Frequency.QUARTERLY, day_count
    )


def generate_euribor_6m_schedule(
    effective_date: Union[date, datetime],
    maturity_date: Union[date, datetime],
    day_count: DayCountConvention,
    conventions: SwapLegConvention,
) -> List[SchedulePeriod]:
    """Generate semiannual EURIBOR 6M schedule."""
    generator = ScheduleGenerator(conventions)
    return generator.generate_schedule(
        effective_date, maturity_date, Frequency.SEMIANNUAL, day_count
    )