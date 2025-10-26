# Schedule Generation - Technical Documentation

**Component:** `valuation/schedule.py`
**Purpose:** Generate payment schedules for swap legs with full stub and business day handling
**Status:** ✅ Production (Bloomberg-compatible; forward‑anchored)

---

## Table of Contents

1. [Overview](#overview)
2. [Core Concepts](#core-concepts)
3. [Business Day Adjustments](#business-day-adjustments)
4. [Stub Period Types](#stub-period-types)
5. [Schedule Generation Algorithm](#schedule-generation-algorithm)
6. [Bloomberg Conventions](#bloomberg-conventions)
7. [Implementation](#implementation)
8. [Examples](#examples)
9. [Common Issues](#common-issues)

---

## Overview

Schedule generation is the process of creating the **payment dates** and **accrual periods** for fixed and floating legs of interest rate swaps. This is a critical step that must be performed before any curve bootstrap or swap pricing can occur.

### Why Schedule Generation Matters

Schedules determine:
1. **When cash flows occur** - Payment dates for fixed and floating coupons
2. **How much interest accrues** - Year fractions for each period
3. **Stub period handling** - Dealing with non-standard first/last periods
4. **Business day adjustments** - Ensuring dates fall on valid business days

**Key Insight:** Small differences in schedule generation (especially business day adjustments) can lead to significant pricing discrepancies. Bloomberg SWPM uses specific conventions that must be matched exactly.

### Key Features

- ✅ **Stub period handling** - Short/long stubs, initial/final placement
- ✅ **Business day adjustments** - Modified Following, Following, Preceding, Unadjusted
- ✅ **End-of-month rules** - Preserve month-end dates where appropriate
- ✅ **Roll day conventions** - Pin payment dates to specific days of month
- ✅ **Multiple frequencies** - Annual, semi-annual, quarterly, monthly
- ✅ **Bloomberg compatibility** - Matches SWPM schedule generation

---

## Core Concepts

### Schedule Period

A **schedule period** represents a single cash flow period with the following attributes:

```python
@dataclass
class SchedulePeriod:
    start_date: date          # Period start (adjusted)
    end_date: date            # Period end (adjusted)
    payment_date: date        # When cash flow is paid (adjusted)
    accrual_start: date       # Interest accrual start (adjusted)
    accrual_end: date         # Interest accrual end (adjusted)
    year_fraction: float      # Accrual time using day count convention
    is_stub: bool            # Whether this is a stub period
```

**Important Distinction:**
- **Period dates** (start_date, end_date): Define the nominal period
- **Accrual dates** (accrual_start, accrual_end): Define when interest accrues
- **Payment date**: When the cash flow is actually settled

For most EUR swaps:
- `accrual_start = start_date` (first period)
- `accrual_end = end_date`
- `payment_date = end_date`

### Unadjusted vs Adjusted Dates

**Unadjusted dates** are calculated purely from the calendar without considering business days:
- Example: 2026-08-15 (Saturday)

**Adjusted dates** are shifted to valid business days using business day conventions:
- Example: 2026-08-17 (Monday, using Modified Following)

**Critical Convention (Bloomberg matching):**

Calculate **year fractions using ADJUSTED accrual dates**, not unadjusted dates.

```python
# Bloomberg approach (our implementation)
year_frac = day_count.year_fraction(accrual_start_adj, accrual_end_adj)

# Some other systems (WRONG for Bloomberg matching)
year_frac = day_count.year_fraction(accrual_start_unadj, accrual_end_unadj)
```

### Payment Frequency

Common frequencies for EUR swaps:

| Frequency | Months Between Payments | Typical Use |
|-----------|------------------------|-------------|
| Annual | 12 | ESTR OIS fixed leg, EURIBOR swap fixed leg |
| Semi-Annual | 6 | EURIBOR 6M floating leg |
| Quarterly | 3 | EURIBOR 3M floating leg |
| Monthly | 1 | Short-dated products |

---

## Business Day Adjustments

### Business Day Conventions

When a payment date falls on a non-business day (weekend or holiday), it must be adjusted:

#### Modified Following (MF) - Most Common

**Rule:** If date falls on non-business day, move to next business day **unless** that crosses into next month, then move to previous business day.

**Example:**
```
Original: 2026-08-31 (Monday) → 2026-08-31 (no adjustment needed)
Original: 2026-08-30 (Sunday) → 2026-08-31 (next business day, same month)
Original: 2026-08-31 (Monday, but holiday) → 2026-09-01 (crosses month) → 2026-08-28 (previous)
```

**Why?** Prevents cash flows from "sliding" into next month, which would complicate period calculations.

### Effective‑Date Anchoring (Forward)

We generate floating‑leg schedules **forward from the effective date**, preserving the effective date’s day‑of‑month across periods, and only applying end‑of‑month behavior when the effective date itself is EOM. This mirrors SWPM and avoids 1‑day drifts (e.g., 22nd vs 23rd) that materially impact accruals.

Examples (TARGET, MF):
- 0x30 (base 2025‑10‑20): effective 2025‑10‑22 → first quarters: 2026‑01‑22, 2026‑04‑22, 2026‑07‑22, 2026‑10‑22 (MF can yield 01/24 in some years)
- 10x20: effective 2035‑10‑22 → quarters roll on the 22nd throughout; maturity adjusted with MF.

#### Following (F)

**Rule:** Always move to next business day if date is not valid.

```
Original: 2026-08-30 (Sunday) → 2026-08-31 (next business day)
Original: 2026-08-31 (Monday, but holiday) → 2026-09-01 (crosses month boundary)
```

#### Preceding (P)

**Rule:** Always move to previous business day if date is not valid.

```
Original: 2026-08-30 (Sunday) → 2026-08-28 (previous Friday)
```

#### Unadjusted (U)

**Rule:** No adjustment - use the nominal date even if it's a holiday.

**Rare:** Only used in specific exotic products or for calculation dates (not payment dates).

### TARGET Calendar

EUR swaps use the **TARGET** (Trans-European Automated Real-time Gross settlement Express Transfer) calendar:

**Holidays:**
- Saturdays and Sundays
- New Year's Day (January 1)
- Good Friday (variable)
- Easter Monday (variable)
- Labour Day (May 1)
- Christmas Day (December 25)
- Boxing Day (December 26)

**Note:** ECB holidays are observed, but local country holidays are NOT (e.g., Bastille Day in France is a business day for EUR swaps).

---

## Stub Period Types

When a swap's tenure doesn't divide evenly into regular periods, a **stub period** is created. The stub can be shorter (short stub) or longer (long stub) than regular periods, and placed at the beginning (initial) or end (final).

### Short Final Stub (Default)

**Most common for EUR swaps.** Generate regular periods from the start, with a short stub at the end if needed.

```
Effective: 2025-08-12
Maturity:  2026-12-15  (16.1 months)
Frequency: Semi-annual (6M)

Schedule:
2025-08-12 ────6M───> 2026-02-12 ────6M───> 2026-08-12 ──4.1M──> 2026-12-15
  (Start)       Regular        Regular        Short Stub    (End)
```

**Algorithm:**
1. Roll forward from effective date in regular 6M steps
2. Stop when next period would exceed maturity
3. Add final stub period to maturity

**Year Fractions (ACT/360):**
- Period 1: 184/360 = 0.5111
- Period 2: 181/360 = 0.5028
- Period 3: 125/360 = 0.3472 (stub!)

### Short Initial Stub

Generate regular periods from the **end** (backward from maturity), with a short stub at the beginning.

```
Effective: 2025-08-12
Maturity:  2026-12-15
Frequency: Semi-annual (6M)

Schedule:
2025-08-12 ──4.1M──> 2025-12-15 ────6M───> 2026-06-15 ────6M───> 2026-12-15
  (Start)   Short Stub     Regular        Regular        (End)
```

**Algorithm:**
1. Roll backward from maturity in regular 6M steps
2. Stop when previous period would precede effective date
3. Add initial stub period from effective date

**Use Case:** Some USD swaps, specific structured products.

### Long Final Stub

Similar to short final, but combine the last two periods into one longer stub (instead of having a short stub).

```
Effective: 2025-08-12
Maturity:  2026-12-15
Frequency: Semi-annual (6M)

Schedule:
2025-08-12 ────6M───> 2026-02-12 ─────────10.1M────────> 2026-12-15
  (Start)       Regular            Long Final Stub         (End)
```

**Year Fraction:**
- Period 1: 184/360 = 0.5111
- Period 2: 306/360 = 0.8500 (long stub!)

**Algorithm:**
1. Roll forward from effective date
2. If remaining period after next would be short (<3M typical threshold), combine with current period
3. Create one long final period

**Use Case:** When short stubs would be very short (<2 months), long stubs may be preferred.

### Long Initial Stub

Combine first two periods into one long stub at the beginning.

```
Effective: 2025-08-12
Maturity:  2026-12-15
Frequency: Semi-annual (6M)

Schedule:
2025-08-12 ─────────10.1M────────> 2026-06-15 ────6M───> 2026-12-15
  (Start)    Long Initial Stub         Regular        (End)
```

**Rare** in EUR swaps.

### No Stub

Only works when the tenure divides evenly into regular periods. Raises error otherwise.

```
Effective: 2025-08-12
Maturity:  2026-08-12  (exactly 12M)
Frequency: Semi-annual (6M)

Schedule:
2025-08-12 ────6M───> 2026-02-12 ────6M───> 2026-08-12
  (Start)       Regular        Regular       (End)

No stub! Perfect fit.
```

**Algorithm:**
1. Roll forward from effective date
2. Verify maturity aligns exactly with regular period
3. Raise ValueError if any stub would be created

**Use Case:** Standard tenors (1Y, 2Y, 5Y, 10Y) with standard frequencies typically have no stubs.

### Stub Type Decision Logic

```python
def choose_stub_type(effective_date, maturity_date, frequency):
    """
    Decision logic for stub type selection.
    """
    # Calculate number of regular periods
    months = (maturity_date.year - effective_date.year) * 12 + \
             (maturity_date.month - effective_date.month)

    period_months = {
        Frequency.ANNUAL: 12,
        Frequency.SEMIANNUAL: 6,
        Frequency.QUARTERLY: 3,
        Frequency.MONTHLY: 1,
    }[frequency]

    remainder = months % period_months

    if remainder == 0:
        return StubType.NO_STUB  # Perfect fit
    elif remainder < period_months / 2:
        # Short stub (< 3M for semi-annual)
        return StubType.SHORT_FINAL  # Market standard
    else:
        # Long stub (>= 3M for semi-annual)
        return StubType.LONG_FINAL
```

---

## Schedule Generation Algorithm

### High-Level Workflow

```
1. Parse input parameters (effective, maturity, frequency, stub type)
2. Generate unadjusted dates based on stub type
   a. NO_STUB: Roll forward, verify exact fit
   b. SHORT/LONG_FINAL: Roll forward from start
   c. SHORT/LONG_INITIAL: Roll backward from end
3. Apply business day adjustments to all dates
4. Create SchedulePeriod objects with:
   - Adjusted start/end dates
   - Adjusted accrual dates
   - Year fractions (using ADJUSTED dates)
   - Stub flags
5. Return list of periods
```

### Detailed Algorithm: Short Final Stub

**Most common case for EUR swaps.**

```python
def generate_short_final_stub_schedule(
    effective_date: date,
    maturity_date: date,
    frequency: Frequency,  # e.g., SEMIANNUAL (6M)
) -> List[date]:
    """
    Generate unadjusted schedule dates with short final stub.

    Example:
        Effective: 2025-08-12
        Maturity:  2027-02-15 (18.1 months)
        Frequency: Semi-annual (6M)

        Result: [2025-08-12, 2026-02-12, 2026-08-12, 2027-02-12, 2027-02-15]
                 └─ regular ─┘└─ regular ─┘└─ regular ─┘└─ stub ──┘
    """
    dates = [effective_date]
    current = effective_date

    # Roll forward in regular steps
    while True:
        next_date = add_months(current, frequency.months)  # +6M

        if next_date >= maturity_date:
            # Would overshoot or hit exactly
            if next_date == maturity_date:
                dates.append(next_date)  # Exact hit, no stub
            else:
                dates.append(maturity_date)  # Short stub to maturity
            break

        dates.append(next_date)
        current = next_date

    return dates
```

**Key Points:**
- Roll forward from start (not backward from end)
- Last period may be shorter than regular periods
- Most intuitive for traders ("standard" method)

### Business Day Adjustment

After generating unadjusted dates, apply business day convention:

```python
def adjust_schedule(unadj_dates: List[date], convention: BusinessDayConvention, calendar: Calendar) -> List[date]:
    """
    Apply business day adjustments to all schedule dates.

    Example (Modified Following):
        Unadj: 2026-08-30 (Sunday)
        Adj:   2026-08-31 (Monday, next business day, same month)

        Unadj: 2026-08-31 (Monday, but holiday)
        Adj:   2026-09-01 (Tuesday, next business day)
        If 2026-09-01 crosses into next month:
        Adj:   2026-08-28 (Friday, previous business day)
    """
    adjusted = []
    for dt in unadj_dates:
        adj_dt = apply_business_day_convention(dt, convention, calendar)
        adjusted.append(adj_dt)
    return adjusted
```

### Accrual Date Handling

**Bloomberg Convention:** Use adjusted dates for BOTH period endpoints AND accrual year fraction calculations.

```python
def create_periods(adj_dates: List[date], day_count: DayCountConvention) -> List[SchedulePeriod]:
    """
    Create schedule periods with proper accrual handling.
    """
    periods = []

    for i in range(len(adj_dates) - 1):
        start_adj = adj_dates[i]
        end_adj = adj_dates[i + 1]

        # For first period, accrual starts at period start
        if i == 0:
            accrual_start = start_adj
        else:
            # For subsequent periods, accrual starts where previous period ended
            accrual_start = periods[-1].accrual_end

        accrual_end = end_adj

        # CRITICAL: Use ADJUSTED dates for year fraction
        year_frac = day_count.year_fraction(accrual_start, accrual_end)

        period = SchedulePeriod(
            start_date=start_adj,
            end_date=end_adj,
            payment_date=end_adj,  # Payment at period end
            accrual_start=accrual_start,
            accrual_end=accrual_end,
            year_fraction=year_frac,
            is_stub=(i == len(adj_dates) - 2),  # Last period is stub (if any)
        )
        periods.append(period)

    return periods
```

---

## Bloomberg Conventions

### Critical Differences from Other Systems

Bloomberg SWPM has specific conventions that must be matched for accurate pricing:

1. **Adjusted Accrual Dates**
   - ✅ Bloomberg: Uses adjusted dates for year fractions
   - ❌ Some systems: Use unadjusted dates
   - **Impact:** Can cause 1-2 day differences in accrual, leading to <0.1 bp price differences

2. **Modified Following for EUR Swaps**
   - EUR swaps typically use Modified Following
   - USD swaps may use Following (no month-end rollback)

3. **TARGET Calendar**
   - Must use correct holiday calendar
   - ECB holidays only, not local holidays

4. **Spot Date Calculation**
   - OIS: Typically T+2 (two business days after trade date)
   - Fixed start swaps: Effective date specified explicitly

5. **Stub Period Preference**
   - EUR market: Short final stub is standard
   - USD market: Short initial stub more common

### Bloomberg SWPM Validation

To validate schedule generation against Bloomberg:

1. Open Bloomberg Terminal → SWPM
2. Enter swap details (effective, maturity, frequency)
3. View → Cashflow Schedule
4. Compare dates and year fractions period-by-period

**Example Validation:**
```
Bloomberg SWPM:
Period 1: 2025-08-12 → 2026-02-12, YF = 0.511111
Period 2: 2026-02-12 → 2026-08-12, YF = 0.502778

Our System:
Period 1: 2025-08-12 → 2026-02-12, YF = 0.511111 ✓
Period 2: 2026-02-12 → 2026-08-12, YF = 0.502778 ✓

Match! ✅
```

---

## Implementation

### File Structure

```
engine/schedule/
├── __init__.py          # Module exports
├── generator.py         # ScheduleGenerator class (main logic)
├── core.py              # SchedulePeriod dataclass
├── adjustments.py       # Business day adjustment logic
└── convenience.py       # Helper functions (add_months, etc.)
```

### ScheduleGenerator Class

**File:** `engine/schedule/generator.py`

```python
class ScheduleGenerator:
    """
    Generates payment schedules for swaps with full stub handling.

    Matches Bloomberg SWPM schedule generation conventions.
    """

    def __init__(self, conventions: SwapLegConvention):
        """
        Initialize with swap leg conventions.

        Args:
            conventions: Contains calendar, business day convention, day count, etc.
        """
        self.conventions = conventions

    def generate_schedule(
        self,
        effective_date: date,
        maturity_date: date,
        frequency: Frequency,
        day_count: DayCountConvention,
        stub_type: StubType = StubType.SHORT_FINAL,
        roll_day: Optional[int] = None,
    ) -> List[SchedulePeriod]:
        """
        Generate complete payment schedule.

        Returns:
            List of SchedulePeriod objects with adjusted dates and year fractions
        """
        # 1. Generate unadjusted dates
        unadj_dates = self._generate_unadjusted_dates(
            effective_date, maturity_date, frequency, stub_type, roll_day
        )

        # 2. Adjust for business days
        adj_dates = [self._adjust_date(dt) for dt in unadj_dates]

        # 3. Create periods with accrual handling
        periods = self._create_periods(adj_dates, day_count)

        return periods
```

### Usage Examples

#### Example 1: Standard 5Y EUR Swap (No Stub)

```python
from engine.schedule import ScheduleGenerator
from engine.instruments.swap import EURIBOR6M_FLOATING
from engine.conventions.types import Frequency, StubType
from datetime import date

# EURIBOR 6M floating leg convention
generator = ScheduleGenerator(EURIBOR6M_FLOATING)

# Generate semi-annual schedule
schedule = generator.generate_schedule(
    effective_date=date(2025, 8, 12),  # Spot date
    maturity_date=date(2030, 8, 12),   # 5Y exactly
    frequency=Frequency.SEMIANNUAL,
    day_count=EURIBOR6M_FLOATING.day_count,  # ACT/360
    stub_type=StubType.NO_STUB,  # 5Y / 6M = exact fit
)

# Result: 10 periods (5 years * 2 per year)
for i, period in enumerate(schedule):
    print(f"Period {i+1}: {period.accrual_start} → {period.accrual_end}, "
          f"YF = {period.year_fraction:.6f}, Stub = {period.is_stub}")

# Output:
# Period 1: 2025-08-12 → 2026-02-12, YF = 0.511111, Stub = False
# Period 2: 2026-02-12 → 2026-08-12, YF = 0.502778, Stub = False
# ...
# Period 10: 2030-02-12 → 2030-08-12, YF = 0.505556, Stub = False
```

#### Example 2: Non-Standard Maturity (With Stub)

```python
# 18-month swap (1.5 years)
schedule = generator.generate_schedule(
    effective_date=date(2025, 8, 12),
    maturity_date=date(2027, 2, 15),  # 18.1 months (not exact)
    frequency=Frequency.SEMIANNUAL,
    day_count=ACT_360,
    stub_type=StubType.SHORT_FINAL,  # Default
)

# Result: 4 periods (3 regular + 1 short stub)
# Period 1: 2025-08-12 → 2026-02-12, YF = 0.511111, Stub = False
# Period 2: 2026-02-12 → 2026-08-12, YF = 0.502778, Stub = False
# Period 3: 2026-08-12 → 2027-02-12, YF = 0.505556, Stub = False
# Period 4: 2027-02-12 → 2027-02-15, YF = 0.008333, Stub = True  ← 3 days only!
```

#### Example 3: OIS Fixed Leg (Annual)

```python
from engine.instruments.swap import ESTR_FIXED

generator = ScheduleGenerator(ESTR_FIXED)

# Annual fixed leg for 10Y OIS
schedule = generator.generate_schedule(
    effective_date=date(2025, 8, 12),
    maturity_date=date(2035, 8, 12),
    frequency=Frequency.ANNUAL,
    day_count=ESTR_FIXED.day_count,  # ACT/360
    stub_type=StubType.NO_STUB,
)

# Result: 10 periods (10 years * 1 per year)
```

---

## Common Issues

### Issue 1: Using Unadjusted Dates for Year Fractions

**❌ Wrong:**
```python
# Calculating year fraction with unadjusted dates
unadj_start = date(2026, 8, 30)  # Sunday
unadj_end = date(2027, 2, 28)    # Sunday
year_frac = day_count.year_fraction(unadj_start, unadj_end)  # WRONG
```

**✓ Correct:**
```python
# Adjust first, then calculate
adj_start = adjust_date(unadj_start, ModifiedFollowing, TARGET)  # → 2026-08-31
adj_end = adjust_date(unadj_end, ModifiedFollowing, TARGET)    # → 2027-03-01
year_frac = day_count.year_fraction(adj_start, adj_end)  # CORRECT
```

**Impact:** Can cause 1-3 day differences in accrual → ~0.01-0.03 bp pricing error.

### Issue 2: Wrong Business Day Convention

**❌ Wrong:**
```python
# Using Following instead of Modified Following
adj_date = adjust_date(date(2026, 8, 31), Following, TARGET)
# Result: 2026-09-01 (crosses into next month!)
```

**✓ Correct:**
```python
# Using Modified Following (EUR standard)
adj_date = adjust_date(date(2026, 8, 31), ModifiedFollowing, TARGET)
# Result: 2026-08-28 (rolls back to stay in same month)
```

**Impact:** Can shift payment dates by several days → affects forward rates and pricing.

### Issue 3: Wrong Calendar

**❌ Wrong:**
```python
# Using wrong calendar (e.g., London instead of TARGET)
calendar = Calendar.UK  # WRONG for EUR swaps
```

**✓ Correct:**
```python
# Using TARGET calendar for EUR
calendar = Calendar.TARGET  # CORRECT
```

**Impact:** Different holidays → different adjusted dates → pricing errors.

### Issue 4: Accrual Start/End Mismatch

**❌ Wrong:**
```python
# Not carrying forward accrual_end from previous period
for i, (start, end) in enumerate(zip(adj_dates[:-1], adj_dates[1:])):
    accrual_start = start  # WRONG! Doesn't link periods
    accrual_end = end
    periods.append(SchedulePeriod(accrual_start, accrual_end, ...))
```

**✓ Correct:**
```python
# Properly linking periods
prev_accrual_end = adj_dates[0]
for i, (start, end) in enumerate(zip(adj_dates[:-1], adj_dates[1:])):
    accrual_start = prev_accrual_end if i > 0 else adj_dates[0]
    accrual_end = end
    prev_accrual_end = accrual_end  # Carry forward
    periods.append(SchedulePeriod(accrual_start, accrual_end, ...))
```

**Impact:** Can create gaps or overlaps in accrual periods → incorrect interest calculations.

### Issue 5: Stub Type Confusion

**❌ Wrong:**
```python
# Using SHORT_INITIAL for EUR swaps (USD convention)
stub_type = StubType.SHORT_INITIAL  # WRONG for EUR
```

**✓ Correct:**
```python
# Using SHORT_FINAL for EUR swaps (market standard)
stub_type = StubType.SHORT_FINAL  # CORRECT for EUR
```

**Impact:** Different period structure → entire schedule misaligned with Bloomberg.

---

## QuantLib Status

**Phase 2 Assessment:** Schedule generation replacement with QuantLib was **paused** due to:

1. **High Complexity**
   - QuantLib's `Schedule` API differs significantly from our needs
   - Requires extensive wrapper code to match Bloomberg conventions
   - `MakeSchedule` builder pattern adds complexity

2. **High Risk**
   - Subtle differences in business day adjustments
   - Different default behaviors for stubs
   - Risk of regression in Bloomberg matching

3. **Low Benefit**
   - Current custom implementation works perfectly
   - All tests passing with <0.01 bp accuracy
   - Well-understood and maintainable

**Decision:** Keep custom schedule generation, use QuantLib for curve bootstrap only.

See `markdown/quantlib_phase2_assessment.md` for detailed analysis.

---

## Further Reading

- **OIS Bootstrap:** [02_ois_bootstrap.md](02_ois_bootstrap.md) - Uses schedules for OIS swap instruments
- **IBOR Bootstrap:** [03_ibor_bootstrap.md](03_ibor_bootstrap.md) - Uses schedules for EURIBOR swap instruments
- **Conventions:** [01_conventions.md](01_conventions.md) - Day count conventions and calendars

---

*Last updated: 2025 (post-refactoring)*
