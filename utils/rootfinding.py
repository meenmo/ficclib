"""Root-finding utilities (Newton–Raphson with safe fallbacks)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Tuple

import logging

logger = logging.getLogger(__name__)

FuncDeriv = Callable[[float], Tuple[float, float]]
Func = Callable[[float], float]


@dataclass
class RootResult:
    root: float
    iterations: int
    converged: bool
    method: str


class RootFindingError(RuntimeError):
    """Raised when root-finding fails to converge."""


def _bisect(
    func: Func, lower: float, upper: float, tol: float = 1e-6, max_iter: int = 100
) -> RootResult:
    f_lower = func(lower)
    f_upper = func(upper)
    if f_lower == 0.0:
        return RootResult(lower, 0, True, "bisect")
    if f_upper == 0.0:
        return RootResult(upper, 0, True, "bisect")
    if f_lower * f_upper > 0:
        raise RootFindingError("Bisection requires a sign change in the bracket")

    for iteration in range(1, max_iter + 1):
        mid = 0.5 * (lower + upper)
        f_mid = func(mid)
        if abs(f_mid) <= tol or abs(upper - lower) <= tol:
            return RootResult(mid, iteration, True, "bisect")
        if f_lower * f_mid < 0:
            upper, f_upper = mid, f_mid
        else:
            lower, f_lower = mid, f_mid
    raise RootFindingError("Bisection failed to converge")


def _find_bracket(
    func: Func,
    guess: float,
    lower: float = -0.02,
    upper: float = 0.30,
    expansion: float = 1.8,
    max_iter: int = 12,
) -> Tuple[float, float]:
    a, b = lower, upper
    f_a = func(a)
    f_b = func(b)
    for _ in range(max_iter):
        if f_a == 0.0:
            return a, a
        if f_b == 0.0:
            return b, b
        if f_a * f_b < 0:
            return a, b
        a = guess - (guess - a) * expansion
        b = guess + (b - guess) * expansion
        f_a = func(a)
        f_b = func(b)
    raise RootFindingError("Failed to bracket the root")


def newton_with_bisect(
    func_and_deriv: FuncDeriv,
    initial_guess: float,
    *,
    tol_value: float = 1e-6,
    tol_step: float = 1e-10,
    max_iter: int = 50,
    clamp: float = 0.01,
    bracket: Tuple[float, float] | None = None,
) -> RootResult:
    """Newton-Raphson root finder with a bisection fallback.

    Parameters
    ----------
    func_and_deriv:
        Callable returning (value, derivative) at a given point.
    initial_guess:
        Starting point for Newton iterations.
    tol_value:
        Absolute tolerance for the function value.
    tol_step:
        Absolute tolerance for successive updates.
    clamp:
        Maximum absolute Newton step size (e.g., 0.01 = 100 bps).
    bracket:
        Optional explicit bracket (lower, upper) used for fallback.
    """
    x = float(initial_guess)
    lower, upper = (bracket if bracket is not None else (-0.02, 0.30))

    for iteration in range(1, max_iter + 1):
        value, deriv = func_and_deriv(x)
        logger.debug("Newton iter %s: x=%s value=%s deriv=%s", iteration, x, value, deriv)
        if abs(value) <= tol_value:
            return RootResult(x, iteration, True, "newton")
        if deriv == 0.0:
            logger.debug("Zero derivative; aborting Newton at iter %s", iteration)
            break
        step = value / deriv
        if abs(step) > clamp:
            step = clamp if step > 0 else -clamp
        x_new = x - step
        x_new = max(lower, min(upper, x_new))
        if abs(x_new - x) <= tol_step:
            return RootResult(x_new, iteration, True, "newton")
        x = x_new

    def func_only(v: float) -> float:
        return func_and_deriv(v)[0]

    if bracket is None:
        try:
            bracket = _find_bracket(func_only, x, lower=lower, upper=upper)
        except RootFindingError as exc:
            logger.debug("Bracketing failed: %s", exc)
            bracket = (lower, upper)
    b_lower, b_upper = bracket
    result = _bisect(func_only, b_lower, b_upper, tol=tol_value)
    return RootResult(result.root, result.iterations, True, "bisect")
