"""Step 4: Swap Pricing and Spread Calculation Test with Hard-coded Data

This test prices a 10x10 basis swap (3M vs 6M) and solves for the par spread
using hard-coded market data from sample_data.py (curve date: 2024-01-02).
"""

import sys
from datetime import date
from pathlib import Path

# Ensure workspace root is on PYTHONPATH so `pricer.swap` imports work
_file_dir = Path(__file__).resolve().parent
_tests_dir = _file_dir.parent
_project_root = _tests_dir.parent         # pricer
_workspace_root = _project_root.parent    # workspace root (contains 'pricer')
if str(_workspace_root) not in sys.path:
    sys.path.insert(0, str(_workspace_root))

from ficclib.swap.business_calendar.date_calculator import compute_maturity
from ficclib.swap.conventions.types import RollConvention
from ficclib.swap.curves.ibor import IborCurveBuilder
from ficclib.swap.curves.ois import OISQuote
from ficclib.swap.instruments.deposit import EURIBOR_3M_DEPOSIT, EURIBOR_6M_DEPOSIT
from ficclib.swap.instruments.swap import (
    ESTR_FLOATING,
    EURIBOR_3M_FLOATING,
    EURIBOR_6M_FLOATING,
)
from ficclib.swap.schema.quotes import Quote
from ficclib.swap.test.input_curves import (
    CURVE_DATE,
    ESTR_QUOTES,
    EURIBOR3M_QUOTES,
    EURIBOR6M_QUOTES,
)
from ficclib.swap.valuation.pv import price_swap
from ficclib.swap.valuation.solver import solve_receive_leg_spread
from ficclib.swap.valuation.types import CurveSet, SwapSpec


def load_sample_data():
    """Load hard-coded quotes from in-repo Python data module."""
    return CURVE_DATE, ESTR_QUOTES, EURIBOR3M_QUOTES, EURIBOR6M_QUOTES


def prepare_ois_quotes(curve_date: date, estr_quotes: list):
    """Prepare OIS quotes."""
    calendar = ESTR_FLOATING.calendar_obj
    spot_lag = 2
    business_day_adjustment = ESTR_FLOATING.business_day_adjustment
    end_of_month_rule = (ESTR_FLOATING.roll_convention == RollConvention.BACKWARD_EOM)

    ois_quote_objects = []
    for q in estr_quotes:
        if q["rate"] is None:
            continue

        maturity_date = compute_maturity(
            curve_date,
            q["tenor"],
            calendar=calendar,
            spot_lag=spot_lag,
            business_day_adjustment=business_day_adjustment,
            end_of_month_rule=end_of_month_rule
        )

        ois_quote = OISQuote(
            tenor=q["tenor"],
            maturity_date=maturity_date,
            rate=q["rate"] / 100.0,
            quote_type="PAR_RATE"
        )
        ois_quote_objects.append(ois_quote)

    return ois_quote_objects


def prepare_ibor_quotes(ibor_quotes_raw: list, floating_instrument, deposit_instrument, deposit_tenor: str):
    """Prepare IBOR quotes from JSON data."""
    ibor_quotes = []
    for i, q in enumerate(ibor_quotes_raw):
        if q["rate"] is not None:
            tenor = q["tenor"]
            rate = q["rate"]

            # Use deposit instrument for first occurrence of deposit tenor
            if tenor == deposit_tenor and i == 0:
                instrument = deposit_instrument
            else:
                instrument = floating_instrument

            ibor_quotes.append(Quote(tenor=tenor, rate=rate, instrument=instrument))

    return ibor_quotes


def build_curves(curve_date: date, ois_quotes, ibor_quotes_3m, ibor_quotes_6m):
    """Build all curves (OIS, EURIBOR 3M, EURIBOR 6M)."""
    # Build EURIBOR 3M curve (includes OIS bootstrapping)
    builder_3m = IborCurveBuilder(curve_date)
    builder_3m.set_ois_quotes(ois_quotes)
    builder_3m.add_ibor_quotes(ibor_quotes_3m)
    build_3m = builder_3m.build()

    # Build EURIBOR 6M curve (includes OIS bootstrapping)
    builder_6m = IborCurveBuilder(curve_date)
    builder_6m.set_ois_quotes(ois_quotes)
    builder_6m.add_ibor_quotes(ibor_quotes_6m)
    build_6m = builder_6m.build()

    # Get OIS curve from one of the builders (they're the same)
    ois_curve = builder_3m._ois_curve

    # Create CurveSet
    curves = CurveSet(
        ois_curve=ois_curve,
        euribor3m_curve=build_3m.curve,
        euribor6m_curve=build_6m.curve,
    )

    return curves


