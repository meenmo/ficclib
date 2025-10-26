"""
Base abstractions for data loading.

Defines interfaces for data sources and quote filters following SOLID principles.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import List, Protocol, runtime_checkable

from ficclib.swap.schema.quotes import Quote


@runtime_checkable
class DataSource(Protocol):
    """
    Protocol for market data sources.

    Defines interface for loading market quotes from any source (DB, file, API, etc.).
    Follows Interface Segregation and Dependency Inversion principles.
    """

    def load_ois_quotes(
        self,
        curve_date: date,
        reference_index: str = "ESTR",
        source: str = "BGN"
    ) -> List[Quote]:
        """
        Load OIS quotes for a specific date.

        Args:
            curve_date: Date for which to load quotes
            reference_index: Reference index (e.g., "ESTR", "SOFR")
            source: Data source identifier (e.g., "BGN", "BGN")

        Returns:
            List of Quote objects
        """
        ...

    def load_ibor_quotes(
        self,
        curve_date: date,
        reference_index: str = "EURIBOR3M",
        source: str = "BGN"
    ) -> List[Quote]:
        """
        Load IBOR quotes for a specific date.

        Args:
            curve_date: Date for which to load quotes
            reference_index: Reference index (e.g., "EURIBOR3M", "EURIBOR6M")
            source: Data source identifier

        Returns:
            List of Quote objects
        """
        ...


@runtime_checkable
class QuoteFilter(Protocol):
    """
    Protocol for filtering market quotes.

    Allows composable filtering strategies.
    """

    def filter(self, quotes: List[Quote]) -> List[Quote]:
        """
        Filter quotes based on implementation-specific criteria.

        Args:
            quotes: List of quotes to filter

        Returns:
            Filtered list of quotes
        """
        ...


class BaseDataSource(ABC):
    """
    Abstract base class for data sources.

    Provides common functionality for concrete implementations.
    """

    def __init__(self):
        """Initialize data source."""
        self._filters: List[QuoteFilter] = []

    def add_filter(self, filter_instance: QuoteFilter) -> None:
        """
        Add a filter to be applied when loading quotes.

        Args:
            filter_instance: Filter to add
        """
        self._filters.append(filter_instance)

    def _apply_filters(self, quotes: List[Quote]) -> List[Quote]:
        """
        Apply all registered filters to quotes.

        Args:
            quotes: Quotes to filter

        Returns:
            Filtered quotes
        """
        result = quotes
        for filter_instance in self._filters:
            result = filter_instance.filter(result)
        return result

    @abstractmethod
    def load_ois_quotes(
        self,
        curve_date: date,
        reference_index: str = "ESTR",
        source: str = "BGN"
    ) -> List[Quote]:
        """Load OIS quotes (to be implemented by subclasses)."""
        pass

    @abstractmethod
    def load_ibor_quotes(
        self,
        curve_date: date,
        reference_index: str = "EURIBOR3M",
        source: str = "BGN"
    ) -> List[Quote]:
        """Load IBOR quotes (to be implemented by subclasses)."""
        pass


class BaseFilter(ABC):
    """
    Abstract base class for quote filters.

    Provides template for filter implementations.
    """

    @abstractmethod
    def filter(self, quotes: List[Quote]) -> List[Quote]:
        """
        Filter quotes based on specific criteria.

        Args:
            quotes: Quotes to filter

        Returns:
            Filtered quotes
        """
        pass
