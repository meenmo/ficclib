"""Interest Rate Swap Pricing Engine.

This package provides tools for pricing interest rate swaps using dual-curve
framework with OIS discounting and IBOR projection curves.

Key modules:
- valuation: Swap pricing and valuation
- curves: OIS and IBOR curve bootstrapping
- instruments: Swap and deposit instrument definitions
- schedule: Payment schedule generation
- conventions: Market conventions and day count conventions
"""

__version__ = "1.0.0"

__all__ = [
    "__version__",
    # Main modules are imported via subpackages
    "valuation",
    "curves",
    "instruments",
    "schedule",
    "conventions",
    "interpolation",
]
