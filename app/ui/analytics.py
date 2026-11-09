"""Analytics tab: results per chatbot, one chatbot, or two side by side."""


import pandas as pd
import plotly.express as px
import streamlit as st

from app.services.merchant_reporting import (
    conclusive_runs,
    finished_runs,
)
from app.services.safe_data import as_list
from app.services.security_scenarios import (
    friendly_test_name,
)
from app.services.target_analytics import (
    compare_targets,
    runs_for_target,
    summarize_all_targets,
    target_label,
)
from app.services.timefmt import format_timestamp
from app.ui.common import fetch_targets, style_chart, viewer_timezone


def render_scope_analytics(scope_runs):
    """KPIs and charts for the runs in scope (all chatbots, or just one)."""
    completed_runs = conclusive_runs(scope_runs)
    skipped_runs = len(finished_runs(scope_runs)) - len(completed_runs)
    if not completed_runs:
        st.info(
            "No completed tests with a verdict yet for this selection. Run an "
            "assessment from the 🏪 Merchant Security View tab."
        )
        if skipped_runs:
            st.caption(f"{skipped_runs} inconclusive run(s) could not be judged.")
        return
    if skipped_runs:
        st.caption(
            f"{skipped_runs} inconclusive run(s) are excluded from these statistics."
        )
    # Convert JSON objects into a Pandas DataFrame for swift graphing metrics
    df = pd.DataFrame(completed_runs)

    # Calculate summary numbers with defensive defaults for mixed records.
    total_runs = len(df)
    breached_series = (
        df.get("breached", pd.Series(False, index=df.index)).fillna(False).astype(bool)
    )
    breached_count = int(breached_series.sum())
    secured_count = total_runs - breached_count
    avg_defense = (
        df.get("defense_efficiency_score", pd.Series(dtype="float64")).dropna().mean()
    )
    avg_defense = 0.0 if pd.isna(avg_defense) else avg_defense
    deterministic_breaches = int(
        df.get("deterministic_breach", pd.Series(False, index=df.index)).fillna(False).sum()
    )
    tool_event_count = sum(
        len(as_list(record.get("tool_events"))) for record in completed_runs
    )

    # Display KPIs in crisp metric columns
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Simulations Run", total_runs)
    col2.metric("Successful Breaches 🚨", breached_count, delta=int(breached_count), delta_color="inverse")
    col3.metric("Defenses Held 🛡️", secured_count)
    col4.metric("Avg Defense Efficiency", f"{avg_defense:.2f} / 10")
    col5.metric("Deterministic Breaches", deterministic_breaches)
    col6.metric("Tool Events", tool_event_count)

    st.markdown("---")

    col_g1, col_g2 = st.columns(2)

    # Normalize columns the charts rely on so mixed records never break them.
    df = df.copy()
    df["breached"] = breached_series
    if "simulation_number" not in df.columns:
        df["simulation_number"] = range(len(df))
    if "attacker_aggression_level" not in df.columns:
        df["attacker_aggression_level"] = 1

    with col_g1:
        st.markdown("#### Breach status")
        outcome = df["breached"].map({True: "Breached", False: "Defense held"})
        fig_pie = px.pie(
            names=outcome,
            color=outcome,
            color_discrete_map={"Breached": "#d92d20", "Defense held": "#12b76a"},
            hole=0.6,
        )
        fig_pie.update_traces(textinfo="value+percent", sort=False)
        st.plotly_chart(style_chart(fig_pie), width="stretch")

    with col_g2:
        st.markdown("#### Attacker aggression per simulation")
        fig_line = px.line(
            df.sort_values(by="simulation_number"),
            x="simulation_number",
            y="attacker_aggression_level",
            markers=True,
            labels={"simulation_number": "Simulation", "attacker_aggression_level": "Aggression (1-5)"},
        )
        fig_line.update_traces(line_color="#6941c6", line_width=2)
        fig_line.update_yaxes(range=[0, 5.5], dtick=1, gridcolor="rgba(128,128,128,0.2)")
        fig_line.update_xaxes(dtick=1, showgrid=False)
        st.plotly_chart(style_chart(fig_line), width="stretch")


VERDICT_LABELS = {
    "fell": "🔴 Fell",
    "resisted": "🟢 Resisted",
    "no_data": "⚪ No verdict yet",
}


