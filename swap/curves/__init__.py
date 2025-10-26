"""
Curves package - Unified module for curve construction and management.

This package contains everything related to interest rate curves:
- OIS discount curves
- IBOR projection curves
- Curve bootstrapping
- Forward rate calculations

Main APIs:
---------
OIS:
    - OISBootstrapper: Build OIS discount curves
    - OISDiscountCurve: Query OIS discount factors

IBOR:
    - IborCurveBuilder: Build IBOR projection curves (recommended)
    - IborProjectionCurve: Query IBOR projection factors
    - bootstrap_ibor_curve_simple: One-line curve building
"""

# OIS - Import from curves/ois (which now contains bootstrap logic)
from ficclib.swap.curves.ois.bootstrapper import OISBootstrapper
from ficclib.swap.curves.ois.curve import OISDiscountCurve
from ficclib.swap.curves.ois.quotes import OISQuote

# Also support old imports from curves.projection and curves.discount
from ficclib.swap.curves.projection import IborProjectionCurve

# Base
from .base import Curve
from .discount import OISDiscountCurve as OISDiscountCurve_Legacy

# IBOR - Import consolidated API
from .ibor import (
    BootstrapEngine,
    BootstrapInstrument,
    BootstrapResult,
    BuilderConfig,
    BuildResult,
    DepositInstrument,
    ForwardFixingRate,
    IborCurveBuilder,
    IborForwardRateCalculator,
    ProjectionCurveState,
    SwapInstrument,
    bootstrap_ibor_curve_simple,
    create_instrument_from_quote,
    generate_forward_rates_for_leg,
    generate_reset_rates_for_leg,
)

__all__ = [
    # OIS
    "OISBootstrapper",
    "OISDiscountCurve",
    "OISQuote",
    # IBOR - Main API
    "IborCurveBuilder",
    "BuilderConfig",
    "IborProjectionCurve",
    "bootstrap_ibor_curve_simple",
    # IBOR - Engine components
    "BootstrapEngine",
    "ProjectionCurveState",
    "BootstrapResult",
    "BuildResult",
    # IBOR - Instruments
    "DepositInstrument",
    "SwapInstrument",
    "BootstrapInstrument",
    "create_instrument_from_quote",
    # IBOR - Forward utilities
    "ForwardFixingRate",
    "IborForwardRateCalculator",
    "generate_forward_rates_for_leg",
    "generate_reset_rates_for_leg",
    # Base
    "Curve",
]
