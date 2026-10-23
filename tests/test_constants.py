"""Control chart constants vs. the published table.

Reference: Montgomery, D. C., Introduction to Statistical Quality Control,
Appendix Table VI "Factors for Constructing Variables Control Charts"
(identical values in ASTM E2587 and the NIST/SEMATECH e-Handbook 6.3.2).
"""

import pytest

from spc.constants import MAX_N, MIN_N, d2_numeric, get_constants

# n: (A2, A3, c4, B3, B4, d2, D3, D4) - Montgomery Appendix VI
TABLE = {
    2: (1.880, 2.659, 0.7979, 0.000, 3.267, 1.128, 0.000, 3.267),
    3: (1.023, 1.954, 0.8862, 0.000, 2.568, 1.693, 0.000, 2.574),
    4: (0.729, 1.628, 0.9213, 0.000, 2.266, 2.059, 0.000, 2.282),
    5: (0.577, 1.427, 0.9400, 0.000, 2.089, 2.326, 0.000, 2.114),
    6: (0.483, 1.287, 0.9515, 0.030, 1.970, 2.534, 0.000, 2.004),
    7: (0.419, 1.182, 0.9594, 0.118, 1.882, 2.704, 0.076, 1.924),
    8: (0.373, 1.099, 0.9650, 0.185, 1.815, 2.847, 0.136, 1.864),
    10: (0.308, 0.975, 0.9727, 0.284, 1.716, 3.078, 0.223, 1.777),
    15: (0.223, 0.789, 0.9823, 0.428, 1.572, 3.472, 0.347, 1.653),
    20: (0.180, 0.680, 0.9869, 0.510, 1.490, 3.735, 0.415, 1.585),
    25: (0.153, 0.606, 0.9896, 0.565, 1.435, 3.931, 0.459, 1.541),
}


@pytest.mark.parametrize("n", sorted(TABLE))
def test_constants_match_montgomery_table(n):
    a2, a3, c4, b3, b4, d2, d3f, d4 = TABLE[n]
    c = get_constants(n)
    # Table values are rounded to 3-4 decimals; derived factors may differ by 1-2 in the last digit.
    assert c.A2 == pytest.approx(a2, abs=2e-3)
    assert c.A3 == pytest.approx(a3, abs=2e-3)
    assert c.c4 == pytest.approx(c4, abs=1e-4)
    assert c.B3 == pytest.approx(b3, abs=2e-3)
    assert c.B4 == pytest.approx(b4, abs=2e-3)
    assert c.d2 == pytest.approx(d2, abs=1e-3)
    assert c.D3 == pytest.approx(d3f, abs=2e-3)
    assert c.D4 == pytest.approx(d4, abs=2e-3)


@pytest.mark.parametrize("n", range(MIN_N, MAX_N + 1))
def test_tabulated_d2_agrees_with_numerical_integration(n):
    # d2(n) = E[range of n iid N(0,1)] computed independently by quadrature.
    assert get_constants(n).d2 == pytest.approx(d2_numeric(n), abs=6e-4)


def test_out_of_range_subgroup_size():
    with pytest.raises(ValueError):
        get_constants(1)
    with pytest.raises(ValueError):
        get_constants(26)
