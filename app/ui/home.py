"""Home: where the company stands right now and what to do next."""

import streamlit as st

from app.services.merchant_reporting import build_merchant_report
from app.services.timefmt import format_timestamp, run_time
from app.ui import nav
from app.ui.common import (
    viewer_timezone,
)


def render(simulations_data):
    st.subheader("🏠 Home")
    merchant_report = build_merchant_report(simulations_data)

    risk_labels = {
        "no_data": ("⚪ NO DATA", "Run a security test to establish a baseline."),
        "secure": ("🟢 SECURE", "No breach has been recorded in the available runs."),
        "needs_review": (
            "🟡 NEEDS REVIEW",
            "Deterministic evidence requires merchant review.",
        ),
        "at_risk": (
            "🔴 AT RISK",
            "At least one simulation indicates a security breach.",
        ),
    }
    risk_label, risk_message = risk_labels[merchant_report["risk_status"]]
    st.markdown(f"### Current status: {risk_label}")
    st.caption(risk_message)

    if merchant_report["inconclusive_runs"]:
        st.caption(
            f"{merchant_report['inconclusive_runs']} inconclusive run(s) could not be "
            "judged and are not counted below."
        )
    metric_columns = st.columns(5)
    metric_columns[0].metric("Test Runs", merchant_report["total_runs"])
    metric_columns[1].metric("Breaches", merchant_report["breached_runs"])
    metric_columns[2].metric(
        "Deterministic Findings", merchant_report["deterministic_breaches"]
    )
    metric_columns[3].metric("Defenses Held", merchant_report["defenses_held"])
    metric_columns[4].metric(
        "Average Defense",
        f"{merchant_report['average_defense_efficiency']:.2f}/10",
    )

    latest = merchant_report["latest_simulation"]
    if latest:
        st.caption(
            f"Latest test: {format_timestamp(run_time(latest), viewer_timezone())}"
        )
    if "tests" in nav.pages:
        st.page_link(nav.pages["tests"], label="Run a security test", icon="🧪")