def calculate_maturity_date(start_date: date, tenor_years: int) -> date:
    """Calculate maturity date from start date and tenor in years."""
    year = start_date.year + tenor_years
    try:
        maturity = date(year, start_date.month, start_date.day)
    except ValueError:
        # Handle Feb 29 in non-leap years
        maturity = date(year, start_date.month, 28)
    return maturity


def test_swap_pricing(curves: CurveSet, curve_date: date, forward_years: int, tenor_years: int):
    """Test swap pricing with zero spread and with solved spread."""
    print("\n" + "=" * 120)
    print(f"SWAP PRICING TEST - {forward_years}x{tenor_years} BASIS SWAP (EURIBOR 3M vs 6M)")
    print("=" * 120)

    # Get calendar
    calendar = EURIBOR_6M_FLOATING.calendar_obj

    # Calculate dates - use curve date as trade date for hard-coded data
    trade_date = curve_date
    spot_date = calendar.add_business_days(trade_date, 2)

    # Calculate effective date (spot + forward tenor)
    if forward_years > 0:
        unadjusted_effective = calculate_maturity_date(spot_date, forward_years)
    else:
        unadjusted_effective = spot_date
    effective_date = calendar.add_business_days(unadjusted_effective, 0)

    # Calculate maturity date
    unadjusted_maturity = calculate_maturity_date(effective_date, tenor_years)
    maturity_date = calendar.add_business_days(unadjusted_maturity, 0)

    print(f"\nSwap Details:")
    print(f"  Curve Date:      {curve_date}")
    print(f"  Trade Date:      {trade_date}")
    print(f"  Effective Date:  {effective_date}")
    print(f"  Maturity Date:   {maturity_date}")
    print(f"  Notional:        EUR 10,000,000")
    print(f"  Structure:       PAY EURIBOR 6M, RECEIVE EURIBOR 3M")

    # Create swap spec with zero spread
    spec = SwapSpec(
        notional=10_000_000,
        effective_date=effective_date,
        maturity_date=maturity_date,
        pay_leg=EURIBOR_6M_FLOATING,
        rec_leg=EURIBOR_3M_FLOATING,
        discounting="OIS",
        pay_leg_spread=0.0,
        rec_leg_spread=0.0,
        include_principal_exchanges=True,
    )

    # Price with zero spread
    print("\n" + "-" * 120)
    print("PRICING WITH ZERO SPREAD")
    print("-" * 120)

    result_zero = price_swap(
        spec=spec,
        curves=curves,
        valuation_date=curve_date,
    )

    print(f"\nNPV Breakdown:")
    print(f"  Total NPV:              EUR {result_zero.pv_total:>20,.2f}")
    print(f"  Pay Leg (6M) NPV:       EUR {result_zero.pay_leg_pv.pv:>20,.2f}")
    print(f"  Receive Leg (3M) NPV:   EUR {result_zero.rec_leg_pv.pv:>20,.2f}")
    print(f"  Number of 6M cashflows: {len(result_zero.pay_leg_pv.cashflows):>24}")
    print(f"  Number of 3M cashflows: {len(result_zero.rec_leg_pv.cashflows):>24}")

    # Solve for par spread
    print("\n" + "-" * 120)
    print("SOLVING FOR PAR SPREAD (Receive Leg)")
    print("-" * 120)

    try:
        spread_bp, result_par = solve_receive_leg_spread(
            spec=spec,
            curves=curves,
            valuation_date=curve_date,
            target=0.0,
            tolerance=1e-3,
            max_iterations=100,
            lower_bound_bp=-500.0,
            upper_bound_bp=500.0,
        )

        print(f"\nSolved Spread: {spread_bp:.6f} bp")
        print(f"\nNPV with Par Spread:")
        print(f"  Total NPV:              EUR {result_par.pv_total:>20,.2f}")
        print(f"  Pay Leg (6M) NPV:       EUR {result_par.pay_leg_pv.pv:>20,.2f}")
        print(f"  Receive Leg (3M) NPV:   EUR {result_par.rec_leg_pv.pv:>20,.2f}")

        # Display first few cashflows from each leg
        print("\n" + "-" * 120)
        print("PAY LEG CASHFLOWS (EURIBOR 6M) - First 5 Periods")
        print("-" * 120)
        print(
            f"{'Period':<8} {'Accrual Start':<15} {'Accrual End':<15} "
            f"{'Payment Date':<15} {'Fwd Rate':<12} {'DF':<12} {'PV (EUR)':<18}"
        )
        print("-" * 120)

        for cf in result_par.pay_leg_pv.cashflows[:5]:
            if cf.forward_rate is not None:  # Skip principal exchanges
                print(
                    f"{cf.idx:<8} "
                    f"{cf.accrual_start.isoformat():<15} "
                    f"{cf.accrual_end.isoformat():<15} "
                    f"{cf.payment_date.isoformat():<15} "
                    f"{cf.forward_rate * 100:>10.4f}% "
                    f"{cf.discount_factor:>10.6f} "
                    f"{cf.pv:>18,.2f}"
                )

        print("\n" + "-" * 120)
        print("RECEIVE LEG CASHFLOWS (EURIBOR 3M) - First 5 Periods")
        print("-" * 120)
        print(
            f"{'Period':<8} {'Accrual Start':<15} {'Accrual End':<15} "
            f"{'Payment Date':<15} {'Fwd Rate':<12} {'DF':<12} {'PV (EUR)':<18}"
        )
        print("-" * 120)

        for cf in result_par.rec_leg_pv.cashflows[:5]:
            if cf.forward_rate is not None:  # Skip principal exchanges
                # For receive leg with spread, show effective rate
                effective_rate = cf.forward_rate + (spread_bp * 1e-4)
                print(
                    f"{cf.idx:<8} "
                    f"{cf.accrual_start.isoformat():<15} "
                    f"{cf.accrual_end.isoformat():<15} "
                    f"{cf.payment_date.isoformat():<15} "
                    f"{effective_rate * 100:>10.4f}% "
                    f"{cf.discount_factor:>10.6f} "
                    f"{cf.pv:>18,.2f}"
                )

    except Exception as e:
        print(f"\nError solving for spread: {e}")
        return False

    print("\n" + "=" * 120)
    print("TEST COMPLETED - Swap priced and spread solved successfully")
    print("=" * 120)
    print()

    return True


