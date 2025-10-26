# Objective
Investigate and fix the small but critical near-term discount factor mismatch causing the initial PV gap.

Current observation:
- DF(2024-01-04): our model ≈ 0.99972158
- DF(2024-01-04): Bloomberg SWPM ≈ 0.999783
→ PV gap ≈ -618 EUR on the first PAY cashflow.

Goal:
Match this first discount factor to SWPM exactly (within 1e-6) **without degrading any other discount factors or leg NPVs**.

# Hypothesis
The source is likely one of:
1. **Value-date / spot-lag mismatch** — curve anchored at trade vs. settlement date.  
2. **Stub period logic** — first coupon or DF derived from a short stub misalignment.  
3. **Day-count / compounding convention error** (ACT/360 vs ACT/365F, simple vs continuous).  
4. **Calendar shift** — TARGET holiday handling differences on 2024-01-02 / 2024-01-04.

# Tasks
1. **Verify date alignment**  
   Print:
   - Trade / valuation date  
   - Curve value date (spot date)  
   - Swap effective date (2024-01-04)  
   - First reset and payment dates per leg  
   - First pillar date and DF(spot) in the curve  

2. **Extract short-end curve nodes** from `pricer/swap/.venv/bin/python -m pricer.swap.test.bootstrapping`  
   Display a table:  
     maturity | zero_rate | discount_factor | days_from_value_date

3. **Compare to SWPM DFs** (from CSV)  
   Build DataFrame:
     date | our_DF | swpm_DF | ΔDF | days_from_val_date | PV_impact

4. **Check curve anchoring logic**  
   - Is DF = 1.0 at trade date or value date?  
   - Spot-lag parameter (T+0, T+1, T+2)?  
   - Any short stub created for first period?

5. **Manual validation**  
   Compute DF analytically using ACT/360 continuous compounding:  
   `DF = exp(-r * Δt)`  
   with short-end OIS rate ≈ 2.9 % and Δt = (2024-01-04 – 2024-01-02)/360.  
   Confirm whether this gives ~0.999783.

6. **Test controlled adjustments**  
   If mismatch is from anchoring or stub logic, try:
   - Shift curve spot date  
   - Re-anchor DF = 1.0 at correct date  
   - Adjust interpolation basis near spot  

   ➤ After each change:
      • Re-compute all DFs and leg PVs  
      • If *any* other DF or NPV diverges more than before, **revert to prior configuration** immediately.

7. **Produce final diagnostic report**
   - Table: date | our_DF | swpm_DF | ΔDF (bp) | days | suspected_cause  
   - “Diagnosis summary” paragraph explaining the precise cause.  
   - Code/config line(s) adjusted.  
   - Before/after NPV comparison confirming no regression on other results.

# Key Requirements
- Do **not** re-bootstrap the full curve yet.  
- Focus only on reproducing SWPM’s **first discount factor** and confirming consistent date anchoring.  
- Any attempt that worsens existing alignment elsewhere must be **reverted automatically**.  
- Terminate once DF(2024-01-04) matches SWPM within ±1 e-6 and total NPV difference ≤ ±10 EUR.

# Output
- Compact table of near-term DFs (our vs SWPM)  
- Narrative summary of findings and fix  
- Confirmation message: “Front-end DF now matches Bloomberg; no other regressions observed.”