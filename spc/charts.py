"""Shewhart control chart calculations (pure functions, no UI).

Formulas follow Montgomery, *Introduction to Statistical Quality Control*
(chapters 6 and 7) and the NIST/SEMATECH e-Handbook, section 6.3.

Every chart returns a :class:`ControlChart` made of one or two
:class:`ChartSeries` (e.g. X-bar + R). Limits are stored per point as arrays
so that charts with varying sample size (p, u) use the same structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .constants import get_constants


@dataclass
class ChartSeries:
    title: str
    values: np.ndarray
    cl: np.ndarray
    ucl: np.ndarray
    lcl: np.ndarray
    # Index labels of the plotted points (subgroup number, sample id, ...)
    labels: np.ndarray | None = None

    def __post_init__(self):
        n = len(self.values)
        self.values = np.asarray(self.values, dtype=float)
        self.cl = _as_array(self.cl, n)
        self.ucl = _as_array(self.ucl, n)
        self.lcl = _as_array(self.lcl, n)
        if self.labels is None:
            self.labels = np.arange(1, n + 1)

    @property
    def sigma(self) -> np.ndarray:
        """One-sigma width of the zones (distance CL -> UCL divided by 3)."""
        return (self.ucl - self.cl) / 3.0

    @property
    def beyond_limits(self) -> np.ndarray:
        return (self.values > self.ucl + 1e-12) | (self.values < self.lcl - 1e-12)


@dataclass
class ControlChart:
    kind: str
    primary: ChartSeries
    secondary: ChartSeries | None = None
    # Estimate of within-subgroup (short-term) sigma implied by the chart
    sigma_within: float | None = None
    info: dict = field(default_factory=dict)

    @property
    def series(self) -> list[ChartSeries]:
        return [s for s in (self.primary, self.secondary) if s is not None]


def _as_array(x, n):
    a = np.asarray(x, dtype=float)
    if a.ndim == 0:
        a = np.full(n, float(a))
    return a


def _check_subgroups(subgroups) -> np.ndarray:
    x = np.asarray(subgroups, dtype=float)
    if x.ndim != 2:
        raise ValueError("Subgroup data must be a 2-D array (subgroups x observations)")
    if np.isnan(x).any():
        raise ValueError("Subgroup data contains missing values; subgroups must be complete")
    k, n = x.shape
    if k < 2:
        raise ValueError("Need at least 2 subgroups")
    if n < 2:
        raise ValueError("Subgroup size must be at least 2 (use the I-MR chart for n = 1)")
    return x


# ---------------------------------------------------------------- variables
def xbar_r(subgroups) -> ControlChart:
    """X-bar and R chart. Limits: X-bar-bar +/- A2*R-bar; R: D3*R-bar, D4*R-bar."""
    x = _check_subgroups(subgroups)
    k, n = x.shape
    c = get_constants(n)
    means = x.mean(axis=1)
    ranges = x.max(axis=1) - x.min(axis=1)
    xbb, rbar = means.mean(), ranges.mean()
    return ControlChart(
        kind="Xbar-R",
        primary=ChartSeries("X-bar", means, xbb, xbb + c.A2 * rbar, xbb - c.A2 * rbar),
        secondary=ChartSeries("Range", ranges, rbar, c.D4 * rbar, c.D3 * rbar),
        sigma_within=rbar / c.d2,
        info={"n": n, "k": k, "grand_mean": xbb, "r_bar": rbar, "A2": c.A2, "D3": c.D3, "D4": c.D4, "d2": c.d2},
    )


def xbar_s(subgroups) -> ControlChart:
    """X-bar and S chart. Limits: X-bar-bar +/- A3*S-bar; S: B3*S-bar, B4*S-bar."""
    x = _check_subgroups(subgroups)
    k, n = x.shape
    c = get_constants(n)
    means = x.mean(axis=1)
    sds = x.std(axis=1, ddof=1)
    xbb, sbar = means.mean(), sds.mean()
    return ControlChart(
        kind="Xbar-S",
        primary=ChartSeries("X-bar", means, xbb, xbb + c.A3 * sbar, xbb - c.A3 * sbar),
        secondary=ChartSeries("Std Dev", sds, sbar, c.B4 * sbar, c.B3 * sbar),
        sigma_within=sbar / c.c4,
        info={"n": n, "k": k, "grand_mean": xbb, "s_bar": sbar, "A3": c.A3, "B3": c.B3, "B4": c.B4, "c4": c.c4},
    )


def imr(values) -> ControlChart:
    """Individuals and moving range (span 2) chart.

    I limits: x-bar +/- 3*MR-bar/d2 (= 2.66 MR-bar); MR UCL = D4*MR-bar (3.267).
    """
    x = np.asarray(values, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) < 3:
        raise ValueError("Need at least 3 observations for an I-MR chart")
    c = get_constants(2)
    mr = np.abs(np.diff(x))
    xbar, mrbar = x.mean(), mr.mean()
    sigma = mrbar / c.d2
    return ControlChart(
        kind="I-MR",
        primary=ChartSeries("Individual", x, xbar, xbar + 3 * sigma, xbar - 3 * sigma),
        secondary=ChartSeries("Moving Range", mr, mrbar, c.D4 * mrbar, c.D3 * mrbar,
                              labels=np.arange(2, len(x) + 1)),
        sigma_within=sigma,
        info={"n": 1, "k": len(x), "mean": xbar, "mr_bar": mrbar, "d2": c.d2, "D4": c.D4},
    )


# --------------------------------------------------------------- attributes
def p_chart(defectives, sample_sizes) -> ControlChart:
    """Fraction nonconforming chart. p-bar = sum(d)/sum(n); limits p-bar +/- 3 sqrt(p-bar(1-p-bar)/n_i)."""
    d = np.asarray(defectives, dtype=float)
    n = _as_array(sample_sizes, len(d))
    if (d < 0).any() or (d > n).any():
        raise ValueError("Defectives must be between 0 and the sample size")
    p = d / n
    pbar = d.sum() / n.sum()
    half = 3 * np.sqrt(pbar * (1 - pbar) / n)
    return ControlChart(
        kind="p",
        primary=ChartSeries("Proportion defective", p, pbar, np.minimum(1, pbar + half), np.maximum(0, pbar - half)),
        info={"p_bar": pbar, "k": len(d), "n_constant": bool(np.all(n == n[0]))},
    )


def np_chart(defectives, sample_size: int) -> ControlChart:
    """Number nonconforming chart (constant n). Limits n*p-bar +/- 3 sqrt(n p-bar (1-p-bar))."""
    d = np.asarray(defectives, dtype=float)
    n = float(sample_size)
    if (d < 0).any() or (d > n).any():
        raise ValueError("Defectives must be between 0 and the sample size")
    pbar = d.mean() / n
    cl = n * pbar
    half = 3 * np.sqrt(n * pbar * (1 - pbar))
    return ControlChart(
        kind="np",
        primary=ChartSeries("Number defective", d, cl, min(n, cl + half), max(0.0, cl - half)),
        info={"p_bar": pbar, "n": n, "k": len(d)},
    )


def c_chart(counts) -> ControlChart:
    """Nonconformities per unit (constant inspection unit). Limits c-bar +/- 3 sqrt(c-bar)."""
    c = np.asarray(counts, dtype=float)
    if (c < 0).any():
        raise ValueError("Counts must be non-negative")
    cbar = c.mean()
    half = 3 * np.sqrt(cbar)
    return ControlChart(
        kind="c",
        primary=ChartSeries("Defects", c, cbar, cbar + half, max(0.0, cbar - half)),
        info={"c_bar": cbar, "k": len(c)},
    )


def u_chart(counts, units) -> ControlChart:
    """Nonconformities per unit with varying inspection size. Limits u-bar +/- 3 sqrt(u-bar/n_i)."""
    c = np.asarray(counts, dtype=float)
    n = _as_array(units, len(c))
    if (c < 0).any() or (n <= 0).any():
        raise ValueError("Counts must be non-negative and units positive")
    u = c / n
    ubar = c.sum() / n.sum()
    half = 3 * np.sqrt(ubar / n)
    return ControlChart(
        kind="u",
        primary=ChartSeries("Defects per unit", u, ubar, ubar + half, np.maximum(0, ubar - half)),
        info={"u_bar": ubar, "k": len(c)},
    )


# ------------------------------------------------------------------ helpers
def subgroups_from_long(values, subgroup_ids=None, subgroup_size: int | None = None) -> np.ndarray:
    """Turn a single measurement column into a (k x n) array.

    Either group by an ID column (all groups must have the same size) or cut
    consecutive rows into blocks of ``subgroup_size`` (an incomplete final
    block is dropped).
    """
    v = np.asarray(values, dtype=float)
    if subgroup_ids is not None:
        import pandas as pd

        df = pd.DataFrame({"v": v, "g": subgroup_ids}).dropna()
        groups = [g["v"].to_numpy() for _, g in df.groupby("g", sort=False)]
        sizes = {len(g) for g in groups}
        if len(sizes) != 1:
            raise ValueError(f"Subgroups have unequal sizes {sorted(sizes)}; X-bar charts here need equal n")
        return np.vstack(groups)
    if not subgroup_size or subgroup_size < 2:
        raise ValueError("Provide a subgroup ID column or a subgroup size >= 2")
    v = v[~np.isnan(v)]
    k = len(v) // subgroup_size
    if k < 2:
        raise ValueError("Not enough data for two complete subgroups")
    return v[: k * subgroup_size].reshape(k, subgroup_size)
