"""
Date adjustment functions for schedule generation.
"""

from datetime import date, datetime, timedelta
from typing import Union

from ficclib.swap.conventions.calendars import Calendar
from ficclib.swap.conventions.types import BusinessDayAdjustment


def adjust_date(
    dt: Union[date, datetime], adjustment: BusinessDayAdjustment, calendar: Calendar
) -> date:
    """Apply business day adjustment to a date."""
    if isinstance(dt, datetime):
        dt = dt.date()

    if adjustment == BusinessDayAdjustment.NO_ADJUSTMENT:
        return dt

    elif adjustment == BusinessDayAdjustment.FOLLOWING:
        while not calendar.is_business_day(dt):
            dt += timedelta(days=1)
        return dt

    elif adjustment == BusinessDayAdjustment.MODIFIED_FOLLOWING:
        original_month = dt.month
        adjusted = dt

        # Apply following convention
        while not calendar.is_business_day(adjusted):
            adjusted += timedelta(days=1)

        # If month changed, use preceding instead
        if adjusted.month != original_month:
            adjusted = dt
            while not calendar.is_business_day(adjusted):
                adjusted -= timedelta(days=1)

        return adjusted

    elif adjustment == BusinessDayAdjustment.PRECEDING:
        while not calendar.is_business_day(dt):
            dt -= timedelta(days=1)
        return dt

    elif adjustment == BusinessDayAdjustment.MODIFIED_PRECEDING:
        original_month = dt.month
        adjusted = dt

        # Apply preceding convention
        while not calendar.is_business_day(adjusted):
            adjusted -= timedelta(days=1)

        # If month changed, use following instead
        if adjusted.month != original_month:
            adjusted = dt
            while not calendar.is_business_day(adjusted):
                adjusted += timedelta(days=1)

        return adjusted

    else:
        raise ValueError(f"Unknown business day adjustment: {adjustment}")


def is_end_of_month(dt: Union[date, datetime]) -> bool:
    """Check if date is end of month."""
    if isinstance(dt, datetime):
        dt = dt.date()

    # Get last day of the month
    if dt.month == 12:
        next_month = date(dt.year + 1, 1, 1)
    else:
        next_month = date(dt.year, dt.month + 1, 1)

    last_day = next_month - timedelta(days=1)
    return dt == last_day


def get_month_end(year: int, month: int) -> date:
    """Get the last calendar day of a given month."""
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    return next_month - timedelta(days=1)


def apply_end_of_month_rule(
    dt: Union[date, datetime], months_to_add: int, apply_eom_rule: bool = True
) -> date:
    """Add months to a date, applying end-of-month rule if applicable."""
    if isinstance(dt, datetime):
        dt = dt.date()

    # Check if original date is end of month
    is_eom_start = is_end_of_month(dt) and apply_eom_rule

    # Add months
    new_year = dt.year
    new_month = dt.month + months_to_add

    # Handle year overflow/underflow
    while new_month > 12:
        new_month -= 12
        new_year += 1
    while new_month < 1:
        new_month += 12
        new_year -= 1

    # If original was EOM, make result EOM too
    if is_eom_start:
        return get_month_end(new_year, new_month)

    # Otherwise, try to keep same day
    try:
        return date(new_year, new_month, dt.day)
    except ValueError:
        # Day doesn't exist in target month (e.g., Jan 31 -> Feb 31)
        # Use last day of target month
        return get_month_end(new_year, new_month)