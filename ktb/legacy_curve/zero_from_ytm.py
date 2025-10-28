from __future__ import annotations

from typing import Dict

from .utils import _interpolate_zero_rate


def bootstrap_zero_curve_from_ytm(ytm_curve: Dict[float, float]) -> Dict[float, float]:
    """Bootstrap zero-curve from a YTM grid (percent) using semi-annual coupons.

    Returns a dict tenor_years -> zero_rate_percent. Internally uses simple
    compounding for zero rates and discounts coupon cashflows at their exact
    payment times using already-bootstrapped zero rates.
    """
    # Convert YTM percentages to decimals
    ytm_decimal = {tenor: ytm / 100.0 for tenor, ytm in ytm_curve.items()}

    # Sort tenors in ascending order
    tenors = sorted(ytm_decimal.keys())
    zero_rates: Dict[float, float] = {}  # decimals

    # Step 1: Handle zero-coupon anchor (0.25y only for KTB semi-annual coupons)
    if 0.25 in ytm_decimal:
        zero_rates[0.25] = ytm_decimal[0.25]

    # Step 2: Bootstrap 0.5-year tenor (first coupon-bearing)
    # For semi-annual coupons, the only cashflow at 0.5y is (coupon + face).
    # Par condition: 10000 = (c + 10000) / (1 + Z_0.5)^{0.5}
    # => (1 + Z_0.5)^{0.5} = 1 + c/2  =>  Z_0.5 = (1 + c/2)^2 - 1
    if 0.5 in ytm_decimal:
        c = ytm_decimal[0.5]
        z_05 = (1.0 + c / 2.0) ** 2 - 1.0
        zero_rates[0.5] = z_05

    # Step 3: Iterative bootstrapping for remaining half-year tenors only
    tiny = 1e-9
    for tenor in tenors:
        # allow >0.5y half-year nodes, and explicitly allow 0.75y if present in input
        if tenor <= 0.5 + tiny:
            continue
        if abs((tenor / 0.5) - round(tenor / 0.5)) > 1e-9 and abs(tenor - 0.75) > 1e-9:
            continue

        # coupon times strictly before maturity at 0.5-year spacing
        k_max = int((tenor - tiny) / 0.5)
        coupon_rate = ytm_decimal[tenor]
        coupon_payment = coupon_rate * 10000.0 / 2.0

        # Determine last known tenor strictly less than current T
        known_ts = sorted(zero_rates.keys())
        t_lo = max([t for t in known_ts if t < tenor], default=0.0)
        # DF at lower anchor
        if t_lo > 0.0:
            df_lo = 1.0 / (1.0 + zero_rates[t_lo]) ** t_lo
        else:
            # if nothing known (shouldn't happen after anchors), approximate with coupon rate
            df_lo = 1.0 / (1.0 + coupon_rate) ** 1.0

        # Build PV as const + sum K * DF_T^w + (c+Face) * DF_T
        const_pv = 0.0
        coeffs: list[tuple[float, float]] = []  # (K, w)

        for period in range(1, k_max + 1):  # exclude the final cashflow at T
            t = period * 0.5
            if t <= t_lo:
                # Fully within known region: discount directly using existing/interpolated zeros
                z_t = (
                    _interpolate_zero_rate(t, zero_rates)
                    if t not in zero_rates
                    else zero_rates[t]
                )
                df_t = 1.0 / (1.0 + z_t) ** t
                const_pv += coupon_payment * df_t
            else:
                # Between t_lo and T: use ln-DF interpolation between DF_lo and DF_T (unknown)
                w = (t - t_lo) / (tenor - t_lo)
                K = coupon_payment * (df_lo ** (1.0 - w))
                coeffs.append((K, w))

        final_payment = coupon_payment + 10000.0

        # Solve for DF_T in (0,1]
        def f(df_T: float) -> float:
            s = const_pv + final_payment * df_T
            for K, w in coeffs:
                s += K * (df_T**w)
            return s - 10000.0

        lo, hi = 1e-10, 1.0
        f_lo, f_hi = f(lo), f(hi)
        if f_lo > 0 and f_hi > 0:
            df_T_star = lo
        elif f_lo < 0 and f_hi < 0:
            df_T_star = hi
        else:
            for _ in range(80):
                mid = 0.5 * (lo + hi)
                fm = f(mid)
                if abs(fm) < 1e-10:
                    df_T_star = mid
                    break
                if f_lo * fm <= 0:
                    hi, f_hi = mid, fm
                else:
                    lo, f_lo = mid, fm
            else:
                df_T_star = 0.5 * (lo + hi)

        z_T = df_T_star ** (-1.0 / tenor) - 1.0
        zero_rates[tenor] = z_T

    # Convert back to percentages
    return {tenor: z * 100.0 for tenor, z in zero_rates.items()}


def build_zero_curve_from_ytm(ytm_curve: Dict[float, float]) -> Dict[float, float]:
    return bootstrap_zero_curve_from_ytm(ytm_curve)


class YTMZeroCurveBuilder:
    def __init__(self, ytm_curve: Dict[float, float]):
        self.ytm_curve = ytm_curve

    def build_zero_curve(self) -> Dict[float, float]:
        return build_zero_curve_from_ytm(self.ytm_curve)
