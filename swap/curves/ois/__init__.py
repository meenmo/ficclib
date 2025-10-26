"""
OIS curve construction and discounting.

This module contains everything needed for OIS curves:
- Curve bootstrapping (OISBootstrapper)
- Curve objects (OISDiscountCurve)
- Quote objects (OISQuote)

Main API:
    OISBootstrapper - Build OIS discount curves
    OISDiscountCurve - Query discount factors
    OISQuote - OIS quote data structure
"""

from .bootstrapper import OISBootstrapper
from .curve import OISDiscountCurve, create_flat_ois_curve
from .quotes import OISQuote

__all__ = [
    "OISBootstrapper",
    "OISDiscountCurve",
    "OISQuote",
    "create_flat_ois_curve",
]
