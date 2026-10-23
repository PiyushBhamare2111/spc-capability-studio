"""Capability indices and normality test."""

import numpy as np
import pytest
from scipy import stats

from spc.capability import anderson_darling, capability, capability_from_stats, sigma_within


def test_nist_handbook_6_1_6_example():
    # NIST/SEMATECH e-Handbook of Statistical Methods, 6.1.6 "What is Process
    # Capability?": USL = 20, LSL = 8, mean = 16, sigma = 2 ->
    # Cp = 1.0, Cpu = 0.6667, Cpl = 1.3333, Cpk = 0.6667.
    r = capability_from_stats(mean=16, sigma_within=2, lsl=8, usl=20)
    assert r.Cp == pytest.approx(1.0)
    assert r.Cpu == pytest.approx(0.6667, abs=1e-4)
    assert r.Cpl == pytest.approx(1.3333, abs=1e-4)
    assert r.Cpk == pytest.approx(0.6667, abs=1e-4)


def test_montgomery_flow_width_cp():
    # Montgomery, Intro to SQC, sec. 8.3 (hard-bake flow width): USL = 2.00,
    # LSL = 1.00, sigma-hat = R-bar/d2 = 0.32521/2.326 = 0.1398 -> Cp = 1.192.
    sigma = 0.32521 / 2.326
    r = capability_from_stats(mean=1.5056, sigma_within=sigma, lsl=1.0, usl=2.0)
    assert r.Cp == pytest.approx(1.192, abs=1e-3)


@pytest.mark.parametrize("cp,ppm", [(1.00, 2700), (1.33, 66), (1.50, 6.8)])
def test_centered_process_ppm_montgomery_table_8_4(cp, ppm):
    # Montgomery, Intro to SQC, Table 8.4: PCR vs. ppm defective for a centered,
    # normal process with two-sided specs.
    r = capability_from_stats(mean=0, sigma_within=1, lsl=-3 * cp, usl=3 * cp)
    assert r.ppm_within == pytest.approx(ppm, rel=0.06)


def test_one_sided_spec():
    r = capability_from_stats(mean=10, sigma_within=1, usl=14)
    assert r.Cp is None and r.Cpl is None
    assert r.Cpk == pytest.approx(4 / 3)


def test_within_vs_overall_with_shift():
    # Mean shift between subgroups inflates overall sigma, so Ppk < Cpk.
    rng = np.random.default_rng(3)
    x = rng.normal(0, 1, (30, 5)) + np.repeat(rng.normal(0, 1.5, 30), 5).reshape(30, 5)
    r = capability(x.ravel(), lsl=-8, usl=8, subgroup_size=5)
    assert r.sigma_overall > r.sigma_within
    assert r.Ppk < r.Cpk
    assert r.sigma_within == pytest.approx(np.ptp(x, axis=1).mean() / 2.326, rel=1e-3)


def test_sigma_within_methods():
    rng = np.random.default_rng(4)
    x = rng.normal(0, 2, 500)
    sub = x.reshape(100, 5)
    assert sigma_within(x, 5, "Sbar/c4") == pytest.approx(sub.std(axis=1, ddof=1).mean() / 0.9400, rel=1e-4)
    assert sigma_within(x, 1) == pytest.approx(np.abs(np.diff(x)).mean() / 1.128, rel=1e-3)
    for m in ("Rbar/d2", "Sbar/c4", "Pooled SD"):
        assert sigma_within(x, 5, m) == pytest.approx(2.0, rel=0.1)


def test_anderson_darling_statistic_matches_scipy():
    rng = np.random.default_rng(5)
    x = rng.normal(0, 1, 50)
    assert anderson_darling(x).ad_statistic == pytest.approx(stats.anderson(x, "norm", method="interpolate").statistic, rel=1e-6)


def test_anderson_darling_p_values():
    rng = np.random.default_rng(6)
    assert anderson_darling(rng.normal(0, 1, 100)).ad_p_value > 0.05
    assert anderson_darling(rng.exponential(1, 100)).ad_p_value < 0.005


def test_invalid_specs():
    with pytest.raises(ValueError):
        capability_from_stats(0, 1, lsl=5, usl=1)
    with pytest.raises(ValueError):
        capability_from_stats(0, 1)
