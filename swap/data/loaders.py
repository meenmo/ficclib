"""
Concrete data source implementations.

Provides loaders for PostgreSQL, JSON, and other data sources.
"""

import json
import os
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from ficclib.swap.schema.quotes import Quote

from .base import BaseDataSource


class PostgreSQLDataSource(BaseDataSource):
    """
    Load market quotes from PostgreSQL database.

    Connects to marketdata.swap table and retrieves quotes.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        """
        Initialize PostgreSQL data source.

        Args:
            host: Database host (defaults to env var POSTGRES_HOST)
            port: Database port (defaults to env var POSTGRES_PORT)
            user: Database user (defaults to env var POSTGRES_USER)
            password: Database password (defaults to env var POSTGRES_PASSWORD)
            database: Database name (defaults to env var POSTGRES_DB)
        """
        super().__init__()
        self.config = {
            "host": host or os.getenv("POSTGRES_HOST", "192.168.31.249"),
            "port": port or int(os.getenv("POSTGRES_PORT", "1013")),
            "user": user or os.getenv("POSTGRES_USER", "airflow"),
            "password": password or os.getenv("POSTGRES_PASSWORD", "airflow"),
            "database": database or os.getenv("POSTGRES_DB", "airflow"),
            "sslmode": "disable",
        }

    def _fetch_quotes(
        self,
        curve_date: date,
        curve_type: str,
        reference_index: str,
        source: str,
    ) -> List[Dict]:
        """
        Fetch raw quotes from database.

        Args:
            curve_date: Date for which to fetch quotes
            curve_type: Type of curve (OIS or IRS)
            reference_index: Reference index
            source: Data source identifier

        Returns:
            List of quote dictionaries
        """
        try:
            import psycopg2
        except ImportError:
            raise ImportError(
                "psycopg2 is required for PostgreSQL data source. "
                "Install it with: pip install psycopg2-binary"
            )

        conn = psycopg2.connect(**self.config)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT quotes
                    FROM market_data.swap
                    WHERE curve_date = %s
                      AND curve_type = %s
                      AND reference_index = %s
                      AND source = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (curve_date, curve_type, reference_index, source),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError(
                        f"No curve found for {curve_date}, {curve_type}, "
                        f"{reference_index}, {source}"
                    )
                quotes_data = row[0]
                return quotes_data.get("quotes", [])
        finally:
            conn.close()

    def load_ois_quotes(
        self,
        curve_date: date,
        reference_index: str = "ESTR",
        source: str = "BGN",
    ) -> List[Quote]:
        """
        Load OIS quotes from PostgreSQL.

        Args:
            curve_date: Date for which to load quotes
            reference_index: Reference index (default: ESTR)
            source: Data source identifier (default: BGN)

        Returns:
            List of Quote objects with filters applied
        """
        # Import here to avoid circular dependency
        from ficclib.swap.instruments.swap import ESTR_FLOATING

        raw_quotes = self._fetch_quotes(
            curve_date, "OIS", reference_index, source
        )

        quotes = [
            Quote(tenor=q["tenor"], rate=q["rate"], instrument=ESTR_FLOATING)
            for q in raw_quotes
        ]

        return self._apply_filters(quotes)

    def load_ibor_quotes(
        self,
        curve_date: date,
        reference_index: str = "EURIBOR3M",
        source: str = "BGN",
    ) -> List[Quote]:
        """
        Load IBOR quotes from PostgreSQL.

        Args:
            curve_date: Date for which to load quotes
            reference_index: Reference index (default: EURIBOR3M)
            source: Data source identifier (default: BGN)

        Returns:
            List of Quote objects with filters applied
        """
        # Import here to avoid circular dependency
        from ficclib.swap.instruments.deposit import EURIBOR3M_DEPOSIT, EURIBOR6M_DEPOSIT
        from ficclib.swap.instruments.swap import EURIBOR3M_FIXED, EURIBOR6M_FIXED

        raw_quotes = self._fetch_quotes(
            curve_date, "IRS", reference_index, source
        )

        # Determine instrument convention based on reference index
        if "3M" in reference_index.upper():
            swap_instrument = EURIBOR3M_FIXED
            deposit_instrument = EURIBOR3M_DEPOSIT
        elif "6M" in reference_index.upper():
            swap_instrument = EURIBOR6M_FIXED
            deposit_instrument = EURIBOR6M_DEPOSIT
        else:
            raise ValueError(f"Unknown reference index: {reference_index}")

        quotes = []
        for q in raw_quotes:
            tenor = q["tenor"]
            rate = q["rate"]

            # Use deposit convention for short tenors, swap for longer
            if tenor.endswith("M") and not tenor.startswith("1"):
                # Months < 1Y use deposit
                instrument = deposit_instrument
            else:
                instrument = swap_instrument

            quotes.append(Quote(tenor=tenor, rate=rate, instrument=instrument))

        return self._apply_filters(quotes)


class JSONDataSource(BaseDataSource):
    """
    Load market quotes from JSON files.

    Useful for testing, backtesting, or when database is unavailable.
    """

    def __init__(self, data_directory: Path):
        """
        Initialize JSON data source.

        Args:
            data_directory: Directory containing JSON quote files
        """
        super().__init__()
        self.data_directory = Path(data_directory)

    def _load_json_file(self, filepath: Path) -> Dict:
        """
        Load and parse JSON file.

        Args:
            filepath: Path to JSON file

        Returns:
            Parsed JSON data
        """
        with open(filepath, "r") as f:
            return json.load(f)

    def _get_quote_file(
        self,
        curve_date: date,
        curve_type: str,
        reference_index: str,
    ) -> Path:
        """
        Get path to quote file for given parameters.

        Args:
            curve_date: Date for quotes
            curve_type: OIS or IRS
            reference_index: Index name

        Returns:
            Path to JSON file
        """
        filename = (
            f"{curve_date.isoformat()}_"
            f"{curve_type}_{reference_index}.json"
        )
        return self.data_directory / filename

    def load_ois_quotes(
        self,
        curve_date: date,
        reference_index: str = "ESTR",
        source: str = "BGN",
    ) -> List[Quote]:
        """
        Load OIS quotes from JSON file.

        Args:
            curve_date: Date for which to load quotes
            reference_index: Reference index (default: ESTR)
            source: Data source identifier (ignored for JSON)

        Returns:
            List of Quote objects with filters applied
        """
        from ficclib.swap.instruments.swap import ESTR_FLOATING

        filepath = self._get_quote_file(curve_date, "OIS", reference_index)
        data = self._load_json_file(filepath)

        quotes = [
            Quote(tenor=q["tenor"], rate=q["rate"], instrument=ESTR_FLOATING)
            for q in data.get("quotes", [])
        ]

        return self._apply_filters(quotes)

    def load_ibor_quotes(
        self,
        curve_date: date,
        reference_index: str = "EURIBOR3M",
        source: str = "BGN",
    ) -> List[Quote]:
        """
        Load IBOR quotes from JSON file.

        Args:
            curve_date: Date for which to load quotes
            reference_index: Reference index (default: EURIBOR3M)
            source: Data source identifier (ignored for JSON)

        Returns:
            List of Quote objects with filters applied
        """
        from ficclib.swap.instruments.deposit import EURIBOR3M_DEPOSIT, EURIBOR6M_DEPOSIT
        from ficclib.swap.instruments.swap import EURIBOR3M_FIXED, EURIBOR6M_FIXED

        filepath = self._get_quote_file(curve_date, "IRS", reference_index)
        data = self._load_json_file(filepath)

        # Determine instrument convention
        if "3M" in reference_index.upper():
            swap_instrument = EURIBOR3M_FIXED
            deposit_instrument = EURIBOR3M_DEPOSIT
        elif "6M" in reference_index.upper():
            swap_instrument = EURIBOR6M_FIXED
            deposit_instrument = EURIBOR6M_DEPOSIT
        else:
            raise ValueError(f"Unknown reference index: {reference_index}")

        quotes = []
        for q in data.get("quotes", []):
            tenor = q["tenor"]
            rate = q["rate"]

            # Use deposit for short tenors, swap for longer
            if tenor.endswith("M") and not tenor.startswith("1"):
                instrument = deposit_instrument
            else:
                instrument = swap_instrument

            quotes.append(Quote(tenor=tenor, rate=rate, instrument=instrument))

        return self._apply_filters(quotes)
