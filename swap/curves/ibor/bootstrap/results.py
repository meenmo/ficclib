"""Result dataclasses for the IBOR bootstrapping stack."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List

from ficclib.swap.curves.projection import IborProjectionCurve


@dataclass(frozen=True)
class BootstrapResult:
    """Single pillar solved during the bootstrap."""

    tenor: str
    maturity: date
    time_act360: float
    discount_factor: float
    zero_rate: float


@dataclass(frozen=True)
class BuildResult:
    """Aggregate output returned by :class:`IborCurveBuilder`."""

    curve: IborProjectionCurve
    results: List[BootstrapResult]
    projection_map: Dict[date, float]

    def __iter__(self):  # pragma: no cover - compatibility helper
        yield self.curve
        yield self.results

    def without_projection_map(self) -> tuple[IborProjectionCurve, List[BootstrapResult]]:
        """Legacy helper returning only (curve, results)."""

        return self.curve, self.results
