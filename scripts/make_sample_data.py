"""Regenerate the sample CSV files in data/ (deterministic, seeded).

Two files reproduce small, widely published textbook datasets so users can
compare the app with the book; the rest are synthetic (seeded) process data.

    python scripts/make_sample_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"
DATA.mkdir(exist_ok=True)
rng = np.random.default_rng(2111)

# 1) Shaft diameter, 25 subgroups of 5 (synthetic). Specs 25.000 +/- 0.015 mm.
#    A +0.007 mm mean shift is injected in subgroups 18-22 (e.g. a worn tool).
rows = []
for g in range(1, 26):
    shift = 0.007 if 18 <= g <= 22 else 0.0
    for j, v in enumerate(rng.normal(25.000 + shift, 0.004, 5), start=1):
        rows.append({"subgroup": g, "sample": j, "diameter_mm": round(v, 4)})
pd.DataFrame(rows).to_csv(DATA / "shaft_diameter_subgroups.csv", index=False)

# 2) Tablet weight, 60 individual readings (synthetic). Spec 250 mg +/- 5%.
#    A slow upward drift starts at observation 41.
x = rng.normal(250.0, 3.0, 60)
x[40:] += np.linspace(0, 6, 20)
pd.DataFrame({"tablet": np.arange(1, 61), "weight_mg": x.round(2)}).to_csv(
    DATA / "tablet_weight_individuals.csv", index=False)

# 3) Orange juice can seals: 30 samples of n = 50, number nonconforming.
#    Montgomery, Introduction to Statistical Quality Control, Example 7.1 / Table 7.1.
oj = [12, 15, 8, 10, 4, 7, 16, 9, 14, 10, 5, 6, 17, 12, 22, 8, 10, 5, 13, 11, 20, 18, 24, 15, 9, 12, 7, 13, 9, 6]
pd.DataFrame({"sample": np.arange(1, 31), "nonconforming": oj, "sample_size": 50}).to_csv(
    DATA / "orange_juice_cans_p.csv", index=False)

# 4) Printed circuit boards: nonconformities in 26 samples of 100 boards.
#    Montgomery, Introduction to Statistical Quality Control, Example 7.3 / Table 7.7.
pcb = [21, 24, 16, 12, 15, 5, 28, 20, 31, 25, 20, 24, 16, 19, 10, 17, 13, 22, 18, 39, 30, 24, 16, 19, 17, 15]
pd.DataFrame({"sample": np.arange(1, 27), "nonconformities": pcb}).to_csv(
    DATA / "pcb_nonconformities_c.csv", index=False)

# 5) Coating defects with varying inspected area (synthetic) for the u chart.
units = rng.integers(8, 16, 25)
defects = rng.poisson(1.4 * units)
defects[19] += 14
pd.DataFrame({"lot": np.arange(1, 26), "defects": defects, "units_inspected": units}).to_csv(
    DATA / "coating_defects_u.csv", index=False)

# 6) Gage R&R: 10 parts x 3 appraisers x 3 trials.
#    AIAG Measurement Systems Analysis Reference Manual, 4th ed. (2010), the
#    worked GRR example (data sheet Fig. III-B 15). Values are deviations from nominal.
aiag = {
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
rows = [{"part": p + 1, "operator": op, "trial": t + 1, "measurement": trials[t][p]}
        for op, trials in aiag.items() for t in range(3) for p in range(10)]
pd.DataFrame(rows).to_csv(DATA / "gage_rr_aiag.csv", index=False)

print("Wrote:", ", ".join(sorted(f.name for f in DATA.glob("*.csv"))))
