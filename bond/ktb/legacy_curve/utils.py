from typing import Dict, List, Tuple, Union
import math
from ..curve_types import CurveNode


def _ensure_sorted_pairs(d: Dict[float, float]) -> List[Tuple[float, float]]:
    return sorted(((float(k), float(v)) for k, v in d.items()), key=lambda kv: kv[0])


def _normalize_ytm_input_to_pct_pairs(
    ytm_input: Union[Dict[float, float], List[CurveNode]],
) -> List[Tuple[float, float]]:
    if isinstance(ytm_input, dict):
        return _ensure_sorted_pairs(ytm_input)
    pairs: List[Tuple[float, float]] = [
        (float(node.tenor_years), float(node.ytm) * 100.0) for node in ytm_input
    ]
    pairs.sort(key=lambda kv: kv[0])
    return pairs


def build_halfyear_grid(
    ytm_curve: Union[Dict[float, float], List[CurveNode]], max_t: float | None = None
) -> List[float]:
    pairs = _normalize_ytm_input_to_pct_pairs(ytm_curve)
    keys = [t for t, _ in pairs]
    if not keys:
        return []
    if max_t is None:
        max_t = keys[-1]
    n = int(math.floor(float(max_t) / 0.5))
    grid = [0.5 * k for k in range(1, n + 1)]
    if 0.25 <= max_t:
        grid = [0.25] + grid
    if 0.75 <= max_t and 0.75 not in grid:
        grid = sorted(set(grid + [0.75]))
    return grid


def _interpolate_zero_rate(tenor: float, zero_rates: Dict[float, float]) -> float:
    """Linear interpolation of zero rates (expects decimal inputs)."""
    known_tenors = sorted(zero_rates.keys())
    if tenor in zero_rates:
        return zero_rates[tenor]
    if tenor < known_tenors[0]:
        return zero_rates[known_tenors[0]]
    if tenor > known_tenors[-1]:
        return zero_rates[known_tenors[-1]]
    for i in range(len(known_tenors) - 1):
        if known_tenors[i] <= tenor <= known_tenors[i + 1]:
            t_a, t_b = known_tenors[i], known_tenors[i + 1]
            z_a, z_b = zero_rates[t_a], zero_rates[t_b]
            z_t = z_a + (z_b - z_a) * (tenor - t_a) / (t_b - t_a)
            return z_t
    return zero_rates[known_tenors[-1]]


def discount_factor_from_zero(
    zero_rates_pct: Dict[float, float], tenor: float
) -> float:
    if not zero_rates_pct:
        return 1.0
    zero_rates_dec = {t: z / 100.0 for t, z in zero_rates_pct.items()}
    z_t = _interpolate_zero_rate(tenor, zero_rates_dec)
    return 1.0 / (1.0 + z_t) ** tenor


def build_df_zero_grid(
    zero_rates_pct: Dict[float, float], max_tenor: float | None = None
) -> Dict[float, Tuple[float, float]]:
    if not zero_rates_pct:
        return {}
    keys_sorted = sorted(float(k) for k in zero_rates_pct.keys())
    if not keys_sorted:
        return {}
    if max_tenor is None:
        max_tenor = keys_sorted[-1]
    n = int(math.floor(float(max_tenor) / 0.5))
    target_tenors = [0.5 * i for i in range(1, n + 1)]
    out: Dict[float, Tuple[float, float]] = {}
    for t in target_tenors:
        df_t = discount_factor_from_zero(zero_rates_pct, t)
        z_dec = _interpolate_zero_rate(
            t, {k: v / 100.0 for k, v in zero_rates_pct.items()}
        )
        out[t] = (df_t, z_dec * 100.0)
    return out
