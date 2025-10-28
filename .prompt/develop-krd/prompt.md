
---

# Codex Prompt — **Refactor & Extend KTB Pricing** (do **not** touch `futures.py`)

## Scope & Non-negotiables

* Work **only** inside: `ktb/` and `utils/`.
* **Do not modify** `ktb/futures.py` (freeze it; treat as read-only).
* Create/run all debug runners in **`.debug/`**.
* Sample data lives at `.prompt/develop-ktb/sample_data.py`. **Import** it in debug/tests; **do not embed** it in library modules.
* In this project, **KTB prices are quoted as DIRTY prices** (i.e., include accrued interest). Provide helpers to get clean if needed.

## Objectives

1. **Solve YTM given DIRTY price** (semiannual KTB).
2. **Solve DIRTY price given YTM**.
3. **Key Rate Delta (KRD)** using a **zero curve** with node-specific –1 bp shifts and re-interpolation.

## Refactor Mandate (aggressive, but safe)

Refactor as much existing code as possible **without changing public behavior** (except where clarified here), and **without touching `ktb/futures.py`**:

* Eliminate dead/duplicated code; collapse helpers into `utils/`.
* Replace implicit globals with explicit parameters; add **type hints** and **docstrings**.
* Separate concerns: schedule/accrual ↔ pricing ↔ curve ↔ rootfinding.
* Make units consistent (rates as **decimals** internally).
* Keep modules ≤ ~300 LOC; functions ≤ ~50 LOC where feasible.
* Preserve existing file paths for imports unless trivially improved; add **compat shims** if you must move names.

## Target Package Layout

```
ktb/
  __init__.py
  analytics.py        # price_from_ytm, ytm_from_price (DIRTY by default)
  curve.py            # ZeroCurve: zero(t), df(t), clone_with_shifted_node(...)
  krd.py              # key_rate_delta, batch_key_rate_delta (curve-discounting)
  # DO NOT EDIT:
  futures.py          # <leave unchanged>

utils/
  daycount.py         # ACT/365F; registry if needed
  schedule.py         # coupon schedule (semiannual)
  cashflows.py        # coupon CFs, accrued_interest, price_clean<->dirty helpers
  rootfinding.py      # newton_raphson + brent/bisection fallback
```

## Public API (keep stable)

```python
# ktb/analytics.py
def price_from_ytm(issue_date, maturity_date, coupon, payment_frequency,
                   ytm, face=10_000, day_count="ACT/365F", as_clean=False) -> float: ...

def ytm_from_price(issue_date, maturity_date, coupon, payment_frequency,
                   price_dirty, face=10_000, day_count="ACT/365F",
                   guess: float | None = None) -> float: ...

# ktb/curve.py
class ZeroCurve:
    def __init__(self, curve_date, nodes: dict[float, float], comp: str = "cont"): ...
    def zero(self, t: float) -> float: ...
    def df(self, t: float) -> float: ...
    def clone_with_shifted_node(self, tenor: float, shift_bp: float) -> "ZeroCurve": ...

# ktb/krd.py
def key_rate_delta(bond_spec: dict, curve: ZeroCurve, key_tenor_years: float,
                   as_clean=True) -> float: ...
def batch_key_rate_delta(bonds: list[dict], curve: ZeroCurve,
                         key_tenors: list[float], as_clean=True) -> dict: ...
```

## Formulas & Conventions

### Year fraction (ACT/365F)
$$
\left[
\text{yearfrac}(d_1,d_2)=\frac{\text{ActualDays}(d_1,d_2)}{365}
\right]
$$


---

### Accrued Interest (AI)

Let $C = F \cdot \tfrac{\text{coupon}}{m}$.
With last/next coupon dates $d_L, d_N$ and settlement $d_S$:

$$
\text{AI} = C \cdot \frac{\text{yearfrac}(d_L, d_S)}{\text{yearfrac}(d_L, d_N)}
$$

Dirty = Clean + AI.
(**KTB convention:** inputs/outputs default to **DIRTY**.)

---

### Price from YTM (DIRTY, street comp with frequency $m$)

Let $r = \tfrac{y}{m}$, and $t_i$ = ACT/365F from **settlement = curve_date** to payment $i$.
Coupons $CF_i = C$, final $CF_N = C + F$:

$$
P_{\text{dirty}}(y) = \sum_{i=1}^{N} \frac{CF_i}{(1 + r)^{m t_i}}
$$

---

### YTM from DIRTY price (root solve)

