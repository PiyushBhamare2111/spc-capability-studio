"""Smoke-test every page of the Streamlit app on the bundled sample data (streamlit AppTest)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def run(page, **widgets):
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.sidebar.radio(key="page").set_value(page).run()
    for key, value in widgets.items():
        at.selectbox(key=key).set_value(value).run() if key != "grr_method" else at.radio(key=key).set_value(value).run()
    assert not at.exception, at.exception
    return at


@pytest.mark.parametrize("chart", [
    "X̄-R (subgroups, n = 2-10)", "X̄-S (subgroups, n > 10 or any n)", "I-MR (individuals)",
    "p (fraction defective)", "np (number defective)", "c (defects per unit, constant area)",
    "u (defects per unit, varying area)"])
def test_control_chart_page(chart):
    at = run("📈 Control charts", cc_type=chart)
    assert not at.error


def test_control_chart_signals_on_shaft_data():
    at = run("📈 Control charts")
    assert any(m.label == "Signals" and not m.value.startswith("0 ") for m in at.metric)


def test_capability_page():
    at = run("🎯 Capability")
    assert {m.label for m in at.metric} >= {"Cp", "Cpk", "Pp", "Ppk"}
    assert not at.error


def test_capability_individuals():
    at = run("🎯 Capability", cap_ds="tablet_weight_individuals.csv")
    assert not at.error


@pytest.mark.parametrize("method", ["ANOVA (recommended)", "Average & Range (AIAG)"])
def test_gage_page(method):
    at = run("📏 Gage R&R", grr_method=method)
    pct = next(m.value for m in at.metric if m.label == "%Study Var (GRR)")
    assert pct in ("27.86%", "26.68%")
    assert not at.error


def test_about_page():
    run("ℹ️ About")
