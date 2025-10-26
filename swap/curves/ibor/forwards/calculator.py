"""Forward rate calculations for IBOR projection curves."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List

from ficclib.swap.conventions.daycount import get_day_count_convention
from ficclib.swap.curves.projection import IborProjectionCurve
from ficclib.swap.instruments.swap import SwapLegConvention
from ficclib.swap.schedule.generator import ScheduleGenerator


@dataclass
class ForwardFixingRate:
    """Forward rate information for a floating-rate accrual period."""

    fixing_date: date
    accrual_start: date
    accrual_end: date
    forward_rate: float  # Forward rate as percentage
    year_fraction: float

    @property
    def reset_date(self) -> date:  # pragma: no cover - compatibility helper
        return self.fixing_date

    @property
    def reset_rate(self) -> float:  # pragma: no cover - compatibility helper
        return self.forward_rate


class IborForwardRateCalculator:
    """Calculator producing forward fixings from an IBOR projection curve."""

    def __init__(self, conventions: SwapLegConvention):
        self.conventions = conventions

    def calculate_forward_rates(
        self,
        effective_date: date,
        maturity_date: date,
        curve: IborProjectionCurve,
        convention: SwapLegConvention,
    ) -> List[ForwardFixingRate]:
        generator = ScheduleGenerator(convention)

        if hasattr(convention.day_count, "year_fraction"):
            day_count = convention.day_count
        else:
            day_count = get_day_count_convention(convention.day_count)

        from conventions.types import StubType

        schedule = generator.generate_schedule(
            effective_date=effective_date,
            maturity_date=maturity_date,
            frequency=convention.reset_frequency,
            day_count=day_count,
            stub_type=StubType.LONG_FINAL,
        )

        forward_rates: List[ForwardFixingRate] = []
        for period in schedule:
            if period.year_fraction <= 1e-9:
                continue

            fixing_date = convention.calendar_obj.add_business_days(
                period.accrual_start, -convention.fixing_lag_days
            )

            px_start = curve.px(period.accrual_start)
            px_end = curve.px(period.accrual_end)
            if px_start <= 0 or px_end <= 0:
                continue

            if hasattr(day_count, "year_fraction"):
                accrual = day_count.year_fraction(period.accrual_start, period.accrual_end)
            else:
                accrual = period.year_fraction
            if accrual <= 0:
                continue

            forward_simple = (px_start / px_end - 1.0) / accrual
            forward_rates.append(
                ForwardFixingRate(
                    fixing_date=fixing_date,
                    accrual_start=period.accrual_start,
                    accrual_end=period.accrual_end,
                    forward_rate=forward_simple * 100.0,
                    year_fraction=period.year_fraction,
                )
            )

        return forward_rates

    def get_forward_rate_at_date(
        self,
        fixing_date: date,
        accrual_start: date,
        accrual_end: date,
        curve: IborProjectionCurve,
        day_count_convention,
    ) -> float:
        if hasattr(day_count_convention, "year_fraction"):
            dcc = day_count_convention
        else:
            from conventions.daycount import get_day_count_convention as _get

            dcc = _get(day_count_convention)

        px_start = curve.px(accrual_start)
        px_end = curve.px(accrual_end)
        if px_start <= 0 or px_end <= 0:
            raise ValueError("Non-positive pseudo discount factor encountered")

        accrual = dcc.year_fraction(accrual_start, accrual_end)
        if accrual <= 0:
            return 0.0

        return (px_start / px_end - 1.0) / accrual * 100.0

    def calculate_reset_rates(
        self,
        effective_date: date,
        maturity_date: date,
        curve: IborProjectionCurve,
        convention: SwapLegConvention,
    ) -> List[ForwardFixingRate]:  # pragma: no cover - compatibility
        return self.calculate_forward_rates(effective_date, maturity_date, curve, convention)

    def get_reset_rate_at_date(
        self,
        reset_date: date,
        accrual_start: date,
        accrual_end: date,
        curve: IborProjectionCurve,
        day_count_convention: str,
    ) -> float:  # pragma: no cover - compatibility
        return self.get_forward_rate_at_date(
            fixing_date=reset_date,
            accrual_start=accrual_start,
            accrual_end=accrual_end,
            curve=curve,
            day_count_convention=day_count_convention,
        )


def generate_forward_rates_for_leg(
    leg_spec,
    curve: IborProjectionCurve,
    conventions: SwapLegConvention | None = None,
) -> List[ForwardFixingRate]:
    if conventions is None:
        conventions = leg_spec.convention

    calculator = IborForwardRateCalculator(conventions)
    return calculator.calculate_forward_rates(
        effective_date=leg_spec.effective_date,
        maturity_date=leg_spec.maturity_date,
        curve=curve,
        convention=leg_spec.convention,
    )


def generate_reset_rates_for_leg(
    leg_spec,
    curve: IborProjectionCurve,
    conventions: SwapLegConvention | None = None,
) -> List[ForwardFixingRate]:  # pragma: no cover - compatibility
    return generate_forward_rates_for_leg(leg_spec, curve, conventions)


ResetRate = ForwardFixingRate  # pragma: no cover - compatibility alias
IborResetRateCalculator = IborForwardRateCalculator  # pragma: no cover

