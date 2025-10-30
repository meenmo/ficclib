"""Mathematical utility functions for KTB analytics."""

from __future__ import annotations

from typing import Dict


def linear_interpolate(value: float, data: Dict[float, float]) -> float:
    """
    Perform piecewise-linear interpolation in a sorted dict of {x: y}.

    Flat extrapolation is applied outside the data range:
      - If value <= min(keys), return data[min(keys)]
      - If value >= max(keys), return data[max(keys)]
      - Otherwise, linearly interpolate between adjacent keys

    Parameters
    ----------
    value : float
        The x-coordinate at which to interpolate
    data : Dict[float, float]
        A dictionary mapping x-values to y-values

    Returns
    -------
    float
        The interpolated (or extrapolated) y-value

    Raises
    ------
    ValueError
        If data is empty
    """
    if not data:
        raise ValueError("data must not be empty for interpolation")

    keys = sorted(data.keys())

    # Flat extrapolation below
    if value <= keys[0]:
        return data[keys[0]]

    # Flat extrapolation above
    if value >= keys[-1]:
        return data[keys[-1]]

    # Linear interpolation
    for idx in range(1, len(keys)):
        x0, x1 = keys[idx - 1], keys[idx]
        if x0 <= value <= x1:
            y0, y1 = data[x0], data[x1]
            weight = (value - x0) / (x1 - x0)
            return y0 + weight * (y1 - y0)

    # Fallback (should never reach here)
    return data[keys[-1]]
