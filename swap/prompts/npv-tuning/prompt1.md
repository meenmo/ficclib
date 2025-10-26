# === Codex/Claude Plan Preamble ===
Step 1. Verify that curve bootstrapping is functioning correctly by running:
        pricer/swap/.venv/bin/python -m pricer.swap.test.bootstrapping
        → Confirm the OIS (ESTR) and EURIBOR curves are correctly built and consistent with Bloomberg discount/forward curves.

Step 2. Load the reference CSV file located at:

    /Users/meenmo/Documents/workspace/pricer/swap/prompts/npv-tuning/swpm_240102_0x30.csv
    → Inspect columns and validate meanings:

        - "Reset date" = Forward fixing date
        - "Reset rate" = Forward rate
        - "Discount" = ESTR(OIS) discount factor
        - "Payment" = Projected coupon or floating payment
        - "PV" = Present value = Discount × Payment

Step 3. Generate an SWPM-style DataFrame for each leg (Receive 3M / Pay 6M) including:
    
    - reset_date
    - payment_date
    - forward_rate
    - discount_factor
    - accrual_factor
    - cashflow
    - pv
    - leg_type

→ Use 'polars' for structure; align dates with Bloomberg’s schedule (TARGET calendar).

Step 4. Run and analyze internal model pricing using:
        pricer/swap/.venv/bin/python -m pricer.swap.test.npv
        → Extract leg PVs, forward rates, and DFs used internally.

Step 5. Compare Bloomberg vs. model results:
        - Total NPV
        - Pay/Receive leg PVs
        - Forward rate paths
        - Discount factors
        - Cashflow timings and accruals

Step 6. Identify and document sources of discrepancy:
        - Curve construction issues (e.g., compounding, interpolation, or day-count mismatch)
        - Reset schedule misalignment (lags, stubs, business-day adjustments)
        - Notional or accrual factor scaling differences
        - Sign conventions or date roll errors
        - Rounding precision or floating-leg reset rate logic

Step 7. Produce a concise diagnostic report:
        - “Summary of observed discrepancies”
        - “Root cause hypothesis”
        - “Proposed fix or parameter to adjust”
        - Include recomputed SWPM-style DataFrame confirming any fix.

---

## === Context Setup ===

- Working directory: /Users/meenmo/Documents/workspace  
- Target command: pricer/swap/.venv/bin/python -m pricer.swap.test.npv  
- Curve bootstrapping validation: pricer/swap/.venv/bin/python -m pricer.swap.test.bootstrapping  
- Reference data: /Users/meenmo/Documents/workspace/temp/swpm/240102_0x30.csv  
- Python Environment: pricer/swap/.venv/bin/python (uv venv)
---

## === SWPM Example Specification ===
- Trade / Curve / Valuation Date: 2024-01-02  
- Effective Date: 2024-01-04  
- Maturity Date: 2054-01-05  
- Receive Leg Index: EURIBOR 3M  
- Pay Leg Index: EURIBOR 6M  
- Receive Pay / Reset Frequency: Quarterly  
- Pay Pay / Reset Frequency: Semi-Annual  
- Day Count (both legs): ACT/360  
- Discounting: ESTR (OIS)

Bloomberg SWPM outputs:
  Total NPV (EUR):      170,536.51  
  Pay Leg (6M) NPV:     -16,897.19  
  Rec Leg (3M) NPV:     187,443.70

Internal pricer current output:
  Total NPV (EUR):      170,738.22  
  Pay Leg (6M) NPV:     -10,000,612.75  
  Rec Leg (3M) NPV:     10,171,350.98  

The NPV in the CSV can be validated by summing the “PV” column.

---

## === Objective ===
Replicate the Bloomberg SWPM result precisely using the `pricer/swap` engine.  
Ensure that the engine’s bootstrapped curves, forward rates, and cashflow valuations are fully aligned with Bloomberg conventions.

---

## === Expected Claude/Codex Behavior ===
- Read CSV and validate each column’s meaning.
- Create SWPM-style polars DataFrame with PV breakdowns per leg.
- Compute NPV totals and compare against both Bloomberg and internal results.
- Run curve bootstrapping test and log discount factors used.
- Diagnose root causes of any discrepancy in rates, DFs, or timing.
- Suggest and optionally patch code/configuration differences.
- Produce structured diagnostic report containing:
    • Summary of observed discrepancies  
    • Root cause hypothesis  
    • Proposed fix or test to validate  
    • Recomputed SWPM-style DataFrame  

## === Deliverable ===
Return:
1. SWPM-style DataFrame for both legs showing reset_date, forward_rate, discount_factor, accrual_factor, cashflow, PV.  
2. Side-by-side NPV comparison (internal vs Bloomberg).  
3. A clearly written diagnostic report with actionable adjustments (e.g., compounding, accrual, day-count).  
4. Optional validation step rerunning bootstrapping and pricing after adjustments.

## === Ultimate Goal ===
Achieve one-to-one replication of Bloomberg SWPM results using `pricer/swap` model.