Solve $f(y) = P_{\text{dirty}}(y) - P^{*}_{\text{dirty}} = 0$
via **Newton–Raphson** with analytic derivative:

$$
\frac{dP}{dy} = - \sum_{i=1}^{N} CF_i , t_i , (1 + r)^{-m t_i - 1}
$$

Safeguards: clamp $\Delta y$ to ±100 bps; fallback to **Brent/bisection** if derivative is tiny or NR diverges.
Converge when $|P - P^{*}| \le 10^{-6}$ or $|\Delta y| \le 10^{-10}$.

---

### Curve-discounted price (for KRD)

Interpolate **linearly in zero-rate space** over maturities.
With continuous compounding by default:

$$
z(T) = \text{lin.interp}(T), \quad
DF(T) = e^{-z(T),T}, \quad
P_{\text{dirty,curve}} = \sum_i CF_i \cdot DF(t_i)
$$

---

### Key Rate Delta (node-specific –1 bp)

Shift only node $T_k$ by $-1\text{ bp} = -0.0001$ (decimal), rebuild interpolation, and reprice:

$$
\text{KRD}(T_k) = P_{\text{as-is}} - P_{\text{shift}(T_k,,-1\text{ bp})}
$$

Use **curve-discounting** (not YTM) to reflect the node move.

---

## Ordered Tasks

### Phase 1 — Survey & Refactor (no features yet)

1. **Read-only scan** of `ktb/` and `utils/`; identify:

   * duplicate helpers, hidden state, untyped functions, unreachable code.
2. **Do not edit** `ktb/futures.py`—add it to a local “do-not-touch” list.
3. Consolidate utilities into `utils/`:

   * `daycount.py` (ACT/365F), `schedule.py`, `cashflows.py`, `rootfinding.py`.
4. Normalize **units** (all rates in decimals internally).
5. Add type hints, docstrings (with the formulas above), and lightweight input validation.
6. Keep public symbols stable; if renaming internals, update imports within `ktb/`.

### Phase 2 — Curve engine

7. Implement `ZeroCurve`:

   * store sorted nodes `{tenor_years: zero_decimal}`;
   * `zero(t)`: piecewise-linear; flat extrapolation beyond ends;
   * `df(t)`: `exp(-z(t)*t)` by default; future-proof a `comp` switch;
   * `clone_with_shifted_node(tenor, shift_bp)`: shift one node in **decimal** by `shift_bp/10_000`.

### Phase 3 — Pricing APIs

8. `price_from_ytm(...)` (DIRTY by default; `as_clean=True` subtracts AI).
9. `ytm_from_price(...)` using **NR + Brent/bisection fallback** (tolerances as above).
10. Internal helper `_price_from_curve(...)` (DIRTY/CLEAN) using `ZeroCurve.df`.

### Phase 4 — KRD

11. `key_rate_delta(...)` and `batch_key_rate_delta(...)` per definition (curve-discounting, –1 bp at the node).

### Phase 5 — Debug & Tests in `.debug/`

12. `.debug/quickcheck_price_ytm.py`

* Import sample bonds; `ytm_from_price(price_dirty)` ≈ provided YTM (abs err ≤ 1e-4).
* `price_from_ytm(ytm)` ≈ provided **DIRTY** price (abs err ≤ 0.05).

13. `.debug/quickcheck_krd.py`

* Build `ZeroCurve` from the sample curve; recompute each bond’s KRD tenors; compare to sample KRD (≤ 1e-6).

14. `.debug/profile_rootfinding.py`

* Stress initial guesses; print iterations/steps; assert fallback kicks in on flat derivatives.

### Phase 6 — Hygiene

15. Add lightweight logging (DEBUG in `.debug/`, silent by default in lib).
16. Ensure **no diffs in `ktb/futures.py`**. (Locally: `git update-index --assume-unchanged ktb/futures.py` if helpful.)
17. Ruff/PEP8 clean; keep functions cohesive; document corner cases (coupon date, short accruals).

## Runbook (local)

* Round-trip & KRD checks:

  ```
  python .debug/quickcheck_price_ytm.py
  python .debug/quickcheck_krd.py
  python .debug/profile_rootfinding.py
  ```

## Notes & Options

* If matching an external convention (e.g., KOFIA compounding not continuous) is required later, expose `comp="cont" | "street(m=2)"` in `ZeroCurve`.
* If Newton oscillates near zero-coupon short bonds, widen Brent bracket (e.g., y in [-2%, 20%]) with DF guards.

---
