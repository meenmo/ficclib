"""
Market quote schemas for different bootstrap processes.
"""

from dataclasses import dataclass
from typing import Optional, Union

from ficclib.swap.instruments.deposit import DepositConvention
from ficclib.swap.instruments.swap import SwapLegConvention


@dataclass
class Quote:
    """Unified quote for both OIS and IBOR bootstrap using convention-based approach."""

    tenor: str
    rate: float
    instrument: Union[SwapLegConvention, DepositConvention]



@dataclass
class IborTargetEntry:
    """Target validation entry for IBOR bootstrap results."""

    tenor: str
    zero_rate: float
    discount: float
    maturity: Optional[str] = None


@dataclass
class OISTargetEntry:
    """Target validation entry for OIS bootstrap results."""

    tenor: str
    expected_date: str
    zero_rate: float


# Generic target entry (flexible)
@dataclass
class TargetEntry:
    """Generic target validation entry for bootstrap results."""

    tenor: str
    zero_rate: float
    discount: Optional[float] = None
    expected_date: Optional[str] = None
    maturity: Optional[str] = None


# Legacy support - will be phased out
from . import RateType


@dataclass
class LegacyQuote:
    """Legacy quote format using primitive fields (being phased out)."""

    tenor: str
    rate: float
    day_count: Optional[str] = None
    rate_type: Optional[RateType] = None


# Quote is now the primary unified type