"""
Date calculation utilities for interest rate swap markets.
Provides standalone functions for business day adjustments, spot lag calculations, and tenor arithmetic.
"""

from datetime import date, datetime
from enum import Enum
from typing import List, Union

from ficclib.swap.conventions.calendars import Calendar, get_calendar
from ficclib.swap.conventions.types import BusinessDayAdjustment
from ficclib.swap.schedule import (
    adjust_date,
    apply_end_of_month_rule,
)


class RollConvention(Enum):
    """Roll conventions for schedule generation."""

    NO_ROLL = "NO_ROLL"
    EOM = "EOM"  # End of Month
    IMM = "IMM"  # International Money Market (3rd Wednesday)
    SFE = "SFE"  # Sydney Futures Exchange


# Default market settings
_DEFAULT_CALENDAR = None  # Will be initialized on first use
_DEFAULT_SPOT_LAG = 2
_DEFAULT_BUSINESS_DAY_ADJUSTMENT = BusinessDayAdjustment.MODIFIED_FOLLOWING
_DEFAULT_END_OF_MONTH_RULE = True


def _get_default_calendar() -> Calendar:
    """Get default calendar, initializing if needed."""
    global _DEFAULT_CALENDAR
    if _DEFAULT_CALENDAR is None:
        _DEFAULT_CALENDAR = get_calendar("TARGET")
    return _DEFAULT_CALENDAR


def set_default_calendar(calendar_name: str) -> None:
    """Set the default calendar for date calculations."""
    global _DEFAULT_CALENDAR
    _DEFAULT_CALENDAR = get_calendar(calendar_name)


def apply_spot_lag(
    trade_date: Union[date, datetime], 
    spot_lag_days: int = _DEFAULT_SPOT_LAG,
    calendar: Calendar = None
) -> date:
    """Apply spot lag to get settlement/value date."""
    if isinstance(trade_date, datetime):
        trade_date = trade_date.date()

    if calendar is None:
        calendar = _get_default_calendar()
    
    return calendar.add_business_days(trade_date, spot_lag_days)


def get_spot_date(trade_date: Union[date, datetime], calendar: Calendar = None, spot_lag: int = None) -> date:
    """Get spot date from trade date using market conventions."""
    if calendar is None:
        calendar = _get_default_calendar()
    if spot_lag is None:
        spot_lag = _DEFAULT_SPOT_LAG
    return apply_spot_lag(trade_date, spot_lag, calendar)


def adjust_business_date(
    dt: Union[date, datetime],
    adjustment: BusinessDayAdjustment = _DEFAULT_BUSINESS_DAY_ADJUSTMENT,
    calendar: Calendar = None
) -> date:
    """Apply business day adjustment using market conventions."""
    if calendar is None:
        calendar = _get_default_calendar()
    return adjust_date(dt, adjustment, calendar)


def add_tenor_months(
    start_date: Union[date, datetime], 
    tenor_months: int,
    end_of_month_rule: bool = _DEFAULT_END_OF_MONTH_RULE,
    adjustment: BusinessDayAdjustment = _DEFAULT_BUSINESS_DAY_ADJUSTMENT,
    calendar: Calendar = None
) -> date:
    """Add tenor (in months) with end-of-month rule and business day adjustment."""
    if isinstance(start_date, datetime):
        start_date = start_date.date()

    if calendar is None:
        calendar = _get_default_calendar()

    unadjusted = apply_end_of_month_rule(start_date, tenor_months, end_of_month_rule)
    return adjust_date(unadjusted, adjustment, calendar)


def add_tenor_years(start_date: Union[date, datetime], years: int) -> date:
    """Add whole years using ModFollowing/TARGET conventions."""
    return add_tenor_months(start_date, years * 12)


def tenor_to_months(tenor: str) -> int:
    """Convert tenor string to months."""
    t = tenor.upper().strip()
    if t.endswith("M"):
        return int(t[:-1])
    if t.endswith("Y"):
        return int(t[:-1]) * 12
    raise ValueError(f"Unsupported tenor: {tenor}")


def compute_maturity(curve_date: date, tenor: str, calendar: Calendar = None, spot_lag: int = None,
                    business_day_adjustment: BusinessDayAdjustment = None, end_of_month_rule: bool = None) -> date:
    """Compute maturity date from curve date and tenor."""
    if calendar is None:
        calendar = _get_default_calendar()
    if spot_lag is None:
        spot_lag = _DEFAULT_SPOT_LAG
    if business_day_adjustment is None:
        business_day_adjustment = _DEFAULT_BUSINESS_DAY_ADJUSTMENT
    if end_of_month_rule is None:
        end_of_month_rule = _DEFAULT_END_OF_MONTH_RULE

    spot = get_spot_date(curve_date, calendar, spot_lag)
    months = tenor_to_months(tenor)
    return add_tenor_months(spot, months, end_of_month_rule, business_day_adjustment, calendar)


def generate_annual_payment_schedule(curve_date: date, tenor: str, calendar: Calendar = None, spot_lag: int = None,
                                    business_day_adjustment: BusinessDayAdjustment = None, end_of_month_rule: bool = None) -> List[date]:
    """Generate annual payment schedule from curve date to maturity."""
    if calendar is None:
        calendar = _get_default_calendar()
    if spot_lag is None:
        spot_lag = _DEFAULT_SPOT_LAG
    if business_day_adjustment is None:
        business_day_adjustment = _DEFAULT_BUSINESS_DAY_ADJUSTMENT
    if end_of_month_rule is None:
        end_of_month_rule = _DEFAULT_END_OF_MONTH_RULE

    spot = get_spot_date(curve_date, calendar, spot_lag)
    maturity = compute_maturity(curve_date, tenor, calendar, spot_lag, business_day_adjustment, end_of_month_rule)
    dates: List[date] = [spot]
    current = spot
    while True:
        next_d = add_tenor_months(current, 12, end_of_month_rule, business_day_adjustment, calendar)
        if next_d >= maturity:
            dates.append(maturity)
            break
        dates.append(next_d)
        current = next_d
    return dates


# Legacy compatibility - these will be removed after transition
class DateCalculator:
    """DEPRECATED: Legacy compatibility class. Use standalone functions instead."""
    
    def __init__(self, calendar_name: str = "TARGET", spot_lag: int = 2, 
                 business_day_adjustment: BusinessDayAdjustment = BusinessDayAdjustment.MODIFIED_FOLLOWING,
                 end_of_month_rule: bool = True, target_holidays: List[date] = None):
        import warnings
        warnings.warn("DateCalculator is deprecated. Use standalone functions from date_utils instead.", 
                     DeprecationWarning, stacklevel=2)
    
    def get_spot_date(self, trade_date: Union[date, datetime]) -> date:
        return get_spot_date(trade_date)
    
    def add_tenor(self, start_date: Union[date, datetime], tenor_months: int) -> date:
        return add_tenor_months(start_date, tenor_months)
    
    def adjust_date(self, dt: Union[date, datetime]) -> date:
        return adjust_business_date(dt)


# Legacy constants for backward compatibility
EUR_OIS_CONVENTIONS = DateCalculator()
EUR_SWAP_CONVENTIONS = DateCalculator()