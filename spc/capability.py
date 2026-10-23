"""Process capability (Cp, Cpk, Pp, Ppk, Cpm) and normality testing.

Definitions (NIST/SEMATECH e-Handbook 6.1.6; Montgomery ch. 8; AIAG SPC manual):

    Cp  = (USL - LSL) / (6 sigma_within)
    Cpk = min(USL - mu, mu - LSL) / (3 sigma_within)
    Pp  = (USL - LSL) / (6 sigma_overall)
    Ppk = min(USL - mu, mu - LSL) / (3 sigma_overall)
    Cpm = (USL - LSL) / (6 sqrt(sigma_overall^2 + (mu - T)^2))

*Within* sigma is the short-term, common-cause variation estimated from the
control chart (R-bar/d2, S-bar/c4, pooled SD, or MR-bar/d2 for individuals).
*Overall* sigma is the ordinary sample standard deviation of all data, so it
also contains any drift between subgroups.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import stats

from .constants import c4, get_constants

SIGMA_METHODS = ("Rbar/d2", "Sbar/c4", "Pooled SD", "MRbar/d2")


# ----------------------------------------------------------- within sigma
def sigma_within(data, subgroup_size: int = 1, method: str | None = None) -> float:
    """Short-term sigma.

    * n = 1 -> MR-bar / d2(2) (moving range of span 2)
    * n > 1 -> R-bar/d2 (default), S-bar/c4 or pooled SD / c4(d+1)
      where d = total degrees of freedom (Minitab's default within estimate).
    """
    x = np.asarray(data, dtype=float)
    if subgroup_size <= 1 or method == "MRbar/d2":
        mr = np.abs(np.diff(x[~np.isnan(x)]))
        return mr.mean() / get_constants(2).d2
    x = np.asarray(x, dtype=float).reshape(-1, subgroup_size)
    n = subgroup_size
    method = method or "Rbar/d2"
    if method == "Rbar/d2":
        r = x.max(axis=1) - x.min(axis=1)
        return r.mean() / get_constants(n).d2
    if method == "Sbar/c4":
        return x.std(axis=1, ddof=1).mean() / c4(n)
    if method == "Pooled SD":
        dof = x.shape[0] * (n - 1)
        sp = math.sqrt(((x - x.mean(axis=1, keepdims=True)) ** 2).sum() / dof)
        return sp / c4(dof + 1)
    raise ValueError(f"Unknown sigma method {method!r}")


# ------------------------------------------------------------- normality
@dataclass
class NormalityResult:
    ad_statistic: float
    ad_adjusted: float
    ad_p_value: float
    shapiro_w: float | None
    shapiro_p: float | None

    @property
    def is_normal(self) -> bool:
        return self.ad_p_value >= 0.05


def anderson_darling(data) -> NormalityResult:
    """Anderson-Darling normality test with mean and sigma estimated from the data.

    A^2 is the standard statistic; the small-sample adjustment
    A*^2 = A^2 (1 + 0.75/n + 2.25/n^2) and the p-value approximation are from
    D'Agostino & Stephens, *Goodness-of-Fit Techniques* (1986), Table 4.9 -
    the same approach Minitab uses.
    """
    x = np.sort(np.asarray(data, dtype=float))
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 8:
        raise ValueError("Anderson-Darling test needs at least 8 observations")
    z = (x - x.mean()) / x.std(ddof=1)
    logcdf = stats.norm.logcdf(z)
    logsf = stats.norm.logsf(z)
    i = np.arange(1, n + 1)
    a2 = -n - np.sum((2 * i - 1) * (logcdf + logsf[::-1])) / n
    a = a2 * (1 + 0.75 / n + 2.25 / n**2)
    if a >= 0.6:
        p = math.exp(1.2937 - 5.709 * a + 0.0186 * a**2)
    elif a >= 0.34:
        p = math.exp(0.9177 - 4.279 * a - 1.38 * a**2)
    elif a > 0.2:
        p = 1 - math.exp(-8.318 + 42.796 * a - 59.938 * a**2)
    else:
        p = 1 - math.exp(-13.436 + 101.14 * a - 223.73 * a**2)
    p = min(max(p, 0.0), 1.0)
    sw, sp = (stats.shapiro(x) if 3 <= n <= 5000 else (None, None))
    return NormalityResult(float(a2), float(a), float(p),
                           None if sw is None else float(sw), None if sp is None else float(sp))


# ------------------------------------------------------------ capability
@dataclass
class CapabilityResult:
    n: int
    mean: float
    sigma_within: float
    sigma_overall: float
    lsl: float | None
    usl: float | None
    target: float | None
    Cp: float | None
    Cpl: float | None
    Cpu: float | None
    Cpk: float | None
    Pp: float | None
    Ppl: float | None
    Ppu: float | None
    Ppk: float | None
    Cpm: float | None
    ppm_observed: float
    ppm_within: float
    ppm_overall: float
    normality: NormalityResult | None = None
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k not in ("normality", "extra")}
        if self.normality:
            d.update({"AD": self.normality.ad_statistic, "AD p-value": self.normality.ad_p_value})
        return d


def _indices(mean, sigma, lsl, usl):
    cpu = (usl - mean) / (3 * sigma) if usl is not None else None
    cpl = (mean - lsl) / (3 * sigma) if lsl is not None else None
    cp = (usl - lsl) / (6 * sigma) if (usl is not None and lsl is not None) else None
    cpk = min(v for v in (cpu, cpl) if v is not None)
    return cp, cpl, cpu, cpk


def _expected_ppm(mean, sigma, lsl, usl):
    p = 0.0
    if lsl is not None:
        p += stats.norm.cdf((lsl - mean) / sigma)
    if usl is not None:
        p += stats.norm.sf((usl - mean) / sigma)
    return 1e6 * p


def capability_from_stats(mean: float, sigma_within: float, sigma_overall: float | None = None,
                          lsl: float | None = None, usl: float | None = None,
                          target: float | None = None, n: int = 0) -> CapabilityResult:
    """Capability indices from summary statistics (no raw data needed)."""
    if lsl is None and usl is None:
        raise ValueError("Provide at least one specification limit")
    if lsl is not None and usl is not None and lsl >= usl:
        raise ValueError("LSL must be less than USL")
    if sigma_within <= 0:
        raise ValueError("Sigma must be positive")
    so = sigma_overall if sigma_overall is not None else sigma_within
    cp, cpl, cpu, cpk = _indices(mean, sigma_within, lsl, usl)
    pp, ppl, ppu, ppk = _indices(mean, so, lsl, usl)
    cpm = None
    if lsl is not None and usl is not None:
        t = target if target is not None else (lsl + usl) / 2
        cpm = (usl - lsl) / (6 * math.sqrt(so**2 + (mean - t) ** 2))
    return CapabilityResult(
        n=n, mean=mean, sigma_within=sigma_within, sigma_overall=so, lsl=lsl, usl=usl, target=target,
        Cp=cp, Cpl=cpl, Cpu=cpu, Cpk=cpk, Pp=pp, Ppl=ppl, Ppu=ppu, Ppk=ppk, Cpm=cpm,
        ppm_observed=float("nan"),
        ppm_within=_expected_ppm(mean, sigma_within, lsl, usl),
        ppm_overall=_expected_ppm(mean, so, lsl, usl),
    )


def capability(data, lsl: float | None = None, usl: float | None = None, target: float | None = None,
               subgroup_size: int = 1, sigma_method: str | None = None) -> CapabilityResult:
    """Full capability analysis on raw data (in time order)."""
    x = np.asarray(data, dtype=float)
    x = x[~np.isnan(x)]
    if subgroup_size > 1:
        x = x[: (len(x) // subgroup_size) * subgroup_size]
    if len(x) < 2:
        raise ValueError("Need at least 2 observations")
    sw = sigma_within(x, subgroup_size, sigma_method)
    so = x.std(ddof=1)
    res = capability_from_stats(x.mean(), sw, so, lsl, usl, target, n=len(x))
    out = np.zeros(len(x), dtype=bool)
    if lsl is not None:
        out |= x < lsl
    if usl is not None:
        out |= x > usl
    res.ppm_observed = 1e6 * out.mean()
    if len(x) >= 8:
        res.normality = anderson_darling(x)
    return res


def capability_verdict(index: float | None) -> str:
    """Common industry reading of Cpk/Ppk (AIAG PPAP: >=1.67 new, >=1.33 ongoing)."""
    if index is None or not np.isfinite(index):
        return "n/a"
    if index >= 1.67:
        return "Excellent (>= 1.67)"
    if index >= 1.33:
        return "Capable (>= 1.33)"
    if index >= 1.0:
        return "Marginal (1.00 - 1.33)"
    return "Not capable (< 1.00)"
