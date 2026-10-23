"""SPC & Capability Studio - Streamlit front end.

All statistics live in the ``spc`` package; this file only handles input,
layout and downloads.  Run with:  streamlit run app.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from spc import charts, rules
from spc.capability import SIGMA_METHODS, capability, capability_verdict
from spc.constants import get_constants
from spc.gage import gage_rr_anova, gage_rr_average_range
from spc.plots import capability_figure, control_chart_figure, gage_figures
from spc.report import Report

DATA_DIR = Path(__file__).parent / "data"

SAMPLES = {
    "shaft_diameter_subgroups.csv": "Shaft diameter - 25 subgroups of 5 (synthetic, mean shift injected)",
    "tablet_weight_individuals.csv": "Tablet weight - 60 individuals (synthetic, drift at the end)",
    "orange_juice_cans_p.csv": "Orange juice cans - nonconforming (Montgomery Ex. 7.1)",
    "pcb_nonconformities_c.csv": "PCB nonconformities (Montgomery Ex. 7.3)",
    "coating_defects_u.csv": "Coating defects with varying inspected units (synthetic)",
    "gage_rr_aiag.csv": "Gage R&R 10 parts x 3 operators x 3 trials (AIAG MSA 4th ed.)",
}
UPLOAD = "Upload your own CSV..."

CHART_TYPES = {
    "X̄-R (subgroups, n = 2-10)": "xbar_r",
    "X̄-S (subgroups, n > 10 or any n)": "xbar_s",
    "I-MR (individuals)": "imr",
    "p (fraction defective)": "p",
    "np (number defective)": "np",
    "c (defects per unit, constant area)": "c",
    "u (defects per unit, varying area)": "u",
}
DEFAULT_SAMPLE = {"xbar_r": "shaft_diameter_subgroups.csv", "xbar_s": "shaft_diameter_subgroups.csv",
                  "imr": "tablet_weight_individuals.csv", "p": "orange_juice_cans_p.csv",
                  "np": "orange_juice_cans_p.csv", "c": "pcb_nonconformities_c.csv", "u": "coating_defects_u.csv"}
SPEC_DEFAULTS = {"shaft_diameter_subgroups.csv": (24.985, 25.015, 25.0),
                 "tablet_weight_individuals.csv": (237.5, 262.5, 250.0)}


# ----------------------------------------------------------------- helpers
@st.cache_data
def load_sample(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / name)


def pick_data(key: str, default: str) -> tuple[pd.DataFrame | None, str]:
    options = list(SAMPLES) + [UPLOAD]
    choice = st.selectbox("Dataset", options, index=options.index(default), key=f"{key}_ds",
                          format_func=lambda o: SAMPLES.get(o, o))
    if choice == UPLOAD:
        up = st.file_uploader("CSV file (one observation per row, with a header row)", type=["csv"], key=f"{key}_up")
        if up is None:
            st.info("Upload a CSV to continue, or pick one of the sample datasets.")
            return None, ""
        return pd.read_csv(up), up.name
    return load_sample(choice), choice


def guess(cols, *names, numeric_df: pd.DataFrame | None = None, offset: int = 0) -> int:
    lower = [c.lower() for c in cols]
    for n in names:
        for i, c in enumerate(lower):
            if n in c:
                return i
    if numeric_df is not None:
        num = [i for i, c in enumerate(cols) if pd.api.types.is_numeric_dtype(numeric_df[c])]
        if num:
            return num[min(offset, len(num) - 1)]
    return 0


def fmt(v, d=4):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "-"
    return f"{v:.{d}f}"


def download_buttons(report: Report, csv_df: pd.DataFrame, stem: str):
    c1, c2 = st.columns(2)
    c1.download_button("⬇ HTML report", report.to_html(), file_name=f"{stem}_report.html", mime="text/html",
                       width="stretch")
    c2.download_button("⬇ CSV data + flags", csv_df.to_csv(index=False), file_name=f"{stem}_points.csv",
                       mime="text/csv", width="stretch")


# ------------------------------------------------------------ control charts
def page_control_charts():
    st.header("Control charts")
    left, right = st.columns([1, 3])
    with left:
        label = st.selectbox("Chart type", list(CHART_TYPES), key="cc_type")
        kind = CHART_TYPES[label]
        df, name = pick_data("cc", DEFAULT_SAMPLE[kind])
        if df is None:
            return
        cols = list(df.columns)
        if kind in ("xbar_r", "xbar_s", "imr"):
            meas = st.selectbox("Measurement column", cols, index=guess(cols, "diameter", "weight", "value",
                                                                         "measure", numeric_df=df, offset=1))
            if kind != "imr":
                mode = st.radio("Subgroups defined by", ["ID column", "Fixed size (consecutive rows)"], key="cc_mode")
                if mode == "ID column":
                    sg_col = st.selectbox("Subgroup ID column", cols, index=guess(cols, "subgroup", "batch", "lot"))
                    size = None
                else:
                    sg_col = None
                    size = st.number_input("Subgroup size", 2, 25, 5)
        elif kind in ("p", "np"):
            dcol = st.selectbox("Defectives column", cols, index=guess(cols, "nonconform", "defect", numeric_df=df, offset=1))
            ncol = st.selectbox("Sample size column", cols, index=guess(cols, "size", "n_", numeric_df=df, offset=2))
        else:
            ccol = st.selectbox("Defect count column", cols, index=guess(cols, "nonconform", "defect", "count",
                                                                          numeric_df=df, offset=1))
            if kind == "u":
                ucol = st.selectbox("Units inspected column", cols, index=guess(cols, "unit", "area", numeric_df=df, offset=2))
        rs_name = st.selectbox("Run rules", list(rules.RULE_SETS), key="cc_rules")
        rs = rules.RULE_SETS[rs_name]
        sel = st.multiselect("Rules applied", list(rules.NELSON_RULES), default=rs["rules"], key=f"cc_sel_{rs_name}",
                             format_func=lambda r: f"Rule {r}")

    try:
        if kind in ("xbar_r", "xbar_s"):
            sub = charts.subgroups_from_long(df[meas], df[sg_col] if sg_col else None, size)
            chart = (charts.xbar_r if kind == "xbar_r" else charts.xbar_s)(sub)
        elif kind == "imr":
            chart = charts.imr(df[meas])
        elif kind == "p":
            chart = charts.p_chart(df[dcol], df[ncol])
        elif kind == "np":
            n = df[ncol].iloc[0]
            if not (df[ncol] == n).all():
                st.warning("Sample size varies - np chart assumes constant n; using the p chart is recommended.")
            chart = charts.np_chart(df[dcol], int(n))
        elif kind == "c":
            chart = charts.c_chart(df[ccol])
        else:
            chart = charts.u_chart(df[ccol], df[ucol])
    except (ValueError, KeyError, TypeError) as e:
        right.error(f"Could not build the chart: {e}")
        return

    viol = {chart.primary.title: rules.evaluate(chart.primary, sel, rs["run"])}
    if chart.secondary is not None:  # dispersion charts: limits test only (zones are not symmetric)
        viol[chart.secondary.title] = rules.evaluate(chart.secondary, [1])
    vdf = pd.concat([rules.violations_frame(v, k) for k, v in viol.items()], ignore_index=True)

    with right:
        p = chart.primary
        m = st.columns(4)
        m[0].metric("Center line", fmt(p.cl[0]))
        m[1].metric("UCL", fmt(p.ucl[0]) + (" (varies)" if not np.allclose(p.ucl, p.ucl[0]) else ""))
        m[2].metric("LCL", fmt(p.lcl[0]) + (" (varies)" if not np.allclose(p.lcl, p.lcl[0]) else ""))
        npts = vdf["point"].nunique() if len(vdf) else 0
        m[3].metric("Signals", f"{len(vdf)} on {npts} pts")
        fig = control_chart_figure(chart, viol, title=f"{chart.kind} chart - {name}")
        st.plotly_chart(fig, width="stretch", theme=None)
        if len(vdf):
            st.subheader("Out-of-control signals")
            st.dataframe(vdf, width="stretch", hide_index=True)
        else:
            st.success("No rule violations - the process looks in statistical control.")
        with st.expander("Calculation details"):
            st.json({k: (round(v, 6) if isinstance(v, float) else v) for k, v in chart.info.items()})
            if chart.sigma_within:
                st.write(f"Within-subgroup sigma implied by the chart: **{chart.sigma_within:.5g}**")

        points = []
        for s in chart.series:
            flags = {}
            for v in viol.get(s.title, []):
                flags.setdefault(v.index, []).append(str(v.rule))
            for i in range(len(s.values)):
                points.append({"chart": s.title, "point": s.labels[i], "value": s.values[i], "CL": s.cl[i],
                               "UCL": s.ucl[i], "LCL": s.lcl[i], "rules_violated": " ".join(flags.get(i, []))})
        rep = Report(f"{chart.kind} control chart - {name}")
        rep.heading("Limits")
        rep.table(pd.DataFrame([{"chart": s.title, "CL": s.cl[0], "UCL": s.ucl[0], "LCL": s.lcl[0]} for s in chart.series]))
        rep.heading("Chart")
        rep.figure(fig)
        rep.heading("Out-of-control signals")
        rep.text(f"Rules: {rs_name}; applied {sorted(sel)}")
        rep.table(vdf) if len(vdf) else rep.text("None")
        download_buttons(rep, pd.DataFrame(points), f"control_chart_{chart.kind}")


# ---------------------------------------------------------------- capability
def page_capability():
    st.header("Process capability")
    left, right = st.columns([1, 3])
    with left:
        df, name = pick_data("cap", "shaft_diameter_subgroups.csv")
        if df is None:
            return
        cols = list(df.columns)
        meas = st.selectbox("Measurement column", cols, index=guess(cols, "diameter", "weight", "value", "measure",
                                                                     numeric_df=df, offset=1), key="cap_col")
        default_n = 5 if "subgroup" in [c.lower() for c in cols] else 1
        n = st.number_input("Subgroup size (1 = individuals)", 1, 25, default_n, key=f"cap_n_{name}")
        method = None
        if n > 1:
            method = st.selectbox("Within-sigma estimate", SIGMA_METHODS[:3], key="cap_m")
        lsl0, usl0, t0 = SPEC_DEFAULTS.get(name, (None, None, None))
        lsl = st.number_input("LSL", value=lsl0, format="%.4f", key=f"lsl_{name}")
        usl = st.number_input("USL", value=usl0, format="%.4f", key=f"usl_{name}")
        target = st.number_input("Target (optional)", value=t0, format="%.4f", key=f"t_{name}")

    if lsl is None and usl is None:
        right.info("Enter at least one specification limit (LSL and/or USL).")
        return
    x = pd.to_numeric(df[meas], errors="coerce").dropna().to_numpy()
    try:
        res = capability(x, lsl, usl, target, int(n), method)
    except ValueError as e:
        right.error(str(e))
        return

    with right:
        m = st.columns(5)
        m[0].metric("Cp", fmt(res.Cp, 2))
        m[1].metric("Cpk", fmt(res.Cpk, 2))
        m[2].metric("Pp", fmt(res.Pp, 2))
        m[3].metric("Ppk", fmt(res.Ppk, 2))
        m[4].metric("Expected PPM (overall)", f"{res.ppm_overall:,.0f}")
        st.markdown(f"**Cpk verdict:** {capability_verdict(res.Cpk)} &nbsp;|&nbsp; "
                    f"**Ppk verdict:** {capability_verdict(res.Ppk)}")
        fig = capability_figure(x[: res.n], res, title=f"Capability histogram - {name}")
        st.plotly_chart(fig, width="stretch", theme=None)

        c1, c2 = st.columns(2)
        stats_tbl = pd.DataFrame({"value": {
            "N": res.n, "Mean": res.mean, "Sigma (within)": res.sigma_within, "Sigma (overall)": res.sigma_overall,
            "LSL": lsl, "USL": usl, "Target": target, "Cpl": res.Cpl, "Cpu": res.Cpu, "Cpm": res.Cpm,
            "Ppl": res.Ppl, "Ppu": res.Ppu, "PPM observed": res.ppm_observed, "PPM expected (within)": res.ppm_within,
            "PPM expected (overall)": res.ppm_overall}})
        c1.subheader("Statistics")
        c1.dataframe(stats_tbl.style.format(lambda v: fmt(v, 5) if isinstance(v, (float, np.floating)) else v),
                     width="stretch")
        c2.subheader("Normality")
        nr = res.normality
        if nr:
            c2.write(f"Anderson-Darling A² = **{nr.ad_statistic:.3f}**, p-value = **{nr.ad_p_value:.3f}**")
            if nr.shapiro_p is not None:
                c2.write(f"Shapiro-Wilk W = {nr.shapiro_w:.3f}, p-value = {nr.shapiro_p:.3f}")
            if nr.is_normal:
                c2.success("No evidence against normality (p ≥ 0.05) - normal-based indices are appropriate.")
            else:
                c2.warning("Data are not normal (p < 0.05). Cp/Cpk assume normality; consider a transformation "
                           "or a non-normal capability analysis, and check the control chart for special causes.")
        if n > 1:
            c2.caption("Within sigma comes from subgroup variation (short-term); overall sigma is the standard "
                       "deviation of all data (long-term). A big gap means the mean drifts between subgroups.")

        rep = Report(f"Process capability - {name}")
        rep.text(f"Cpk {fmt(res.Cpk, 2)}: {capability_verdict(res.Cpk)}; Ppk {fmt(res.Ppk, 2)}: "
                 f"{capability_verdict(res.Ppk)}", verdict=True)
        rep.heading("Indices")
        rep.table({k: v for k, v in res.as_dict().items() if v is not None})
        rep.heading("Histogram")
        rep.figure(fig)
        download_buttons(rep, pd.DataFrame([res.as_dict()]), "capability")


# ------------------------------------------------------------------ gage R&R
def page_gage():
    st.header("Gage R&R (crossed)")
    left, right = st.columns([1, 3])
    with left:
        df, name = pick_data("grr", "gage_rr_aiag.csv")
        if df is None:
            return
        cols = list(df.columns)
        part = st.selectbox("Part column", cols, index=guess(cols, "part"))
        oper = st.selectbox("Operator column", cols, index=guess(cols, "operator", "appraiser"))
        meas = st.selectbox("Measurement column", cols, index=guess(cols, "measure", "value", "y"))
        method = st.radio("Method", ["ANOVA (recommended)", "Average & Range (AIAG)"], key="grr_method")
        tol = st.number_input("Tolerance USL - LSL (optional, for %Tolerance)", value=None, min_value=0.0,
                              format="%.4f", key="grr_tol")

    try:
        fn = gage_rr_anova if method.startswith("ANOVA") else gage_rr_average_range
        res = fn(df, part, oper, meas, tolerance=tol or None)
    except (ValueError, KeyError, TypeError) as e:
        right.error(f"Could not run the study: {e}")
        return

    with right:
        m = st.columns(4)
        m[0].metric("%Study Var (GRR)", f"{res.pct_study_grr:.2f}%")
        m[1].metric("%Contribution (GRR)", f"{res.pct_contribution_grr:.2f}%")
        m[2].metric("%Tolerance (GRR)", "-" if res.pct_tolerance_grr is None else f"{res.pct_tolerance_grr:.2f}%")
        m[3].metric("Distinct categories", res.ndc)
        verdict = res.verdict
        (st.success if verdict.startswith("Acceptable") else st.warning if verdict.startswith("Marginal")
         else st.error)(f"Measurement system: {verdict}")
        if res.ndc < 5:
            st.warning(f"ndc = {res.ndc} < 5: the gage cannot reliably distinguish enough part categories.")
        st.caption(f"{res.n_parts} parts x {res.n_operators} operators x {res.n_trials} trials - method: {res.method}")

        c1, c2 = st.columns(2)
        if res.anova is not None:
            c1.subheader("ANOVA table" if res.method == "ANOVA" else "AIAG worksheet values")
            if res.method == "ANOVA" and res.interaction_pooled:
                p_int = res.anova_full.loc["Part*Operator", "P"]
                c1.caption(f"Part*Operator interaction p = {p_int:.3f} > 0.25, so it was pooled into "
                           "repeatability (reduced model).")
            shown = res.anova.apply(lambda col: col.map(
                lambda v: "" if pd.isna(v) else (f"{int(v)}" if col.name == "DF" else f"{v:.5f}")))
            c1.dataframe(shown, width="stretch")
        c2.subheader("Variance components")
        c2.dataframe(res.components.style.format(precision=4), width="stretch")

        figs = gage_figures(res, df, part, oper, meas)
        st.plotly_chart(figs[0], width="stretch", theme=None)
        g1, g2 = st.columns(2)
        g1.plotly_chart(figs[1], width="stretch", theme=None)
        g2.plotly_chart(figs[2], width="stretch", theme=None)

        rep = Report(f"Gage R&R - {name}")
        rep.text(f"%Study Var (GRR) = {res.pct_study_grr:.2f}% -> {verdict}; ndc = {res.ndc}", verdict=True)
        if res.anova is not None:
            rep.heading("ANOVA" if res.method == "ANOVA" else "AIAG worksheet")
            rep.table(res.anova)
        rep.heading("Variance components")
        rep.table(res.components)
        for f in figs:
            rep.figure(f)
        download_buttons(rep, res.components.reset_index(names="source"), "gage_rr")


# --------------------------------------------------------------------- about
def page_about():
    st.header("About")
    st.markdown("""
