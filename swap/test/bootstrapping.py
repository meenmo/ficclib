"""OIS and IBOR Bootstrapping Tests with Hard-coded Data.

This module bootstraps the OIS (ESTR) curve and the EURIBOR 3M/6M projection
curves using hard-coded market data from input_curves.py (curve date: 2024-01-02)
and prints key results.
"""

import math
import sys
from datetime import date
from pathlib import Path

# Ensure workspace and package roots are on PYTHONPATH
_file_dir = Path(__file__).resolve().parent
_tests_dir = _file_dir.parent
_project_root = _tests_dir.parent         # pricer
_workspace_root = _project_root.parent    # workspace root (contains 'pricer')
if str(_workspace_root) not in sys.path:
    sys.path.insert(0, str(_workspace_root))

from ficclib.swap.business_calendar.date_calculator import compute_maturity
from ficclib.swap.conventions.daycount import get_day_count_convention
from ficclib.swap.conventions.types import RollConvention
from ficclib.swap.curves.ibor import IborCurveBuilder
from ficclib.swap.curves.ois import OISBootstrapper, OISQuote
from ficclib.swap.instruments.deposit import (
    EURIBOR_3M_DEPOSIT,
    EURIBOR_6M_DEPOSIT,
)
from ficclib.swap.instruments.swap import (
    ESTR_FIXED,
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


def prepare_ois_quotes(curve_date: date, estr_quotes: list):
    """Prepare OIS quotes for bootstrapper."""
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
            end_of_month_rule=end_of_month_rule,
        )

        ois_quote = OISQuote(
            tenor=q["tenor"],
            maturity_date=maturity_date,
            rate=q["rate"] / 100.0,
            quote_type="PAR_RATE",
        )
        ois_quote_objects.append(ois_quote)

    return ois_quote_objects


def display_ois_results(curve_date: date, ois_curve, ois_quotes):
    print("\n" + "=" * 100)
    print("OIS BOOTSTRAP TEST - HARD-CODED DATA (2024-01-02)")
    print("=" * 100)
    print(f"\nCurve Date: {curve_date}")
    print(f"Number of ESTR quotes: {len(ois_quotes)}")
    print(f"Successfully bootstrapped OIS curve with ESTR_FLOATING convention")
    print(f"Interpolation: STEP_FORWARD_CONTINUOUS")

    print("\n" + "-" * 100)
    print("DISCOUNT FACTORS AT KEY PILLARS")
    print("-" * 100)
    print(f"{'Tenor':<8} {'Maturity':<12} {'Time(Y)':<10} {'Zero Rate %':<12} {'DF':<12}")
    print("-" * 100)

    day_count = get_day_count_convention("ACT/365F")

    display_tenors = list(ois_quotes[:15])
    for tenor in ["5Y", "10Y", "15Y", "20Y", "30Y", "40Y", "50Y"]:
        for q in ois_quotes:
            if q.tenor == tenor and q not in display_tenors:
                display_tenors.append(q)
                break

    for quote in display_tenors:
        time_years = day_count.year_fraction(curve_date, quote.maturity_date)
        zero_rate = ois_curve.zero(time_years) * 100.0 if time_years > 0 else 0.0
        df = math.exp(-zero_rate / 100.0 * time_years) if time_years > 0 else 1.0

        print(
            f"{quote.tenor:<8} {str(quote.maturity_date):<12} "
            f"{time_years:<10.4f} {zero_rate:<12.6f} {df:<12.8f}"
        )

    print("\n" + "=" * 100)
    print("OIS curve bootstrapped successfully")
    print("=" * 100)


def prepare_ibor_quotes(ibor_quotes_raw: list, floating_instrument, deposit_instrument, deposit_tenor: str):
    ibor_quotes = []
    for i, q in enumerate(ibor_quotes_raw):
        if q["rate"] is not None:
            tenor = q["tenor"]
            rate = q["rate"]
            instrument = deposit_instrument if (tenor == deposit_tenor and i == 0) else floating_instrument
            ibor_quotes.append(Quote(tenor=tenor, rate=rate, instrument=instrument))
    return ibor_quotes


