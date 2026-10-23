"""Control chart constants for subgroup sizes n = 2..25.

d2 and d3 (mean and standard deviation of the relative range W = R/sigma of a
normal sample) are the standard tabulated values (e.g. Montgomery,
*Introduction to Statistical Quality Control*, Appendix Table VI; ASTM E2587).
Every other factor is *derived* from d2, d3 and c4 using the textbook
definitions, so a single source of truth drives all the charts:

    A2 = 3 / (d2 * sqrt(n))          X-bar limits from R-bar
    D3 = max(0, 1 - 3 d3 / d2)       R chart LCL factor
    D4 = 1 + 3 d3 / d2               R chart UCL factor
    c4 = sqrt(2/(n-1)) * Gamma(n/2) / Gamma((n-1)/2)
    A3 = 3 / (c4 * sqrt(n))          X-bar limits from S-bar
    B3 = max(0, 1 - 3 sqrt(1 - c4^2) / c4)
    B4 = 1 + 3 sqrt(1 - c4^2) / c4
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from scipy import integrate, stats

# Tabulated d2, d3 for n = 2..25 (Montgomery Appendix VI / ASTM E2587).
_D2 = [1.128, 1.693, 2.059, 2.326, 2.534, 2.704, 2.847, 2.970, 3.078, 3.173,
       3.258, 3.336, 3.407, 3.472, 3.532, 3.588, 3.640, 3.689, 3.735, 3.778,
       3.819, 3.858, 3.895, 3.931]
_D3 = [0.853, 0.888, 0.880, 0.864, 0.848, 0.833, 0.820, 0.808, 0.797, 0.787,
       0.778, 0.770, 0.763, 0.756, 0.750, 0.744, 0.739, 0.734, 0.729, 0.724,
       0.720, 0.716, 0.712, 0.708]

MIN_N, MAX_N = 2, 25


@dataclass(frozen=True)
class Constants:
    n: int
    d2: float
    d3: float
    c4: float
    A2: float
    A3: float
    D3: float
    D4: float
    B3: float
    B4: float


def c4(n: int) -> float:
    """Unbiasing constant for the sample standard deviation: E[s] = c4 * sigma."""
    if n < 2:
        raise ValueError("c4 requires n >= 2")
    return math.sqrt(2.0 / (n - 1)) * math.exp(math.lgamma(n / 2) - math.lgamma((n - 1) / 2))


def d2_numeric(n: int) -> float:
    """d2 = E[range of n standard normals], computed by numerical integration.

    d2(n) = integral over x of [1 - Phi(x)^n - (1 - Phi(x))^n] dx.
    Used only to cross-check the tabulated values in the tests.
    """
    f = lambda x: 1.0 - stats.norm.cdf(x) ** n - stats.norm.sf(x) ** n  # noqa: E731
    val, _ = integrate.quad(f, -np.inf, np.inf)
    return val


@lru_cache(maxsize=None)
def get_constants(n: int) -> Constants:
    if not MIN_N <= n <= MAX_N:
        raise ValueError(f"Subgroup size must be between {MIN_N} and {MAX_N}, got {n}")
    d2 = _D2[n - 2]
    d3 = _D3[n - 2]
    cc4 = c4(n)
    s_fac = 3.0 * math.sqrt(1.0 - cc4 ** 2) / cc4
    return Constants(
        n=n,
        d2=d2,
        d3=d3,
        c4=cc4,
        A2=3.0 / (d2 * math.sqrt(n)),
        A3=3.0 / (cc4 * math.sqrt(n)),
        D3=max(0.0, 1.0 - 3.0 * d3 / d2),
        D4=1.0 + 3.0 * d3 / d2,
        B3=max(0.0, 1.0 - s_fac),
        B4=1.0 + s_fac,
    )


def constants_table() -> "list[dict]":
    """All constants as a list of dicts (handy for display)."""
    return [get_constants(n).__dict__ for n in range(MIN_N, MAX_N + 1)]
