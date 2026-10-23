"""Control chart limits vs. textbook examples."""

import numpy as np
import pytest

from spc import charts
from spc.constants import get_constants
from tests.reference_data import ORANGE_JUICE_D, ORANGE_JUICE_N, PCB_C


def test_piston_ring_xbar_r_limits_montgomery_example_6_1():
    # Montgomery, Intro to SQC, Example 6.1 (piston ring inside diameter, n = 5):
    # X-double-bar = 74.001, R-bar = 0.023 -> X-bar UCL 74.014, LCL 73.988;
    # R chart UCL 0.049, LCL 0.
    c = get_constants(5)
    xbb, rbar = 74.001, 0.023
    assert xbb + c.A2 * rbar == pytest.approx(74.014, abs=5e-4)
    assert xbb - c.A2 * rbar == pytest.approx(73.988, abs=5e-4)
    assert c.D4 * rbar == pytest.approx(0.049, abs=5e-4)
    assert c.D3 * rbar == 0


def test_piston_ring_xbar_s_limits_montgomery_example_6_3():
    # Montgomery, Intro to SQC, Example 6.3: X-double-bar = 74.001, S-bar = 0.0094
    # -> X-bar UCL 74.014, LCL 73.988; S chart UCL 0.0196, LCL 0.
    c = get_constants(5)
    xbb, sbar = 74.001, 0.0094
    assert xbb + c.A3 * sbar == pytest.approx(74.014, abs=5e-4)
    assert xbb - c.A3 * sbar == pytest.approx(73.988, abs=5e-4)
    assert c.B4 * sbar == pytest.approx(0.0196, abs=1e-4)
    assert c.B3 * sbar == 0


def test_xbar_r_matches_hand_calculation_with_table_constants():
    rng = np.random.default_rng(1)
    x = rng.normal(10, 1, (20, 4))
    ch = charts.xbar_r(x)
    xbb, rbar = x.mean(), np.ptp(x, axis=1).mean()
    # n = 4: A2 = 0.729, D4 = 2.282, D3 = 0, d2 = 2.059 (Montgomery Appendix VI)
    assert ch.primary.ucl[0] == pytest.approx(xbb + 0.729 * rbar, rel=1e-3)
    assert ch.primary.lcl[0] == pytest.approx(xbb - 0.729 * rbar, rel=1e-3)
    assert ch.secondary.ucl[0] == pytest.approx(2.282 * rbar, rel=1e-3)
    assert ch.secondary.lcl[0] == 0
    assert ch.sigma_within == pytest.approx(rbar / 2.059, rel=1e-3)


def test_xbar_s_matches_hand_calculation():
    rng = np.random.default_rng(2)
    x = rng.normal(5, 0.2, (25, 10))
    ch = charts.xbar_s(x)
    sbar = x.std(axis=1, ddof=1).mean()
    # n = 10: A3 = 0.975, B3 = 0.284, B4 = 1.716, c4 = 0.9727
    assert ch.primary.ucl[0] - x.mean() == pytest.approx(0.975 * sbar, rel=1e-3)
    assert ch.secondary.ucl[0] == pytest.approx(1.716 * sbar, rel=1e-3)
    assert ch.secondary.lcl[0] == pytest.approx(0.284 * sbar, rel=3e-3)
    assert ch.sigma_within == pytest.approx(sbar / 0.9727, rel=1e-4)


def test_imr_small_hand_example():
    # Hand calculation: x = 10, 12, 11, 15, 13 -> MR = 2, 1, 4, 2; MR-bar = 2.25.
    # I chart: 12.2 +/- 2.66 * 2.25 (2.66 = 3/d2, d2 = 1.128); MR UCL = 3.267 * 2.25.
    ch = charts.imr([10, 12, 11, 15, 13])
    assert ch.primary.cl[0] == pytest.approx(12.2)
    assert ch.primary.ucl[0] == pytest.approx(12.2 + 2.66 * 2.25, abs=5e-3)
    assert ch.primary.lcl[0] == pytest.approx(12.2 - 2.66 * 2.25, abs=5e-3)
    assert ch.secondary.cl[0] == pytest.approx(2.25)
    assert ch.secondary.ucl[0] == pytest.approx(3.267 * 2.25, abs=5e-3)
    assert list(ch.secondary.labels) == [2, 3, 4, 5]


