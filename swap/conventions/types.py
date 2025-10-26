"""
Basic types and enums used across the scheduling system.
"""

from enum import Enum


class Frequency(Enum):
    """Payment frequencies."""

    ANNUAL = 12
    SEMIANNUAL = 6
    QUARTERLY = 3
    MONTHLY = 1
    DAILY = 0.08333333333333333

    def months(self) -> int:
        return self.value


class BusinessDayAdjustment(Enum):
    """Business day adjustment rules."""

    NO_ADJUSTMENT = "NO_ADJUSTMENT"
    FOLLOWING = "FOLLOWING"
    MODIFIED_FOLLOWING = "MODIFIED_FOLLOWING"
    PRECEDING = "PRECEDING"
    MODIFIED_PRECEDING = "MODIFIED_PRECEDING"


class StubType(Enum):
    """Stub period types for schedule generation."""

    NO_STUB = "NO_STUB"
    SHORT_INITIAL = "SHORT_INITIAL"
    LONG_INITIAL = "LONG_INITIAL"
    SHORT_FINAL = "SHORT_FINAL"
    LONG_FINAL = "LONG_FINAL"

class RollConvention(Enum):
    """Roll convention for date adjustments."""

    BACKWARD_EOM = "BACKWARD_EOM"

class CalendarType(Enum):
    """Predefined calendars."""

    TARGET = "TARGET"
    USNY = "USNY"
    UK = "UK"

class RefereceRate(Enum):
    """Reference rate types."""

    EURIBOR6M = "EURIBOR6M"
    EURIBOR3M = "EURIBOR3M"
    ESTR = "ESTR"
    SOFR = "SOFR"
    SONIA = "SONIA"
    SORA = "SORA"
    TONA = "TONA"
    KOFR = "KOFR"
    HIBOR = "HIBOR"
    SHIBOR = "SHIBOR"
    TIBOR = "TIBOR"