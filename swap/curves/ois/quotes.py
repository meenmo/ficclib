"""
OIS market quote data structures.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class OISQuote:
    """Market quote for OIS instrument."""

    tenor: str  # "ON", "TN", "1W", "2W", "1M", "2M", etc.
    maturity_date: Optional[date]  # If None, calculated from tenor
    rate: float  # Par rate in decimal (e.g., 0.035 for 3.5%)
    quote_type: str = "PAR_RATE"  # "PAR_RATE", "DISCOUNT_FACTOR"

    def __post_init__(self):
        """Validate quote after initialization."""
        if self.quote_type not in ["PAR_RATE", "DISCOUNT_FACTOR"]:
            raise ValueError(f"Invalid quote_type: {self.quote_type}")