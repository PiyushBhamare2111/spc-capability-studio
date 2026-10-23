"""Plotly figures for control charts, capability histograms and Gage R&R."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

from .capability import CapabilityResult
from .charts import ControlChart, ChartSeries
from .gage import GageResult
from .rules import Violation

# Dark theme matching the project branding (accent #ff8a3d on #0b0c0f).
ACCENT = "#ff8a3d"
BG = "#0b0c0f"
PANEL = "#14161b"
TEXT = "#e8e8ea"
MUTED = "#8b8f99"
GRID = "#262a33"
BLUE = "#5b8def"
RED = "#ff4d5e"
GREEN = "#3ddc97"
GREY = MUTED


def apply_theme(fig: go.Figure, title: str | None = None, **layout) -> go.Figure:
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=PANEL,
        font=dict(family="Inter, Segoe UI, Helvetica, Arial, sans-serif", color=TEXT, size=13),
        title=dict(text=title, font=dict(size=18, color=TEXT)), **layout)
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID)
    return fig


def _add_series(fig, s: ChartSeries, row: int, flagged: set[int]):
    x = s.labels
    fig.add_trace(go.Scatter(x=x, y=s.values, mode="lines+markers", name=s.title,
                             line=dict(color=ACCENT, width=2), marker=dict(size=6, color=ACCENT)), row=row, col=1)
    for arr, name, dash, color in ((s.ucl, "UCL", "dash", RED), (s.cl, "CL", "solid", GREEN),
                                   (s.lcl, "LCL", "dash", RED)):
        shape = "hv" if not np.allclose(arr, arr[0]) else "linear"
        fig.add_trace(go.Scatter(x=x, y=arr, mode="lines", name=name, line=dict(color=color, dash=dash, width=1,
                                 shape=shape), showlegend=False, hoverinfo="skip"), row=row, col=1)
        fig.add_annotation(x=x[-1], y=arr[-1], text=f"{name}={arr[-1]:.6g}", showarrow=False, xanchor="left",
                           font=dict(size=10, color=color), row=row, col=1)
    if flagged:
        idx = sorted(flagged)
        fig.add_trace(go.Scatter(x=x[idx], y=s.values[idx], mode="markers", name="Out of control",
                                 marker=dict(color=RED, size=14, symbol="circle-open", line=dict(width=3, color=RED))),
                      row=row, col=1)


def control_chart_figure(chart: ControlChart, violations: dict[str, list[Violation]] | None = None,
                         title: str | None = None) -> go.Figure:
    violations = violations or {}
    rows = len(chart.series)
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=False, vertical_spacing=0.12,
                        subplot_titles=[s.title for s in chart.series],
                        row_heights=[0.6, 0.4][:rows] if rows == 2 else None)
    for i, s in enumerate(chart.series, start=1):
        flagged = {v.index for v in violations.get(s.title, [])}
        _add_series(fig, s, i, flagged)
    apply_theme(fig, title=title or f"{chart.kind} chart", height=330 * rows + 40, showlegend=False,
                margin=dict(l=60, r=110, t=80, b=40))
    return fig


def capability_figure(data, res: CapabilityResult, title: str = "Process capability") -> go.Figure:
    x = np.asarray(data, dtype=float)
    x = x[~np.isnan(x)]
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=x, histnorm="probability density", name="Data",
                               marker=dict(color="#3a4560", line=dict(color=BG, width=1)), opacity=0.95))
    lo = min([x.min()] + [v for v in (res.lsl,) if v is not None])
    hi = max([x.max()] + [v for v in (res.usl,) if v is not None])
    pad = 0.15 * (hi - lo)
    grid = np.linspace(lo - pad, hi + pad, 400)
    fig.add_trace(go.Scatter(x=grid, y=stats.norm.pdf(grid, res.mean, res.sigma_within), name="Within (short-term)",
                             line=dict(color=ACCENT, width=3)))
    fig.add_trace(go.Scatter(x=grid, y=stats.norm.pdf(grid, res.mean, res.sigma_overall), name="Overall (long-term)",
                             line=dict(color=TEXT, width=2, dash="dash")))
    for v, name in ((res.lsl, "LSL"), (res.usl, "USL"), (res.target, "Target")):
        if v is not None:
            fig.add_vline(x=v, line=dict(color=RED if name != "Target" else GREEN, width=2,
                                         dash="solid" if name != "Target" else "dot"),
                          annotation_text=name, annotation_position="top")
    apply_theme(fig, title=title, height=420, bargap=0.02,
                legend=dict(orientation="h", y=-0.15), margin=dict(l=60, r=30, t=70, b=40))
    return fig


def gage_figures(res: GageResult, df: pd.DataFrame, part: str, operator: str, measurement: str) -> list[go.Figure]:
    comp = res.components
    keys = [k for k in ["Total Gage R&R", "Repeatability", "Reproducibility", "Part-to-Part"] if k in comp.index]
    bars = go.Figure()
    cols = ["%Contribution", "%Study Var"] + (["%Tolerance"] if "%Tolerance" in comp.columns else [])
    colors = [BLUE, ACCENT, GREEN]
    for c, colr in zip(cols, colors):
        bars.add_trace(go.Bar(x=keys, y=comp.loc[keys, c], name=c, marker_color=colr))
    bars.add_hline(y=10, line=dict(color=GREEN, dash="dot"), annotation_text="10%")
    bars.add_hline(y=30, line=dict(color=RED, dash="dot"), annotation_text="30%")
    apply_theme(bars, title="Components of variation", barmode="group", height=380, yaxis_title="Percent",
                legend=dict(orientation="h", y=-0.15))

    by_part = go.Figure()
    for op, g in df.groupby(operator):
        m = g.groupby(part)[measurement].mean()
        by_part.add_trace(go.Scatter(x=m.index.astype(str), y=m.values, mode="lines+markers", name=f"Operator {op}"))
    apply_theme(by_part, title="Operator * Part interaction (mean of trials)", height=380,
                xaxis_title="Part", yaxis_title=measurement, colorway=[ACCENT, BLUE, GREEN, RED, "#c084fc"])

    box = go.Figure()
    for op, g in df.groupby(operator):
        box.add_trace(go.Box(y=g[measurement], name=str(op), boxmean=True))
    apply_theme(box, title="Measurements by operator", height=380, showlegend=False,
                colorway=[ACCENT, BLUE, GREEN, RED, "#c084fc"])
    return [bars, by_part, box]
