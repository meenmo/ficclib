"""
OIS curve bootstrapping implementation using QuantLib with custom fallback.

Refactored to use base bootstrap framework with clean separation of concerns.
Includes custom Python bootstrap engine for cases where QuantLib fails.
"""

import logging
import math
from datetime import date
from typing import List, Optional, Tuple

import QuantLib as ql

from ficclib.swap.business_calendar.date_calculator import compute_maturity
from ficclib.swap.conventions.daycount import get_day_count_convention
from ficclib.swap.curves.bootstrap.base import (
    BaseBootstrapper,
    BootstrapConfig,
    QuoteProcessor,
)
from ficclib.swap.curves.discount import OISDiscountCurve

from .bootstrap_engine import CustomOISBootstrapEngine, OISInstrument
from .quotes import OISQuote

logger = logging.getLogger(__name__)


class OISBootstrapper(BaseBootstrapper[OISQuote, OISDiscountCurve]):
    """Bootstrap OIS discount curve from market quotes using QuantLib."""

    def __init__(
        self,
        reference_date: date,
        config: Optional[BootstrapConfig] = None
    ):
        """
        Initialize OIS bootstrapper.

        Args:
            reference_date: Curve valuation date
            config: Bootstrap configuration (optional)
        """
        super().__init__(reference_date, config)

    def bootstrap(
        self,
        quotes: List[OISQuote],
        interpolation_method: str = "STEP_FORWARD_CONTINUOUS",
        floating_leg_convention=None,
        fixed_leg_convention=None,
        use_quantlib: bool = True,
    ) -> OISDiscountCurve:
        """
        Bootstrap OIS discount curve from quotes.

        Args:
            quotes: List of OIS market quotes
            interpolation_method: Interpolation method for curve
            floating_leg_convention: Floating leg convention (e.g., ESTR_FLOATING)
            fixed_leg_convention: Fixed leg convention (e.g., ESTR_FIXED)
            use_quantlib: If True, try QuantLib first with fallback to custom engine
                         If False, use custom Python engine directly

        Returns:
            Bootstrapped OIS discount curve
        """
        if use_quantlib:
            try:
                return self._bootstrap_with_quantlib(
                    quotes,
                    interpolation_method,
                    floating_leg_convention,
                    fixed_leg_convention
                )
            except RuntimeError as e:
                error_msg = str(e)
                if "root not bracketed" in error_msg:
                    logger.warning(
                        f"QuantLib bootstrap failed for {self.reference_date}: {error_msg[:100]}"
                    )
                    logger.info("Falling back to custom Python bootstrap engine")
                    return self._bootstrap_with_custom_engine(
                        quotes,
                        interpolation_method
                    )
                else:
                    # Re-raise other errors
                    raise
        else:
            return self._bootstrap_with_custom_engine(
                quotes,
                interpolation_method
            )

    def _bootstrap_with_quantlib(
        self,
        quotes: List[OISQuote],
        interpolation_method: str,
        floating_leg_convention,
        fixed_leg_convention,
    ) -> OISDiscountCurve:
        """
        Bootstrap using QuantLib (original implementation).

        Args:
            quotes: List of OIS market quotes
            interpolation_method: Interpolation method for curve
            floating_leg_convention: Floating leg convention
            fixed_leg_convention: Fixed leg convention

        Returns:
            Bootstrapped OIS discount curve
        """
        # Setup conventions
        float_conv, fixed_conv = self._setup_conventions(
            floating_leg_convention,
            fixed_leg_convention
        )

        # Validate and process quotes
        QuoteProcessor.validate_quotes(quotes)
        processed_quotes = self._process_quotes(quotes)
        processed_quotes = QuoteProcessor.sort_quotes_by_maturity(
            processed_quotes
        )

        # Setup QuantLib environment
        ql_ref_date = self._setup_quantlib_environment()

        # Map conventions to QuantLib objects
        calendar = self._map_calendar(float_conv)
        curve_day_count = ql.Actual365Fixed()
        fixed_day_count = self._map_day_count(fixed_conv)
        bdc = self._map_business_day_convention(float_conv)
        payment_freq = self._map_payment_frequency(float_conv)

        # Create overnight index
        overnight_index = self._create_overnight_index(float_conv, calendar)

        # Calculate rate adjustment factor
        rate_adj_factor = self._calc_rate_adjustment_factor(
            float_conv,
            fixed_conv
        )

        # Create rate helpers
        helpers = self._create_rate_helpers(
            processed_quotes,
            overnight_index,
            rate_adj_factor,
            bdc,
            payment_freq,
            calendar,
            float_conv
        )

        # Build QuantLib curve
        try:
            curve = self._build_quantlib_curve(
                ql_ref_date,
                helpers,
                curve_day_count
            )
        except RuntimeError as e:
            logger.error(
                f"Failed to bootstrap OIS curve for {self.reference_date}: {e}"
            )
            logger.error(
                f"  Number of quotes: {len(processed_quotes)}, "
                f"Tenor range: {processed_quotes[0].tenor} to {processed_quotes[-1].tenor}"
            )
            raise

        # Extract curve data
        try:
            pillar_times, discount_factors = self._extract_curve_data(
                curve,
                processed_quotes,
                ql_ref_date,
                calendar,
                bdc,
                float_conv,
                fixed_conv
            )
        except Exception as e:
            logger.error(
                f"Failed to extract curve data for {self.reference_date}: {e}"
            )
            raise

        # Create and return OIS discount curve
        curve_name = self._generate_curve_name(float_conv)

        return OISDiscountCurve(
            reference_date=self.reference_date,
            pillar_times=pillar_times,
            discount_factors=discount_factors,
            interpolation_method=interpolation_method,
            name=curve_name,
        )

    def _setup_conventions(
        self,
        floating_leg_convention,
        fixed_leg_convention
    ) -> Tuple:
        """Setup default conventions if not provided."""
        if floating_leg_convention is None:
            from ficclib.swap.instruments.swap import ESTR_FLOATING
            floating_leg_convention = ESTR_FLOATING

        if fixed_leg_convention is None:
            from ficclib.swap.instruments.swap import ESTR_FIXED
            fixed_leg_convention = ESTR_FIXED

        # Log convention info if verbose
        self._log_convention_info(
            floating_leg_convention,
            fixed_leg_convention
        )

        return floating_leg_convention, fixed_leg_convention

    def _setup_quantlib_environment(self) -> ql.Date:
        """Setup QuantLib environment and return reference date."""
        ql_ref_date = ql.Date(
            self.reference_date.day,
            self.reference_date.month,
            self.reference_date.year
        )
        ql.Settings.instance().evaluationDate = ql_ref_date
        return ql_ref_date

    def _map_calendar(self, convention) -> ql.Calendar:
        """Map calendar from convention to QuantLib."""
        calendar_map = {
            "TARGET": ql.TARGET(),
            "USNY": ql.UnitedStates(ql.UnitedStates.GovernmentBond),
            "UK": ql.UnitedKingdom(),
        }
        return calendar_map.get(
            convention.calendar.name,
            ql.TARGET()
        )

    def _map_day_count(self, convention) -> ql.DayCounter:
        """Map day count convention to QuantLib."""
        if convention.day_count.name == "ACT/360":
            return ql.Actual360()
        elif convention.day_count.name == "ACT/365F":
            return ql.Actual365Fixed()
        else:
            return ql.Actual360()

    def _map_business_day_convention(self, convention) -> int:
        """Map business day convention to QuantLib."""
        bdc_map = {
            "MODIFIED_FOLLOWING": ql.ModifiedFollowing,
            "FOLLOWING": ql.Following,
            "PRECEDING": ql.Preceding,
            "UNADJUSTED": ql.Unadjusted,
        }
        return bdc_map.get(
            convention.business_day_adjustment.name,
            ql.ModifiedFollowing
        )

    def _map_payment_frequency(self, convention) -> int:
        """Map payment frequency to QuantLib."""
        freq_map = {
            "DAILY": ql.Daily,
            "ANNUAL": ql.Annual,
            "SEMIANNUAL": ql.Semiannual,
            "QUARTERLY": ql.Quarterly,
        }
        return freq_map.get(convention.pay_frequency.name, ql.Annual)

    def _create_overnight_index(
        self,
        convention,
        calendar: ql.Calendar
    ) -> ql.OvernightIndex:
        """Create QuantLib overnight index from convention."""
        index_day_count = self._map_day_count(convention)

        return ql.OvernightIndex(
            convention.reference_rate.value,
            convention.fixing_lag_days,
            ql.EURCurrency(),
            calendar,
            index_day_count
        )

    def _calc_rate_adjustment_factor(
        self,
        float_conv,
        fixed_conv
    ) -> float:
        """Calculate rate adjustment factor for day count differences."""
        if float_conv.day_count.name != fixed_conv.day_count.name:
            float_denom = 365 if "365" in float_conv.day_count.name else 360
            fixed_denom = 365 if "365" in fixed_conv.day_count.name else 360
            return float_denom / fixed_denom
        return 1.0

    def _create_rate_helpers(
        self,
        quotes: List[OISQuote],
        overnight_index: ql.OvernightIndex,
        rate_adj_factor: float,
        bdc: int,
        payment_freq: int,
        calendar: ql.Calendar,
        convention
    ) -> List[ql.OISRateHelper]:
        """Create OIS rate helpers from quotes."""
        helpers = []
        spot_lag = 2

        for quote in quotes:
            # Parse tenor to QuantLib Period
            period = self._parse_tenor_to_period(quote.tenor)

            # Apply rate adjustment
            adjusted_rate = quote.rate * rate_adj_factor
            rate_quote = ql.QuoteHandle(ql.SimpleQuote(adjusted_rate))

            # Create OIS rate helper
            helper = ql.OISRateHelper(
                spot_lag,
                period,
                rate_quote,
                overnight_index,
                ql.YieldTermStructureHandle(),
                True,  # use telescopic value dates for stability
                convention.pay_delay_days,
                bdc,
                payment_freq,
                calendar
            )
            helpers.append(helper)

        return helpers

    def _parse_tenor_to_period(self, tenor: str) -> ql.Period:
        """Parse tenor string to QuantLib Period."""
        tenor_str = tenor.upper()

        if tenor_str.endswith('D'):
            return ql.Period(int(tenor_str[:-1]), ql.Days)
        elif tenor_str.endswith('W'):
            return ql.Period(int(tenor_str[:-1]), ql.Weeks)
        elif tenor_str.endswith('M'):
            return ql.Period(int(tenor_str[:-1]), ql.Months)
        elif tenor_str.endswith('Y'):
            return ql.Period(int(tenor_str[:-1]), ql.Years)
        else:
            raise ValueError(f"Unsupported tenor format: {tenor}")

    def _build_quantlib_curve(
        self,
        ql_ref_date: ql.Date,
        helpers: List,
        day_count: ql.DayCounter
    ):
        """Build QuantLib piecewise yield curve."""
        curve = ql.PiecewiseLogLinearDiscount(
            ql_ref_date,
            helpers,
            day_count
        )
        curve.enableExtrapolation()
        return curve

    def _extract_curve_data(
        self,
        curve,
        quotes: List[OISQuote],
        ql_ref_date: ql.Date,
        calendar: ql.Calendar,
        bdc: int,
        float_conv,
        fixed_conv
    ) -> Tuple[List[float], List[float]]:
        """Extract pillar times and discount factors from curve."""
        pillar_times: List[float] = []
        discount_factors: List[float] = []

        act365f = get_day_count_convention("ACT/365F")
        fixed_dcc = self._get_day_count_convention(fixed_conv)
        manual_front_stub_df: Optional[float] = None

        for idx, quote in enumerate(quotes):
            # Get maturity date
            maturity_ql = self._get_maturity_ql_date(
                quote,
                ql_ref_date,
                calendar,
                bdc
            )

            # Calculate time and discount factor
            time_years = ql.Actual365Fixed().yearFraction(
                ql_ref_date,
                maturity_ql
            )

            # Extract discount factor
            try:
                df = curve.discount(maturity_ql)
            except RuntimeError as e:
                # Log the error with context for debugging
                logger.error(
                    f"Failed to extract discount factor for {quote.tenor} "
                    f"(maturity: {maturity_ql}, rate: {quote.rate:.6f}): {e}"
                )
                # Re-raise - this date likely has bad market data
                raise

            pillar_times.append(time_years)
            discount_factors.append(df)

            # Apply manual adjustment for single-period tenors
            if self._is_single_period_tenor(quote.tenor):
                manual_df = self._calc_manual_front_stub_df(
                    quote,
                    act365f,
                    fixed_dcc,
                    manual_front_stub_df
                )
                if manual_df is not None:
                    if manual_front_stub_df is None:
                        manual_front_stub_df = manual_df[1]
                    discount_factors[idx] = manual_df[0]

        return pillar_times, discount_factors

    def _get_maturity_ql_date(
        self,
        quote: OISQuote,
        ql_ref_date: ql.Date,
        calendar: ql.Calendar,
        bdc: int
    ) -> ql.Date:
        """Get maturity date as QuantLib Date.

        For consistency with OISRateHelper scheduling, derive maturity from
        tenor using QuantLib calendar advance rather than relying on any
        pre-set maturity on the quote (which may differ by a day under
        different conventions).
        """
        period = self._parse_tenor_to_period(quote.tenor)
        return calendar.advance(ql_ref_date, period, bdc)

    def _get_day_count_convention(self, convention):
        """Get day count convention object."""
        if hasattr(convention.day_count, "year_fraction"):
            return convention.day_count
        return get_day_count_convention(convention.day_count)

    def _calc_manual_front_stub_df(
        self,
        quote: OISQuote,
        act365f,
        fixed_dcc,
        existing_stub_df: Optional[float]
    ) -> Optional[Tuple[float, float]]:
        """Calculate manual front stub discount factor."""
        if not quote.maturity_date:
            return None

        alpha_fix = fixed_dcc.year_fraction(
            self.spot_date,
            quote.maturity_date
        )
        tau_spot_to_end = act365f.year_fraction(
            self.spot_date,
            quote.maturity_date
        )

        if alpha_fix <= 0.0 or tau_spot_to_end <= 0.0:
            return None

        z = math.log1p(quote.rate * alpha_fix) / tau_spot_to_end

        if existing_stub_df is None:
            tau_curve_to_spot = act365f.year_fraction(
                self.reference_date,
                self.spot_date
            )
            front_stub_df = math.exp(-z * tau_curve_to_spot)
        else:
            front_stub_df = existing_stub_df

        manual_df = front_stub_df * math.exp(-z * tau_spot_to_end)
        return (manual_df, front_stub_df)

    def _generate_curve_name(self, convention) -> str:
        """Generate curve name from convention."""
        ref_rate = getattr(convention, "reference_rate", None)
        if ref_rate is not None and hasattr(ref_rate, "value"):
            return f"{ref_rate.value}-OIS-BOOTSTRAPPED-QL"
        return "OIS-BOOTSTRAPPED-QL"

    def _process_quotes(self, quotes: List[OISQuote]) -> List[OISQuote]:
        """Process and validate quotes, calculating maturity dates if needed."""
        processed = []

        for quote in quotes:
            # Ensure maturity date is set
            if quote.maturity_date is None:
                maturity_date = compute_maturity(
                    self.reference_date,
                    quote.tenor
                )
            else:
                maturity_date = quote.maturity_date

            processed_quote = OISQuote(
                tenor=quote.tenor,
                maturity_date=maturity_date,
                rate=quote.rate,
                quote_type=quote.quote_type,
            )
            processed.append(processed_quote)

        return processed

    @staticmethod
    def _is_single_period_tenor(tenor: str) -> bool:
        """Check if tenor is a single period (≤1Y)."""
        t = tenor.upper().strip()

        if t.endswith("D"):
            return True
        if t.endswith("W"):
            return True
        if t.endswith("M"):
            try:
                months = int(t[:-1])
            except ValueError:
                return False
            return months <= 12
        if t.endswith("Y"):
            try:
                years = int(t[:-1])
            except ValueError:
                return False
            return years <= 1
        return False

    def _bootstrap_with_custom_engine(
        self,
        quotes: List[OISQuote],
        interpolation_method: str,
    ) -> OISDiscountCurve:
        """
        Bootstrap using custom Python engine (no QuantLib).

        This method is used as a fallback when QuantLib fails with
        "root not bracketed" errors, typically in negative rate environments.

        Args:
            quotes: List of OIS market quotes
            interpolation_method: Interpolation method for curve

        Returns:
            Bootstrapped OIS discount curve
        """
        logger.info(
            f"Bootstrapping OIS curve with custom engine for {self.reference_date}"
        )

        # Validate and process quotes
        QuoteProcessor.validate_quotes(quotes)
        processed_quotes = self._process_quotes(quotes)
        processed_quotes = QuoteProcessor.sort_quotes_by_maturity(processed_quotes)

        # Convert to OISInstrument objects
        instruments = [
            OISInstrument(
                tenor=q.tenor,
                rate=q.rate,
                maturity_date=q.maturity_date
            )
            for q in processed_quotes
        ]

        # Create custom bootstrap engine
        engine = CustomOISBootstrapEngine(
            reference_date=self.reference_date,
            calendar=None,  # TODO: Pass actual calendar if needed
            day_count_convention="ACT/360"
        )

        # Bootstrap
        curve = engine.bootstrap(instruments, interpolation_method)

        logger.info(
            f"Custom bootstrap successful: {len(curve.pillar_times)} pillars"
        )

        return curve


def bootstrap_ois_curve(
    reference_date: date,
    quotes: List[OISQuote],
    interpolation_method: str = "STEP_FORWARD_CONTINUOUS",
    floating_leg_convention=None,
    fixed_leg_convention=None,
) -> OISDiscountCurve:
    """
    Convenience function to bootstrap OIS curve.

    Args:
        reference_date: Curve valuation date
        quotes: List of OIS market quotes
        interpolation_method: Interpolation method
        floating_leg_convention: Floating leg convention (e.g., ESTR_FLOATING)
        fixed_leg_convention: Fixed leg convention (e.g., ESTR_FIXED)

    Returns:
        Bootstrapped OIS discount curve
    """
    bootstrapper = OISBootstrapper(reference_date)
    return bootstrapper.bootstrap(
        quotes,
        interpolation_method,
        floating_leg_convention,
        fixed_leg_convention
    )