def test_p_chart_orange_juice_montgomery_example_7_1():
    # Montgomery Example 7.1: p-bar = 0.2313, UCL = 0.4102, LCL = 0.0524,
    # samples 15 and 23 above UCL.
    ch = charts.p_chart(ORANGE_JUICE_D, ORANGE_JUICE_N)
    assert ch.primary.cl[0] == pytest.approx(0.2313, abs=1e-4)
    assert ch.primary.ucl[0] == pytest.approx(0.4102, abs=1e-4)
    assert ch.primary.lcl[0] == pytest.approx(0.0524, abs=1e-4)
    assert list(np.flatnonzero(ch.primary.beyond_limits) + 1) == [15, 23]


def test_np_chart_orange_juice():
    # Same data as an np chart: CL = n p-bar = 11.57, limits = 50 x (0.4102, 0.0524)
    ch = charts.np_chart(ORANGE_JUICE_D, ORANGE_JUICE_N)
    assert ch.primary.cl[0] == pytest.approx(50 * 0.23133, abs=1e-2)
    assert ch.primary.ucl[0] == pytest.approx(50 * 0.4102, abs=1e-2)
    assert ch.primary.lcl[0] == pytest.approx(50 * 0.0524, abs=1e-2)


def test_c_chart_pcb_montgomery_example_7_3():
    # Montgomery Example 7.3: c-bar = 19.85, UCL = 33.22, LCL = 6.48; samples 6 and 20 out.
    ch = charts.c_chart(PCB_C)
    assert ch.primary.cl[0] == pytest.approx(19.85, abs=5e-3)
    # The book rounds c-bar to 19.85 before computing 19.85 +/- 3*sqrt(19.85);
    # with the unrounded c-bar = 516/26 the limits are 33.211 and 6.481.
    assert ch.primary.ucl[0] == pytest.approx(33.22, abs=1e-2)
    assert ch.primary.lcl[0] == pytest.approx(6.48, abs=1e-2)
    assert list(np.flatnonzero(ch.primary.beyond_limits) + 1) == [6, 20]


def test_u_chart_variable_sample_size():
    # u-bar = sum(c)/sum(n); limits u-bar +/- 3 sqrt(u-bar / n_i) (Montgomery sec. 7.3)
    c = [10, 12, 8, 15]
    n = [5, 6, 4, 5]
    ch = charts.u_chart(c, n)
    ubar = 45 / 20
    assert ch.primary.cl[0] == pytest.approx(ubar)
    assert ch.primary.ucl[1] == pytest.approx(ubar + 3 * np.sqrt(ubar / 6))
    assert ch.primary.lcl[2] == pytest.approx(max(0, ubar - 3 * np.sqrt(ubar / 4)))


def test_p_chart_variable_n_limits_vary():
    ch = charts.p_chart([5, 10, 3], [100, 200, 50])
    assert ch.primary.cl[0] == pytest.approx(18 / 350)
    assert ch.primary.ucl[1] < ch.primary.ucl[0] < ch.primary.ucl[2]


def test_subgroups_from_long():
    v = np.arange(12.0)
    assert charts.subgroups_from_long(v, subgroup_size=5).shape == (2, 5)
    ids = np.repeat([1, 2, 3], 4)
    assert charts.subgroups_from_long(v, subgroup_ids=ids).shape == (3, 4)
    with pytest.raises(ValueError):
        charts.subgroups_from_long(v, subgroup_ids=[1] * 5 + [2] * 7)
