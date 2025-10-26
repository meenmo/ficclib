"""Instrument representations used by the IBOR bootstrapper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List

from ficclib.swap.business_calendar.date_calculator import (
    compute_maturity,
    generate_annual_payment_schedule,
    get_spot_date,
)
from ficclib.swap.conventions.daycount import (
    DayCountConvention,
    get_day_count_convention,
)
from ficclib.swap.instruments.deposit import DepositConvention
from ficclib.swap.instruments.swap import SwapLegConvention
from ficclib.swap.schedule import ScheduleGenerator, SchedulePeriod
from ficclib.swap.schema.quotes import Quote


@dataclass(frozen=True)
class FloatingPeriod:
    """Single floating-leg accrual period used during bootstrapping."""

    accrual_start: date
    accrual_end: date
    year_fraction: float


class BootstrapInstrument:  # pragma: no cover - interface
    """Common interface for bootstrap instruments."""

    def get_maturity(self) -> date:
        raise NotImplementedError

    def get_tenor(self) -> str:
        raise NotImplementedError

    @property
    def index_name(self) -> str:
        raise NotImplementedError


class DepositInstrument(BootstrapInstrument):
    """Representation of a single money-market deposit quote."""

    def __init__(self, curve_date: date, tenor: str, rate: float, convention: DepositConvention):
        self.curve_date = curve_date
        self.tenor = tenor.upper().strip()
        self.rate = rate
        self.convention = convention

        self.spot_date = get_spot_date(
            curve_date,
            convention.calendar_obj,
            convention.settlement_lag_days,
        )
        self.maturity_date = compute_maturity(
            curve_date,
            self.tenor,
            calendar=convention.calendar_obj,
            spot_lag=convention.settlement_lag_days,
            business_day_adjustment=convention.business_day_adjustment,
        )
        self.day_count: DayCountConvention = convention.day_count

    def get_maturity(self) -> date:
        return self.maturity_date

    def get_tenor(self) -> str:
        return self.tenor

    @property
    def index_name(self) -> str:
        ref = (
            self.convention.reference_rate.value
            if hasattr(self.convention.reference_rate, "value")
            else str(self.convention.reference_rate)
        )
        return f"EUR-{ref}"

    def accrual_fraction(self) -> float:
        return self.day_count.year_fraction(self.spot_date, self.maturity_date)


class SwapInstrument(BootstrapInstrument):
    """Plain-vanilla fixed/floating swap quote used in the bootstrap."""

    def __init__(self, curve_date: date, tenor: str, rate: float, floating_leg: SwapLegConvention):
        self.curve_date = curve_date
        self.tenor = tenor.upper().strip()
        self.fixed_rate = rate
        self.floating_leg = floating_leg

        fixing_lag = floating_leg.fixing_lag_days or 2
        self.spot_date = get_spot_date(
            curve_date,
            floating_leg.calendar_obj,
            fixing_lag,
        )
        self.maturity_date = compute_maturity(
            curve_date,
            self.tenor,
            calendar=floating_leg.calendar_obj,
            spot_lag=fixing_lag,
            business_day_adjustment=floating_leg.business_day_adjustment,
        )

        self.fixed_day_count = get_day_count_convention("30E/360")
        self.float_day_count: DayCountConvention = floating_leg.day_count

        self._fixed_schedule = self._build_fixed_schedule()
        self._floating_periods = self._build_floating_periods()

    def get_maturity(self) -> date:
        return self.maturity_date

    def get_tenor(self) -> str:
        return self.tenor

    @property
    def index_name(self) -> str:
        ref = (
            self.floating_leg.reference_rate.value
            if hasattr(self.floating_leg.reference_rate, "value")
            else str(self.floating_leg.reference_rate)
        )
        return f"EUR-{ref}"

    def fixed_cashflows(self) -> Iterable[tuple[date, date, float]]:
        for i in range(1, len(self._fixed_schedule)):
            start = self._fixed_schedule[i - 1]
            end = self._fixed_schedule[i]
            alpha = self.fixed_day_count.year_fraction(start, end)
            yield start, end, alpha

    def floating_periods(self) -> List[FloatingPeriod]:
        return list(self._floating_periods)

    def _build_fixed_schedule(self) -> List[date]:
        fixing_lag = self.floating_leg.fixing_lag_days or 2
        return generate_annual_payment_schedule(
            self.curve_date,
            self.tenor,
            calendar=self.floating_leg.calendar_obj,
            spot_lag=fixing_lag,
            business_day_adjustment=self.floating_leg.business_day_adjustment,
        )

    def _build_floating_periods(self) -> List[FloatingPeriod]:
        generator = ScheduleGenerator(self.floating_leg)
        schedule: List[SchedulePeriod] = generator.generate_schedule(
            effective_date=self.spot_date,
            maturity_date=self.maturity_date,
            frequency=self.floating_leg.reset_frequency,
            day_count=self.float_day_count,
        )

        periods: List[FloatingPeriod] = []
        for period in schedule:
            if period.year_fraction <= 1e-12:
                continue
            periods.append(
                FloatingPeriod(
                    accrual_start=period.accrual_start,
                    accrual_end=period.accrual_end,
                    year_fraction=period.year_fraction,
                )
            )
        return periods


def create_instrument_from_quote(curve_date: date, quote: Quote) -> BootstrapInstrument:
    """Create a bootstrap instrument from a generic quote."""

    rate = quote.rate / 100.0 if quote.rate > 1.0 else quote.rate

    if isinstance(quote.instrument, DepositConvention):
        return DepositInstrument(curve_date, quote.tenor, rate, quote.instrument)

    if isinstance(quote.instrument, SwapLegConvention):
        return SwapInstrument(curve_date, quote.tenor, rate, quote.instrument)

    raise TypeError(f"Unsupported instrument type: {type(quote.instrument).__name__}")