def build_ibor_curves(curve_date: date, ois_quotes, ibor_quotes_3m, ibor_quotes_6m):
    builder_3m = IborCurveBuilder(curve_date)
    builder_3m.set_ois_quotes(ois_quotes)
    builder_3m.add_ibor_quotes(ibor_quotes_3m)
    build_3m = builder_3m.build()

    builder_6m = IborCurveBuilder(curve_date)
    builder_6m.set_ois_quotes(ois_quotes)
    builder_6m.add_ibor_quotes(ibor_quotes_6m)
    build_6m = builder_6m.build()

    return build_3m, build_6m


def display_ibor_results(curve_date: date, build_3m, build_6m):
    print("\n" + "=" * 120)
    print("IBOR BOOTSTRAP TEST - HARD-CODED DATA (2024-01-02)")
    print("=" * 120)
    print(f"\nCurve Date: {curve_date}")

    print("\n" + "-" * 120)
    print("EURIBOR 3M PROJECTION CURVE")
    print("-" * 120)
    print(f"{'Tenor':<8} {'Maturity':<12} {'Zero Rate %':<14} {'Discount Factor':<16} {'Status'}")
    print("-" * 120)
    for result in build_3m.results[:20]:
        print(f"{result.tenor:<8} {str(result.maturity):<12} {result.zero_rate*100:<14.6f} {result.discount_factor:<16.8f} {'✓'}")

    for tenor in ["10Y", "15Y", "20Y", "30Y", "40Y", "50Y"]:
        for r in build_3m.results:
            if r.tenor.upper() == tenor:
                print(f"{r.tenor:<8} {str(r.maturity):<12} {r.zero_rate*100:<14.6f} {r.discount_factor:<16.8f} {'✓'}")
                break

    print("\n" + "-" * 120)
    print("EURIBOR 6M PROJECTION CURVE")
    print("-" * 120)
    print(f"{'Tenor':<8} {'Maturity':<12} {'Zero Rate %':<14} {'Discount Factor':<16} {'Status'}")
    print("-" * 120)
    for result in build_6m.results[:20]:
        print(f"{result.tenor:<8} {str(result.maturity):<12} {result.zero_rate*100:<14.6f} {result.discount_factor:<16.8f} {'✓'}")

    for tenor in ["10Y", "15Y", "20Y", "30Y", "40Y", "50Y"]:
        for r in build_6m.results:
            if r.tenor.upper() == tenor:
                print(f"{r.tenor:<8} {str(r.maturity):<12} {r.zero_rate*100:<14.6f} {r.discount_factor:<16.8f} {'✓'}")
                break

    print("\n" + "=" * 120)
    print("IBOR curves bootstrapped successfully")
    print("=" * 120)


def main():
    curve_date = CURVE_DATE

    # OIS bootstrap
    ois_quotes = prepare_ois_quotes(curve_date, ESTR_QUOTES)
    bootstrapper = OISBootstrapper(curve_date)
    ois_curve = bootstrapper.bootstrap(
        ois_quotes,
        interpolation_method="STEP_FORWARD_CONTINUOUS",
        floating_leg_convention=ESTR_FLOATING,
        fixed_leg_convention=ESTR_FIXED,
    )
    display_ois_results(curve_date, ois_curve, ois_quotes)

    # IBOR bootstrap (uses the same OIS input quotes)
    ibor_quotes_3m = prepare_ibor_quotes(EURIBOR3M_QUOTES, EURIBOR_3M_FLOATING, EURIBOR_3M_DEPOSIT, "3M")
    ibor_quotes_6m = prepare_ibor_quotes(EURIBOR6M_QUOTES, EURIBOR_6M_FLOATING, EURIBOR_6M_DEPOSIT, "6M")
    build_3m, build_6m = build_ibor_curves(curve_date, ois_quotes, ibor_quotes_3m, ibor_quotes_6m)
    display_ibor_results(curve_date, build_3m, build_6m)

    return True


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
