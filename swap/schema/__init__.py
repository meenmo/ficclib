"""
Market data schemas for EUR basis swap engine.
"""

# Import all core types for backward compatibility
from .enums import BusinessDayRule, Calendar, Frequency, RateType
from .quotes import IborTargetEntry, OISTargetEntry, Quote, TargetEntry

__all__ = [
    # Enums
    "Frequency",
    "BusinessDayRule",
    "Calendar",
    "RateType",
    # Quote types
    "TargetEntry",
    "IborTargetEntry",
    "OISTargetEntry",
    "Quote",  # Default alias
]
