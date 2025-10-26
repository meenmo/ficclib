"""
DEPRECATED: This module has been renamed to forwards.py

This compatibility layer will be removed in a future version.
Please update your imports to use the forward-based API:
    from curves.ibor.forwards import IborForwardRateCalculator
"""

# Re-export everything from forwards for backward compatibility
from .forwards import *

__all__ = [
    "IborForwardRateCalculator",
    "ForwardFixingRate",
    "generate_forward_rates_for_leg",
    "IborResetRateCalculator",
    "ResetRate",
    "generate_reset_rates_for_leg",
]
