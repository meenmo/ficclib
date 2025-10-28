# Progress

- Refactored analytics stack: semi-annual coupon schedule, ACT/365F day-count, accrued interest helpers, and YTM/price inversion with Newton–Raphson + bisection fallback are in place. `.debug/quickcheck_price_ytm.py` passes under `.venv/bin/python`.
- `ZeroCurve` rebuilt with piecewise interpolation, multiple compounding modes, and support for constructing from par yields. Legacy curve helpers isolated under `ktb/legacy_curve/`.
- Key-rate delta flow now detects par-yield curves, rebuilds discount factors from the original par nodes, and reprices bonds via the new utility path. `.debug/quickcheck_krd.py` runs but still reports residual diffs against the sample data (up to ~7e-05 on mid tenors).
- Rootfinding profiler verifies fallback activation on flat derivatives (`.debug/profile_rootfinding.py`).

# Upcoming Assignments

- Tighten the par-yield bootstrap so curve-based pricing exactly reproduces the sample dirty prices before/after –1 bp node bumps; resolve remaining KRD tolerance failures.
- Cross-check dirty vs clean handling in the par-based pricer, ensuring accrued interest alignment with sample fixtures.
- Consolidate duplicated interpolation logic (ZeroCurve vs KRD helpers) and add unit coverage or targeted debug cases once the sample benchmarks pass.
- Final hygiene: confirm code formatting, logging defaults, and prepare commit once KRD tolerances meet ≤1e-6 as mandated.
