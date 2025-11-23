## Task(Key Rate Delta/Duration of KTB: Korea Treasury Bond)
PYTHON EXECUTABLE TO USE: ficclib/.venv/bin/python (MUST)


Bring `test/krd.py` Method 2 (price-based KRD) in line with Bloomberg/TARGET_KRD methodology, taking into account that KTB prices are **dirty** by default.

## Context

- `test/krd.py` currently runs two methods:
  1. Method 1: `_price_bond_with_par_curve` + `_shift_par_curve` (par/YTM bump inside krd.py).
  2. Method 2: bootstrap discount factors from `TARGET_PRICE`, convert to a zero curve, and build a par(ytm) curve from the zero curve. Finally, bump the par curve by –1 bp on each tenor.
- Method 2 now uses ACT/ACT but still bumps zero rates and computes `P_bumped − P_base`, so every KRD remains positive.
- We already bootstrap DFs from prices (Method 2). Need to convert those DFs into an equivalent par grid, apply tenor bumps in par space, rebuild zero curves, reprice, and use the dirty-price difference.

## Requirements

1. **Day Count / Pricing basis**:
   - Use ACT/ACT for year fractions throughout.
   - Treat KTB prices as DIRTY by default (only subtract accrued interest if we explicitly want clean KRDs; Bloomberg targets appear dirty).
2. **Bootstrapped Curve**:
   - Build discount factors via `bootstrap_dfs_from_bonds` using all bonds with `TARGET_PRICE`.
   - Interpolate the DFs to CURVE_T tenors.
   - Convert those DFs into both zero rates and par (YTM) percentages (semiannual) so CURVE_T reflects the curve implied by market prices.
3. **Method 2 KRD**:
   - Base price: price each test bond (4 ISINs) using `KTB.price_from_zero_curve` with the bootstrapped zero curve (dirty price).
   - For each key tenor in CURVE_T:
     * Copy the par grid and shift only that tenor **down by 1 bp**.
     * Rebuild a zero curve from the bumped par grid (`ZeroCurve.from_par_yields`).
     * Reprice the bond; `KRD = P_bumped - P_base` (dirty price difference).
   - Print the results and compare to `TARGET_KRD` with suitable tolerance.
4. **Method 1**: keep for reference but flag as legacy; Method 2 should become authoritative once it matches targets.
5. **Outputs**: run `ficclib/.venv/bin/python test/krd.py` to exercise both methods and summarize pass/fail vs targets.

## Notes
- I am curious the all positive trend in the Calculated KRD, while TARGET_KRD and Bloomberg's KRD shows negative trend in the earlier tenors and clear positive numbers at the end. 
- Ensure the par conversion uses 0.5-year coupon spacing (semiannual). Interpolate missing par tenors linearly.
- Since KTB prices are dirty by default, the ΔP we compare to `TARGET_KRD` should also be dirty (unless we confirm those targets are clean). Adjust if necessary once we see the magnitudes.
