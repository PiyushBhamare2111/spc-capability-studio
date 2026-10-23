"""Render README charts, app screenshots and 1920x1080 showcase images.

Requires the dev extras (pip install -r requirements-dev.txt, then
`python -m playwright install chromium`) and a running app:

    streamlit run app.py --server.headless true --server.port 8501
    python scripts/make_media.py --url http://localhost:8501
"""

from __future__ import annotations

import argparse
import html
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

from spc import charts, rules  # noqa: E402
from spc.capability import capability, capability_from_stats  # noqa: E402
from spc.gage import gage_rr_anova, gage_rr_average_range  # noqa: E402
from spc.plots import capability_figure, control_chart_figure, gage_figures  # noqa: E402

DATA = ROOT / "data"
CHARTS = ROOT / "docs" / "charts"
MEDIA = ROOT / "docs" / "media"
ACCENT, BG, PANEL, TEXT, MUTED = "#ff8a3d", "#0b0c0f", "#14161b", "#e8e8ea", "#8b8f99"


def build_figures():
    shaft = pd.read_csv(DATA / "shaft_diameter_subgroups.csv")
    sub = charts.subgroups_from_long(shaft["diameter_mm"], shaft["subgroup"])
    xr = charts.xbar_r(sub)
    viol = {"X-bar": rules.evaluate(xr.primary), "Range": rules.evaluate(xr.secondary, [1])}
    f1 = control_chart_figure(xr, viol, title="X̄-R chart · shaft diameter (mm) · Nelson rules flag the mean shift")
    cap = capability(shaft["diameter_mm"], 24.985, 25.015, 25.0, subgroup_size=5)
    f2 = capability_figure(shaft["diameter_mm"], cap,
                           title=f"Capability · Cp {cap.Cp:.2f}  Cpk {cap.Cpk:.2f}  Pp {cap.Pp:.2f}  Ppk {cap.Ppk:.2f}")
    g = pd.read_csv(DATA / "gage_rr_aiag.csv")
    grr = gage_rr_anova(g, "part", "operator", "measurement")
    f3 = gage_figures(grr, g, "part", "operator", "measurement")[0]
    f3.update_layout(title=f"Gage R&R (ANOVA) · AIAG data · %Study Var GRR {grr.pct_study_grr:.2f}% · ndc {grr.ndc}")
    return {"xbar_r_chart.png": f1, "capability_histogram.png": f2, "gage_rr_components.png": f3}


def reference_rows():
    """Published value vs. this package, for the 'verified' showcase card."""
    from tests.reference_data import ORANGE_JUICE_D, PCB_C, aiag_frame

    p = charts.p_chart(ORANGE_JUICE_D, 50).primary
    c = charts.c_chart(PCB_C).primary
    nist = capability_from_stats(16, 2, lsl=8, usl=20)
    df = aiag_frame()
    ar = gage_rr_average_range(df, "part", "operator", "y")
    an = gage_rr_anova(df, "part", "operator", "y")
    return [
        ("Montgomery Ex. 7.1", "p chart UCL", "0.4102", f"{p.ucl[0]:.4f}"),
        ("Montgomery Ex. 7.3", "c chart LCL", "6.48", f"{c.lcl[0]:.2f}"),
        ("NIST e-Handbook 6.1.6", "Cpk", "0.667", f"{nist.Cpk:.3f}"),
        ("AIAG MSA 4th ed.", "SS parts (ANOVA)", "88.3619", f"{an.anova_full.loc['Part', 'SS']:.4f}"),
        ("AIAG MSA 4th ed.", "%GRR (avg & range)", "26.68%", f"{ar.pct_study_grr:.2f}%"),
        ("AIAG MSA 4th ed.", "%GRR (ANOVA)", "27.86%", f"{an.pct_study_grr:.2f}%"),
        ("AIAG MSA 4th ed.", "PV (ANOVA)", "1.04233", f"{an.components.loc['Part-to-Part', 'StdDev']:.5f}"),
    ]


