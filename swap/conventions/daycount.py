"""
QuantLib-backed day count convention implementations.

This module provides a drop-in replacement for the custom day count conventions,
using QuantLib's industry-standard implementations for accuracy and completeness.
"""

from datetime import date, datetime
from typing import Union

import QuantLib as ql


def to_date(dt: Union[date, datetime]) -> date:
    """Convert datetime to date if needed."""
    return dt.date() if isinstance(dt, datetime) else dt


def _to_ql_date(dt: Union[date, datetime]) -> ql.Date:
    """Convert Python date/datetime to QuantLib Date."""
    py_date = to_date(dt)
    return ql.Date(py_date.day, py_date.month, py_date.year)


class DayCountConvention:
    """Base class for QuantLib-backed day count conventions."""

    def __init__(self, name: str, ql_daycount: ql.DayCounter):
        self.name = name
        self._ql_daycount = ql_daycount

    def year_fraction(
        self, start: Union[date, datetime], end: Union[date, datetime]
    ) -> float:
        """Calculate year fraction between two dates using QuantLib."""
        ql_start = _to_ql_date(start)
        ql_end = _to_ql_date(end)
        return self._ql_daycount.yearFraction(ql_start, ql_end)

    def day_count(
        self, start: Union[date, datetime], end: Union[date, datetime]
    ) -> int:
        """Calculate number of days between two dates."""
        ql_start = _to_ql_date(start)
        ql_end = _to_ql_date(end)
        return self._ql_daycount.dayCount(ql_start, ql_end)

    def __str__(self) -> str:
        return self.name


class Actual360(DayCountConvention):
    """ACT/360 day count convention.

    Used for:
    - IBOR floating legs
    - OIS fixed legs
    - Money market instruments
    """

    def __init__(self):
        super().__init__("ACT/360", ql.Actual360())


class Actual365Fixed(DayCountConvention):
    """ACT/365F (ACT/365 Fixed) day count convention.

    Used for:
    - Some fixed IRS legs (market dependent)
    - GBP markets primarily
    """

    def __init__(self):
        super().__init__("ACT/365F", ql.Actual365Fixed())


class Actual360Adjusted(DayCountConvention):
    """ACT/360A (Actual/360 Adjusted - No-Leap) day count convention.

    Note: QuantLib doesn't have a direct equivalent, so we fall back to
    custom implementation for this specialized convention.
    """

    def __init__(self):
        # Use Actual360 as base, override year_fraction
        super().__init__("ACT/360A", ql.Actual360())

    def year_fraction(
        self, start: Union[date, datetime], end: Union[date, datetime]
    ) -> float:
        """Calculate year fraction using actual days excluding Feb 29 / 360."""
        import calendar

        start_date = to_date(start)
        end_date = to_date(end)

        if start_date >= end_date:
            return 0.0

        actual_days = (end_date - start_date).days

        # Count number of Feb 29 occurrences in [start_date, end_date)
        num_feb29 = 0
        for year in range(start_date.year, end_date.year + 1):
            if calendar.isleap(year):
                feb29 = date(year, 2, 29)
                if start_date <= feb29 < end_date:
                    num_feb29 += 1

        adjusted_days = actual_days - num_feb29
        return adjusted_days / 360.0


class Thirty360European(DayCountConvention):
    """30E/360 (30/360 European) day count convention.

    Used for:
    - Fixed IRS legs (common convention)
    - Government bonds
    """

    def __init__(self):
        super().__init__("30E/360", ql.Thirty360(ql.Thirty360.European))


class Thirty360US(DayCountConvention):
    """30U/360 (30/360 US - Bond Basis) day count convention.

    Used for:
    - US corporate bonds
    - Some USD swaps
    """

    def __init__(self):
        # QuantLib's BondBasis is the standard US 30/360
        super().__init__("30U/360", ql.Thirty360(ql.Thirty360.BondBasis))


class ActualActualISDA(DayCountConvention):
    """ACT/ACT ISDA day count convention.

    Used for:
    - Some government bonds
    - USD Treasury bonds
    """

    def __init__(self):
        super().__init__("ACT/ACT", ql.ActualActual(ql.ActualActual.ISDA))


# Pre-defined day count convention instances
ACT_360 = Actual360()
ACT_365F = Actual365Fixed()
THIRTY_360E = Thirty360European()
THIRTY_360U = Thirty360US()
ACT_ACT = ActualActualISDA()
ACT_360A = Actual360Adjusted()

# Registry
DAY_COUNT_CONVENTIONS = {
    "ACT/360": ACT_360,
    "ACTUAL/360": ACT_360,
    "ACT/360A": ACT_360A,
    "ACTUAL/360A": ACT_360A,
    "ACT/365F": ACT_365F,
    "ACT/365": ACT_365F,
    "ACTUAL/365F": ACT_365F,
    "30E/360": THIRTY_360E,
    "30/360E": THIRTY_360E,
    "30/360 EUROPEAN": THIRTY_360E,
    "30U/360A": THIRTY_360U,
    "30U/360": THIRTY_360U,
    "30/360": THIRTY_360U,
    "30/360 US": THIRTY_360U,
    "30/360 AMERICAN": THIRTY_360U,
    "ACT/ACT": ACT_ACT,
    "ACTUAL/ACTUAL": ACT_ACT,
    "ACT/ACT ISDA": ACT_ACT,
}


def get_day_count_convention(name: str) -> DayCountConvention:
    """Get a day count convention by name."""
    name_upper = name.upper()
    if name_upper not in DAY_COUNT_CONVENTIONS:
        raise ValueError(
            f"Unknown day count convention: {name}. "
            f"Available: {list(DAY_COUNT_CONVENTIONS.keys())}"
        )
    return DAY_COUNT_CONVENTIONS[name_upper]