**SPC & Capability Studio** reproduces the core statistical-process-control toolkit a manufacturing or quality
engineer uses every week - control charts, run rules, capability indices and Gage R&R - with formulas that are
checked against published reference results (Montgomery, NIST/SEMATECH e-Handbook, AIAG MSA 4th ed.) by an
automated test suite.

**CSV format** - one observation per row with a header row ("long" format):

| Analysis | Columns needed |
|---|---|
| X̄-R / X̄-S | measurement, subgroup ID (or use a fixed subgroup size) |
| I-MR / capability | measurement (in time order) |
| p / np | number defective, sample size |
| c / u | defect count (and units inspected for u) |
| Gage R&R | part, operator, measurement (balanced: every operator measures every part r times) |
""")
    st.subheader("Control chart constants used")
    st.dataframe(pd.DataFrame([get_constants(n).__dict__ for n in range(2, 26)]).set_index("n").round(4),
                 width="stretch")


PAGES = {"📈 Control charts": page_control_charts, "🎯 Capability": page_capability,
         "📏 Gage R&R": page_gage, "ℹ️ About": page_about}


def main():
    st.set_page_config(page_title="SPC & Capability Studio", page_icon="📈", layout="wide")
    st.sidebar.markdown("## SPC & Capability Studio")
    st.sidebar.caption("Control charts · Nelson rules · Cp/Cpk · Gage R&R")
    page = st.sidebar.radio("Module", list(PAGES), key="page")
    st.sidebar.markdown("---")
    st.sidebar.caption("Formulas verified against Montgomery, NIST/SEMATECH and AIAG MSA reference results. "
                       "[Source on GitHub](https://github.com/PiyushBhamare2111/spc-capability-studio)")
    PAGES[page]()


main()
