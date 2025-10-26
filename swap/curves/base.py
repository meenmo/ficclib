"""
Base curve classes and protocols for the EUR basis engine.
"""

import math
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Protocol, Union

from ficclib.swap.conventions.daycount import (
    DayCountConvention,
    get_day_count_convention,
)


class Curve(Protocol):
    """Protocol defining the interface for all curves."""

    def df(self, t: Union[datetime, date, float]) -> float:
        """Get discount factor at time t."""
        ...

    def zero(self, t: Union[datetime, date, float]) -> float:
        """Get zero rate at time t."""
        ...

    def forward(
        self, u: Union[datetime, date, float], v: Union[datetime, date, float], dcc: str
    ) -> float:
        """Get forward rate between times u and v using day count convention."""
        ...


class BaseCurve(ABC):
    """Base implementation for yield curves."""

    def __init__(
        self,
        reference_date: date,
        name: str = "",
        time_day_count: Union[str, DayCountConvention] = "ACT/360",
    ):
        """
        Initialize base curve.

        Args:
            reference_date: Curve reference/valuation date
            name: Optional curve name for identification
            time_day_count: Day-count convention to convert dates to curve times
        """
        self.reference_date = reference_date
        self.name = name
        if isinstance(time_day_count, DayCountConvention):
            self._time_day_count = time_day_count
        else:
            self._time_day_count = get_day_count_convention(time_day_count)

    def _to_year_fraction(self, dt: Union[datetime, date, float]) -> float:
        """Convert a date or datetime to the curve's year fraction basis."""
        if isinstance(dt, (int, float)):
            return float(dt)

        if isinstance(dt, datetime):
            dt = dt.date()

        # Use the curve-specific time basis for conversion
        return self._time_day_count.year_fraction(self.reference_date, dt)

    @abstractmethod
    def df(self, t: Union[datetime, date, float]) -> float:
        """Get discount factor at time t."""
        pass

    def zero(self, t: Union[datetime, date, float]) -> float:
        """Get continuously compounded zero rate at time t."""
        time_frac = self._to_year_fraction(t)
        if time_frac <= 0:
            return 0.0

        df_val = self.df(t)
        if df_val <= 0:
            raise ValueError(f"Non-positive discount factor: {df_val}")

        return -math.log(df_val) / time_frac

    def forward(
        self, u: Union[datetime, date, float], v: Union[datetime, date, float], dcc: str
    ) -> float:
        """Get forward rate between times u and v using day count convention."""
        # Convert to dates if needed for day count calculation
        if isinstance(u, (int, float)):
            # For float inputs, assume they represent years from reference
            days_u = int(u * 365.25)
            date_u = self.reference_date + timedelta(days=days_u)
        else:
            date_u = u.date() if isinstance(u, datetime) else u

        if isinstance(v, (int, float)):
            days_v = int(v * 365.25)
            date_v = self.reference_date + timedelta(days=days_v)
        else:
            date_v = v.date() if isinstance(v, datetime) else v

        # Get discount factors
        df_u = self.df(u)
        df_v = self.df(v)

        # Get year fraction using specified day count convention
        day_count = get_day_count_convention(dcc)
        alpha = day_count.year_fraction(date_u, date_v)

        if alpha <= 0:
            raise ValueError("Forward period must be positive")

        # Calculate simply compounded forward rate
        return (df_u / df_v - 1) / alpha

    def __str__(self) -> str:
        return (
            f"{self.__class__.__name__}({self.name})"
            if self.name
            else self.__class__.__name__
        )


class DiscountCurve(BaseCurve):
    """Base class for discount curves (OIS curves)."""

    def __init__(
        self,
        reference_date: date,
        name: str = "",
        time_day_count: Union[str, DayCountConvention] = "ACT/360",
    ):
        super().__init__(reference_date, name, time_day_count)
        self.curve_type = "DISCOUNT"


class ProjectionCurve(BaseCurve):
    """Base class for projection curves (IBOR curves)."""

    def __init__(
        self,
        reference_date: date,
        index_name: str,
        name: str = "",
        time_day_count: Union[str, DayCountConvention] = "ACT/360",
    ):
        """
        Initialize projection curve.

        Args:
            reference_date: Curve reference date
            index_name: Name of the index (e.g., "EUR-EURIBOR-3M")
            name: Optional curve name
        """
        super().__init__(reference_date, name, time_day_count)
        self.index_name = index_name
        self.curve_type = "PROJECTION"

    @abstractmethod
    def px(self, t: Union[datetime, date, float]) -> float:
        """
        Get pseudo-discount factor P_x(t) for the index.

        This is the "discount factor" used for projecting forward rates
        of the specific tenor, but discounting is done with the OIS curve.
        """
        pass

    def df(self, t: Union[datetime, date, float]) -> float:
        """For projection curves, df() returns the pseudo-discount factor."""
        return self.px(t)


from datetime import timedelta  # Import needed for forward method
