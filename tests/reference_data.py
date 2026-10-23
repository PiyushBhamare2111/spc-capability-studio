"""Published reference datasets used by the tests.

Each dataset carries its source. They are kept here (not loaded from data/)
so the tests do not depend on the sample files shipped with the app.
"""

# Montgomery, D. C., Introduction to Statistical Quality Control (6th/7th ed.),
# Example 7.1, Table 7.1: frozen orange juice concentrate cans, 30 samples of
# n = 50, number of nonconforming cans. Book results: p-bar = 0.2313,
# UCL = 0.4102, LCL = 0.0524; samples 15 and 23 plot above the UCL.
ORANGE_JUICE_D = [12, 15, 8, 10, 4, 7, 16, 9, 14, 10, 5, 6, 17, 12, 22,
                  8, 10, 5, 13, 11, 20, 18, 24, 15, 9, 12, 7, 13, 9, 6]
ORANGE_JUICE_N = 50

# Montgomery, Introduction to Statistical Quality Control, Example 7.3,
# Table 7.7: nonconformities in 26 successive samples of 100 printed circuit
# boards. Book results: c-bar = 19.85, UCL = 33.22, LCL = 6.48; samples 6
# and 20 are outside the limits.
PCB_C = [21, 24, 16, 12, 15, 5, 28, 20, 31, 25, 20, 24, 16, 19, 10, 17, 13,
         22, 18, 39, 30, 24, 16, 19, 17, 15]

# AIAG, Measurement Systems Analysis Reference Manual, 4th ed. (2010),
# worked GRR example: 10 parts x 3 appraisers (A, B, C) x 3 trials.
# AIAG_GRR[appraiser][trial] -> list of 10 part readings.
AIAG_GRR = {
    "A": [[0.29, -0.56, 1.34, 0.47, -0.80, 0.02, 0.59, -0.31, 2.26, -1.36],
          [0.41, -0.68, 1.17, 0.50, -0.92, -0.11, 0.75, -0.20, 1.99, -1.25],
          [0.64, -0.58, 1.27, 0.64, -0.84, -0.21, 0.66, -0.17, 2.01, -1.31]],
    "B": [[0.08, -0.47, 1.19, 0.01, -0.56, -0.20, 0.47, -0.63, 1.80, -1.68],
          [0.25, -1.22, 0.94, 1.03, -1.20, 0.22, 0.55, 0.08, 2.12, -1.62],
          [0.07, -0.68, 1.34, 0.20, -1.28, 0.06, 0.83, -0.34, 2.19, -1.50]],
    "C": [[0.04, -1.38, 0.88, 0.14, -1.46, -0.29, 0.02, -0.46, 1.77, -1.49],
          [-0.11, -1.13, 1.09, 0.20, -1.07, -0.67, 0.01, -0.56, 1.45, -1.77],
          [-0.15, -0.96, 0.67, 0.11, -1.45, -0.49, 0.21, -0.49, 1.87, -2.16]],
}


def aiag_frame():
    import pandas as pd

    rows = [{"part": p + 1, "operator": op, "trial": t + 1, "y": trials[t][p]}
            for op, trials in AIAG_GRR.items() for t in range(3) for p in range(10)]
    return pd.DataFrame(rows)
