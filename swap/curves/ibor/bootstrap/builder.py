"""High-level builder for IBOR projection curves."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import List, Sequence

from ficclib.swap.business_calendar.date_calculator import compute_maturity
from ficclib.swap.conventions.calendars import get_calendar
from ficclib.swap.conventions.daycount import ACT_360, ACT_365F
from ficclib.swap.conventions.types import BusinessDayAdjustment, RollConvention
from ficclib.swap.curves.discount import OISDiscountCurve
from ficclib.swap.curves.ois import OISBootstrapper
from ficclib.swap.curves.ois.quotes import OISQuote
from ficclib.swap.schema.quotes import Quote

from .engine import BootstrapEngine
from .instruments import (
    BootstrapInstrument,
    DepositInstrument,
    SwapInstrument,
    create_instrument_from_quote,
)
from .results import BuildResult


@dataclass
class BuilderConfig:
    """Configuration knobs for the IBOR curve builder."""

    include_projection_map: bool = True
    # Optional override for OIS interpolation method used by the builder when
    # constructing the discount curve. Examples: "STEP_FORWARD_CONTINUOUS",
    # "LINEAR_DF", "LOGLINEAR_ZERO".
    ois_interpolation_method: str | None = None


class IborCurveBuilder:
    """User-friendly wrapper around :class:`BootstrapEngine`."""

    def __init__(self, curve_date: date, config: BuilderConfig | None = None):
        self.curve_date = curve_date
        self.config = config or BuilderConfig()
        self._ois_curve = None
        self._ibor_quotes: List[Quote] = []

    # ------------------------------------------------------------------
    # OIS set-up
    # ------------------------------------------------------------------
    def set_ois_curve(self, curve) -> None:
        self._ois_curve = curve

    def set_ois_quotes(self, quotes: Sequence[Quote]) -> None:
        if not quotes:
            raise ValueError(
                "At least one OIS quote is required to build the discount curve"
            )

        bootstrapper = OISBootstrapper(self.curve_date)
        prepared = [
            OISQuote(
                tenor=q.tenor,
                maturity_date=None,
                rate=q.rate / 100.0 if q.rate > 1.0 else q.rate,
            )
            for q in quotes
        ]

        floating_leg = getattr(quotes[0], "instrument", None)
        if floating_leg is not None and not hasattr(floating_leg, "reference_rate"):
            floating_leg = None
        # Allow overriding OIS interpolation via builder config; default to
        # QuantLib-compatible STEP_FORWARD_CONTINUOUS if not specified.
        interp = self.config.ois_interpolation_method or "STEP_FORWARD_CONTINUOUS"
        self._ois_curve = bootstrapper.bootstrap(
            prepared,
            interpolation_method=interp,
            floating_leg_convention=floating_leg,
        )
        self._ois_curve = self._apply_spot_stub(self._ois_curve, prepared, floating_leg)

    # ------------------------------------------------------------------
    # IBOR quotes
    # ------------------------------------------------------------------
    def add_ibor_quotes(self, quotes: Sequence[Quote]) -> None:
        self._ibor_quotes.extend(quotes)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    def build(self) -> BuildResult:
        if self._ois_curve is None:
            raise ValueError("OIS curve must be provided before bootstrapping")

        instruments = [
            create_instrument_from_quote(self.curve_date, quote)
            for quote in self._ibor_quotes
        ]
        deposits = [inst for inst in instruments if isinstance(inst, DepositInstrument)]
        swaps = [inst for inst in instruments if isinstance(inst, SwapInstrument)]

        index_name = self._determine_index_name(instruments)

        engine = BootstrapEngine(self.curve_date, self._ois_curve, index_name)
        engine.bootstrap_deposits(deposits)
        for swap in sorted(swaps, key=lambda s: s.get_maturity()):
            engine.bootstrap_swap(swap)

        curve = engine.get_curve()
        results = engine.get_results()
        projection_map = (
            engine.get_projection_map() if self.config.include_projection_map else {}
        )
        return BuildResult(curve=curve, results=results, projection_map=projection_map)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _apply_spot_stub(
        self, curve, quotes: Sequence[OISQuote], floating_leg
    ) -> OISDiscountCurve:
        """Insert a near-spot pillar so DF(trade->spot) follows short-rate convention."""
        if curve is None or not quotes:
            return curve

        try:
            calendar = floating_leg.calendar_obj if floating_leg else get_calendar("TARGET")
        except Exception:
            calendar = get_calendar("TARGET")

        spot_date = calendar.add_business_days(self.curve_date, 2)
        stub_time = ACT_365F.year_fraction(self.curve_date, spot_date)
        if stub_time <= 0:
            return curve

        business_day_adjustment = getattr(
            floating_leg,
            "business_day_adjustment",
            BusinessDayAdjustment.MODIFIED_FOLLOWING,
        )
        roll_conv = getattr(floating_leg, "roll_convention", None)
        end_of_month_rule = roll_conv == RollConvention.BACKWARD_EOM if roll_conv else True

        def maturity_date(q: OISQuote) -> date:
            if q.maturity_date is not None:
                return q.maturity_date
            return compute_maturity(
                self.curve_date,
                q.tenor,
                calendar=calendar,
                spot_lag=2,
                business_day_adjustment=business_day_adjustment,
                end_of_month_rule=end_of_month_rule,
            )

        shortest_quote = min(quotes, key=maturity_date)
        short_rate = shortest_quote.rate
        stub_year_fraction_act360 = ACT_360.year_fraction(self.curve_date, spot_date)
        stub_discount = math.exp(-short_rate * stub_year_fraction_act360)

        return curve.with_spot_stub(stub_time, stub_discount)

    @staticmethod
    def _determine_index_name(instruments: Sequence[BootstrapInstrument]) -> str:
        for instrument in instruments:
            try:
                return instrument.index_name
            except AttributeError:
                continue
        return "EUR-EURIBOR-6M"


def bootstrap_ibor_curve_simple(
    curve_date: date, ibor_quotes: Sequence[Quote], ois_quotes: Sequence[Quote]
):
    builder = IborCurveBuilder(curve_date)
    builder.set_ois_quotes(ois_quotes)
    builder.add_ibor_quotes(ibor_quotes)
    result = builder.build()
    return result.curve
