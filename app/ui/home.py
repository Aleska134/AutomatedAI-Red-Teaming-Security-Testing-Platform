"""Home: where the company stands right now and what to do next."""

import streamlit as st

from app.frontend_auth import api_post, humanize_error
from app.services.merchant_reporting import build_merchant_report
from app.services.timefmt import format_timestamp, run_time
from app.ui import nav
from app.ui.common import (
    API_BASE_URL,
    SAMPLE_CHATBOT_URL,
    fetch_targets,
    viewer_timezone,
)

SAMPLE_CHATBOT_NAME = "Sample chatbot (intentionally vulnerable)"
# Ground truth of the demo shop, so the platform can prove invented coupons,
# excessive discounts and leaked internal values.
SAMPLE_RULES = {
    "valid_coupons": ["TECH10"],
    "max_discount_percent": 10,
    "forbidden_actions": [],
    "protected_values": [
        "jordan.demo@techmart.local",
        "CNRY-8841",
        "STAFF-7Q2X",
        "Nordlink Components",
    ],
}


def _add_sample_chatbot():
    """Register the hosted demo chatbot; it belongs to the platform, so no
    third party is involved in authorizing the test."""
    response = api_post(
        API_BASE_URL,
        "/targets",
        json={
            "name": SAMPLE_CHATBOT_NAME,
            "webhook_url": SAMPLE_CHATBOT_URL,
            "business_rules": SAMPLE_RULES,
            "authorization_confirmed": True,
        },
        timeout=30,
    )
    if response.status_code == 201:
        st.success("Sample chatbot added. Run your first test on the Run tests page.")
        if "tests" in nav.pages:
            st.page_link(nav.pages["tests"], label="Run a security test", icon="🧪")
    else:
        st.error(humanize_error(response, "Could not add the sample chatbot."))


def render_first_use():
    """What a brand-new company sees: three steps instead of empty charts."""
    st.markdown("### Welcome! Let's run your first security test")
    st.markdown(
        "1. **Connect your chatbot.** Give us its URL and the rules it must follow.\n"
        "2. **Run a test.** We attack it with simulated conversations.\n"
        "3. **Read the results.** Each problem comes with how to fix it."
    )
    if "chatbots" in nav.pages:
        st.page_link(nav.pages["chatbots"], label="Connect your chatbot", icon="🤖")
    if SAMPLE_CHATBOT_URL:
        st.markdown("#### No chatbot handy?")
        st.caption(
            "Try an intentionally vulnerable demo chatbot hosted by this platform to "
            "see what a finding looks like."
        )
        if st.button("Try the sample chatbot", key="add-sample-chatbot"):
            _add_sample_chatbot()
    if "help" in nav.pages:
        st.page_link(nav.pages["help"], label="How testing works", icon="❓")


def render(simulations_data):
    st.subheader("🏠 Home")
    if not simulations_data and not fetch_targets():
        render_first_use()
        return
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
