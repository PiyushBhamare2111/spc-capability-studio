"""Run rules for detecting out-of-control (special-cause) patterns.

The eight Nelson rules (L. S. Nelson, "The Shewhart Control Chart - Tests for
Special Causes", J. Quality Technology 16(4), 1984), which are also Minitab's
"Tests 1-8". The Western Electric rules (WECO *Statistical Quality Control
Handbook*, 1956) are the subset 1, 5, 6 plus "8 in a row on one side".

Zones are measured in units of sigma = (UCL - CL) / 3 for each point. As in
Minitab, a violation is flagged on the point that *completes* the pattern.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .charts import ChartSeries

NELSON_RULES = {
    1: "1 point more than 3 sigma from the center line",
    2: "{run} points in a row on the same side of the center line",
    3: "6 points in a row steadily increasing or decreasing",
    4: "14 points in a row alternating up and down",
    5: "2 out of 3 points more than 2 sigma from the center line (same side)",
    6: "4 out of 5 points more than 1 sigma from the center line (same side)",
    7: "15 points in a row within 1 sigma of the center line (either side)",
    8: "8 points in a row more than 1 sigma from the center line (either side)",
}

RULE_SETS = {
    "Nelson (all 8 rules)": {"rules": [1, 2, 3, 4, 5, 6, 7, 8], "run": 9},
    "Western Electric (4 rules)": {"rules": [1, 2, 5, 6], "run": 8},
    "Limits only (rule 1)": {"rules": [1], "run": 9},
}


@dataclass
class Violation:
    index: int  # 0-based position in the series
    label: object  # point label (subgroup number)
    rule: int
    description: str
    value: float


def _window_flags(cond: np.ndarray, window: int, need: int) -> np.ndarray:
    """flag[i] = at least `need` of cond[i-window+1 .. i] are True (and cond[i] itself)."""
    out = np.zeros(len(cond), dtype=bool)
    c = cond.astype(int)
    for i in range(window - 1, len(cond)):
        if cond[i] and c[i - window + 1 : i + 1].sum() >= need:
            out[i] = True
    return out


def _run_flags(cond: np.ndarray, run: int) -> np.ndarray:
    """flag[i] = cond holds for the `run` consecutive points ending at i."""
    out = np.zeros(len(cond), dtype=bool)
    count = 0
    for i, c in enumerate(cond):
        count = count + 1 if c else 0
        if count >= run:
            out[i] = True
    return out


def evaluate(series: ChartSeries, rules=(1, 2, 3, 4, 5, 6, 7, 8), run_length: int = 9) -> list[Violation]:
    """Apply the selected rules to a chart series and return every violation."""
    x = series.values
    cl = series.cl
    sig = series.sigma
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(sig > 0, (x - cl) / sig, 0.0)
    n = len(x)
    flags: dict[int, np.ndarray] = {}

    if 1 in rules:
        flags[1] = series.beyond_limits
    if 2 in rules:
        flags[2] = _run_flags(z > 0, run_length) | _run_flags(z < 0, run_length)
    if 3 in rules:
        d = np.diff(x)
        up = np.concatenate([[False], d > 0])
        down = np.concatenate([[False], d < 0])
        flags[3] = _run_flags(up, 5) | _run_flags(down, 5)  # 5 moves = 6 points
    if 4 in rules:
        d = np.diff(x)
        alt = np.zeros(n, dtype=bool)
        if n >= 3:
            alt[2:] = (d[1:] * d[:-1]) < 0
        flags[4] = _run_flags(alt, 12)  # 12 sign changes = 13 moves = 14 points
    if 5 in rules:
        flags[5] = _window_flags(z > 2, 3, 2) | _window_flags(z < -2, 3, 2)
    if 6 in rules:
        flags[6] = _window_flags(z > 1, 5, 4) | _window_flags(z < -1, 5, 4)
    if 7 in rules:
        flags[7] = _run_flags(np.abs(z) < 1, 15)
    if 8 in rules:
        flags[8] = _run_flags(np.abs(z) > 1, 8)

    out = []
    for rule in sorted(flags):
        desc = NELSON_RULES[rule].format(run=run_length)
        for i in np.flatnonzero(flags[rule]):
            out.append(Violation(int(i), series.labels[i], rule, desc, float(x[i])))
    return out


def violations_frame(violations: list[Violation], chart_name: str = "") -> pd.DataFrame:
    rows = [
        {"chart": chart_name, "point": v.label, "value": v.value, "rule": v.rule, "description": v.description}
        for v in violations
    ]
    return pd.DataFrame(rows, columns=["chart", "point", "value", "rule", "description"])
