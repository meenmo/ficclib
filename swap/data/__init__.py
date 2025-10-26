"""
Data loading module for market quotes.

Provides abstractions and implementations for loading market data from various sources.
"""

from .base import BaseDataSource, BaseFilter, DataSource, QuoteFilter
from .factory import (
    DataSourceType,
    create_data_source,
    create_ibor_data_source,
    create_ois_data_source,
)
from .filters import CompositeFilter, CustomFilter, RateRangeFilter, TenorFilter
from .loaders import JSONDataSource, PostgreSQLDataSource

__all__ = [
    # Base abstractions
    "DataSource",
    "QuoteFilter",
    "BaseDataSource",
    "BaseFilter",
    # Concrete implementations
    "PostgreSQLDataSource",
    "JSONDataSource",
    # Filters
    "TenorFilter",
    "RateRangeFilter",
    "CompositeFilter",
    "CustomFilter",
    # Factory
    "create_data_source",
    "create_ois_data_source",
    "create_ibor_data_source",
    "DataSourceType",
]
