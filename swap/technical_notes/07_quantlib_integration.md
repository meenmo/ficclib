# QuantLib Integration - Technical Documentation

**Purpose:** Document QuantLib replacement effort (Phase 1 complete)
**Status:** Day Count + Calendar replaced, Schedule deferred

---

## Phase 1: Conventions (✅ Complete)

### 1.1 Day Count Conventions

**Replaced:** `engine/conventions/daycount.py`

**Before (Custom):**
```python
class Actual360(DayCountConvention):
    def year_fraction(self, start, end):
        actual_days = (end - start).days
        return actual_days / 360.0
```

**After (QuantLib):**
```python
class Actual360(DayCountConvention):
    def __init__(self):
        super().__init__("ACT/360", ql.Actual360())
```

**Benefits:**
- Industry-standard implementation
- Handles all edge cases correctly
- Reduced maintenance burden
- **Zero regression** in all tests

**Documentation:** `markdown/quantlib_phase1_complete.md`

---

### 1.2 Calendar

**Replaced:** `engine/conventions/calendars.py`

**Before (Custom):**
```python
# Manual holiday list (282 dates!)
TE = [
    "2025-01-01", "2025-04-18", ..., "2081-12-26"
]
```

**After (QuantLib):**
```python
class TargetCalendar(Calendar):
    def __init__(self):
        super().__init__("TARGET", ql.TARGET())
```

**Benefits:**
- **Eliminated 282 manually maintained holidays**
- Automatic Easter calculation
- No annual updates needed
- Industry-standard ECB calendar
- **Zero regression** in all tests

**Documentation:** `markdown/quantlib_phase1.2_complete.md`

---

## Phase 2: Schedule Generation (⏸️ Paused)

**Status:** Assessed as HIGH RISK, LOW BENEFIT

**Reasons for deferral:**
1. Current implementation works correctly
2. QuantLib API has significant differences
3. High risk of subtle regressions
4. No maintenance burden with current code

**Documentation:** `markdown/quantlib_phase2_assessment.md`

---

## Phase 1 Summary

| Component | Lines Saved | Maintenance Burden | Risk | Status |
|-----------|-------------|-------------------|------|--------|
| Day Count | ~100 | Eliminated | LOW | ✅ Complete |
| Calendar | ~300 + 282 holidays | Eliminated | LOW | ✅ Complete |
| Schedule | 0 | Low (already working) | HIGH | ⏸️ Deferred |

**Total:** ~700 lines eliminated, zero regression

---

## Implementation Pattern

**Wrapper approach for API compatibility:**

```python
# QuantLib backend
class DayCountConvention:
    def __init__(self, name: str, ql_daycount: ql.DayCounter):
        self._ql_daycount = ql_daycount

    def year_fraction(self, start, end):
        # Convert Python dates → QuantLib dates
        ql_start = _to_ql_date(start)
        ql_end = _to_ql_date(end)

        # Use QuantLib
        return self._ql_daycount.yearFraction(ql_start, ql_end)
```

**Benefits:**
- 100% API compatibility
- Can swap implementations without changing calling code
- Easy rollback if needed

---

*For detailed results, see `markdown/quantlib_phase1_complete.md` and `markdown/quantlib_phase1.2_complete.md`*
