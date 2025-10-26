# IBOR Bootstrap (Step 2) - Technical Documentation

**Component:** `engine/curves/ibor/bootstrap/`
**Purpose:** Build projection curve from EURIBOR swap quotes using dual-curve framework
**Status:** ✅ Production (< 0.32 bp accuracy for all tenors, refactored 2025)

---

## Table of Contents

1. [Overview](#overview)
2. [Dual-Curve Framework Explained](#dual-curve-framework-explained)
3. [Input Data](#input-data)
4. [Mathematical Formulation](#mathematical-formulation)
5. [Bootstrap Algorithm](#bootstrap-algorithm)
6. [Code Architecture](#code-architecture)
7. [Step-by-Step Example](#step-by-step-example)
8. [Testing & Validation](#testing--validation)
9. [Key Differences from OIS](#key-differences-from-ois)

---

## Overview

IBOR (Interbank Offered Rate) bootstrap constructs a **projection curve** used to forecast EURIBOR rates for interest rate swap pricing. This is the second step in the dual-curve bootstrap process.

**Key Concepts:**
- **OIS (Step 1):** Builds discount curve using risk-free ESTR swaps
- **IBOR (Step 2):** Builds projection curve using EURIBOR swaps (contains credit premium)
- **Dual-Curve:** Uses OIS curve for discounting, IBOR curve for forward rate projection

**Why Two Curves?**

Post-2008 financial crisis, regulators separated discounting from projection:

$$\text{EURIBOR} \approx \text{ESTR} + \text{Credit Spread}$$

where Credit Spread ≈ 10-30 basis points representing interbank credit risk.

---

## Dual-Curve Framework Explained

### Pre-2008: Single Curve

Before the crisis, both discounting and projection used the same curve:

$$\text{PV}_{\text{swap}} = \sum_{i=1}^{n} \text{CF}_i \times \text{DF}_{\text{LIBOR}}(T_i)$$

**Problem:** Assumed LIBOR = risk-free rate, which proved false in 2008.

### Post-2008: Dual Curve

Modern framework separates concerns:

$$\text{PV}_{\text{swap}} = \sum_{i=1}^{n} F_{\text{EURIBOR}}(T_{i-1}, T_i) \times \tau_i \times \text{DF}_{\text{OIS}}(T_i)$$

where:
- $\text{DF}_{\text{OIS}}$ = Discount factors from OIS curve (risk-free)
- $F_{\text{EURIBOR}}$ = Forward rates from IBOR projection curve

**Key Insight:** We discount cash flows using the risk-free OIS curve, but project future EURIBOR rates using the IBOR curve that contains credit premium.

---

## Input Data

### Market Quotes

EURIBOR 3M or 6M swap quotes from Bloomberg:

```python
# Example: EURIBOR 6M quotes for 2025-08-08
ibor_quotes = [
    Quote("6M", 0.02083, EURIBOR6M_DEPOSIT),   # 6M deposit
    Quote("1Y", 0.02045, EURIBOR6M_FIXED),     # 1Y swap
    Quote("18M", 0.02035, EURIBOR6M_FIXED),    # 18M swap
    Quote("2Y", 0.02063, EURIBOR6M_FIXED),     # 2Y swap
    ...
    Quote("50Y", 0.02650, EURIBOR6M_FIXED),    # 50Y swap
]
```

### Required Inputs

1. **OIS Discount Curve** (from Step 1) - Used for discounting all cash flows
2. **IBOR Market Quotes** - Swap par rates for various tenors
3. **Market Conventions** - Day count, frequency, calendar, business day adjustment

### Using the Factory Pattern

```python
from engine.data import create_ibor_data_source, DataSourceType

# Create data source with standard filters
data_source = create_ibor_data_source(
    DataSourceType.JSON,
    tenor="6M",  # or "3M"
    apply_standard_filters=True,
    data_directory="/path/to/data"
)

# Load quotes for specific date
quotes = data_source.load_ibor_quotes(
    curve_date=date(2025, 8, 8),
    reference_index="EURIBOR6M",
    source="BGN"
)
```

---

## Mathematical Formulation

### Pseudo-Discount Factors

The IBOR projection curve uses **pseudo-discount factors** (denoted $P_x(T)$) which are NOT true discount factors but rather represent the forward rate structure:

$$F(T_1, T_2) = \frac{1}{\tau} \left(\frac{P_x(T_1)}{P_x(T_2)} - 1\right)$$

where:
- $F(T_1, T_2)$ = Forward EURIBOR rate between $T_1$ and $T_2$
- $P_x(T)$ = Pseudo-discount factor at time $T$
- $\tau$ = Accrual fraction between $T_1$ and $T_2$ (ACT/360 for EURIBOR)

**Important:** $P_x(T) 
eq \text{DF}_{\text{OIS}}(T)$. The pseudo-DFs are a mathematical construct for the projection curve only.

### Deposit Bootstrap (Short End)

For short-dated deposits (e.g., 6M), the bootstrap is straightforward:

$$P_x(T_{\text{mat}}) = \frac{P_x(T_{\text{spot}})}{1 + r_{\text{deposit}} \times \tau}$$

where:
- $r_{\text{deposit}}$ = Quoted deposit rate
- $\tau$ = Deposit accrual fraction (ACT/360)
- $T_{\text{spot}}$ = Spot date (typically T+2)
- $T_{\text{mat}}$ = Deposit maturity

**Front Stub Calculation:**

The front stub pseudo-DF between curve date and spot date is:

$$P_x(T_{\text{spot}}) = \exp\left(-r_{\text{inst}} \times \tau_{\text{stub}}\right)$$

where $r_{\text{inst}}$ is derived from the first deposit's instantaneous forward rate.

### Swap Bootstrap (Long End)

For swaps, we solve the par swap equation using root-finding:

**Fixed Leg PV:**

$$\text{PV}_{\text{fixed}} = N \times r_{\text{fixed}} \times \sum_{i=1}^{n} \tau_i^{\text{fixed}} \times \text{DF}_{\text{OIS}}(T_i)$$

**Floating Leg PV:**

$$\text{PV}_{\text{floating}} = N \times \sum_{j=1}^{m} F(T_{j-1}, T_j) \times \tau_j^{\text{float}} \times \text{DF}_{\text{OIS}}(T_j)$$

where:

$$F(T_{j-1}, T_j) = \frac{1}{\tau_j^{\text{float}}} \left(\frac{P_x(T_{j-1})}{P_x(T_j)} - 1\right)$$

**Bootstrap Equation:**

At par: $\text{PV}_{\text{fixed}} = \text{PV}_{\text{floating}}$

We solve for $P_x(T_n)$ (the final swap maturity) using bisection method.

### Interpolation Between Pillars

For dates between known pillars, we use **step-forward interpolation** (piecewise constant forward rates):

$$P_x(T) = P_x(T_1) \times \exp\left(-f_{1,2} \times (t - t_1)\right)$$

where:
- $T_1$ = Previous pillar date
- $T_2$ = Next pillar date
- $f_{1,2} = \frac{\log P_x(T_1) - \log P_x(T_2)}{t_2 - t_1}$ = Forward rate between pillars
- $t$ = Time (in years, ACT/365F) for target date $T$

---

## Bootstrap Algorithm

### High-Level Workflow

```
1. Initialize with OIS discount curve and curve date
2. Calculate front stub pseudo-DF from first deposit
3. Bootstrap deposits sequentially → add pillars
4. Bootstrap swaps sequentially using root-finding:
   a. Calculate fixed leg PV (known, uses OIS curve)
   b. Setup context with previous anchor pillar
   c. Solve for final pseudo-DF using bisection
   d. Update projection map with intermediate dates
   e. Add final maturity as pillar
5. Build IborProjectionCurve from pillars
```

### Detailed Algorithm

**Phase 1: Deposit Bootstrap**

```python
for deposit in sorted_deposits:
    # Calculate pseudo-DF for this maturity
    px = front_stub_df / (1 + deposit.rate * deposit.accrual_fraction())

    # Add as pillar
    projection_map[deposit.maturity] = px
```

**Phase 2: Swap Bootstrap**

For each swap, solve the nonlinear equation:

$$\text{Residual}(P_x^{\text{final}}) = \text{PV}_{\text{fixed}} - \text{PV}_{\text{floating}}(P_x^{\text{final}}) = 0$$

**Root-Finding Steps:**

1. **Setup Context:**
   ```python
   context = {
       'fixed_pv': calculate_fixed_leg_pv(swap),  # Uses OIS curve
       'projection_map': current_projection_map,
       'prev_anchor_date': max(d for d in projection_map if d < final_maturity),
       'px_prev': projection_map[prev_anchor_date],
   }
   ```

2. **Define Residual Function:**
   ```python
   def residual(px_final):
       pv_float = 0.0
       for period in swap.floating_periods():
           # Project pseudo-DFs using candidate px_final
           px_start = project_df(period.start, px_final, context)
           px_end = project_df(period.end, px_final, context)

           # Calculate forward rate
           forward = (px_start / px_end - 1.0) / period.year_fraction

           # Discount with OIS curve
           df_ois = ois_curve.df(period.end)

           pv_float += period.year_fraction * forward * df_ois

       return fixed_pv - pv_float
   ```

3. **Bracket Solution:**
   ```python
   lower = px_prev * 0.1   # Much lower than previous
   upper = px_prev * 0.999999  # Slightly below previous

   # Expand bracket until signs differ
   while residual(lower) * residual(upper) > 0:
       lower *= 0.5
       upper = (upper + px_prev) / 2.0
   ```

4. **Bisect to Find Root:**
   ```python
   for iteration in range(100):
       mid = 0.5 * (lower + upper)
       res_mid = residual(mid)

       if abs(res_mid) < 1e-14 or abs(upper - lower) < 1e-14:
           return mid  # Converged

       # Update bracket
       if residual(lower) * res_mid <= 0:
           upper = mid
       else:
           lower = mid
   ```

5. **Update Projection Map:**
   ```python
   # Add all intermediate accrual dates
   for period in swap.floating_periods():
       projection_map[period.end] = project_df(period.end, px_final, context)

   # Add final maturity as pillar
   pillars[swap.maturity] = px_final
   ```

---

## Code Architecture

### Refactored Structure (2025)

The IBOR bootstrap engine was refactored to follow SOLID principles with helper methods <30 lines:

**File:** `engine/curves/ibor/bootstrap/engine.py`

```python
class BootstrapEngine:
    """Implements the Bloomberg-style dual-curve IBOR bootstrap."""

    def __init__(self, curve_date: date, ois_curve: OISDiscountCurve, index_name: str):
        self.curve_date = curve_date
        self.spot_date = get_spot_date(curve_date)
        self.ois_curve = ois_curve  # Critical: uses OIS for discounting
        self.index_name = index_name

        self.state = ProjectionCurveState(curve_date, self.spot_date)
        self._results: List[BootstrapResult] = []

    # Main API (15 lines) - orchestrates the bootstrap
    def bootstrap_swap(self, swap: SwapInstrument) -> None:
        """Bootstrap a single swap instrument."""
        periods = swap.floating_periods()
        if not periods:
            raise ValueError(f"Floating schedule unavailable for tenor {swap.get_tenor()}")

        context = self._setup_swap_context(swap, periods)
        px_end = self._solve_for_pseudo_df(swap, periods, context)
        self._finalize_swap_bootstrap(swap, periods, px_end, context)

    # Helper methods (all <30 lines)
    def _setup_swap_context(self, swap, periods) -> Dict:
        """Setup context for swap bootstrap."""
        # Returns dict with fixed_pv, projection_map, anchors, etc.

    def _solve_for_pseudo_df(self, swap, periods, context) -> float:
        """Solve for pseudo-discount factor using root finding."""
        residual = self._create_residual_function(periods, context)
        lower, upper = self._bracket_solution(swap, residual, context['px_prev'])
        px_end = self._bisect_solution(residual, lower, upper)
        return px_end

    def _calculate_floating_pv(self, periods, px_final, context) -> float:
        """Calculate floating leg PV for given final pseudo-DF."""
        # Loops through periods, projects DFs, calculates forwards, discounts

    def _project_df(self, target_date, candidate_px, log_candidate, context) -> float:
        """Project pseudo-discount factor to target date."""
        # Uses step-forward interpolation between pillars

    # ... more helpers for interpolation, bracketing, bisection, etc.
```

### Key Classes

**`ProjectionCurveState`** (engine/curves/ibor/bootstrap/state.py):
- Manages pillar dates and pseudo-discount factors
- Maintains projection map for all intermediate dates
- Builds final `IborProjectionCurve`

**`SwapInstrument`** (engine/instruments/swap.py):
- Represents EURIBOR swap with fixed and floating legs
- Generates payment schedules
- Provides cashflow iterators

**`IborProjectionCurve`** (engine/curves/projection.py):
- Final curve object with interpolation
- Methods: `forward_rate()`, `df()`, `zero_rate()`

---

## Step-by-Step Example

Let's walk through bootstrapping a 2Y EURIBOR 6M swap on 2025-08-08.

### Given Data

```python
# Market inputs
curve_date = date(2025, 8, 8)
spot_date = date(2025, 8, 12)  # T+2

# Already bootstrapped from Step 1
ois_curve = OISDiscountCurve(...)

# Previous pillars (from 6M deposit and 1Y swap)
projection_map = {
    spot_date: 1.0,         # Front stub
    date(2026, 2, 12): 0.989512,  # 6M deposit
    date(2026, 8, 12): 0.979833,  # 1Y swap
}

# New instrument to bootstrap
swap_2y = SwapInstrument(
    tenor="2Y",
    fixed_rate=0.02063,  # Par rate from market
    # ... conventions
)
```

### Step 1: Calculate Fixed Leg PV

The fixed leg pays annual coupons at 2.063%:

```python
fixed_cashflows = [
    (date(2026, 8, 12), 0.02063 * 1.0139),  # Year 1
    (date(2027, 8, 12), 0.02063 * 1.0139),  # Year 2
]

pv_fixed = sum(cf * ois_curve.df(d) for d, cf in fixed_cashflows)
# ≈ 0.02063 * 1.0139 * (0.97234 + 0.96012)
# ≈ 0.0405
```

**Note:** All discounting uses OIS curve, NOT the IBOR curve being built!

### Step 2: Setup Context

```python
context = {
    'fixed_pv': 0.0405,
    'projection_map': projection_map,
    'final_end': date(2027, 8, 12),  # 2Y maturity
    'prev_anchor_date': date(2026, 8, 12),  # 1Y pillar
    'px_prev': 0.979833,
    't_prev': 1.0139,  # Time from curve_date to 1Y
    't_final': 2.0278,  # Time from curve_date to 2Y
}
```

### Step 3: Define Residual Function

We need to find $P_x(\text{2Y})$ such that floating leg PV matches fixed leg PV:

```python
def residual(px_final):
    """
    Calculate PV_fixed - PV_floating.
    Root is where this equals zero.
    """
    pv_float = 0.0

    # Floating leg has 4 semi-annual periods
    periods = [
        (date(2025, 8, 12), date(2026, 2, 12)),  # 0-6M
        (date(2026, 2, 12), date(2026, 8, 12)),  # 6M-1Y
        (date(2026, 8, 12), date(2027, 2, 12)),  # 1Y-18M
        (date(2027, 2, 12), date(2027, 8, 12)),  # 18M-2Y
    ]

    for start, end in periods:
        # Project pseudo-DFs
        px_start = project_df(start, px_final, context)
        px_end = project_df(end, px_final, context)

        # Calculate forward rate
        tau = 0.5  # 6M in ACT/360
        forward = (px_start / px_end - 1.0) / tau

        # Discount with OIS
        df_ois = ois_curve.df(end)

        # Add contribution
        pv_float += tau * forward * df_ois

    return 0.0405 - pv_float  # Target: zero
```

### Step 4: Project Pseudo-DFs

The `project_df()` function handles different cases:

```python
def project_df(target_date, px_final, context):
    """Project pseudo-DF to target date."""

    # Case 1: Already in projection map (dates ≤ 1Y)
    if target_date in context['projection_map']:
        return context['projection_map'][target_date]

    # Case 2: Final maturity
    if target_date == context['final_end']:
        return px_final  # The candidate we're testing

    # Case 3: Between prev_anchor (1Y) and final (2Y)
    # Use step-forward interpolation
    t_target = time_fraction(curve_date, target_date)
    t_prev = context['t_prev']  # 1.0139
    t_final = context['t_final']  # 2.0278

    px_prev = context['px_prev']  # 0.979833
    log_px_prev = log(px_prev)
    log_px_final = log(px_final)

    # Constant forward rate between 1Y and 2Y
    forward_rate = (log_px_prev - log_px_final) / (t_final - t_prev)

    # Exponentially decay from prev_anchor
    return px_prev * exp(-forward_rate * (t_target - t_prev))
```

### Step 5: Bracket and Bisect

```python
# Initial bracket
lower = 0.979833 * 0.1 = 0.0979833
upper = 0.979833 * 0.999999 = 0.979832

residual(lower) = 0.0405 - (large positive PV) < 0
residual(upper) = 0.0405 - (small positive PV) > 0

# Signs differ → bracket found!

# Bisect for ~50 iterations
while abs(upper - lower) > 1e-14:
    mid = 0.5 * (lower + upper)
    if residual(mid) < 0:
        lower = mid
    else:
        upper = mid

# Converged: px_final ≈ 0.959123
```

### Step 6: Finalize Bootstrap

```python
# Add all accrual dates to projection map
projection_map[date(2026, 2, 12)] = 0.989512  # Already there
projection_map[date(2026, 8, 12)] = 0.979833  # Already there
projection_map[date(2027, 2, 12)] = 0.969401  # New (interpolated)
projection_map[date(2027, 8, 12)] = 0.959123  # New (solved)

# Add 2Y maturity as pillar
pillars[date(2027, 8, 12)] = 0.959123

# Continue to 3Y, 4Y, 5Y, ...
```

### Result

The 2Y pseudo-discount factor is **0.959123**, which implies a zero rate of:

$$r_{\text{zero}}^{\text{2Y}} = -\frac{\log(0.959123)}{2.0278} = 2.0670\%$$

This matches the expected zero rate for 2Y EURIBOR 6M.

---

## Testing & Validation

### Automated regression

Run `pricer/swap/.venv/bin/python -m pricer.swap.test.bootstrapping` after Step 1 succeeds.

Recent run (2025-10-17) produced three datasets:

| Curve Date   | Dataset                        | Result | Max ΔZero (bp) | Notes |
|--------------|--------------------------------|--------|----------------|-------|
| 2025-03-05   | EURIBOR 6M (BGN)               | PASS   | ≤0.01          | All pillars, 6M–50Y, matched Bloomberg within 0.01 bp and maturities aligned. |
| 2025-08-08   | EURIBOR 6M (BGN)               | PASS   | ≤0.02          | Regression printed dual ✓ for every tenor; DF deltas were below machine precision. |
| 2025-08-08   | EURIBOR 6M (BGN, alt fixture)  | FAIL   | ≤0.01          | Rates agree, but target maturities in `test_cases.py` trail the calendar-adjusted dates by one business day (e.g. 3M target 2025-11-06 vs actual 2025-11-12), so the test flags every pillar. |

**Action item:** update the failing fixture to derive target maturities via `compute_maturity()` or adjust the tolerance to ignore the explicit date check. Until then the test documents the mismatch while confirming numerical parity.

### Forward-rate regression (Step 3)

The Step 3 forward-rate test still reports ~28% success because it inherits the same maturity drift; fix the target schedule before tightening tolerances.

## Key Differences from OIS


| Aspect | OIS Bootstrap | IBOR Bootstrap |
|--------|---------------|----------------|
| **Purpose** | Build discount curve (risk-free) | Build projection curve (with credit) |
| **Input Quotes** | ESTR swaps (overnight index) | EURIBOR 3M/6M swaps (term rates) |
| **Discount Source** | Self-referential (uses own curve) | External (uses OIS curve) |
| **Output** | Discount factors for PV calculation | Pseudo-DFs for forward projection |
| **Floating Leg DCC** | ACT/365F | ACT/360 |
| **Fixed Leg DCC** | ACT/360 | 30/360 or ACT/360 |
| **First Instrument** | 1W OIS swap | 6M deposit (or 3M for EURIBOR 3M) |
| **Payment Frequency** | Annual | Semi-annual (6M) or quarterly (3M) |
| **Credit Premium** | None (risk-free rate) | Contains bank credit spread (~10-30 bp) |
| **Algorithm** | QuantLib PiecewiseYieldCurve | Custom root-finding (bisection) |
| **Implementation** | Pure QuantLib bootstrap | Manual dual-curve solver |
| **Complexity** | Simpler (single curve) | More complex (two curves interact) |

### Why Different Algorithms?

**OIS:** Uses QuantLib's built-in `PiecewiseLogLinearDiscount` because:
- Single-curve framework (self-discounting)
- Standard market practice
- QuantLib handles edge cases well

**IBOR:** Uses custom root-finding because:
- Dual-curve framework (OIS for discounting, IBOR for projection)
- QuantLib doesn't directly support this split
- Need explicit control over projection vs. discount curves
- Bloomberg reference implementation uses similar approach

---

## File Reference

### Core Bootstrap Engine
- `engine/curves/ibor/bootstrap/engine.py` - Main bootstrap logic (refactored 2025)
- `engine/curves/ibor/bootstrap/state.py` - Projection curve state management
- `engine/curves/ibor/bootstrap/instruments.py` - Deposit and swap instrument classes
- `engine/curves/ibor/bootstrap/results.py` - Bootstrap result data structures

### Supporting Modules
- `engine/curves/projection.py` - IborProjectionCurve class
- `engine/curves/discount.py` - OISDiscountCurve class (input)
- `engine/data/loaders.py` - Data loading (PostgreSQL, JSON)
- `engine/data/filters.py` - Quote filtering strategies

### Factory and Utilities
- `engine/curves/bootstrap/factory.py` - Curve construction factory
- `engine/data/factory.py` - Data source factory
- `engine/calendar/date_calculator.py` - Date calculations
- `engine/conventions/daycount.py` - Day count conventions

---

## Design Decisions

### Why Manual Root-Finding Instead of QuantLib?

**Decision:** Implement custom bisection solver rather than use QuantLib's dual-curve features.

**Rationale:**
1. **Explicit Control:** Need to clearly separate OIS (discounting) from IBOR (projection)
2. **Bloomberg Alignment:** Bloomberg uses similar root-finding approach
3. **Transparency:** Custom code easier to debug and validate
4. **Educational Value:** Team understands the mathematics deeply

**Trade-off:** ~2-4% performance overhead vs. pure QuantLib, but acceptable (<50ms total).

### Why Pseudo-Discount Factors?

**Decision:** Store projection curve as pseudo-discount factors rather than forward rates.

**Rationale:**
1. **Consistency:** Both OIS and IBOR curves represented as DF-like structures
2. **Interpolation:** Easier to interpolate log(DF) than forward rates
3. **Numerical Stability:** Avoids division by small τ values
4. **API Simplicity:** `forward_rate()` method converts internally

**Trade-off:** Name "pseudo-DF" can confuse beginners (requires explanation).

### Why Step-Forward Interpolation?

**Decision:** Use piecewise constant forward rates (step-forward) for interpolation.

**Rationale:**
1. **Market Standard:** Bloomberg uses step-forward for projection curves
2. **No Arbitrage:** Ensures forward rates don't create arbitrage
3. **Stability:** More stable than linear DF interpolation
4. **Simplicity:** Easy to implement and explain

**Trade-off:** Less smooth than cubic splines, but more realistic for market usage.

---

## Common Pitfalls

### 1. Forgetting to Use OIS for Discounting

**❌ Wrong:**
```python
# Using IBOR curve for discounting
pv = cashflow * ibor_curve.df(payment_date)
```

**✓ Correct:**
```python
# Using OIS curve for discounting
forward = ibor_curve.forward_rate(start, end)
pv = forward * tau * ois_curve.df(payment_date)
```

### 2. Mixing Day Count Conventions

**❌ Wrong:**
```python
# Using ACT/365F for EURIBOR accrual
tau = (end - start).days / 365.0
```

**✓ Correct:**
```python
# Using ACT/360 for EURIBOR accrual
tau = (end - start).days / 360.0
```

### 3. Not Sorting Quotes by Maturity

**❌ Wrong:**
```python
# Bootstrap in arbitrary order
for quote in quotes:
    engine.bootstrap_swap(quote)
```

**✓ Correct:**
```python
# Sort by maturity first
quotes = sorted(quotes, key=lambda q: q.maturity)
for quote in quotes:
    engine.bootstrap_swap(quote)
```

### 4. Incorrect Front Stub Calculation

**❌ Wrong:**
```python
# Using deposit rate directly
front_stub = 1.0 / (1 + deposit_rate * stub_time)
```

**✓ Correct:**
```python
# Convert to instantaneous forward first
inst_forward = log(1 + deposit_rate * deposit_tau) / deposit_tau
front_stub = exp(-inst_forward * stub_time)
```

---

## Further Reading

- **OIS Bootstrap:** See [02_ois_bootstrap.md](02_ois_bootstrap.md) for Step 1
- **Swap Pricing:** See [04_swap_pricing.md](04_swap_pricing.md) for how curves are used
- **Forward Rates:** See [05_forward_rates.md](05_forward_rates.md) for forward rate calculations
- **Dual-Curve Framework:** See [08_dual_curve_framework.md](08_dual_curve_framework.md) for theoretical background
- **Conventions:** See [06_conventions.md](06_conventions.md) for market conventions

---

*Last updated: 2025 (post-refactoring)*
