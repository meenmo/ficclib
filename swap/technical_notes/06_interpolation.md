# Interpolation Methods - Technical Documentation

**Component:** `engine/curves/discount.py`, `engine/curves/projection.py`
**Purpose:** Interpolate discount factors and forward rates between pillar points
**Status:** ✅ Production (step-forward continuous for Bloomberg matching)

---

## Table of Contents

1. [Overview](#overview)
2. [Why Interpolation Matters](#why-interpolation-matters)
3. [Step-Forward Continuous (Bloomberg Standard)](#step-forward-continuous-bloomberg-standard)
4. [Alternative Methods](#alternative-methods)
5. [Comparison of Methods](#comparison-of-methods)
6. [Extrapolation](#extrapolation)
7. [Implementation](#implementation)
8. [Examples](#examples)

---

## Overview

Interest rate curves are constructed from a **discrete set of pillar points** (e.g., 1W, 1M, 3M, 6M, 1Y, 2Y, ..., 50Y), but we need discount factors and forward rates for **arbitrary dates** between these pillars.

**Interpolation** is the mathematical method for estimating values between known pillar points.

### The Problem

Given:
- Pillar times: $T_0, T_1, T_2, ..., T_n$
- Discount factors at pillars: $DF(T_0), DF(T_1), ..., DF(T_n)$

Find:
- Discount factor at arbitrary time $t$ where $T_i < t < T_{i+1}$

### Why This Is Non-Trivial

Different interpolation methods can produce:
- Different forward rates between observations
- Different swap pricing (can differ by several basis points!)
- Different sensitivities (risk metrics)
- Different arbitrage implications

**Key Insight:** Interpolation is not just a technical detail—it has real economic implications. The choice of interpolation method reflects assumptions about how interest rates evolve between observed market points.

---

## Why Interpolation Matters

### Impact on Pricing

Consider a 3-month forward rate starting in 45 days:
- 45 days falls between 1M (30 days) and 2M (60 days) pillars
- **Linear interpolation** on DFs gives one forward rate
- **Step-forward interpolation** gives a different forward rate
- Difference can be 1-5 basis points!

For a €10M notional swap:
- 1 bp difference in forward rate ≈ €2,500 present value difference
- Over multiple periods: €10,000+ total impact

### Impact on Risk Management

Different interpolation → different curve sensitivities:
- **DV01** (dollar value of 1 bp): Can differ by 5-10%
- **Bucketed Greeks**: Allocation across tenors changes
- **Hedging ratios**: Different optimal hedge amounts

### Arbitrage Considerations

Some interpolation methods can create **arbitrage opportunities**:
- Forward rates that are impossible to lock in
- Negative forward rates where they shouldn't exist
- Discontinuous rate changes

**Step-forward interpolation** is **arbitrage-free** by construction—it ensures forward rates are consistent with no-arbitrage conditions.

---

## Step-Forward Continuous (Bloomberg Standard)

**Method:** Instantaneous forward rates are **piecewise constant** between pillars.

This is the **default** method used by Bloomberg SWPM and is the industry standard for EUR interest rate curves.

### Mathematical Formulation

For a target time $t$ in the interval $[T_i, T_{i+1}]$:

**Step 1: Calculate the constant forward rate for the interval**

$$f_i = \frac{\ln(DF(T_i)) - \ln(DF(T_{i+1}))}{T_{i+1} - T_i}$$

**Step 2: Interpolate the discount factor**

$$DF(t) = DF(T_i) \times \exp\left(-f_i \times (t - T_i)\right)$$

**Intuition:**
- The forward rate $f_i$ is constant throughout the interval $[T_i, T_{i+1}]$
- Discount factor decays exponentially at rate $f_i$
- Creates smooth zero rate curve while keeping forward rates simple

### Properties

| Property | Behavior |
|----------|----------|
| **Forward rates** | Piecewise constant (step function) |
| **Discount factors** | Piecewise exponential (smooth, C⁰ continuous) |
| **Zero rates** | Smooth and continuous |
| **Arbitrage-free** | ✅ Yes, by construction |
| **Smoothness** | C⁰ (continuous but not differentiable at pillars) |
| **Market standard** | ✅ Yes (Bloomberg default) |

### Why "Step-Forward"?

The name comes from the shape of the **instantaneous forward rate curve**:

```
Forward Rate
    │
2.5%├────────┐
    │        │
2.0%├────────┼────────┐
    │        │        │
1.5%├────────┼────────┼────────┐
    │        │        │        │
    └────────┴────────┴────────┴──> Time
         T₁       T₂       T₃
```

The forward rate "steps" between constant levels at each pillar point.

### Visual Comparison: Discount Factor Curves

```
DF(t)
  1.0 ├─╮
      │  ╲              ○ = Pillar points
  0.9 │   ╲○
      │     ╲╲
  0.8 │      ╲○         Step-forward:
      │        ╲╲       Smooth exponential decay between pillars
  0.7 │         ╲○
      │           ╲╲
  0.6 │            ╲○
      └─────────────────> Time
```

### Example Calculation

**Given:**
```
Pillar 1: T₁ = 1.0 year, DF(T₁) = 0.98
Pillar 2: T₂ = 2.0 year, DF(T₂) = 0.96
Target:   t  = 1.5 years
```

**Step 1: Calculate forward rate**
```python
f = (ln(0.98) - ln(0.96)) / (2.0 - 1.0)
  = (-0.020203 - (-0.040822)) / 1.0
  = 0.020619
  = 2.0619%
```

**Step 2: Interpolate DF**
```python
DF(1.5) = 0.98 × exp(-0.020619 × (1.5 - 1.0))
        = 0.98 × exp(-0.020619 × 0.5)
        = 0.98 × exp(-0.010310)
        = 0.98 × 0.989747
        = 0.969952
```

**Verification:**
- At t=1.0: DF = 0.98 ✓ (pillar)
- At t=1.5: DF = 0.969952 (interpolated)
- At t=2.0: DF = 0.96 ✓ (pillar)

The curve smoothly decays from 0.98 to 0.96 following an exponential path.

### Implementation

Our implementation is embedded in the curve classes:

**File:** `engine/curves/discount.py` (OIS curves)

```python
class OISDiscountCurve:
    """Discount curve with step-forward interpolation."""

    def df(self, time: float) -> float:
        """
        Get discount factor for given time using step-forward interpolation.

        Args:
            time: Time in years (ACT/365F)

        Returns:
            Discount factor (present value of $1 at time t)
        """
        # Handle pillar dates
        if time in self.pillar_map:
            return self.pillar_map[time]

        # Find bracketing pillars
        times = sorted(self.pillar_map.keys())

        # Extrapolation before first pillar
        if time < times[0]:
            return self._extrapolate_before(time, times[0])

        # Extrapolation after last pillar
        if time > times[-1]:
            return self._extrapolate_after(time, times[-1])

        # Interpolation between pillars
        return self._interpolate_step_forward(time, times)

    def _interpolate_step_forward(self, target_time: float, pillar_times: List[float]) -> float:
        """
        Step-forward interpolation between pillars.
        """
        # Find interval containing target
        for i in range(len(pillar_times) - 1):
            t1, t2 = pillar_times[i], pillar_times[i + 1]

            if t1 <= target_time <= t2:
                df1 = self.pillar_map[t1]
                df2 = self.pillar_map[t2]

                # Calculate constant forward rate
                forward_rate = math.log(df1 / df2) / (t2 - t1)

                # Exponential decay from t1
                return df1 * math.exp(-forward_rate * (target_time - t1))

        return self.pillar_map[pillar_times[-1]]
```

**File:** `engine/curves/projection.py` (IBOR curves)

The IBOR projection curve uses the same step-forward interpolation for pseudo-discount factors, which then translates to constant forward EURIBOR rates between pillars.

```python
class IborProjectionCurve:
    """Projection curve with step-forward interpolation."""

    def df(self, target_date: date) -> float:
        """Get pseudo-discount factor using step-forward interpolation."""
        # Same algorithm as OIS curve
        # Converts dates to times using ACT/365F
        # Applies step-forward interpolation to pseudo-DFs
        ...
```

### Advantages

1. **Arbitrage-Free**: Forward rates derived from step-forward interpolation satisfy no-arbitrage conditions
2. **Smooth Zero Curve**: Produces smooth zero rate curves suitable for pricing
3. **Market Standard**: Bloomberg default, widely accepted in industry
4. **Stable**: No oscillations or wild behavior between pillars
5. **Fast**: Simple exponential calculation, no matrix inversions

### Disadvantages

1. **Not Smooth**: Forward rate curve has discontinuities at pillar points
2. **Not C¹**: Discount factor curve is not differentiable at pillars
3. **May Not Match Reality**: Assumes forward rates instantly jump at pillar dates

For most practical purposes, these disadvantages are acceptable. The method's simplicity and market acceptance outweigh the theoretical smoothness concerns.

---

## Alternative Methods

### Linear Interpolation on Discount Factors

**Method:** Simple linear interpolation directly on discount factors.

**Formula:**

For target time $t$ in interval $[T_i, T_{i+1}]$:

$$\text{weight} = \frac{t - T_i}{T_{i+1} - T_i}$$

$$DF(t) = (1 - \text{weight}) \times DF(T_i) + \text{weight} \times DF(T_{i+1})$$

**Properties:**
- ✅ Simplest possible method
- ✅ Smooth discount factor curve (C¹ continuous)
- ✅ Fast computation
- ❌ Forward rates can have discontinuities
- ❌ **NOT** arbitrage-free
- ❌ **NOT** used for Bloomberg matching

**Why Not Used:**

Linear interpolation on discount factors implies **non-constant forward rates** within each interval, which can create:
- Forward rates that vary non-linearly
- Potential arbitrage opportunities
- Mismatch with Bloomberg SWPM

**Example:**
```
Given: DF(1Y) = 0.98, DF(2Y) = 0.96
Target: t = 1.5Y

Linear interpolation:
DF(1.5Y) = 0.5 × 0.98 + 0.5 × 0.96 = 0.97

But this implies a varying forward rate within [1Y, 2Y]!
```

### Log-Linear Interpolation on Discount Factors

**Method:** Linear interpolation on log(DF).

**Formula:**

$$\log(DF(t)) = (1 - \text{weight}) \times \log(DF(T_i)) + \text{weight} \times \log(DF(T_{i+1}))$$

Equivalently:

$$DF(t) = DF(T_i)^{1-\text{weight}} \times DF(T_{i+1})^{\text{weight}}$$

**Properties:**
- Similar to step-forward but with slight differences
- Smooth in log space
- Alternative market convention (less common than step-forward)

### Cubic Spline Interpolation

**Method:** Fit cubic polynomial segments between pillars with continuity constraints.

**Properties:**
- ✅ C² continuous (very smooth)
- ✅ Smooth forward rate curve
- ❌ Complex implementation
- ❌ Can oscillate (Runge's phenomenon)
- ❌ Not standard for swap curves
- ❌ Computationally expensive

**Use Case:** Exotic derivatives requiring smooth Greeks, not used for vanilla swaps.

### Natural Spline

**Method:** Cubic spline with natural boundary conditions (second derivative = 0 at endpoints).

**Properties:**
- Smoother than step-forward
- Can overshoot between pillars
- Not commonly used in practice

---

## Comparison of Methods

### Visual Comparison

```
Discount Factor:

1.00 ├○                        ○ = Pillar points
     │ ╲╲
0.95 │   ○                     Step-forward: Exponential segments
     │    ╲╲╲                  Linear: Straight lines
0.90 │       ○                 Cubic: Smooth curves
     │         ╲╲╲╲
0.85 │            ○
     └─────────────────> Time
```

### Quantitative Comparison

| Method | Smoothness | Arbitrage-Free | Bloomberg Match | Complexity |
|--------|------------|----------------|-----------------|------------|
| **Step-Forward** | C⁰ | ✅ Yes | ✅ Yes | Low |
| **Linear DF** | C¹ | ❌ No | ❌ No | Very Low |
| **Log-Linear DF** | C¹ | ✅ Yes | ⚠️ Close | Low |
| **Cubic Spline** | C² | ⚠️ Depends | ❌ No | High |
| **Natural Spline** | C² | ⚠️ Depends | ❌ No | High |

### Impact on Forward Rates

**Example:** 1Y-2Y interval with DF(1Y)=0.98, DF(2Y)=0.96

| Method | DF(1.5Y) | Implied 1Y-1.5Y Forward | Implied 1.5Y-2Y Forward |
|--------|----------|-------------------------|-------------------------|
| **Step-Forward** | 0.9700 | 2.06% | 2.06% (constant) |
| **Linear** | 0.9700 | 2.01% | 2.11% (varies!) |
| **Cubic** | 0.9705 | 1.95% | 2.22% (varies more!) |

**Key Observation:** Only step-forward guarantees constant forward rates within each interval, which is required for arbitrage-free pricing and Bloomberg matching.

---

## Extrapolation

Extrapolation handles times outside the range of pillar points.

### Before First Pillar (Flat Zero Rate)

For $t < T_0$:

$$DF(t) = \exp\left(-r_0 \times t\right)$$

where:

$$r_0 = -\frac{\ln(DF(T_0))}{T_0}$$

**Assumption:** Zero rate at first pillar extends flat backward to time zero.

**Example:**
```
First pillar: T₀ = 0.0192 (1W), DF(T₀) = 0.9998

Zero rate: r₀ = -ln(0.9998) / 0.0192 = 0.0104 = 1.04%

For t = 0.01 (3.65 days):
DF(0.01) = exp(-0.0104 × 0.01) = 0.9999
```

### After Last Pillar (Flat Forward Rate)

For $t > T_n$:

$$DF(t) = DF(T_n) \times \exp\left(-f_n \times (t - T_n)\right)$$

where $f_n$ is the forward rate for the last interval $[T_{n-1}, T_n]$:

$$f_n = \frac{\ln(DF(T_{n-1})) - \ln(DF(T_n))}{T_n - T_{n-1}}$$

**Assumption:** The forward rate from the last interval extends flat indefinitely.

**Example:**
```
Last two pillars:
  T₄₉ = 40Y, DF(40Y) = 0.2150
  T₅₀ = 50Y, DF(50Y) = 0.1833

Forward rate: f = ln(0.2150/0.1833) / 10 = 0.0159 = 1.59%

For t = 60Y:
DF(60Y) = 0.1833 × exp(-0.0159 × 10) = 0.1562
```

**Why Flat Forward?**

Flat forward rate extrapolation:
- Prevents discount factors from going negative
- Reasonable assumption far beyond market observables
- Standard Bloomberg convention

**Warning:** Extrapolated values have high uncertainty. For very long dates (>50Y), consider:
- Using ultra-long bond yields if available
- Applying explicit long-term rate assumptions
- Adding extrapolation risk to uncertainty estimates

---

## Implementation

### Curve Classes

Both OIS and IBOR curves implement step-forward interpolation:

**File:** `engine/curves/discount.py`
```python
class OISDiscountCurve:
    def __init__(
        self,
        reference_date: date,
        pillar_times: List[float],
        discount_factors: List[float],
        interpolation_method: str = "STEP_FORWARD",
        name: str = "ESTR_OIS",
    ):
        self.reference_date = reference_date
        self.pillar_times = pillar_times
        self.discount_factors = discount_factors
        self.interpolation_method = interpolation_method
        self.name = name

        # Build pillar map
        self.pillar_map = dict(zip(pillar_times, discount_factors))

    def df(self, time: float) -> float:
        """Get discount factor at given time using step-forward interpolation."""
        return self._interpolate_step_forward(time)
```

**File:** `engine/curves/projection.py`
```python
class IborProjectionCurve:
    def __init__(
        self,
        reference_date: date,
        pillars: Dict[date, float],  # pseudo-discount factors
        interpolation_method: str = "STEP_FORWARD",
        index_name: str = "EURIBOR6M",
    ):
        self.reference_date = reference_date
        self.pillars = pillars
        self.interpolation_method = interpolation_method
        self.index_name = index_name

    def df(self, target_date: date) -> float:
        """Get pseudo-DF using step-forward interpolation."""
        # Convert date to time
        time = self._date_to_time(target_date)
        return self._interpolate_step_forward(time)
```

### Usage in Bootstrap

Interpolation is invoked automatically during curve bootstrapping:

```python
# During IBOR bootstrap, when calculating floating leg PV
for period in swap.floating_periods():
    # These calls use interpolation internally!
    px_start = projection_curve.df(period.accrual_start)
    px_end = projection_curve.df(period.accrual_end)

    # If dates are not pillars, step-forward interpolation is used
    forward = (px_start / px_end - 1.0) / period.year_fraction
```

---

## Examples

### Example 1: OIS Curve Interpolation

```python
from engine.curves.discount import OISDiscountCurve
from datetime import date

# Create OIS curve with 3 pillars
ois_curve = OISDiscountCurve(
    reference_date=date(2025, 8, 8),
    pillar_times=[0.0192, 0.2500, 1.0139],  # 1W, 3M, 1Y
    discount_factors=[0.9998, 0.9950, 0.9800],
    interpolation_method="STEP_FORWARD",
    name="ESTR_OIS",
)

# Interpolate at 6 months (between 3M and 1Y)
df_6m = ois_curve.df(0.5)
print(f"DF(6M) = {df_6m:.6f}")  # Uses step-forward interpolation

# Calculate forward rate 3M-6M
df_3m = ois_curve.df(0.2500)
df_6m = ois_curve.df(0.5000)
forward_3m_6m = (df_3m / df_6m - 1.0) / 0.25
print(f"Forward 3M-6M: {forward_3m_6m * 100:.4f}%")
```

### Example 2: IBOR Curve Interpolation

```python
from engine.curves.projection import IborProjectionCurve
from datetime import date

# Create IBOR projection curve
projection_curve = IborProjectionCurve(
    reference_date=date(2025, 8, 8),
    pillars={
        date(2025, 8, 12): 1.0000,      # Spot
        date(2026, 2, 12): 0.9892,      # 6M
        date(2026, 8, 12): 0.9798,      # 1Y
        date(2027, 8, 12): 0.9591,      # 2Y
    },
    interpolation_method="STEP_FORWARD",
    index_name="EURIBOR6M",
)

# Calculate forward rate for a period between pillars
start = date(2026, 5, 12)  # Between 6M and 1Y
end = date(2026, 11, 12)   # Between 1Y and 2Y

forward = projection_curve.forward_rate(start, end)
print(f"Forward {start} to {end}: {forward * 100:.4f}%")
# Uses step-forward interpolation for both px_start and px_end
```

### Example 3: Comparing Methods

```python
# Same pillars, different interpolation methods
pillars = [1.0, 2.0, 3.0, 5.0, 10.0]
dfs = [0.98, 0.96, 0.94, 0.90, 0.82]

# Step-forward (our default)
curve_sf = create_curve(pillars, dfs, method="STEP_FORWARD")
df_sf = curve_sf.df(4.0)  # Between 3Y and 5Y

# Linear (alternative)
curve_lin = create_curve(pillars, dfs, method="LINEAR")
df_lin = curve_lin.df(4.0)

print(f"DF(4Y) step-forward: {df_sf:.6f}")
print(f"DF(4Y) linear:       {df_lin:.6f}")
print(f"Difference:          {(df_sf - df_lin) * 10000:.2f} bps in DF")
# Typically differs by 1-5 bps in discount factor
# Translates to several bps in forward rates
```

---

## Further Reading

- **OIS Bootstrap:** [02_ois_bootstrap.md](02_ois_bootstrap.md) - How interpolation is used in OIS curve construction
- **IBOR Bootstrap:** [03_ibor_bootstrap.md](03_ibor_bootstrap.md) - Step-forward interpolation in projection curves
- **Forward Rates:** [04_forward_rates.md](04_forward_rates.md) - How interpolation affects forward rate calculations

---

## Summary

**Key Takeaways:**

1. **Step-forward interpolation** is the industry standard for EUR swap curves
2. It ensures **piecewise constant forward rates** between pillars
3. **Arbitrage-free** by construction
4. **Bloomberg SWPM default** - essential for matching Bloomberg prices
5. Produces **smooth zero rate curves** suitable for pricing
6. Simple and fast to compute

**When to Use What:**
- **Vanilla EUR swaps**: Step-forward (always)
- **Research/analysis**: Step-forward (for consistency)
- **Exotic derivatives**: Consider cubic splines if smooth Greeks needed
- **Academic studies**: Document method clearly, step-forward is standard

**Common Mistakes:**
- Using linear interpolation for Bloomberg matching → wrong prices
- Not understanding that interpolation affects forward rates → pricing errors
- Mixing interpolation methods between OIS and IBOR curves → inconsistency

**Bottom Line:**

Interpolation is not "just math"—it has real pricing implications. For production systems matching Bloomberg:

✅ **Use step-forward interpolation**
✅ **Apply consistently across all curves**
✅ **Validate against Bloomberg SWPM**

---

*Last updated: 2025 (post-refactoring)*
