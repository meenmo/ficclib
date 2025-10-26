"""
Forward-starting EUR 3M-6M basis swap implementation.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional

from ficclib.swap.conventions.calendars import Calendar, get_calendar

# Local bootstrappers not used here
from ficclib.swap.conventions.daycount import ACT_360, ACT_365F, DayCountConvention
from ficclib.swap.conventions.types import (
    BusinessDayAdjustment,
    CalendarType,
    Frequency,
    RefereceRate,
    RollConvention,
)

rate_type = Enum("FIXED", "FLOATING")
LegDirection = Enum("LegDirection", ["PAY", "RECEIVE"])


# Floating leg specification for common EUR swaps
class ResetPosition(Enum):
    IN_ADVANCE = "IN_ADVANCE"
    IN_ARREARS = "IN_ARREARS"


class LegType(Enum):
    FLOATING = "FLOATING"
    FIXED = "FIXED"


@dataclass
class SwapLegConvention:
    """Specification for a swap leg convention."""

    leg_type: LegType
    day_count: DayCountConvention
    pay_frequency: Frequency
    pay_delay_days: int
    business_day_adjustment: BusinessDayAdjustment
    roll_convention: RollConvention
    reset_frequency: Optional[Frequency]
    fixing_lag_days: Optional[int]
    calendar: CalendarType
    reset_position: Optional[ResetPosition] = ResetPosition.IN_ADVANCE
    rate_cutoff_days: int = 0
    reference_rate: Optional[RefereceRate] = None
    _calendar_obj: Calendar = field(init=False)

    def __post_init__(self):
        calendar_name = self.calendar.value if hasattr(self.calendar, 'value') else self.calendar
        self._calendar_obj = get_calendar(calendar_name)

    @property
    def calendar_obj(self) -> Calendar:
        """Get the actual calendar object."""
        return self._calendar_obj


@dataclass
class SwapLeg:
    """Specification for a forward-starting basis swap."""

    effective_date: date
    maturity_date: date
    convention: SwapLegConvention
    notional: float
    leg_direction: LegDirection
    spread: float = 0


# Predefined floating leg specs
EURIBOR_3M_FLOATING = SwapLegConvention(
    leg_type=LegType.FLOATING,
    reference_rate=RefereceRate.EURIBOR3M,
    day_count=ACT_360,
    reset_frequency=Frequency.QUARTERLY,
    pay_frequency=Frequency.QUARTERLY,
    fixing_lag_days=2,
    pay_delay_days=0,
    business_day_adjustment=BusinessDayAdjustment.MODIFIED_FOLLOWING,
    roll_convention=RollConvention.BACKWARD_EOM,
    calendar=CalendarType.TARGET,
    reset_position=ResetPosition.IN_ADVANCE,
)

EURIBOR_6M_FLOATING = SwapLegConvention(
    leg_type=LegType.FLOATING,
    reference_rate=RefereceRate.EURIBOR6M,
    day_count=ACT_360,
    reset_frequency=Frequency.SEMIANNUAL,
    pay_frequency=Frequency.SEMIANNUAL,
    fixing_lag_days=2,
    pay_delay_days=0,
    business_day_adjustment=BusinessDayAdjustment.MODIFIED_FOLLOWING,
    calendar=CalendarType.TARGET,
    reset_position=ResetPosition.IN_ADVANCE,
    roll_convention=RollConvention.BACKWARD_EOM,
)

ESTR_FLOATING = SwapLegConvention(
    leg_type=LegType.FLOATING,
    reference_rate=RefereceRate.ESTR,
    day_count=ACT_365F,
    reset_frequency=Frequency.DAILY,
    pay_frequency=Frequency.ANNUAL,
    fixing_lag_days=0,
    rate_cutoff_days=1,
    pay_delay_days=1,
    business_day_adjustment=BusinessDayAdjustment.MODIFIED_FOLLOWING,
    calendar=CalendarType.TARGET,
    reset_position=ResetPosition.IN_ARREARS,
    roll_convention=RollConvention.BACKWARD_EOM,
)

ESTR_FIXED = SwapLegConvention(
    leg_type=LegType.FIXED,
    reference_rate=RefereceRate.ESTR,
    day_count=ACT_360,
    reset_frequency=None,  # Not applicable for fixed legs
    pay_frequency=Frequency.ANNUAL,
    fixing_lag_days=0,
    pay_delay_days=1,
    business_day_adjustment=BusinessDayAdjustment.MODIFIED_FOLLOWING,
    calendar=CalendarType.TARGET,
    roll_convention=RollConvention.BACKWARD_EOM,
)

EUR_IRS_FIXED = SwapLegConvention(
    leg_type=LegType.FIXED,
    day_count=ACT_360,
    reset_frequency=None,  # Not applicable for fixed legs
    pay_frequency=Frequency.ANNUAL,
    fixing_lag_days=None,  # Not applicable for fixed legs
    pay_delay_days=1,
    business_day_adjustment=BusinessDayAdjustment.MODIFIED_FOLLOWING,
    roll_convention=RollConvention.BACKWARD_EOM,
    calendar=CalendarType.TARGET,
    reset_position=None,  # Not applicable for fixed legs
    reference_rate=None,  # Fixed legs don't reference a rate
)
