"""Base bootstrap framework for OIS and IBOR curve construction."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Dict, Generic, List, Optional, TypeVar

from ficclib.swap.business_calendar.date_calculator import get_spot_date
from ficclib.swap.conventions.daycount import get_day_count_convention

T = TypeVar('T')  # Quote type
C = TypeVar('C')  # Curve type

logger = logging.getLogger(__name__)


@dataclass
class BootstrapConfig:
    """Configuration for bootstrap process."""

    interpolation_method: str = "STEP_FORWARD_CONTINUOUS"
    day_count_convention: str = "ACT/365F"
    calendar: str = "TARGET"
    verbose: bool = False


class QuoteProcessor:
    """Utility class for processing and validating market quotes."""

    @staticmethod
    def validate_quotes(quotes: List[T]) -> None:
        """
        Validate quote list for bootstrap.

        Args:
            quotes: List of market quotes

        Raises:
            ValueError: If quotes are invalid
        """
        if not quotes:
            raise ValueError("Need at least one quote to bootstrap")

        if len(quotes) < 2:
            raise ValueError(
                "Need at least two quotes for meaningful curve construction"
            )

    @staticmethod
    def sort_quotes_by_maturity(
        quotes: List[T],
        key_func=None
    ) -> List[T]:
        """
        Sort quotes by maturity date.

        Args:
            quotes: List of quotes to sort
            key_func: Optional custom key function

        Returns:
            Sorted list of quotes
        """
        if key_func is None:
            # Assume quotes have maturity_date attribute
            def key_func(q):
                return q.maturity_date

        return sorted(quotes, key=key_func)

    @staticmethod
    def filter_duplicate_tenors(quotes: List[T]) -> List[T]:
        """
        Remove duplicate tenors, keeping the most recent quote.

        Args:
            quotes: List of quotes

        Returns:
            Filtered list without duplicates
        """
        seen_tenors = {}
        for quote in quotes:
            tenor = getattr(quote, 'tenor', None)
            if tenor:
                seen_tenors[tenor] = quote

        return list(seen_tenors.values())


class BaseBootstrapper(ABC, Generic[T, C]):
    """
    Abstract base class for curve bootstrappers.

    Provides common functionality for OIS and IBOR bootstrapping:
    - Reference date management
    - Spot date calculation
    - Quote validation
    - Day count convention setup
    - Common configuration

    Type Parameters:
        T: Quote type (e.g., OISQuote, IBORQuote)
        C: Curve type (e.g., OISDiscountCurve, IborProjectionCurve)
    """

    def __init__(
        self,
        reference_date: date,
        config: Optional[BootstrapConfig] = None
    ):
        """
        Initialize bootstrapper.

        Args:
            reference_date: Curve valuation date
            config: Bootstrap configuration (optional)
        """
        self.reference_date = reference_date
        self.spot_date = get_spot_date(reference_date)
        self.config = config or BootstrapConfig()

        # Setup day count conventions
        self._day_count = get_day_count_convention(
            self.config.day_count_convention
        )
        self._time_axis = get_day_count_convention("ACT/365F")

        # Storage for results
        self._pillars: Dict[date, float] = {}

    def _calculate_year_fraction(
        self,
        start_date: date,
        end_date: date
    ) -> float:
        """
        Calculate year fraction between dates.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Year fraction
        """
        return self._time_axis.year_fraction(start_date, end_date)

    def _add_pillar(self, pillar_date: date, value: float) -> None:
        """
        Add a pillar point to the curve.

        Args:
            pillar_date: Date of the pillar
            value: Value at the pillar (DF or zero rate)
        """
        self._pillars[pillar_date] = value

    def _get_pillar(self, pillar_date: date) -> Optional[float]:
        """
        Get pillar value at specific date.

        Args:
            pillar_date: Date to query

        Returns:
            Pillar value if exists, None otherwise
        """
        return self._pillars.get(pillar_date)

    def _log_convention_info(
        self,
        floating_convention,
        fixed_convention=None
    ) -> None:
        """
        Log convention information (if verbose).

        Args:
            floating_convention: Floating leg convention
            fixed_convention: Fixed leg convention (optional)
        """
        if not self.config.verbose:
            return

        logger.info(
            "   Using floating leg convention: %s",
            getattr(floating_convention, "reference_rate", "UNKNOWN"),
        )
        logger.info(
            "   Pay frequency: %s, Reset frequency: %s",
            getattr(floating_convention, "pay_frequency", "UNKNOWN"),
            getattr(floating_convention, "reset_frequency", "UNKNOWN"),
        )
        logger.info(
            "   Floating day count: %s, Pay delay: %s days",
            getattr(floating_convention, "day_count", "UNKNOWN"),
            getattr(floating_convention, "pay_delay_days", "UNKNOWN"),
        )

        if fixed_convention:
            logger.info("   Fixed day count: %s", getattr(fixed_convention, "day_count", "UNKNOWN"))

    @abstractmethod
    def bootstrap(self, quotes: List[T], **kwargs) -> C:
        """
        Bootstrap curve from market quotes.

        Args:
            quotes: List of market quotes
            **kwargs: Additional bootstrap parameters

        Returns:
            Bootstrapped curve
        """
        pass

    @abstractmethod
    def _process_quotes(self, quotes: List[T]) -> List[T]:
        """
        Process and validate quotes before bootstrap.

        Args:
            quotes: Raw market quotes

        Returns:
            Processed quotes ready for bootstrap
        """
        pass