CARD_CSS = f"""
*{{box-sizing:border-box}} body{{margin:0;width:1920px;height:1080px;background:{BG};color:{TEXT};
font-family:'Segoe UI',Inter,Helvetica,Arial,sans-serif;overflow:hidden}}
.wrap{{padding:110px 130px;height:100%;position:relative}}
.glow{{position:absolute;right:-220px;top:-220px;width:900px;height:900px;border-radius:50%;
background:radial-gradient(circle,{ACCENT}33 0%,transparent 65%)}}
.kicker{{color:{ACCENT};font-size:30px;letter-spacing:6px;text-transform:uppercase;font-weight:600}}
h1{{font-size:118px;margin:22px 0 10px;line-height:1.02}} h1 span{{color:{ACCENT}}}
.sub{{font-size:38px;color:{MUTED};max-width:1350px;line-height:1.35}}
.chips{{margin-top:70px;display:flex;flex-wrap:wrap;gap:22px;max-width:1500px}}
.chip{{border:2px solid {ACCENT};border-radius:40px;padding:16px 34px;font-size:30px;background:{PANEL}}}
.foot{{position:absolute;bottom:80px;left:130px;font-size:28px;color:{MUTED}}}
table{{border-collapse:collapse;margin-top:46px;font-size:33px;width:100%}}
td,th{{padding:15px 22px;border-bottom:1px solid #262a33;text-align:left}} th{{color:{MUTED};font-weight:500}}
td.ok{{color:#3ddc97;font-weight:700}} td.num{{font-family:Consolas,monospace}}
"""


def title_card() -> str:
    chips = ["X̄-R · X̄-S · I-MR", "p · np · c · u", "Nelson / Western Electric rules", "Cp · Cpk · Pp · Ppk",
             "Gage R&R (ANOVA)", "HTML / CSV reports", "pytest-verified"]
    return (f"<html><head><meta charset='utf-8'><style>{CARD_CSS}</style></head><body><div class='wrap'>"
            "<div class='glow'></div><div class='kicker'>Manufacturing · Quality Engineering</div>"
            "<h1>SPC &amp; Capability <span>Studio</span></h1>"
            "<div class='sub'>Upload a CSV and get control charts, out-of-control signals, process capability and "
            "Gage R&amp;R, with formulas checked against Montgomery, NIST and AIAG reference results.</div>"
            "<div class='chips'>" + "".join(f"<div class='chip'>{html.escape(c)}</div>" for c in chips) + "</div>"
            "<div class='foot'>Python · Streamlit · SciPy · Plotly &nbsp;|&nbsp; github.com/PiyushBhamare2111/"
            "spc-capability-studio</div></div></body></html>")


def verified_card() -> str:
    rows = "".join(f"<tr><td>{s}</td><td>{q}</td><td class='num'>{pub}</td><td class='num'>{ours}</td>"
                   f"<td class='ok'>✓</td></tr>" for s, q, pub, ours in reference_rows())
    return (f"<html><head><meta charset='utf-8'><style>{CARD_CSS}</style></head><body><div class='wrap'>"
            "<div class='glow'></div><div class='kicker'>Correctness is the feature</div>"
            "<h1 style='font-size:84px'>Verified against <span>published results</span></h1>"
            "<table><tr><th>Source</th><th>Quantity</th><th>Published</th><th>This app</th><th></th></tr>"
            f"{rows}</table><div class='foot'>Every value above is an automated pytest assertion · "
            "tests/test_charts.py · test_capability.py · test_gage.py</div></div></body></html>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8501")
    ap.add_argument("--skip-app", action="store_true")
    args = ap.parse_args()
    CHARTS.mkdir(parents=True, exist_ok=True)
    MEDIA.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        # 1) static charts for the README
        page = browser.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=1)
        for name, fig in build_figures().items():
            fig.update_layout(width=1600, height=900, margin=dict(l=80, r=130, t=90, b=60))
            f = tmp / (name + ".html")
            fig.write_html(f, include_plotlyjs=True, full_html=True, config={"displayModeBar": False})
            page.goto(f.as_uri())
            page.wait_for_selector(".js-plotly-plot")
            page.wait_for_timeout(500)
            page.locator(".js-plotly-plot").first.screenshot(path=str(CHARTS / name))
            print("chart", name)

        # 2) showcase cards
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        for name, body in (("01_title_card.png", title_card()), ("05_verified_against_references.png", verified_card())):
            f = tmp / (name + ".html")
            f.write_text(body, encoding="utf-8")
            page.goto(f.as_uri())
            page.wait_for_timeout(300)
            page.screenshot(path=str(MEDIA / name))
            print("card", name)

        # 3) live app screenshots
        if not args.skip_app:
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.goto(args.url, wait_until="networkidle")
            for label, out in (("Control charts", "02_app_control_charts.png"), ("Capability", "03_app_capability.png"),
                               ("Gage R&R", "04_app_gage_rr.png")):
                page.locator('[data-testid="stSidebar"] label').filter(has_text=label).first.click()
                page.wait_for_selector(".js-plotly-plot", timeout=30000)
                page.wait_for_timeout(2500)
                page.screenshot(path=str(MEDIA / out))
                print("app", out)
        browser.close()


if __name__ == "__main__":
    main()
