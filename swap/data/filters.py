"""
Quote filtering strategies.

Provides composable filters for market quotes.
"""

from typing import Callable, List, Optional, Set

from ficclib.swap.schema.quotes import Quote

from .base import BaseFilter


class TenorFilter(BaseFilter):
    """
    Filter quotes by allowed tenors.

    Useful for excluding specific maturities or standardizing curve pillars.
    """

    # Predefined tenor sets for common use cases
    OIS_STANDARD_TENORS = {
        "1W", "2W", "1M", "2M", "3M", "4M", "5M", "6M", "7M", "8M", "9M", "10M", "11M",
        "1Y", "18M", "2Y", "3Y", "4Y", "5Y", "6Y", "7Y", "8Y", "9Y", "10Y", "11Y", "12Y",
        "15Y", "20Y", "25Y", "30Y", "40Y", "50Y"
    }

    IBOR_3M_STANDARD_TENORS = {
        "3M", "1Y", "2Y", "3Y", "4Y", "5Y", "6Y", "7Y", "8Y", "9Y", "10Y", "11Y", "12Y",
        "15Y", "20Y", "25Y", "30Y", "40Y", "50Y"
    }

    IBOR_6M_STANDARD_TENORS = {
        "6M", "1Y", "18M", "2Y", "3Y", "4Y", "5Y", "6Y", "7Y", "8Y", "9Y", "10Y", "11Y",
        "12Y", "15Y", "20Y", "25Y", "30Y", "40Y", "50Y"
    }

    def __init__(self, allowed_tenors: Set[str]):
        """
        Initialize tenor filter.

        Args:
            allowed_tenors: Set of allowed tenor strings (e.g., {"1Y", "2Y", "5Y"})
        """
        self.allowed_tenors = allowed_tenors

    @classmethod
    def for_ois(cls) -> "TenorFilter":
        """Create filter with standard OIS tenors."""
        return cls(cls.OIS_STANDARD_TENORS)

    @classmethod
    def for_ibor_3m(cls) -> "TenorFilter":
        """Create filter with standard IBOR 3M tenors."""
        return cls(cls.IBOR_3M_STANDARD_TENORS)

    @classmethod
    def for_ibor_6m(cls) -> "TenorFilter":
        """Create filter with standard IBOR 6M tenors."""
        return cls(cls.IBOR_6M_STANDARD_TENORS)

    def filter(self, quotes: List[Quote]) -> List[Quote]:
        """
        Filter quotes by allowed tenors.

        Args:
            quotes: Quotes to filter

        Returns:
            Quotes with tenors in allowed set
        """
        return [q for q in quotes if q.tenor in self.allowed_tenors]


class RateRangeFilter(BaseFilter):
    """
    Filter quotes by rate range.

    Useful for excluding outliers or invalid rates.
    """

    def __init__(
        self,
        min_rate: Optional[float] = None,
        max_rate: Optional[float] = None
    ):
        """
        Initialize rate range filter.

        Args:
            min_rate: Minimum allowed rate (inclusive), None for no lower bound
            max_rate: Maximum allowed rate (inclusive), None for no upper bound
        """
        self.min_rate = min_rate
        self.max_rate = max_rate

    def filter(self, quotes: List[Quote]) -> List[Quote]:
        """
        Filter quotes by rate range.

        Args:
            quotes: Quotes to filter

        Returns:
            Quotes within rate range
        """
        result = quotes

        if self.min_rate is not None:
            result = [q for q in result if q.rate >= self.min_rate]

        if self.max_rate is not None:
            result = [q for q in result if q.rate <= self.max_rate]

        return result


class CustomFilter(BaseFilter):
    """
    Filter quotes using custom predicate function.

    Provides maximum flexibility for ad-hoc filtering.
    """

    def __init__(self, predicate: Callable[[Quote], bool]):
        """
        Initialize custom filter.

        Args:
            predicate: Function that returns True if quote should be kept
        """
        self.predicate = predicate

    def filter(self, quotes: List[Quote]) -> List[Quote]:
        """
        Filter quotes using predicate.

        Args:
            quotes: Quotes to filter

        Returns:
            Quotes for which predicate returns True
        """
        return [q for q in quotes if self.predicate(q)]


class CompositeFilter(BaseFilter):
    """
    Combine multiple filters using AND logic.

    Allows building complex filtering pipelines.
    """

    def __init__(self, filters: List[BaseFilter]):
        """
        Initialize composite filter.

        Args:
            filters: List of filters to apply in sequence
        """
        self.filters = filters

    def add_filter(self, filter_instance: BaseFilter) -> None:
        """
        Add a filter to the pipeline.

        Args:
            filter_instance: Filter to add
        """
        self.filters.append(filter_instance)

    def filter(self, quotes: List[Quote]) -> List[Quote]:
        """
        Apply all filters in sequence.

        Args:
            quotes: Quotes to filter

        Returns:
            Quotes that pass all filters
        """
        result = quotes
        for f in self.filters:
            result = f.filter(result)
        return result