def main():
    """Main test function."""
    # Load hard-coded data
    curve_date, estr_quotes, euribor3m_quotes, euribor6m_quotes = load_sample_data()

    print("\n" + "=" * 120)
    print("SWAP PRICING AND SPREAD CALCULATION - HARD-CODED DATA (2024-01-02)")
    print("=" * 120)
    print(f"\nCurve Date: {curve_date}")

    # Prepare quotes
    ois_quotes = prepare_ois_quotes(curve_date, estr_quotes)
    ibor_quotes_3m = prepare_ibor_quotes(
        euribor3m_quotes, EURIBOR_3M_FLOATING, EURIBOR_3M_DEPOSIT, "3M"
    )
    ibor_quotes_6m = prepare_ibor_quotes(
        euribor6m_quotes, EURIBOR_6M_FLOATING, EURIBOR_6M_DEPOSIT, "6M"
    )

    print(f"\nLoaded data:")
    print(f"  OIS quotes: {len(ois_quotes)}")
    print(f"  EURIBOR 3M quotes: {len(ibor_quotes_3m)}")
    print(f"  EURIBOR 6M quotes: {len(ibor_quotes_6m)}")

    # Build all curves
    print("\nBuilding curves...")
    curves = build_curves(curve_date, ois_quotes, ibor_quotes_3m, ibor_quotes_6m)
    print("Curves built successfully.")

    # Test 10x10 swap
    success = test_swap_pricing(curves, curve_date, forward_years=10, tenor_years=20)

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
