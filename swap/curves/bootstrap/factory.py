"""
Factory pattern for unified curve construction.

Provides centralized curve creation interface with QuantLib mapping utilities.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum

# Lazy imports to avoid circular dependencies
from typing import TYPE_CHECKING, List, Optional, Union

import QuantLib as ql

from ficclib.swap.curves.discount import OISDiscountCurve
from ficclib.swap.curves.projection import IborProjectionCurve

from .base import BootstrapConfig

if TYPE_CHECKING:
    pass


class CurveType(Enum):
    """Supported curve types."""
    OIS = "OIS"
    IBOR = "IBOR"


class Calendar(Enum):
    """Supported calendars."""
    TARGET = "TARGET"
    USNY = "USNY"
    UK = "UK"


class DayCount(Enum):
    """Supported day count conventions."""
    ACT_360 = "ACT/360"
    ACT_365F = "ACT/365F"
    THIRTY_360 = "30/360"


class BusinessDayConvention(Enum):
    """Supported business day conventions."""
    MODIFIED_FOLLOWING = "MODIFIED_FOLLOWING"
    FOLLOWING = "FOLLOWING"
    PRECEDING = "PRECEDING"
    UNADJUSTED = "UNADJUSTED"


class Frequency(Enum):
    """Supported payment frequencies."""
    DAILY = "DAILY"
    ANNUAL = "ANNUAL"
    SEMIANNUAL = "SEMIANNUAL"
    QUARTERLY = "QUARTERLY"
    MONTHLY = "MONTHLY"


@dataclass
class CurveConfig:
    """Configuration for curve construction."""

    curve_type: CurveType
    reference_date: date
    interpolation_method: str = "STEP_FORWARD_CONTINUOUS"
    calendar: Calendar = Calendar.TARGET
    day_count: DayCount = DayCount.ACT_365F
    verbose: bool = False


class QuantLibMapper:
    """Centralized QuantLib object mapping utilities."""

    @staticmethod
    def map_calendar(calendar: Union[Calendar, str]) -> ql.Calendar:
        """
        Map calendar to QuantLib Calendar object.

        Args:
            calendar: Calendar enum or string name

        Returns:
            QuantLib Calendar object
        """
        if isinstance(calendar, str):
            calendar = Calendar[calendar]

        calendar_map = {
            Calendar.TARGET: ql.TARGET(),
            Calendar.USNY: ql.UnitedStates(ql.UnitedStates.GovernmentBond),
            Calendar.UK: ql.UnitedKingdom(),
        }
        return calendar_map.get(calendar, ql.TARGET())

    @staticmethod
    def map_day_count(day_count: Union[DayCount, str]) -> ql.DayCounter:
        """
        Map day count convention to QuantLib DayCounter.

        Args:
            day_count: DayCount enum or string name

        Returns:
            QuantLib DayCounter object
        """
        if isinstance(day_count, str):
            day_count = DayCount[day_count.replace("/", "_")]

        day_count_map = {
            DayCount.ACT_360: ql.Actual360(),
            DayCount.ACT_365F: ql.Actual365Fixed(),
            DayCount.THIRTY_360: ql.Thirty360(),
        }
        return day_count_map.get(day_count, ql.Actual365Fixed())

    @staticmethod
    def map_business_day_convention(
        bdc: Union[BusinessDayConvention, str]
    ) -> int:
        """
        Map business day convention to QuantLib.

        Args:
            bdc: BusinessDayConvention enum or string name

        Returns:
            QuantLib business day convention (int)
        """
        if isinstance(bdc, str):
            bdc = BusinessDayConvention[bdc]

        bdc_map = {
            BusinessDayConvention.MODIFIED_FOLLOWING: ql.ModifiedFollowing,
            BusinessDayConvention.FOLLOWING: ql.Following,
            BusinessDayConvention.PRECEDING: ql.Preceding,
            BusinessDayConvention.UNADJUSTED: ql.Unadjusted,
        }
        return bdc_map.get(bdc, ql.ModifiedFollowing)

    @staticmethod
    def map_frequency(frequency: Union[Frequency, str]) -> int:
        """
        Map payment frequency to QuantLib Frequency.

        Args:
            frequency: Frequency enum or string name

        Returns:
            QuantLib frequency (int)
        """
        if isinstance(frequency, str):
            frequency = Frequency[frequency]

        freq_map = {
            Frequency.DAILY: ql.Daily,
            Frequency.ANNUAL: ql.Annual,
            Frequency.SEMIANNUAL: ql.Semiannual,
            Frequency.QUARTERLY: ql.Quarterly,
            Frequency.MONTHLY: ql.Monthly,
        }
        return freq_map.get(frequency, ql.Annual)


class CurveFactory:
    """
    Factory for unified curve construction.

    Provides centralized curve creation interface with support for:
    - OIS discount curves
    - IBOR projection curves
    - Configuration-driven construction
    - QuantLib mapping utilities
    """

    def __init__(self):
        """Initialize curve factory."""
        self.mapper = QuantLibMapper()

    def create_ois_curve(
        self,
        reference_date: date,
        quotes: List,
        interpolation_method: str = "STEP_FORWARD_CONTINUOUS",
        floating_leg_convention=None,
        fixed_leg_convention=None,
        config: Optional[BootstrapConfig] = None,
    ) -> OISDiscountCurve:
        """
        Create OIS discount curve from market quotes.

        Args:
            reference_date: Curve valuation date
            quotes: List of OIS market quotes
            interpolation_method: Interpolation method
            floating_leg_convention: Floating leg convention
            fixed_leg_convention: Fixed leg convention
            config: Bootstrap configuration (optional)

        Returns:
            Bootstrapped OIS discount curve
        """
        # Lazy import to avoid circular dependency
        from ois.bootstrapper import OISBootstrapper

        bootstrapper = OISBootstrapper(reference_date, config)
        return bootstrapper.bootstrap(
            quotes,
            interpolation_method,
            floating_leg_convention,
            fixed_leg_convention,
        )

    def create_ibor_curve(
        self,
        reference_date: date,
        ois_curve: OISDiscountCurve,
        index_name: str,
        deposits: List,
        swaps: List,
        interpolation_method: str = "STEP_FORWARD_CONTINUOUS",
    ) -> IborProjectionCurve:
        """
        Create IBOR projection curve from market instruments.

        Args:
            reference_date: Curve valuation date
            ois_curve: OIS discount curve for discounting
            index_name: IBOR index name (e.g., "EURIBOR3M")
            deposits: List of deposit instruments
            swaps: List of swap instruments
            interpolation_method: Interpolation method

        Returns:
            Bootstrapped IBOR projection curve
        """
        # Import here to avoid circular dependency
        from ibor.bootstrap.engine import BootstrapEngine

        engine = BootstrapEngine(reference_date, ois_curve, index_name)

        # Bootstrap deposits first
        if deposits:
            engine.bootstrap_deposits(deposits)

        # Then bootstrap swaps
        for swap in swaps:
            engine.bootstrap_swap(swap)

        return engine.get_curve()

    def create_curve_from_config(
        self,
        config: CurveConfig,
        quotes: List,
        **kwargs
    ) -> Union[OISDiscountCurve, IborProjectionCurve]:
        """
        Create curve from configuration object.

        Args:
            config: Curve configuration
            quotes: Market quotes or instruments
            **kwargs: Additional curve-specific parameters

        Returns:
            Bootstrapped curve (OIS or IBOR)
        """
        bootstrap_config = BootstrapConfig(
            interpolation_method=config.interpolation_method,
            day_count_convention=config.day_count.value,
            calendar=config.calendar.value,
            verbose=config.verbose,
        )

        if config.curve_type == CurveType.OIS:
            return self.create_ois_curve(
                reference_date=config.reference_date,
                quotes=quotes,
                interpolation_method=config.interpolation_method,
                config=bootstrap_config,
                **kwargs
            )
        elif config.curve_type == CurveType.IBOR:
            # IBOR requires OIS curve
            ois_curve = kwargs.get("ois_curve")
            if not ois_curve:
                raise ValueError("IBOR curve requires 'ois_curve' in kwargs")

            index_name = kwargs.get("index_name", "EURIBOR3M")
            deposits = kwargs.get("deposits", [])
            swaps = quotes  # Swaps are the main quotes for IBOR

            return self.create_ibor_curve(
                reference_date=config.reference_date,
                ois_curve=ois_curve,
                index_name=index_name,
                deposits=deposits,
                swaps=swaps,
                interpolation_method=config.interpolation_method,
            )
        else:
            raise ValueError(f"Unsupported curve type: {config.curve_type}")


# Convenience factory instance
curve_factory = CurveFactory()


# Convenience functions
def create_ois_curve(
    reference_date: date,
    quotes: List,
    interpolation_method: str = "STEP_FORWARD_CONTINUOUS",
    floating_leg_convention=None,
    fixed_leg_convention=None,
) -> OISDiscountCurve:
    """
    Convenience function to create OIS curve.

    Args:
        reference_date: Curve valuation date
        quotes: List of OIS market quotes
        interpolation_method: Interpolation method
        floating_leg_convention: Floating leg convention
        fixed_leg_convention: Fixed leg convention

    Returns:
        Bootstrapped OIS discount curve
    """
    return curve_factory.create_ois_curve(
        reference_date,
        quotes,
        interpolation_method,
        floating_leg_convention,
        fixed_leg_convention,
    )


def create_ibor_curve(
    reference_date: date,
    ois_curve: OISDiscountCurve,
    index_name: str,
    deposits: List,
    swaps: List,
    interpolation_method: str = "STEP_FORWARD_CONTINUOUS",
) -> IborProjectionCurve:
    """
    Convenience function to create IBOR curve.

    Args:
        reference_date: Curve valuation date
        ois_curve: OIS discount curve for discounting
        index_name: IBOR index name
        deposits: List of deposit instruments
        swaps: List of swap instruments
        interpolation_method: Interpolation method

    Returns:
        Bootstrapped IBOR projection curve
    """
    return curve_factory.create_ibor_curve(
        reference_date,
        ois_curve,
        index_name,
        deposits,
        swaps,
        interpolation_method,
    )
