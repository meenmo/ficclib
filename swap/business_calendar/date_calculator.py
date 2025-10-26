"""
Business day adjustment rules, spot lag handling, and stub conventions.
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


def apply_spot_lag(
    trade_date: Union[date, datetime], spot_lag_days: int, calendar: Calendar
) -> date:
    """Apply spot lag to get settlement/value date."""
    if isinstance(trade_date, datetime):
        trade_date = trade_date.date()

    return calendar.add_business_days(trade_date, spot_lag_days)


# Legacy DateCalculator class removed - use standalone functions instead


# Standalone utility functions (preferred over class usage)
def get_spot_date(trade_date: Union[date, datetime], calendar: Calendar = None, spot_lag: int = 2) -> date:
    """Get spot date from trade date using market conventions (default: 2 business days + TARGET calendar)."""
    if calendar is None:
        calendar = get_calendar("TARGET")
    return apply_spot_lag(trade_date, spot_lag, calendar)


def add_tenor_months(start_date: Union[date, datetime], tenor_months: int, calendar: Calendar = None,
                    business_day_adjustment: BusinessDayAdjustment = BusinessDayAdjustment.MODIFIED_FOLLOWING,
                    end_of_month_rule: bool = True) -> date:
    """Add tenor months using market conventions (default: TARGET calendar + Modified Following + EOM rule)."""
    if isinstance(start_date, datetime):
        start_date = start_date.date()

    if calendar is None:
        calendar = get_calendar("TARGET")
    unadjusted = apply_end_of_month_rule(start_date, tenor_months, end_of_month_rule)
    return adjust_date(unadjusted, business_day_adjustment, calendar)


def tenor_to_months(tenor: str) -> int:
    """Convert tenor string (e.g., '3M', '2Y') to number of months."""
    t = tenor.upper().strip()
    if t.endswith("M"):
        return int(t[:-1])
    if t.endswith("Y"):
        return int(t[:-1]) * 12
    raise ValueError(f"Unsupported tenor: {tenor}")


def tenor_to_days(tenor: str) -> int:
    """Convert tenor string to number of days for short tenors."""
    t = tenor.upper().strip()
    if t.endswith("D"):
        return int(t[:-1])
    if t.endswith("W"):
        return int(t[:-1]) * 7
    raise ValueError(f"Unsupported short tenor: {tenor}")


def compute_maturity(curve_date: date, tenor: str, calendar: Calendar = None, spot_lag: int = 2,
                    business_day_adjustment: BusinessDayAdjustment = BusinessDayAdjustment.MODIFIED_FOLLOWING,
                    end_of_month_rule: bool = True) -> date:
    """Compute maturity date from curve date and tenor string."""
    spot = get_spot_date(curve_date, calendar, spot_lag)
    t = tenor.upper().strip()

    # Handle short tenors (days/weeks) with calendar day arithmetic
    if t.endswith(("D", "W")):
        days = tenor_to_days(tenor)
        from datetime import timedelta
        return spot + timedelta(days=days)  # Use calendar days, not business days

    # Handle longer tenors (months/years) with month arithmetic
    else:
        months = tenor_to_months(tenor)
        return add_tenor_months(spot, months, calendar, business_day_adjustment, end_of_month_rule)


def generate_annual_payment_schedule(curve_date: date, tenor: str, calendar: Calendar = None, spot_lag: int = 2,
                                    business_day_adjustment: BusinessDayAdjustment = BusinessDayAdjustment.MODIFIED_FOLLOWING,
                                    end_of_month_rule: bool = True) -> List[date]:
    """Generate annual payment schedule from curve date to maturity."""
    spot = get_spot_date(curve_date, calendar, spot_lag)
    maturity = compute_maturity(curve_date, tenor, calendar, spot_lag, business_day_adjustment, end_of_month_rule)
    dates: List[date] = [spot]
    current = spot
    while True:
        next_d = add_tenor_months(current, 12, calendar, business_day_adjustment, end_of_month_rule)
        if next_d >= maturity:
            dates.append(maturity)
            break
        dates.append(next_d)
        current = next_d
    return dates


# Legacy constants removed - EUR market conventions are now hardcoded in standalone functions
# Use get_spot_date(), add_tenor_months(), etc. directly instead
