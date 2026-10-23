"""Gage R&R vs. the AIAG MSA 4th edition worked example.

Data: AIAG Measurement Systems Analysis Reference Manual, 4th ed. (2010),
10 parts x 3 appraisers x 3 trials (see tests/reference_data.py).
"""

import numpy as np
import pandas as pd
import pytest

from spc.gage import gage_rr_anova, gage_rr_average_range, grr_verdict
from tests.reference_data import aiag_frame


@pytest.fixture(scope="module")
def df():
    return aiag_frame()


def test_aiag_average_and_range_method(df):
    # AIAG MSA 4th ed., Gage Repeatability and Reproducibility Report (Fig. III-B 16):
    # R-double-bar = 0.3417, X-diff = 0.4447, Rp = 3.511,
    # EV = 0.20188, AV = 0.22963, GRR = 0.30575, PV = 1.10456, TV = 1.14610,
    # %EV = 17.62, %AV = 20.04, %GRR = 26.68, %PV = 96.38, ndc = 5.
    # (AIAG works with the rounded intermediate values, hence the tolerances.)
    r = gage_rr_average_range(df, "part", "operator", "y")
    v = r.anova["value"]
    assert v["R-double-bar"] == pytest.approx(0.3417, abs=1e-4)
    assert v["X-diff"] == pytest.approx(0.4447, abs=1e-4)
    assert v["Rp"] == pytest.approx(3.511, abs=1e-3)
    assert v["EV"] == pytest.approx(0.20188, abs=1e-4)
    assert v["AV"] == pytest.approx(0.22963, abs=1e-4)
    assert v["GRR"] == pytest.approx(0.30575, abs=1e-4)
    assert v["PV"] == pytest.approx(1.10456, abs=1e-4)
    assert v["TV"] == pytest.approx(1.14610, abs=1e-4)
    c = r.components["%Study Var"]
    assert c["Repeatability"] == pytest.approx(17.62, abs=0.02)
    assert c["Reproducibility"] == pytest.approx(20.04, abs=0.02)
    assert c["Total Gage R&R"] == pytest.approx(26.68, abs=0.02)
    assert c["Part-to-Part"] == pytest.approx(96.38, abs=0.02)
    assert r.ndc == 5


def test_aiag_anova_table(df):
    # AIAG MSA 4th ed., ANOVA table for the same study (Table III-B 12):
    # SS appraiser 3.1673 (df 2), parts 88.3619 (9), appraiser*part 0.3590 (18),
    # equipment 2.7589 (60), total 94.6471 (89); F appraiser 79.41, F interaction 0.434.
    r = gage_rr_anova(df, "part", "operator", "y")
    a = r.anova_full
    assert a.loc["Operator", "SS"] == pytest.approx(3.1673, abs=1e-4)
    assert a.loc["Part", "SS"] == pytest.approx(88.3619, abs=1e-4)
    assert a.loc["Part*Operator", "SS"] == pytest.approx(0.3590, abs=1e-4)
    assert a.loc["Repeatability", "SS"] == pytest.approx(2.7589, abs=1e-4)
    assert a.loc["Total", "SS"] == pytest.approx(94.6471, abs=1e-4)
    assert list(a["DF"]) == [9, 2, 18, 60, 89]
    assert a.loc["Operator", "F"] == pytest.approx(79.41, abs=0.01)
    assert a.loc["Part*Operator", "F"] == pytest.approx(0.434, abs=1e-3)


def test_aiag_anova_variance_components(df):
    # AIAG MSA 4th ed., ANOVA method results (Table III-B 13), interaction not
    # significant and pooled: EV = 0.199, AV = 0.227, INT = 0, GRR = 0.302,
    # PV = 1.04233, %GRR = 27.86, ndc = 4.
    r = gage_rr_anova(df, "part", "operator", "y")
    assert r.interaction_pooled
    sd = r.components["StdDev"]
    assert sd["Repeatability"] == pytest.approx(0.199, abs=1e-3)
    assert sd["Reproducibility"] == pytest.approx(0.227, abs=1e-3)
    assert sd["Operator*Part"] == 0
    assert sd["Total Gage R&R"] == pytest.approx(0.302, abs=1e-3)
    assert sd["Part-to-Part"] == pytest.approx(1.04233, abs=1e-4)
    assert r.pct_study_grr == pytest.approx(27.86, abs=0.01)
    assert r.ndc == 4
    assert r.verdict.startswith("Marginal")


def test_percent_tolerance_and_contribution(df):
    r = gage_rr_anova(df, "part", "operator", "y", tolerance=10.0)
    comp = r.components
    assert r.pct_tolerance_grr == pytest.approx(100 * 6 * comp.loc["Total Gage R&R", "StdDev"] / 10.0)
    assert comp.loc["Total Variation", "%Contribution"] == pytest.approx(100)
    assert comp.loc["Total Gage R&R", "%Contribution"] + comp.loc["Part-to-Part", "%Contribution"] == pytest.approx(100)


def test_significant_interaction_is_kept():
    # Construct data with a strong operator*part effect: interaction must not be pooled.
    rng = np.random.default_rng(7)
    rows = []
    for p in range(8):
        for o in range(3):
            effect = 0.8 * ((p * (o + 1)) % 3 - 1)
            for t in range(3):
                rows.append({"part": p, "op": o, "y": p + effect + rng.normal(0, 0.05)})
    r = gage_rr_anova(pd.DataFrame(rows), "part", "op", "y")
    assert not r.interaction_pooled
    assert r.components.loc["Operator*Part", "VarComp"] > 0


def test_unbalanced_design_rejected(df):
    with pytest.raises(ValueError):
        gage_rr_anova(df.iloc[1:], "part", "operator", "y")


@pytest.mark.parametrize("pct,word", [(5, "Acceptable"), (20, "Marginal"), (35, "Unacceptable")])
def test_verdict_thresholds(pct, word):
    assert grr_verdict(pct).startswith(word)
