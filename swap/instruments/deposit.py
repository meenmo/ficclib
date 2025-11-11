"""
EURIBOR deposit instrument specifications and conventions.
"""

from dataclasses import dataclass, field

from ficclib.swap.conventions.calendars import Calendar, get_calendar
from ficclib.swap.conventions.daycount import ACT_360, ACT_365F, DayCountConvention
from ficclib.swap.conventions.types import (
    BusinessDayAdjustment,
    CalendarType,
    RefereceRate,
)


@dataclass
class DepositConvention:
    """Specification for a deposit/cash instrument convention."""

    reference_rate: RefereceRate
    day_count: DayCountConvention
    settlement_lag_days: int
    business_day_adjustment: BusinessDayAdjustment
    calendar: CalendarType
    _calendar_obj: Calendar = field(init=False)

    def __post_init__(self):
        calendar_name = self.calendar.value if hasattr(self.calendar, 'value') else self.calendar
        self._calendar_obj = get_calendar(calendar_name)

    @property
    def calendar_obj(self) -> Calendar:
        """Get the actual calendar object."""
        return self._calendar_obj

EURIBOR3M_DEPOSIT = DepositConvention(
    reference_rate=RefereceRate.EURIBOR3M,
    day_count=ACT_360,
    settlement_lag_days=2,
    business_day_adjustment=BusinessDayAdjustment.MODIFIED_FOLLOWING,
    calendar=CalendarType.TARGET,
)

EURIBOR6M_DEPOSIT = DepositConvention(
    reference_rate=RefereceRate.EURIBOR6M,
    day_count=ACT_360,
    settlement_lag_days=2,
    business_day_adjustment=BusinessDayAdjustment.MODIFIED_FOLLOWING,
    calendar=CalendarType.TARGET,
)

TIBOR3M_DEPOSIT = DepositConvention(
    reference_rate=RefereceRate.TIBOR3M,
    day_count=ACT_365F,
    settlement_lag_days=2,
    business_day_adjustment=BusinessDayAdjustment.MODIFIED_FOLLOWING,
    calendar=CalendarType.JN,
)

TIBOR6M_DEPOSIT = DepositConvention(
    reference_rate=RefereceRate.TIBOR6M,
    day_count=ACT_365F,
    settlement_lag_days=2,
    business_day_adjustment=BusinessDayAdjustment.MODIFIED_FOLLOWING,
    calendar=CalendarType.JN,
)