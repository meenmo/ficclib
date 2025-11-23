"""Key rate delta calculations for KTB bonds.

This module implements Key Rate Delta (KRD) calculations
for KTB using par curve bumping methodology.

KRD measures the price sensitivity of a bond to a 1 basis point parallel shift
in the yield curve at a specific key rate tenor.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Union

import logging

from .bond import KTB
from .curve import ZeroCurve

logger = logging.getLogger(__name__)


def _shift_par_curve(
    par_curve_pct: Dict[float, float],
    tenor: float,
    shift_bp: float,
) -> Dict[float, float]:
    """Shift a par curve by the specified basis points at a given tenor.

    Args:
        par_curve_pct: Par yield curve in percentage format (e.g., 2.5 for 2.5%)
        tenor: The tenor (in years) at which to apply the shift
        shift_bp: The shift amount in basis points (e.g., -1 for -1bp)

    Returns:
        Dict with the shifted par curve
    """
    shift_pct = shift_bp / 100.0  # Convert bp to percentage
    result = dict(par_curve_pct)

    # Apply shift at the specified tenor
    if tenor in result:
        result[tenor] = result[tenor] + shift_pct
    else:
        # If tenor not in curve, linearly interpolate the base value
        tenors = sorted(par_curve_pct.keys())
        if tenor <= tenors[0]:
            base = par_curve_pct[tenors[0]]
        elif tenor >= tenors[-1]:
            base = par_curve_pct[tenors[-1]]
        else:
            # Linear interpolation
            for i in range(len(tenors) - 1):
                if tenors[i] <= tenor <= tenors[i+1]:
                    t0, t1 = tenors[i], tenors[i+1]
                    y0, y1 = par_curve_pct[t0], par_curve_pct[t1]
                    weight = (tenor - t0) / (t1 - t0)
                    base = y0 + weight * (y1 - y0)
                    break
            else:
                base = par_curve_pct[tenors[-1]]
        result[tenor] = base + shift_pct

    return dict(sorted(result.items()))


def key_rate_delta(
    bond: Union[KTB, Dict],
    par_curve: Union[Dict[float, float], ZeroCurve],
    key_tenor: float,
    valuation_date: Optional[Union[str, date]] = None,
    shift_bp: float = -1.0,
) -> float:
    """Calculate the Key Rate Delta for a bond at a specific tenor.

    KRD measures the price change of a bond when the par yield curve is shifted
    by 1bp at a specific key rate tenor, following Bloomberg methodology.

    Args:
        bond: KTB bond instance or dict with bond specifications
        par_curve: Par yield curve as dict (tenor -> yield%) or ZeroCurve
        key_tenor: The key rate tenor (in years) to calculate sensitivity
        valuation_date: Valuation/settlement date (defaults to curve date)
        shift_bp: Basis points to shift (default -1bp for rate decrease)

    Returns:
        KRD value (dirty price difference for the shift)

    Example:
        >>> bond = KTB(issue="2020-06-10", maturity="2030-06-10", coupon=1.375)
        >>> par_curve = {0.5: 2.45, 1.0: 2.51, 2.0: 2.75, 3.0: 2.82, 5.0: 2.98}
        >>> krd = key_rate_delta(bond, par_curve, 3.0, "2025-11-11")
    """
    # Convert bond dict to KTB if needed
    if isinstance(bond, dict):
        bond = KTB(
            issue=bond.get("issue_date") or bond.get("issue"),
            maturity=bond.get("maturity_date") or bond.get("maturity"),
            coupon=bond.get("coupon", 0.0),
            pymt_freq=bond.get("pymt_freq", 6),
            face_value=bond.get("face_value", 10000.0),
        )

    # Extract par curve from ZeroCurve if needed
    if isinstance(par_curve, ZeroCurve):
        if hasattr(par_curve, "_par_nodes") and par_curve._par_nodes:
            # Use internal par nodes if available
            par_curve_pct = {
                tenor: rate * 100.0 for tenor, rate in par_curve._par_nodes.items()
            }
            val_date = valuation_date or par_curve.curve_date
        else:
            # Extract from curve tenors (assuming it was built from par yields)
            par_curve_pct = {}
            for tenor in [0.25, 0.5, 0.75, 1, 1.5, 2, 2.5, 3, 4, 5, 7, 10, 15, 20, 30, 50]:
                if tenor <= 50:  # reasonable maximum
                    # This is a simplification - ideally we'd convert zero to par
                    # For now, we'll raise an error if par nodes not available
                    raise ValueError(
                        "ZeroCurve must have par nodes (_par_nodes) for KRD calculation"
                    )
            val_date = valuation_date or par_curve.curve_date
    else:
        par_curve_pct = dict(par_curve)
        val_date = valuation_date

    if val_date is None:
        raise ValueError("valuation_date must be provided when using dict par_curve")

    # Create base zero curve from par yields
    base_curve = ZeroCurve.from_par_yields(
        val_date,
        par_curve_pct,
        comp="cont",
        frequency=2,  # Semiannual for KTB
    )

    # Calculate base price (dirty)
    base_price = bond.price_from_zero_curve(val_date, base_curve)

    # Shift the par curve at the key tenor
    shifted_par = _shift_par_curve(par_curve_pct, key_tenor, shift_bp)

    # Create shifted zero curve
    shifted_curve = ZeroCurve.from_par_yields(
        val_date,
        shifted_par,
        comp="cont",
        frequency=2,
    )

    # Calculate shifted price (dirty)
    shifted_price = bond.price_from_zero_curve(val_date, shifted_curve)

    # KRD is the dirty price difference
    krd = shifted_price - base_price

    logger.debug(
        "KRD calculation: bond=%s, tenor=%sY, base_price=%.4f, shifted_price=%.4f, krd=%.6f",
        bond.maturity,
        key_tenor,
        base_price,
        shifted_price,
        krd,
    )

    return krd


def batch_key_rate_delta(
    bonds: List[Union[KTB, Dict]],
    par_curve: Union[Dict[float, float], ZeroCurve],
    key_tenors: List[float],
    valuation_date: Optional[Union[str, date]] = None,
    shift_bp: float = -1.0,
) -> Dict[str, Dict[float, float]]:
    """Calculate KRD for multiple bonds and tenors efficiently.

    Args:
        bonds: List of KTB instances or bond specification dicts
        par_curve: Par yield curve as dict or ZeroCurve
        key_tenors: List of key rate tenors to calculate
        valuation_date: Valuation date (defaults to curve date)
        shift_bp: Basis points to shift (default -1bp)

    Returns:
        Dict mapping bond identifier to tenor -> KRD mappings

    Example:
        >>> bonds = [
        ...     {"isin": "KR103502G8C0", "issue": "2018-12-10",
        ...      "maturity": "2028-12-10", "coupon": 2.375},
        ...     {"isin": "KR103502G966", "issue": "2019-06-10",
        ...      "maturity": "2029-06-10", "coupon": 1.875},
        ... ]
        >>> par_curve = {0.5: 2.45, 1.0: 2.51, 2.0: 2.75, 3.0: 2.82}
        >>> krds = batch_key_rate_delta(bonds, par_curve, [1.0, 3.0, 5.0])
    """
    # Extract par curve once
    if isinstance(par_curve, ZeroCurve):
        if hasattr(par_curve, "_par_nodes") and par_curve._par_nodes:
            par_curve_pct = {
                tenor: rate * 100.0 for tenor, rate in par_curve._par_nodes.items()
            }
            val_date = valuation_date or par_curve.curve_date
        else:
            raise ValueError(
                "ZeroCurve must have par nodes (_par_nodes) for KRD calculation"
            )
    else:
        par_curve_pct = dict(par_curve)
        val_date = valuation_date

    if val_date is None:
        raise ValueError("valuation_date must be provided when using dict par_curve")

    # Pre-compute all shifted curves
    shifted_curves = {}
    base_curve = ZeroCurve.from_par_yields(
        val_date, par_curve_pct, comp="cont", frequency=2
    )

    for tenor in key_tenors:
        shifted_par = _shift_par_curve(par_curve_pct, tenor, shift_bp)
        shifted_curves[tenor] = ZeroCurve.from_par_yields(
            val_date, shifted_par, comp="cont", frequency=2
        )

    results = {}

    for bond_spec in bonds:
        # Convert to KTB
        if isinstance(bond_spec, dict):
            bond = KTB(
                issue=bond_spec.get("issue_date") or bond_spec.get("issue"),
                maturity=bond_spec.get("maturity_date") or bond_spec.get("maturity"),
                coupon=bond_spec.get("coupon", 0.0),
                pymt_freq=bond_spec.get("pymt_freq", 6),
                face_value=bond_spec.get("face_value", 10000.0),
            )
            # Get identifier
            bond_id = (
                bond_spec.get("isin") or
                bond_spec.get("ISIN") or
                bond_spec.get("id") or
                f"{bond.issue}_{bond.maturity}"
            )
        else:
            bond = bond_spec
            bond_id = f"{bond.issue}_{bond.maturity}"

        # Calculate base price once
        base_price = bond.price_from_zero_curve(val_date, base_curve)

        # Calculate KRD for each tenor
        tenor_krds = {}
        for tenor in key_tenors:
            shifted_price = bond.price_from_zero_curve(val_date, shifted_curves[tenor])
            tenor_krds[tenor] = shifted_price - base_price

        results[bond_id] = tenor_krds

    return results


# Backwards compatibility function
def calculate_key_rate_delta(
    bond_spec: Dict,
    curve: ZeroCurve,
    key_tenor_years: float,
) -> float:
    """Legacy function for backwards compatibility.

    Deprecated: Use key_rate_delta() instead.
    """
    logger.warning(
        "calculate_key_rate_delta is deprecated. Use key_rate_delta() instead."
    )

    krd = key_rate_delta(
        bond_spec,
        curve,
        key_tenor_years,
        valuation_date=curve.curve_date,
    )

    # Legacy function divided by face value
    face = bond_spec.get("face_value", bond_spec.get("face", 10000.0))
    return krd / face