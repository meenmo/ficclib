# Market Conventions - Technical Documentation

**Component:** `pricer.swap.conventions`
**Dependencies:** QuantLib 1.39
**Version:** 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Day Count Conventions](#day-count-conventions)
3. [Business Day Calendars](#business-day-calendars)
4. [Business Day Adjustments](#business-day-adjustments)
5. [Other Conventions](#other-conventions)
6. [QuantLib Integration](#quantlib-integration)
7. [Usage Examples](#usage-examples)

---

## Overview

Market conventions define how dates, day counts, and business days are handled in financial calculations. These conventions vary by currency, instrument type, and market practice.

**Why they matter:**
- Wrong day count = wrong accrual calculation = wrong pricing
- Wrong business day adjustment = misaligned cash flows
- Must match Bloomberg/market standards exactly

**EUR Market Standards:**
- OIS (ESTR): ACT/365F for floating, ACT/360 for fixed
- IBOR (EURIBOR): ACT/360 for floating
- Calendar: TARGET (Trans-European Automated Real-time Gross settlement)
- Spot lag: T+2

---

## Day Count Conventions

### Purpose

Calculate the year fraction between two dates for accrual calculations.

**Formula:**
```
Year Fraction = Accrual Amount / Notional Amount
              = (Days / Basis) × Interest Rate
```

### Implementation

**Module:** `pricer.swap.conventions.daycount`

**Available Conventions:**

| Convention | Name | Usage | Basis |
|------------|------|-------|-------|
| `ACT/360` | Actual/360 | EURIBOR floating, OIS fixed | 360 |
| `ACT/365F` | Actual/365 Fixed | ESTR floating | 365 |
| `30E/360` | 30/360 European | EUR bonds, some swaps | 360 |
| `30U/360` | 30/360 US | USD bonds | 360 |
| `ACT/ACT` | Actual/Actual ISDA | Bonds | Variable |
| `ACT/360A` | Actual/360 Adjusted | Special (excludes Feb 29) | 360 |

### ACT/360 (Actual/360)

**Used for:** EURIBOR floating legs, OIS fixed legs

**Rule:**
```
Year Fraction = Actual Days / 360
```

**Example:**
```python
# 2025-08-12 to 2026-02-12 = 184 days
# Year fraction = 184 / 360 = 0.511111...
```

**Code Example:**
```python
from ficclib.swap.conventions.daycount import get_day_count_convention

dcc = get_day_count_convention("ACT/360")
year_frac = dcc.year_fraction(start_date, end_date)
```

**QuantLib Implementation:**
- Uses `ql.Actual360()` for exact market standard
- Counts actual calendar days (including weekends/holidays)
- Divides by 360

---

### ACT/365F (Actual/365 Fixed)

**Used for:** ESTR floating legs (OIS)

**Rule:**
```
Year Fraction = Actual Days / 365
```

**Important:** Always 365, even in leap years (hence "Fixed")

**Example:**
```python
# 2024-02-01 to 2024-08-01 = 182 days
# Year fraction = 182 / 365 = 0.498630...
# (NOT 182/366 even though 2024 is a leap year)
```

**Code Example:**
```python
from ficclib.swap.conventions.daycount import get_day_count_convention

dcc = get_day_count_convention("ACT/365F")
year_frac = dcc.year_fraction(start_date, end_date)
```

---

### 30E/360 (30/360 European)

**Used for:** EUR bond fixed legs, some swap fixed legs

**Rules:**
1. If start day = 31, change to 30
2. If end day = 31, change to 30
3. Calculate: `(360 × (Y₂-Y₁) + 30 × (M₂-M₁) + (D₂-D₁)) / 360`

**Example:**
```python
# 2025-01-31 to 2025-04-30
# Adjusted: 2025-01-30 to 2025-04-30
# Days = 360×0 + 30×3 + (30-30) = 90
# Year fraction = 90 / 360 = 0.25
```

**Code Example:**
```python
from ficclib.swap.conventions.daycount import get_day_count_convention

dcc = get_day_count_convention("30E/360")
year_frac = dcc.year_fraction(start_date, end_date)
```

---

### ACT/360A (Actual/360 Adjusted - No Leap)

**Used for:** Special cases (rare in EUR markets)

**Rule:**
```
Year Fraction = (Actual Days - Feb 29 count) / 360
```

**Example:**
```python
# 2024-01-01 to 2024-12-31 = 366 days
# Contains Feb 29, 2024 → subtract 1
# Year fraction = 365 / 360 = 1.013889...
```

**Code Example:**
```python
from ficclib.swap.conventions.daycount import get_day_count_convention

dcc = get_day_count_convention("ACT/360A")
year_frac = dcc.year_fraction(start_date, end_date)
```

**Note:** QuantLib doesn't have this convention, so we use a custom implementation.

---

## Business Day Calendars

### Purpose

Determine which days are business days (markets open) vs holidays/weekends.

**Why it matters:**
- Cash flows only settle on business days
- Swap rates quoted for business day-adjusted dates
- Spot lag calculation requires business day counting

### TARGET Calendar

**Module:** `pricer.swap.conventions.calendars`

**TARGET = Trans-European Automated Real-time Gross settlement Express Transfer**

**Official calendar for:**
- EUR settlements
- ECB operations
- ESTR swaps
- EURIBOR swaps

**Holidays:**
- New Year's Day (January 1)
- Good Friday (varies)
- Easter Monday (varies)
- Labour Day (May 1)
- Christmas (December 25)
- Boxing Day (December 26)

**Easter Calculation:**
- Uses Meeus/Jones/Butcher algorithm
- Automatically calculated by QuantLib
- No manual updates needed

**Code Example:**

```python
from ficclib.swap.conventions.calendars import get_calendar

calendar = get_calendar("TARGET")

# Check if business day
is_bd = calendar.is_business_day(date(2025, 8, 8))  # True (Friday)
is_bd = calendar.is_business_day(date(2025, 8, 9))  # False (Saturday)

# Add business days (T+2 spot lag)
spot = calendar.add_business_days(date(2025, 8, 8), 2)  # 2025-08-12

# Count business days between dates
count = calendar.business_days_between(
    date(2025, 8, 8), date(2025, 8, 12)
)  # 2
```

---

## Business Day Adjustments

### Purpose

When a payment date falls on a non-business day, adjust it to a business day.

**Module:** `pricer.swap.schedule.adjustments`

### Available Adjustments

| Convention | Rule | Example (if Saturday) |
|------------|------|----------------------|
| `NO_ADJUSTMENT` | Keep unadjusted | Saturday |
| `FOLLOWING` | Next business day | Monday |
| `MODIFIED_FOLLOWING` | Following, unless crosses month | Friday (if Following→Monday next month) |
| `PRECEDING` | Previous business day | Friday |
| `MODIFIED_PRECEDING` | Preceding, unless crosses month | Monday (if Preceding→Friday prior month) |

### MODIFIED_FOLLOWING (Most Common)

**Rule:**
1. Apply FOLLOWING (next business day)
2. If result is in different month, apply PRECEDING instead

**Why:** Keeps payment in correct month for month-end dates

**Example:**
```python
# 2025-08-30 (Saturday)
# Following → 2025-09-01 (Monday, but different month!)
# Modified Following → 2025-08-29 (Friday, stays in August)
```

**Code Example:**
```python
from datetime import date
from ficclib.swap.schedule.adjustments import adjust_date
from ficclib.swap.conventions.calendars import get_calendar
from ficclib.swap.conventions.types import BusinessDayAdjustment

calendar = get_calendar("TARGET")
unadjusted = date(2025, 8, 30)  # Saturday
adjusted = adjust_date(unadjusted, BusinessDayAdjustment.MODIFIED_FOLLOWING, calendar)
# Result: 2025-08-29 (Friday, stays in August)
```

---

## Other Conventions

### Frequency

**Module:** `pricer.swap.conventions.types`

| Frequency | Months | Usage |
|-----------|--------|-------|
| `ANNUAL` | 12 | 1Y swaps fixed leg |
| `SEMIANNUAL` | 6 | 6M swaps |
| `QUARTERLY` | 3 | 3M swaps |
| `MONTHLY` | 1 | Money market |
| `DAILY` | ~0.08 | OIS (ESTR) |

**Code Example:**
```python
from ficclib.swap.conventions.types import Frequency

# Access frequency values
freq = Frequency.SEMIANNUAL
months = freq.value  # 6
```

---

### Stub Type

**Module:** `pricer.swap.conventions.types`

| Stub Type | Description | When to Use |
|-----------|-------------|-------------|
| `NO_STUB` | Exact fit | Periods align perfectly |
| `SHORT_INITIAL` | Short period at start | Forward generation |
| `LONG_INITIAL` | Long period at start | Rare |
| `SHORT_FINAL` | Short period at end | **Default (Bloomberg)** |
| `LONG_FINAL` | Long period at end | Rare |

**Example:**
```
SHORT_FINAL: 2025-08-12 ──6M──> 2026-02-12 ──6M──> 2026-08-12 ──4M──> 2026-12-15

SHORT_INITIAL: 2025-08-12 ──4M──> 2025-12-15 ──6M──> 2026-06-15 ──6M──> 2026-12-15
```

---

### Roll Convention

**Module:** `pricer.swap.conventions.types`

**Purpose:** Determine schedule generation direction

| Convention | Description |
|------------|-------------|
| `BACKWARD_EOM` | Generate backward from maturity, apply end-of-month rule |

**Bloomberg Standard:** BACKWARD_EOM for EUR swaps

---

## QuantLib Integration

### Phase 1 Replacement (Complete)

**Before (Custom Implementation):**
```python
# Manual holiday list (282 dates)
TE = [
    "2025-01-01",
    "2025-04-18",
    # ... 280 more dates
]

# Custom day count calculation
def year_fraction(start, end):
    actual_days = (end - start).days
    return actual_days / 360.0
```

**After (QuantLib-backed):**
```python
from ficclib.swap.conventions.daycount import get_day_count_convention
from ficclib.swap.conventions.calendars import get_calendar

# Industry-standard implementation
dcc = get_day_count_convention("ACT/360")
calendar = get_calendar("TARGET")
```

**Benefits:**
- ✅ Eliminated 282 manually maintained holidays
- ✅ Automatic Easter calculation
- ✅ Industry-standard accuracy
- ✅ Reduced maintenance burden
- ✅ Zero regression in tests

**Documentation:** QuantLib integration is complete as of v1.0.0

---

## Usage Examples

### Example 1: Calculate Year Fraction

```python
from datetime import date
from ficclib.swap.conventions.daycount import get_day_count_convention

# Get ACT/360 convention
dcc = get_day_count_convention("ACT/360")

# Calculate year fraction for 6M period
start = date(2025, 8, 12)
end = date(2026, 2, 12)
year_frac = dcc.year_fraction(start, end)

print(f"Days: {(end - start).days}")        # 184
print(f"Year fraction: {year_frac:.10f}")   # 0.5111111111
```

---

### Example 2: Business Day Adjustments

```python
from datetime import date
from ficclib.swap.conventions.calendars import get_calendar

calendar = get_calendar("TARGET")

# Check if business day
friday = date(2025, 8, 8)
saturday = date(2025, 8, 9)

print(f"Friday is BD: {calendar.is_business_day(friday)}")     # True
print(f"Saturday is BD: {calendar.is_business_day(saturday)}") # False

# Calculate spot date (T+2)
curve_date = date(2025, 8, 8)  # Friday
spot_date = calendar.add_business_days(curve_date, 2)
print(f"Spot date: {spot_date}")  # 2025-08-12 (Tuesday)
```

---

### Example 3: Swap Schedule with Conventions

```python
from datetime import date
from ficclib.swap.valuation.schedule import build_schedule
from ficclib.swap.conventions.daycount import get_day_count_convention
from ficclib.swap.conventions.types import Frequency, StubType
from ficclib.swap.instruments.swap import EURIBOR_6M_FLOATING

# Build schedule using convention
schedule = build_schedule(

    effective_date=date(2025, 8, 12),
    maturity_date=date(2026, 8, 12),
    convention=EURIBOR_6M_FLOATING,
)

# Print periods
for i, period in enumerate(schedule):
    print(f"Period {i+1}:")
    print(f"  Accrual: {period.accrual_start} -> {period.accrual_end}")
    print(f"  Payment: {period.payment_date}")
```

---

### Example 4: All Conventions for EURIBOR 6M Swap

```python
from ficclib.swap.instruments.swap import EURIBOR_6M_FLOATING

conv = EURIBOR_6M_FLOATING

print(f"Day count: {conv.day_count}")                        # ACT/360
print(f"Calendar: {conv.calendar}")                          # TARGET
print(f"Reset frequency: {conv.reset_frequency}")            # SEMIANNUAL
print(f"Pay frequency: {conv.pay_frequency}")                # SEMIANNUAL
print(f"Business day adj: {conv.business_day_adjustment}")   # MODIFIED_FOLLOWING
print(f"Fixing lag: {conv.fixing_lag_days}")                 # 2 business days
print(f"Payment delay: {conv.payment_delay_days}")           # 0 business days
```

---

## Module Reference

| Module | Purpose | Lines |
|--------|---------|-------|
| `pricer.swap.conventions.daycount` | Day count conventions (QuantLib) | ~190 |
| `pricer.swap.conventions.calendars` | Business day calendars (QuantLib) | ~150 |
| `pricer.swap.conventions.types` | Enums (Frequency, StubType, etc.) | ~65 |
| `pricer.swap.schedule.adjustments` | Business day adjustment functions | ~125 |

---

## Testing

**Integration Tests:**
- `pricer.swap.test.npv` - Swap pricing with conventions
- `pricer.swap.test.par_swap_spread` - Par swap spread calculation

**Results:** All tests pass with Bloomberg SWPM-matching accuracy

---

## Common Pitfalls

### 1. ACT/365F vs ACT/365

**Wrong:**
```python
# ACT/365 adjusts for leap years
year_frac = days / (366 if is_leap_year else 365)
```

**Right:**
```python
# ACT/365F always uses 365
year_frac = days / 365
```

---

### 2. Business Day vs Calendar Day Counting

**Wrong:**
```python
# Count calendar days
days = (end - start).days
```

**Right:**
```python
# Count business days when needed
bus_days = calendar.business_days_between(start, end)
```

---

### 3. Forgetting to Adjust Dates

**Wrong:**
```python
# Use unadjusted dates for payment
payment_date = schedule_end_date  # Might be weekend!
```

**Right:**
```python
# Always adjust payment dates
payment_date = calendar.adjust(schedule_end_date, ModifiedFollowing)
```

---

## References

### Internal
- [System Overview](00_overview.md)
- [Schedule Generation](05_schedule_generation.md)
- [QuantLib Integration](07_quantlib_integration.md)

### External
- [QuantLib Day Counters](https://www.quantlib.org/reference/group__daycounters.html)
- [QuantLib Calendars](https://www.quantlib.org/reference/group__calendars.html)
- [ECB TARGET Calendar](https://www.ecb.europa.eu/paym/target/target2/profuse/calendar/html/index.en.html)
- [ISDA Day Count Conventions](https://www.isda.org/book/2006-isda-definitions/)

---

*Next: [OIS Bootstrap](02_ois_bootstrap.md) - Building the discount curve*
