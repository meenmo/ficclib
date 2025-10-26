"""
Factory for creating data sources.

Provides convenient methods for creating and configuring data sources.
"""

from enum import Enum
from pathlib import Path

from .base import DataSource
from .filters import TenorFilter
from .loaders import JSONDataSource, PostgreSQLDataSource


class DataSourceType(Enum):
    """Supported data source types."""
    POSTGRESQL = "postgresql"
    JSON = "json"


def create_data_source(
    source_type: DataSourceType,
    **kwargs
) -> DataSource:
    """
    Create data source with appropriate configuration.

    Args:
        source_type: Type of data source to create
        **kwargs: Configuration parameters specific to source type

    Returns:
        Configured data source

    Examples:
        >>> # Create PostgreSQL source with default config
        >>> source = create_data_source(DataSourceType.POSTGRESQL)

        >>> # Create PostgreSQL source with custom config
        >>> source = create_data_source(
        ...     DataSourceType.POSTGRESQL,
        ...     host="localhost",
        ...     port=5432
        ... )

        >>> # Create JSON source
        >>> source = create_data_source(
        ...     DataSourceType.JSON,
        ...     data_directory="/path/to/data"
        ... )
    """
    if source_type == DataSourceType.POSTGRESQL:
        return PostgreSQLDataSource(
            host=kwargs.get("host"),
            port=kwargs.get("port"),
            user=kwargs.get("user"),
            password=kwargs.get("password"),
            database=kwargs.get("database"),
        )
    elif source_type == DataSourceType.JSON:
        data_directory = kwargs.get("data_directory")
        if not data_directory:
            raise ValueError("data_directory required for JSON data source")
        return JSONDataSource(data_directory=Path(data_directory))
    else:
        raise ValueError(f"Unsupported data source type: {source_type}")


def create_ois_data_source(
    source_type: DataSourceType,
    apply_standard_filters: bool = True,
    **kwargs
) -> DataSource:
    """
    Create data source configured for OIS quotes.

    Args:
        source_type: Type of data source
        apply_standard_filters: Whether to apply standard OIS tenor filters
        **kwargs: Additional configuration for data source

    Returns:
        Configured data source with OIS filters
    """
    source = create_data_source(source_type, **kwargs)

    if apply_standard_filters:
        source.add_filter(TenorFilter.for_ois())

    return source


def create_ibor_data_source(
    source_type: DataSourceType,
    tenor: str = "3M",
    apply_standard_filters: bool = True,
    **kwargs
) -> DataSource:
    """
    Create data source configured for IBOR quotes.

    Args:
        source_type: Type of data source
        tenor: IBOR tenor ("3M" or "6M")
        apply_standard_filters: Whether to apply standard IBOR tenor filters
        **kwargs: Additional configuration for data source

    Returns:
        Configured data source with IBOR filters
    """
    source = create_data_source(source_type, **kwargs)

    if apply_standard_filters:
        if tenor == "3M":
            source.add_filter(TenorFilter.for_ibor_3m())
        elif tenor == "6M":
            source.add_filter(TenorFilter.for_ibor_6m())
        else:
            raise ValueError(f"Unsupported IBOR tenor: {tenor}")

    return source
