"""Merchant Security View: run assessments, read findings, see the run history."""


import pandas as pd
import plotly.express as px
import streamlit as st

from app.frontend_auth import (
    api_post,
)
from app.services.batch_runner import (
    collect_scenario_results,
)
from app.services.merchant_reporting import (
    build_findings,
    build_merchant_report,
    group_findings,
)
from app.services.run_report import (
    RULE_TITLES,
    render_combined_report,
)
from app.services.security_scenarios import (
    get_categories,
    get_scenarios,
    scenarios_for_target,
    select_scenarios,
)
from app.ui.common import (
    API_BASE_URL,
    SEVERITY_COLORS,
    SEVERITY_ICONS,
    fetch_all_simulations,
    fetch_targets,
    run_security_test,
    style_chart,
)
from app.ui.targets import render_target_form, render_target_manager


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
                "Created": item.get("created_at", ""),
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
        st.caption(
            f"{finding['owasp']} · found {finding['count']} {times} "
            f"(simulation {seen})"
        )
        st.markdown(f"**What happened**\n\n{finding['description']}")
        st.success(f"**How to fix it**\n\n{finding['recommendation']}")


def run_webhook_scope_test(webhook_url, auth_token):
    """Run the low-friction scope boundary probe against a merchant endpoint."""
    response = api_post(
        API_BASE_URL,
        "/integrations/webhook/test",
        json={
            "webhook_url": webhook_url,
            "auth_token": auth_token or None,
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(response.text)
    return response.json()


def render(simulations_data):
    st.subheader("🏪 Merchant Security View")
    st.markdown("### Choose a security assessment")
    st.caption(
        "Start with the full assessment for broad coverage, or choose a category "
        "when you want to investigate one risk area."
    )
    merchant_col1, merchant_col2 = st.columns([2, 1])
    with merchant_col1:
        assessment_mode = st.radio(
            "Assessment type",
            options=["Full Security Assessment", "Focused Test", "Pick specific tests"],
            horizontal=True,
            key="merchant_assessment_mode",
            help=(
                "Full runs every test. Focused runs one risk category. "
                "Pick specific tests lets you choose exactly which tests to run."
            ),
        )
    with merchant_col2:
        merchant_turns = st.number_input(
            "Conversation turns",
            min_value=1,
            max_value=5,
            value=3,
            step=1,
            key="merchant_simulation_turns",
        )

    render_target_form()
    targets = fetch_targets()
    render_target_manager(targets)
    target_options = [None] + [t["target_id"] for t in targets]
    target_names = {t["target_id"]: f"{t['name']} ({t['webhook_url']})" for t in targets}
    selected_target = st.selectbox(
        "Attack target",
        options=target_options,
        format_func=lambda tid: target_names.get(tid, "Built-in Defender (simulator)"),
        key="merchant_target",
    )

    selected_category = None
    if assessment_mode == "Focused Test":
        selected_category = st.selectbox(
            "Risk category",
            options=get_categories(),
            key="merchant_security_category",
        )

    has_target = selected_target is not None
    if assessment_mode == "Pick specific tests":
        # Offer every runnable test and let the user choose which ones to run.
        pickable = scenarios_for_target(get_scenarios(), has_target=has_target)
        all_names = [scenario.name for scenario in pickable]
        chosen_names = st.multiselect(
            "Choose the tests to run",
            options=all_names,
            default=all_names,
            key="merchant_selected_tests",
            help="Each selected test is one simulation run against the target.",
        )
        scenarios = select_scenarios(
            "pick", has_target=has_target, chosen_names=chosen_names
        )
    elif assessment_mode == "Focused Test":
        scenarios = select_scenarios(
            "focused", has_target=has_target, category=selected_category
        )
    else:
        scenarios = select_scenarios("full", has_target=has_target)

    st.markdown("#### Included simulator scenarios")
    if not scenarios:
        if assessment_mode == "Pick specific tests":
            st.info("Select at least one test above to run.")
        else:
            st.info("This category is available through the connected chatbot webhook below.")
    st.dataframe(
        [
            {
                "Scenario": scenario.name,
                "Category": scenario.category,
                "What it checks": scenario.description,
                "Severity": scenario.severity.upper(),
            }
            for scenario in scenarios
        ],
        width="stretch",
        hide_index=True,
    )
    # Each scenario is one run; with an LLM provider that is one attacker call
    # per turn plus a judge call, so warn before launching several at once.
    if len(scenarios) > 1:
        st.caption(
            f"⚠️ This will run **{len(scenarios)} tests** ({len(scenarios)} simulation "
            f"runs). If your attacker/judge use an LLM provider, each run consumes "
            f"API tokens — pick fewer tests or lower the turns to spend less."
        )
    run_merchant_test = st.button(
        "🚀 Run security assessment",
        type="primary",
        width="stretch",
        disabled=not scenarios,
    )

    if run_merchant_test:
        # Run each scenario independently: one failing test (e.g. the target
        # was asleep and timed out) must NOT abort the remaining tests.
        progress = st.progress(0.0)
        batch_run_ids = []

        def _run_one(scenario, _ids=batch_run_ids):
            with st.spinner(f"Running '{scenario.name}'..."):
                result = run_security_test(
                    scenario.strategy, int(merchant_turns), selected_target
                )
                # Remember the run id so we can build a combined report.
                if result.get("run_id"):
                    _ids.append(result["run_id"])
                return result

        per_test = []
        for index, scenario in enumerate(scenarios):
            per_test.extend(collect_scenario_results([scenario], _run_one))
            progress.progress((index + 1) / len(scenarios))

        breached = sum(1 for r in per_test if r["outcome"] == "BREACHED")
        errored = sum(1 for r in per_test if r["outcome"] == "ERROR")
        st.session_state["last_manual_test"] = {
            "scenario_count": len(per_test),
            "breached_count": breached,
            "error_count": errored,
            "per_test": per_test,
            "run_ids": batch_run_ids,
        }
        fetch_all_simulations.clear()
        st.rerun()

    if "last_manual_test" in st.session_state:
        last_test = st.session_state["last_manual_test"]
        st.info(
            f"Last assessment: {last_test['scenario_count']} test(s), "
            f"{last_test['breached_count']} breach(es)"
            + (
                f", {last_test['error_count']} could not run"
                if last_test.get("error_count")
                else ""
            )
            + "."
        )
        # Per-test breakdown so a failed test is visible, not hidden behind the
        # others.
        for result in last_test.get("per_test", []):
            icon = {"BREACHED": "🔴", "SECURED": "🟢", "ERROR": "⚠️"}.get(
                result["outcome"], "•"
            )
            if result["outcome"] == "ERROR":
                st.warning(
                    f"{icon} **{result['name']}** could not run: {result['error']}"
                )
            else:
                st.write(f"{icon} **{result['name']}** — {result['outcome']}")
        if last_test["breached_count"]:
            st.warning("One or more tests produced a breach.")

        # Combined report: one document for every test in this assessment.
        batch_ids = last_test.get("run_ids", [])
        if batch_ids:
            all_sims = {
                s.get("run_id"): s
                for s in fetch_all_simulations()
                if s.get("run_id")
            }
            batch_runs = [all_sims[rid] for rid in batch_ids if rid in all_sims]
            if batch_runs:
                combined_lang_col, combined_btn_col = st.columns([1, 2])
                combined_lang = combined_lang_col.selectbox(
                    "Report language",
                    options=["en", "es"],
                    format_func={"en": "English", "es": "Español"}.get,
                    key="combined_report_lang",
                )
                combined_btn_col.download_button(
                    "⬇️ Download combined report (all tests, print to PDF)",
                    data=render_combined_report(batch_runs, combined_lang),
                    file_name=f"assessment-report-{combined_lang}.html",
                    mime="text/html",
                )

    st.markdown("---")
    st.markdown("### 🔌 Connected chatbot test")
    st.caption(
        "Connect a staging chatbot without sharing its code or database. "
        "The platform sends a versioned scope-boundary probe."
    )
    webhook_col1, webhook_col2 = st.columns([2, 1])
    webhook_url = webhook_col1.text_input(
        "Staging webhook URL",
        placeholder="https://staging.example.com/agent",
        key="merchant_webhook_url",
    )
    webhook_token = webhook_col2.text_input(
        "Bearer token (optional)",
        type="password",
        key="merchant_webhook_token",
    )
    if st.button("🔎 Test connected chatbot scope", width="stretch"):
        if not webhook_url:
            st.error("Enter a staging webhook URL first.")
        else:
            with st.spinner("Testing connected chatbot scope..."):
                try:
                    webhook_result = run_webhook_scope_test(
                        webhook_url,
                        webhook_token,
                    )
                    if webhook_result["status"] == "failed":
                        st.error(webhook_result.get("error", "Webhook test failed."))
                    elif webhook_result["breached"]:
                        st.error("The connected chatbot answered outside its store scope.")
                        st.json(webhook_result)
                    else:
                        st.success("The connected chatbot stayed within its store scope.")
                        st.json(webhook_result)
                except Exception as error:
                    st.error(f"Connected chatbot test failed: {error}")

    merchant_report = build_merchant_report(simulations_data)
    findings = group_findings(build_findings(simulations_data))

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

    latest = merchant_report["latest_simulation"]
    if latest:
        st.markdown(
            f"**Latest test:** Simulation #{latest.get('simulation_number')} "
            f"({latest.get('session_id')})"
        )
    render_test_run_history(simulations_data)
