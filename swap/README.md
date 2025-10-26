# Interest Rate Swap Pricing Engine

**Version:** 1.0.0

A professional Python library for pricing interest rate swaps using a dual-curve framework with OIS discounting and IBOR projection curves.

## Features

- **Dual-Curve Framework**: Separate OIS discount curves and IBOR projection curves
- **Bootstrapping**: Build discount and forward curves from market quotes
- **Schedule Generation**: Accurate payment schedule generation with business day conventions
- **Market Conventions**: Support for standard market conventions (ACT/360, ACT/365F, TARGET calendar)
- **QuantLib Integration**: QuantLib backend for conventions and calendars

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd pricer/swap

# Install dependencies
uv pip install -r requirements.txt
```

## Quick Start

```python
from ficclib.swap.valuation import price_swap
from ficclib.swap.curves import build_ois_curve, build_ibor_curve
from ficclib.swap.instruments import Swap

# Build curves from market data
ois_curve = build_ois_curve(ois_quotes, value_date)
ibor_curve = build_ibor_curve(ibor_quotes, value_date, ois_curve)

# Price a swap
swap = Swap(
    notional=10_000_000,
    fixed_rate=0.02,
    start_date=start_date,
    maturity_date=maturity_date,
    payment_frequency="6M"
)

npv = price_swap(swap, ois_curve, ibor_curve)
```

## Project Structure

```
pricer/swap/
├── valuation/          # Swap pricing and valuation
├── curves/             # Curve bootstrapping (OIS, IBOR)
├── instruments/        # Instrument definitions (Swap, Deposit)
├── schedule/           # Payment schedule generation
├── conventions/        # Market conventions (day count, calendars)
├── interpolation/      # Curve interpolation methods
├── business_calendar/  # Date utilities and holiday calendars
├── data/               # Data loading and filtering
└── schema/             # Data models and enums
```

## Testing

```bash
# Run core pricing tests
pricer/swap/.venv/bin/python -m pricer.swap.test.npv
pricer/swap/.venv/bin/python -m pricer.swap.test.par_swap_spread
```

## Documentation

Comprehensive technical documentation is available in the `technical_notes/` directory:

- [Package Overview](technical_notes/00_overview.md)
- [Market Conventions](technical_notes/01_conventions.md)
- [OIS Bootstrapping](technical_notes/02_ois_bootstrap.md)
- [IBOR Bootstrapping](technical_notes/03_ibor_bootstrap.md)
- [Forward Rate Calculations](technical_notes/04_forward_rates.md)
- [Schedule Generation](technical_notes/05_schedule_generation.md)
- [Interpolation Methods](technical_notes/06_interpolation.md)
- [QuantLib Integration](technical_notes/07_quantlib_integration.md)
- [Precision Engineering](technical_notes/08_precision_engineering.md)

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

This is a professional-grade financial engineering library. Contributions should maintain:
- Comprehensive test coverage
- Clear documentation with mathematical formulas
- Professional code standards (type hints, logging, proper naming)
