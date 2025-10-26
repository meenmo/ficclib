"""
Core enumeration types for the EUR basis swap engine.
"""

from enum import Enum


class Frequency(Enum):
    """Payment frequencies."""

    ANNUAL = "ANNUAL"
    SEMIANNUAL = "SEMIANNUAL"
    QUARTERLY = "QUARTERLY"
    MONTHLY = "MONTHLY"


class BusinessDayRule(Enum):
    """Business day adjustment rules."""

    MODFOLLOW = "MODFOLLOW"
    FOLLOWING = "FOLLOWING"
    PRECEDING = "PRECEDING"
    NO_ADJUSTMENT = "NO_ADJUSTMENT"


class Calendar(Enum):
    """Holiday calendars."""

    TARGET = "TARGET"
    WEEKEND = "WEEKEND"


class RateType(Enum):
    """Instrument type for input quotes."""

    DEPOSIT = "DEPOSIT"
    SWAP = "SWAP"