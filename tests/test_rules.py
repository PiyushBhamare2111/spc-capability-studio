"""Nelson / Western Electric run rules on constructed sequences.

Rule definitions: Nelson, L. S. (1984) J. Quality Technology 16(4):237-239,
as implemented in Minitab "Tests for special causes" 1-8.
Chart: CL = 0, sigma = 1 (UCL = 3, LCL = -3).
"""

import numpy as np

from spc.charts import ChartSeries
from spc.rules import evaluate


def series(vals):
    return ChartSeries("X", np.asarray(vals, float), 0.0, 3.0, -3.0)


def flagged(vals, rule, **kw):
    return [v.index for v in evaluate(series(vals), rules=[rule], **kw)]


def test_rule1_beyond_3_sigma():
    assert flagged([0, 1, 3.5, 0, -3.2], 1) == [2, 4]


def test_rule2_nine_same_side():
    vals = [-0.5] + [0.2] * 9 + [-0.1]
    assert flagged(vals, 2) == [9]
    assert flagged(vals, 2, run_length=8) == [8, 9]  # Western Electric uses 8


def test_rule3_six_trending():
    assert flagged([0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.4], 3) == [5]
    assert flagged([0, 0.1, 0.2, 0.3, 0.4, 0.3], 3) == []  # only 5 points trending


def test_rule4_fourteen_alternating():
    alt = [(-1) ** i * 0.5 for i in range(14)]
    assert flagged(alt, 4) == [13]
    assert flagged(alt[:13], 4) == []


def test_rule5_two_of_three_beyond_2_sigma():
    assert flagged([0, 2.5, 0.1, 2.2], 5) == [3]
    assert flagged([0, 2.5, 0.1, -2.2], 5) == []  # opposite sides do not count


def test_rule6_four_of_five_beyond_1_sigma():
    assert flagged([1.5, 1.2, 0.0, 1.7, 1.1], 6) == [4]
    assert flagged([1.5, 1.2, 0.0, 0.5, 1.1], 6) == []


def test_rule7_fifteen_within_1_sigma():
    vals = [0.3, -0.3] * 8  # 16 points hugging the center line
    assert flagged(vals, 7) == [14, 15]


def test_rule8_eight_beyond_1_sigma_either_side():
    vals = [1.5, -1.5] * 4
    assert flagged(vals, 8) == [7]


def test_in_control_noise_has_few_alarms():
    rng = np.random.default_rng(0)
    v = evaluate(series(rng.normal(0, 1, 200)), rules=[1])
    assert len(v) <= 3  # ~0.27% false alarm rate for rule 1
