"""Results: findings with fixes, the run history, and chatbot comparisons."""

import pandas as pd
import plotly.express as px
import streamlit as st

from app.services.merchant_reporting import build_findings, build_merchant_report, group_findings
from app.services.run_report import RULE_TITLES
from app.services.timefmt import format_duration, format_timestamp, run_time
from app.ui import analytics, logs
from app.ui.common import (
    SEVERITY_COLORS,
    SEVERITY_ICONS,
    style_chart,
    viewer_timezone,
)


def render_test_run_history(simulations):
    """Render the persistent execution history for merchant operators."""
    st.markdown("### Test run history")
    if not simulations:
        st.caption("No test runs have been persisted yet.")
        return

    st.dataframe(
        [
            {
                "Run ID": item.get("run_id", item.get("session_id", "unknown")),
                **({"Company": item["company_name"]} if "company_name" in item else {}),
                "Status": item.get("status", "legacy"),
                "Strategy": item.get("strategy", "unknown"),
                "Run type": item.get("run_type", "unknown"),
                "Turns": item.get("total_turns", item.get("total_turns_executed", 0)),
                "Breach": "Yes" if item.get("breached") else "No",
                "Date": format_timestamp(run_time(item), viewer_timezone()),
                "Duration": format_duration(item.get("started_at"), item.get("completed_at")) or "—",
            }
            for item in simulations
        ],
        width="stretch",
        hide_index=True,
    )


def render_finding_card(finding):
    """One finding as a readable card: what happened, then how to fix it."""
    severity = str(finding["severity"]).lower()
    title = RULE_TITLES.get(finding["rule"], (finding["rule"],))[0]
    with st.container(border=True):
        st.markdown(
            f"#### {SEVERITY_ICONS.get(severity, '⚪')} {title} "
            f"· {severity.upper()}"
        )
        seen = ", ".join(f"#{n}" for n in finding["simulations"])
        times = "time" if finding["count"] == 1 else "times"
        last = (
            f" · last found {format_timestamp(finding['last_seen'], viewer_timezone())}"
            if finding.get("last_seen") else ""
        )
        st.caption(
            f"{finding['owasp']} · found {finding['count']} {times} "
            f"(simulation {seen}){last}"
        )
        st.markdown(f"**What happened**\n\n{finding['description']}")
        st.success(f"**How to fix it**\n\n{finding['recommendation']}")


def render_findings(simulations_data):
    findings = group_findings(build_findings(simulations_data))

    st.markdown("### Findings requiring attention")
    if not findings:
        st.success("No findings are available for review.")
    else:
        for finding in findings:
            render_finding_card(finding)

        st.markdown("#### Findings by OWASP category")
        by_category = (
            pd.DataFrame(
                [{"OWASP": f["owasp"], "Severity": f["severity"].upper()} for f in findings]
            )
            .value_counts()
            .reset_index(name="Findings")
        )
        fig_bar = px.bar(
            by_category,
            x="Findings",
            y="OWASP",
            color="Severity",
            orientation="h",
            color_discrete_map=SEVERITY_COLORS,
            category_orders={"Severity": list(SEVERITY_COLORS)},
        )
        fig_bar.update_yaxes(title=None, categoryorder="total ascending")
        fig_bar.update_xaxes(dtick=1, gridcolor="rgba(128,128,128,0.2)")
        fig_bar.update_traces(width=0.5)
        height = 90 + 40 * by_category["OWASP"].nunique()
        st.plotly_chart(style_chart(fig_bar, height=height), width="stretch")


def render_history(simulations_data):
    merchant_report = build_merchant_report(simulations_data)

    latest = merchant_report["latest_simulation"]
    if latest:
        st.markdown(
            f"**Latest test:** Simulation #{latest.get('simulation_number')} "
            f"({latest.get('session_id')})"
        )
    render_test_run_history(simulations_data)
    logs.render(simulations_data)


def render(simulations_data):
    st.subheader("📊 Results")
    findings_tab, history_tab, compare_tab = st.tabs(
        ["Findings", "History & reports", "Compare chatbots"]
    )
    with findings_tab:
        render_findings(simulations_data)
    with history_tab:
        render_history(simulations_data)
    with compare_tab:
        analytics.render(simulations_data)
