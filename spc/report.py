"""Self-contained HTML summary report (charts are embedded Plotly, loaded from CDN)."""

from __future__ import annotations

import datetime as _dt
import html

import pandas as pd

_CSS = """
body{font-family:Segoe UI,Helvetica,Arial,sans-serif;max-width:1050px;margin:0 auto;padding:24px 16px;
background:#0b0c0f;color:#e8e8ea}
h1{border-bottom:3px solid #ff8a3d;padding-bottom:6px} h2{margin-top:34px;color:#ff8a3d}
table{border-collapse:collapse;margin:10px 0;font-size:14px} td,th{border:1px solid #262a33;padding:4px 9px;text-align:right}
th{background:#14161b} td:first-child,th:first-child{text-align:left}
.verdict{display:inline-block;padding:4px 10px;border-radius:4px;background:#1d140d;border:1px solid #ff8a3d}
.meta{color:#8b8f99;font-size:13px}
"""


class Report:
    def __init__(self, title: str = "SPC & Capability Report"):
        self.title = title
        self.sections: list[str] = []
        self._plotly_loaded = False

    def heading(self, text: str):
        self.sections.append(f"<h2>{html.escape(text)}</h2>")

    def text(self, text: str, verdict: bool = False):
        cls = ' class="verdict"' if verdict else ""
        self.sections.append(f"<p><span{cls}>{html.escape(text)}</span></p>")

    def table(self, df: pd.DataFrame | dict, floatfmt: str = "{:.4f}"):
        if isinstance(df, dict):
            df = pd.DataFrame({"value": pd.Series(df)})
        def _fmt(v, f=floatfmt):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return ""
            if isinstance(v, float):
                return f.format(v)
            return str(v)

        fmt = {c: _fmt for c in df.columns}
        self.sections.append(df.to_html(formatters=fmt, escape=True, na_rep="", border=0))

    def figure(self, fig):
        inc = "cdn" if not self._plotly_loaded else False
        self._plotly_loaded = True
        self.sections.append(fig.to_html(full_html=False, include_plotlyjs=inc))

    def to_html(self) -> str:
        now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        body = "\n".join(self.sections)
        return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(self.title)}</title>"
                f"<style>{_CSS}</style></head><body><h1>{html.escape(self.title)}</h1>"
                f"<p class='meta'>Generated {now} by SPC &amp; Capability Studio</p>{body}</body></html>")
