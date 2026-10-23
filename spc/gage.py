"""Crossed Gage R&R studies (measurement system analysis).

Two methods are provided:

* :func:`gage_rr_anova` - two-way crossed ANOVA (part x operator), the method
  recommended by AIAG MSA (4th ed.) and Minitab's default. If the
  part*operator interaction is not significant (p > alpha, default 0.25) it is
  pooled into repeatability, exactly as Minitab does.
* :func:`gage_rr_average_range` - the classic AIAG average & range method
  with K1/K2/K3 constants, useful to cross-check against the manual.

Verdict thresholds (AIAG MSA): %Study Var (or %Tolerance) < 10% acceptable,
10-30% marginal / may be acceptable, > 30% unacceptable; the number of
distinct categories (ndc) should be >= 5.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class GageResult:
    method: str
    anova: pd.DataFrame | None
    anova_full: pd.DataFrame | None
    interaction_pooled: bool
    components: pd.DataFrame  # variance components + percentages
    ndc: int
    n_parts: int
    n_operators: int
    n_trials: int
    tolerance: float | None

    @property
    def pct_study_grr(self) -> float:
        return float(self.components.loc["Total Gage R&R", "%Study Var"])

    @property
    def pct_contribution_grr(self) -> float:
        return float(self.components.loc["Total Gage R&R", "%Contribution"])

    @property
    def pct_tolerance_grr(self) -> float | None:
        if self.tolerance is None:
            return None
        return float(self.components.loc["Total Gage R&R", "%Tolerance"])

    @property
    def verdict(self) -> str:
        return grr_verdict(self.pct_study_grr)


def grr_verdict(pct: float) -> str:
    if pct < 10:
        return "Acceptable (< 10%)"
    if pct <= 30:
        return "Marginal (10-30%): may be acceptable depending on application and cost"
    return "Unacceptable (> 30%): improve the measurement system"


def _validate(df: pd.DataFrame, part: str, operator: str, measurement: str):
    d = df[[part, operator, measurement]].dropna().copy()
    d[measurement] = d[measurement].astype(float)
    counts = d.groupby([part, operator]).size()
    p = d[part].nunique()
    o = d[operator].nunique()
    if p < 2 or o < 1:
        raise ValueError("Need at least 2 parts and 1 operator")
    if len(counts) != p * o or counts.nunique() != 1:
        raise ValueError("Design must be balanced and crossed: every operator measures every part the same number of times")
    r = int(counts.iloc[0])
    if r < 2:
        raise ValueError("Need at least 2 trials (replicates) per part/operator")
    return d, p, o, r


def _components_table(var: dict, tolerance: float | None, k: float) -> pd.DataFrame:
    rows = ["Total Gage R&R", "  Repeatability", "  Reproducibility", "    Operator", "    Operator*Part",
            "Part-to-Part", "Total Variation"]
    v = pd.Series({
        "Total Gage R&R": var["repeat"] + var["oper"] + var["inter"],
        "  Repeatability": var["repeat"],
        "  Reproducibility": var["oper"] + var["inter"],
        "    Operator": var["oper"],
        "    Operator*Part": var["inter"],
        "Part-to-Part": var["part"],
    })
    v["Total Variation"] = v["Total Gage R&R"] + v["Part-to-Part"]
    t = pd.DataFrame({"VarComp": v[rows]})
    t["%Contribution"] = 100 * t["VarComp"] / v["Total Variation"]
    t["StdDev"] = np.sqrt(t["VarComp"])
    t[f"StudyVar ({k:g}*SD)"] = k * t["StdDev"]
    t["%Study Var"] = 100 * t["StdDev"] / t.loc["Total Variation", "StdDev"]
    if tolerance:
        t["%Tolerance"] = 100 * t[f"StudyVar ({k:g}*SD)"] / tolerance
    t.index = [i.strip() for i in t.index]  # indentation above only documents the hierarchy
    return t


def _ndc(sd_part: float, sd_grr: float) -> int:
    """Number of distinct categories = 1.41 * sigma_part / sigma_GRR, truncated (AIAG/Minitab), min 1."""
    if sd_grr <= 0:
        return 999
    return max(1, int(math.floor(1.41 * sd_part / sd_grr)))


def gage_rr_anova(df: pd.DataFrame, part: str, operator: str, measurement: str,
                  tolerance: float | None = None, alpha_interaction: float = 0.25,
                  study_multiplier: float = 6.0) -> GageResult:
    d, p, o, r = _validate(df, part, operator, measurement)
    y = d[measurement].to_numpy()
    grand = y.mean()
    part_means = d.groupby(part)[measurement].mean()
    oper_means = d.groupby(operator)[measurement].mean()
    cell_means = d.groupby([part, operator])[measurement].mean()

    ss_total = ((y - grand) ** 2).sum()
    ss_part = o * r * ((part_means - grand) ** 2).sum()
    ss_oper = p * r * ((oper_means - grand) ** 2).sum()
    ss_cells = r * ((cell_means - grand) ** 2).sum()
    ss_inter = ss_cells - ss_part - ss_oper
    ss_error = ss_total - ss_cells

    df_part, df_oper = p - 1, o - 1
    df_inter, df_error = df_part * df_oper, p * o * (r - 1)
    ms_part, ms_error = ss_part / df_part, ss_error / df_error
    ms_oper = ss_oper / df_oper if df_oper else float("nan")
    ms_inter = ss_inter / df_inter if df_inter else float("nan")

    # Full model: part and operator are tested against the interaction.
    if o > 1:
        f_part, f_oper, f_inter = ms_part / ms_inter, ms_oper / ms_inter, ms_inter / ms_error
        p_part = stats.f.sf(f_part, df_part, df_inter)
        p_oper = stats.f.sf(f_oper, df_oper, df_inter)
        p_inter = stats.f.sf(f_inter, df_inter, df_error)
        full = pd.DataFrame(
            {"DF": [df_part, df_oper, df_inter, df_error, p * o * r - 1],
             "SS": [ss_part, ss_oper, ss_inter, ss_error, ss_total],
             "MS": [ms_part, ms_oper, ms_inter, ms_error, np.nan],
             "F": [f_part, f_oper, f_inter, np.nan, np.nan],
             "P": [p_part, p_oper, p_inter, np.nan, np.nan]},
            index=["Part", "Operator", "Part*Operator", "Repeatability", "Total"])
    else:
        p_inter = 1.0
        f_part = ms_part / ms_error
        full = pd.DataFrame(
            {"DF": [df_part, df_error, p * r - 1], "SS": [ss_part, ss_error, ss_total],
             "MS": [ms_part, ms_error, np.nan], "F": [f_part, np.nan, np.nan],
             "P": [stats.f.sf(f_part, df_part, df_error), np.nan, np.nan]},
            index=["Part", "Repeatability", "Total"])

    pooled = o > 1 and p_inter > alpha_interaction
    if o == 1:
        var = {"repeat": ms_error, "oper": 0.0, "inter": 0.0, "part": max(0.0, (ms_part - ms_error) / r)}
        reduced = None
    elif pooled:
        df_pool = df_inter + df_error
        ms_pool = (ss_inter + ss_error) / df_pool
        f_part2, f_oper2 = ms_part / ms_pool, ms_oper / ms_pool
        reduced = pd.DataFrame(
            {"DF": [df_part, df_oper, df_pool, p * o * r - 1],
             "SS": [ss_part, ss_oper, ss_inter + ss_error, ss_total],
             "MS": [ms_part, ms_oper, ms_pool, np.nan],
             "F": [f_part2, f_oper2, np.nan, np.nan],
             "P": [stats.f.sf(f_part2, df_part, df_pool), stats.f.sf(f_oper2, df_oper, df_pool), np.nan, np.nan]},
            index=["Part", "Operator", "Repeatability", "Total"])
        var = {"repeat": ms_pool, "inter": 0.0,
               "oper": max(0.0, (ms_oper - ms_pool) / (p * r)),
               "part": max(0.0, (ms_part - ms_pool) / (o * r))}
    else:
        reduced = None
        var = {"repeat": ms_error,
               "inter": max(0.0, (ms_inter - ms_error) / r),
               "oper": max(0.0, (ms_oper - ms_inter) / (p * r)),
               "part": max(0.0, (ms_part - ms_inter) / (o * r))}

    comp = _components_table(var, tolerance, study_multiplier)
    ndc = _ndc(comp.loc["Part-to-Part", "StdDev"], comp.loc["Total Gage R&R", "StdDev"])
    return GageResult("ANOVA", reduced if pooled else full, full, pooled, comp, ndc, p, o, r, tolerance)


# AIAG MSA 4th ed. constants (1/d2* values), p. 118-119
_K1 = {2: 0.8862, 3: 0.5908}
_K2 = {2: 0.7071, 3: 0.5231}
_K3 = {2: 0.7071, 3: 0.5231, 4: 0.4467, 5: 0.4030, 6: 0.3742, 7: 0.3534, 8: 0.3375, 9: 0.3249, 10: 0.3146}


def gage_rr_average_range(df: pd.DataFrame, part: str, operator: str, measurement: str,
                          tolerance: float | None = None) -> GageResult:
    """AIAG average & range method (EV, AV, GRR, PV, TV with K1, K2, K3).

    Results are expressed as standard deviations; %Study Var = 100 * x / TV.
    """
    d, p, o, r = _validate(df, part, operator, measurement)
    if r not in _K1 or o not in _K2 or p not in _K3:
        raise ValueError("Average & range method constants available for 2-3 trials, 2-3 operators, 2-10 parts")
    cell = d.groupby([operator, part])[measurement]
    ranges = (cell.max() - cell.min())
    rbar_by_op = ranges.groupby(level=0).mean()
    rbarbar = rbar_by_op.mean()
    xbar_by_op = d.groupby(operator)[measurement].mean()
    x_diff = xbar_by_op.max() - xbar_by_op.min()
    part_means = d.groupby(part)[measurement].mean()
    rp = part_means.max() - part_means.min()

    ev = rbarbar * _K1[r]
    av = math.sqrt(max(0.0, (x_diff * _K2[o]) ** 2 - ev**2 / (p * r)))
    grr = math.hypot(ev, av)
    pv = rp * _K3[p]
    tv = math.hypot(grr, pv)

    var = {"repeat": ev**2, "oper": av**2, "inter": 0.0, "part": pv**2}
    comp = _components_table(var, tolerance, 6.0)
    comp = comp.drop(index="Operator*Part")
    ndc = _ndc(pv, grr)
    info = pd.DataFrame({"value": [rbarbar, x_diff, rp, ev, av, grr, pv, tv]},
                        index=["R-double-bar", "X-diff", "Rp", "EV", "AV", "GRR", "PV", "TV"])
    return GageResult("Average & Range (AIAG)", info, None, False, comp, ndc, p, o, r, tolerance)