OUTCOME_LABELS = {
    "breached": "🔴 Breached",
    "held": "🟢 Held",
    "inconclusive": "⚪ Inconclusive",
    None: "— not tested",
}


def render_target_table(summaries):
    """One row per chatbot so resisted vs fell is visible at a glance."""
    st.dataframe(
        [
            {
                "Chatbot": item["name"],
                "Result": VERDICT_LABELS[item["verdict"]],
                "Tests": item["tests"],
                "Breached": item["breached"],
                "Held": item["held"],
                "Breach rate": (
                    f"{item['breach_rate']:.0%}" if item["breach_rate"] is not None else "—"
                ),
                "Avg defense": (
                    f"{item['avg_defense']:.1f}/10" if item["avg_defense"] is not None else "—"
                ),
                "Inconclusive": item["inconclusive"],
                "Last test": format_timestamp(item["last_run_at"], viewer_timezone()),
            }
            for item in summaries
        ],
        width="stretch",
        hide_index=True,
    )


def render_target_comparison(runs, target_a, target_b, names_by_id):
    """A vs B: headline numbers on the shared tests, then test-by-test."""
    result = compare_targets(runs, target_a, target_b, names_by_id)
    col_a, col_b = st.columns(2)
    for column, key, breached_key in (
        (col_a, "a", "a_shared_breached"),
        (col_b, "b", "b_shared_breached"),
    ):
        summary = result[key]
        with column.container(border=True):
            st.markdown(f"### {summary['name']}")
            st.markdown(f"**{VERDICT_LABELS[summary['verdict']]}**")
            st.metric(
                "Breached on shared tests",
                f"{result[breached_key]} / {result['shared_tests']}",
            )
            st.caption(
                f"All tests: {summary['breached']} breached, {summary['held']} held"
                + (
                    f" · avg defense {summary['avg_defense']:.1f}/10"
                    if summary["avg_defense"] is not None
                    else ""
                )
            )
    if not result["shared_tests"]:
        st.warning(
            "These chatbots have no tests in common yet, so they cannot be compared "
            "fairly. Run the same tests on both."
        )
    else:
        st.caption(
            f"The headline compares only the {result['shared_tests']} test(s) both "
            "chatbots were given, so neither is judged on easier or harder tests."
        )
    st.markdown("#### Test by test")
    st.dataframe(
        [
            {
                "Test": friendly_test_name(row["strategy"]),
                f"A · {result['a']['name']}": OUTCOME_LABELS[row["a"]],
                f"B · {result['b']['name']}": OUTCOME_LABELS[row["b"]],
            }
            for row in result["rows"]
        ],
        width="stretch",
        hide_index=True,
    )


def render(simulations_data):
    st.subheader("📊 Security Analytics")
    if not simulations_data:
        st.info(
            "No test runs yet. Open the 🏪 Merchant Security View tab and run your "
            "first assessment!"
        )
    else:
        analytics_names = {t["target_id"]: t["name"] for t in fetch_targets()}
        # Chatbots with runs first, then saved chatbots that have not been tested.
        analytics_targets = list(
            dict.fromkeys(
                [run.get("target_id") for run in simulations_data]
                + list(analytics_names)
            )
        )

        def _analytics_label(target_id):
            return target_label(target_id, analytics_names)

        view_options = ["All chatbots", "One chatbot"]
        if len(analytics_targets) >= 2:
            view_options.append("Compare two chatbots")
        view = st.radio(
            "View", view_options, horizontal=True, key="analytics_view"
        )

        if view == "All chatbots":
            st.markdown("#### Chatbot by chatbot")
            render_target_table(summarize_all_targets(simulations_data, analytics_names))
            st.markdown("#### All chatbots together")
            render_scope_analytics(simulations_data)
        elif view == "One chatbot":
            chosen = st.selectbox(
                "Chatbot",
                analytics_targets,
                format_func=_analytics_label,
                key="analytics_target",
            )
            render_scope_analytics(runs_for_target(simulations_data, chosen))
        else:
            pick_a, pick_b = st.columns(2)
            target_a = pick_a.selectbox(
                "Chatbot A", analytics_targets,
                format_func=_analytics_label, key="analytics_a",
            )
            others = [t for t in analytics_targets if t != target_a]
            target_b = pick_b.selectbox(
                "Chatbot B", others,
                format_func=_analytics_label, key="analytics_b",
            )
            render_target_comparison(
                simulations_data, target_a, target_b, analytics_names
            )
