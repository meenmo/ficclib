"""
QuantLib-backed calendar implementations.

This module provides a drop-in replacement for the custom calendar implementations,
using QuantLib's industry-standard TARGET calendar.
"""

from datetime import date, datetime
from typing import Union

import QuantLib as ql


def _to_ql_date(dt: Union[date, datetime]) -> ql.Date:
    """Convert Python date/datetime to QuantLib Date."""
    if isinstance(dt, datetime):
        dt = dt.date()
    return ql.Date(dt.day, dt.month, dt.year)


def _to_py_date(ql_date: ql.Date) -> date:
    """Convert QuantLib Date to Python date."""
    return date(ql_date.year(), ql_date.month(), ql_date.dayOfMonth())


class Calendar:
    """Base calendar class for QuantLib-backed business day calculations."""

    def __init__(self, name: str, ql_calendar: ql.Calendar):
        self.name = name
        self._ql_calendar = ql_calendar
        # Keep holidays attribute for compatibility (lazy loaded)
        self._holidays = None

    @property
    def holidays(self):
        """Get holidays as a set (for compatibility with old API).

        Note: This is expensive to compute, so only use if really needed.
        """
        if self._holidays is None:
            # Generate holidays from 2020 to 2100 for compatibility
            self._holidays = set()
            start_date = ql.Date(1, 1, 2020)
            end_date = ql.Date(31, 12, 2100)

            current = start_date
            while current <= end_date:
                if self._ql_calendar.isHoliday(current) and current.weekday() < 6:
                    # It's a holiday but not a weekend
                    self._holidays.add(_to_py_date(current))
                current += 1

        return self._holidays

    def is_business_day(self, dt: Union[date, datetime]) -> bool:
        """Check if date is a business day (not weekend or holiday)."""
        ql_date = _to_ql_date(dt)
        return self._ql_calendar.isBusinessDay(ql_date)

    def is_holiday(self, dt: Union[date, datetime]) -> bool:
        """Check if date is a holiday."""
        ql_date = _to_ql_date(dt)
        return self._ql_calendar.isHoliday(ql_date)

    def add_business_days(self, start_date: Union[date, datetime], days: int) -> date:
        """Add business days to a date."""
        ql_date = _to_ql_date(start_date)
        ql_result = self._ql_calendar.advance(ql_date, days, ql.Days)
        return _to_py_date(ql_result)

    def business_days_between(
        self, start: Union[date, datetime], end: Union[date, datetime]
    ) -> int:
        """Count business days between two dates (exclusive of start, inclusive of end)."""
        ql_start = _to_ql_date(start)
        ql_end = _to_ql_date(end)

        # QuantLib's businessDaysBetween is exclusive of both endpoints by default
        # We need exclusive of start, inclusive of end
        # So we add 1 to the start date before counting
        ql_start_plus_one = ql_start + 1

        if ql_start_plus_one > ql_end:
            return 0

        # Count from start+1 to end (exclusive), then check if end is a business day
        count = self._ql_calendar.businessDaysBetween(ql_start_plus_one, ql_end, False, False)

        # Add 1 if end is a business day (to make it inclusive)
        if self._ql_calendar.isBusinessDay(ql_end):
            count += 1

        return count


class TargetCalendar(Calendar):
    """TARGET (Trans-European Automated Real-time Gross settlement Express Transfer) calendar.

    Uses QuantLib's built-in TARGET calendar implementation.
    """

    def __init__(self, holidays_file_path: str = None, target_holidays=None):
        """
        Initialize TARGET calendar.

        Args:
            holidays_file_path: Ignored (for API compatibility)
            target_holidays: Ignored (for API compatibility)

        Note: QuantLib maintains the official TARGET calendar internally.
        Custom holidays are not supported in this version.
        """
        super().__init__("TARGET", ql.TARGET())


class WeekendCalendar(Calendar):
    """Simple calendar that only considers weekends as non-business days."""

    def __init__(self):
        # Use QuantLib's WeekendsOnly calendar
        super().__init__("Weekend", ql.WeekendsOnly())


# Pre-defined calendar instances
TARGET = TargetCalendar()
WEEKEND_ONLY = WeekendCalendar()

# Calendar registry
CALENDARS = {
    "TARGET": TARGET,
    "WEEKEND": WEEKEND_ONLY,
    "EUR": TARGET,  # Alias
}


def get_calendar(name: str, target_holidays=None) -> Calendar:
    """
    Get a calendar by name.

    Args:
        name: Calendar name ("TARGET", "EUR", or "WEEKEND")
        target_holidays: Ignored (for API compatibility)

    Note: Custom holidays are not supported with QuantLib calendars.
    """
    if name not in CALENDARS:
        raise ValueError(
            f"Unknown calendar: {name}. Available: {list(CALENDARS.keys())}"
        )
    return CALENDARS[name]
