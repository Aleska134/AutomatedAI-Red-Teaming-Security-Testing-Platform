import os
import sys
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.frontend_auth import (  # noqa: E402 - needs sys.path tweak above
    api_get,
    api_post,
    current_role,
    is_authenticated,
    render_admin_panel,
    render_auth_gate,
    render_sidebar_profile,
)
from app.services.merchant_reporting import (  # noqa: E402
    build_findings,
    build_merchant_report,
    summarize_finding_rules,
)
from app.services.owasp import owasp_label  # noqa: E402
from app.services.run_report import render_run_report  # noqa: E402
from app.services.security_scenarios import get_categories, get_scenarios  # noqa: E402

# Configure the core Streamlit page parameters
st.set_page_config(
    page_title="Automated AI Red Teaming Platform",
    page_icon="🛡️",
    layout="wide"
)

API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000/api/v1",
).rstrip("/")

# Authentication gate: unauthenticated users see sign in / create account /
# forgot password, and the rest of the dashboard does not render.
if not is_authenticated():
    render_auth_gate(API_BASE_URL)

render_sidebar_profile(API_BASE_URL)

st.title("🛡️ Merchant AI Security Center")
st.markdown("---")

# -------------------------------------------------------------------
# FETCH DATA FROM BACKEND API
# -------------------------------------------------------------------
@st.cache_data(ttl=2)  # Cache updates quickly to allow fast iteration
def fetch_all_simulations(_token: str):
    """Queries FastAPI to pull simulation logs visible to the signed-in user.

    The token is part of the cache key so switching accounts refreshes data.
    """
    try:
        response = api_get(API_BASE_URL, "/simulations", timeout=30)
        if response.status_code == 200:
            return response.json().get("data", [])
        return []
    except Exception:
        return []


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


def run_security_test(strategy, turns, poll_interval=2, max_wait=300):
    """Queue one security test, then poll its run until it finishes."""
    response = api_post(
        API_BASE_URL,
        "/simulation/loop",
        json={"turns": turns, "strategy": strategy, "history": []},
        timeout=30,
    )
    if response.status_code != 202:
        raise RuntimeError(response.text)
    run_id = response.json()["run_id"]

    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        time.sleep(poll_interval)
        response = api_get(API_BASE_URL, f"/test-runs/{run_id}", timeout=30)
        if response.status_code != 200:
            raise RuntimeError(response.text)
        run = response.json()
        if run["status"] == "completed":
            return {**run, "is_breached": run.get("breached", False)}
        if run["status"] == "failed":
            raise RuntimeError(run.get("error") or "The security test failed.")
    raise RuntimeError(f"Test run {run_id} is still running; check the history later.")


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


def render_tool_events(tool_events):
    """Render auditable commerce tool calls for a selected simulation."""
    st.markdown("#### 🔧 Commerce Tool Events")
    if not tool_events:
        st.caption("No commerce tool calls were recorded for this simulation.")
        return

    event_rows = []
    for event in tool_events:
        event_rows.append(
            {
                "Tool": event.get("tool_name", "unknown"),
                "Customer": event.get("customer_id", "unknown"),
                "Status": "✅ Success" if event.get("success") else "❌ Rejected",
                "Checkout authorized": (
                    "Yes" if event.get("checkout_allowed") else "No"
                ),
                "Error": event.get("error") or "",
                "Timestamp": event.get("timestamp", ""),
            }
        )
    st.dataframe(event_rows, width="stretch", hide_index=True)

    for index, event in enumerate(tool_events, start=1):
        with st.expander(
            f"{index}. {event.get('tool_name', 'unknown')} "
            f"({'success' if event.get('success') else 'rejected'})"
        ):
            st.json(
                {
                    "arguments": event.get("arguments", {}),
                    "result_status": "success"
                    if event.get("success")
                    else "rejected",
                    "error": event.get("error"),
                    "checkout_allowed": event.get("checkout_allowed", False),
                    "timestamp": event.get("timestamp"),
                }
            )


simulations_data = fetch_all_simulations(st.session_state.get("access_token", ""))

# -------------------------------------------------------------------
# MAIN DASHBOARD PANELS
# -------------------------------------------------------------------
_base_tabs = [
    "📊 Analytics Dashboard",
    "💬 Conversation Logs Explorer",
    "🏪 Merchant Security View",
    "🧪 System Specs",
]
_is_admin = current_role() == "admin"
_tab_labels = _base_tabs + (["🏢 Admin"] if _is_admin else [])
_tabs = st.tabs(_tab_labels)
tab1, tab2, tab3, tab4 = _tabs[0], _tabs[1], _tabs[2], _tabs[3]
admin_tab = _tabs[4] if _is_admin else None

with tab1:
    st.subheader("📊 Security Analytics Summary")
    
    # Only completed runs carry audit metrics; queued/failed runs (e.g. from an
    # interrupted or provider-less simulation) are skipped in analytics.
    completed_runs = [
        record
        for record in simulations_data
        if record.get("status") == "completed" or "breached" in record
    ]

    if not simulations_data:
        st.info("No logs detected in local database. Run your first simulation from the sidebar control panel!")
    elif not completed_runs:
        st.info(
            "Simulations exist but none have completed yet. Run a completed "
            "simulation to populate the analytics charts."
        )
    else:
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
            len(record.get("tool_events", [])) for record in completed_runs
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
            st.markdown("### Compliance Breach Status")
            fig_pie = px.pie(
                df, 
                names='breached', 
                color='breached',
                color_discrete_map={True: '#EF553B', False: '#636EFA'},
                labels={'breached': 'Is Breached'},
                hole=0.4
            )
            st.plotly_chart(fig_pie, width="stretch")
            
        with col_g2:
            st.markdown("### Attacker Aggression Trends over Time")
            fig_line = px.line(
                df.sort_values(by="simulation_number"),
                x='simulation_number', 
                y='attacker_aggression_level', 
                markers=True,
                labels={'simulation_number': 'Simulation ID', 'attacker_aggression_level': 'Aggression Score (1-5)'},
                title="Adversarial Aggression Volatility"
            )
            st.plotly_chart(fig_line, width="stretch")

with tab2:
    st.subheader("💬 Session Transcript Records")
    
    # Only completed runs have a transcript and audit metrics to inspect.
    transcript_records = [
        record
        for record in simulations_data
        if record.get("simulation_number") is not None and "history" in record
    ]
    if not transcript_records:
        st.info("No completed transcripts available yet.")
    else:
        df_logs = pd.DataFrame(transcript_records).sort_values(
            by="simulation_number", ascending=False
        )

        # Numbers restart per company (admins see several "#1"), so select by
        # the unique session ID and show the owning company when available.
        def _session_label(record):
            company = f" · {record['company_name']}" if record.get("company_name") else ""
            number = int(float(record["simulation_number"]))
            return f"Simulation #{number}{company} (ID: {record['session_id']})"

        records_by_id = {item["session_id"]: item for item in transcript_records}
        selected_session_id = st.selectbox(
            "Select a security log to inspect:",
            options=list(df_logs["session_id"]),
            format_func=lambda session_id: _session_label(records_by_id[session_id]),
        )
        selected_record = records_by_id[selected_session_id]
        selected_sim_num = int(float(selected_record["simulation_number"]))

        # Render Audit Report metadata block
        st.markdown(f"#### 🧑‍⚖️ Auditor Report Summary for Simulation #{selected_sim_num}")
        c_a, c_b, c_c = st.columns(3)
        if selected_record.get("breached"):
            status_color = "🔴 BREACHED"
        elif selected_record.get("conclusive") is False:
            status_color = "⚪ INCONCLUSIVE — " + str(selected_record.get("inconclusive_reason", ""))
        else:
            status_color = "🟢 SECURED"
        c_a.markdown(f"**Compliance Status:** {status_color}")
        c_b.markdown(f"**Attacker Aggression Level:** `{selected_record.get('attacker_aggression_level', 1)}/5`")
        c_c.markdown(f"**Defense Efficiency Score:** `{selected_record.get('defense_efficiency_score', 10)}/10`")
        
        lang_col, button_col = st.columns([1, 2])
        report_lang = lang_col.selectbox(
            "Report language", options=["en", "es"],
            format_func={"en": "English", "es": "Español"}.get,
        )
        button_col.download_button(
            "⬇️ Download report (HTML, print to PDF)",
            data=render_run_report(selected_record, report_lang),
            file_name=f"report-{selected_record['session_id']}-{report_lang}.html",
            mime="text/html",
        )

        st.info(f"**Technical Audit Analysis:**\n{selected_record.get('analysis', 'No analysis available.')}")
        st.caption(f"Keywords Flagged: {', '.join(selected_record.get('attack_vector_keywords', []))}")

        if selected_record.get("deterministic_breach"):
            st.error("Deterministic security evidence confirms a rule violation.")
        else:
            st.success("No deterministic rule violation was found.")

        evidence = selected_record.get("evidence", [])
        if evidence:
            st.markdown("#### 🚨 Deterministic Evidence")
            st.dataframe(
                [
                    {
                        "Rule": item.get("rule", "unknown"),
                        "Severity": item.get("severity", "unknown").upper(),
                        "OWASP": owasp_label(item.get("rule", "")),
                        "Description": item.get("description", ""),
                    }
                    for item in evidence
                ],
                width="stretch",
                hide_index=True,
            )

        render_tool_events(selected_record.get("tool_events", []))

        defense_outcomes = selected_record.get("defense_outcomes", [])
        if defense_outcomes:
            st.markdown("#### 🛡️ Defense Outcomes")
            st.dataframe(
                [
                    {
                        "Security outcome": item.get("security_outcome", "unknown"),
                        "Block reason": item.get("block_reason", "unknown"),
                        "Interaction quality": item.get(
                            "interaction_quality", "unknown"
                        ),
                        "Business behavior": item.get(
                            "business_behavior", "unknown"
                        ),
                    }
                    for item in defense_outcomes
                ],
                width="stretch",
                hide_index=True,
            )

        attack_events = selected_record.get("attack_generation_events", [])
        if attack_events:
            st.markdown("#### ⚔️ Attack Generation Sources")
            st.dataframe(
                [
                    {
                        "Turn": event.get("turn", ""),
                        "Status": event.get("status", "unknown"),
                        "Source": event.get("source", "unknown"),
                        "Provider message": event.get("provider_message") or "",
                    }
                    for event in attack_events
                ],
                width="stretch",
                hide_index=True,
            )
        
        st.markdown("#### 💬 Dialogue Transcript")
        # Paint the dialogue elements dynamically using chat blocks
        for message in selected_record["history"]:
            if message["role"] == "user":
                with st.chat_message("user", avatar="⚔️"):
                    st.write(message["content"])
            else:
                with st.chat_message("assistant", avatar="🛡️"):
                    st.write(message["content"])

with tab3:
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
            options=["Full Security Assessment", "Focused Test"],
            horizontal=True,
            key="merchant_assessment_mode",
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

    selected_category = None
    if assessment_mode == "Focused Test":
        selected_category = st.selectbox(
            "Risk category",
            options=get_categories(),
            key="merchant_security_category",
        )

    scenarios = [
        scenario
        for scenario in get_scenarios(selected_category)
        if getattr(scenario, "execution_mode", "simulator") == "simulator"
    ]
    st.markdown("#### Included simulator scenarios")
    if not scenarios:
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
    run_merchant_test = st.button(
        "🚀 Run security assessment",
        type="primary",
        width="stretch",
    )

    if run_merchant_test:
        with st.spinner(f"Running {len(scenarios)} security scenario(s)..."):
            try:
                results = [
                    run_security_test(scenario.strategy, int(merchant_turns))
                    for scenario in scenarios
                ]
                breached = sum(result.get("is_breached", False) for result in results)
                st.session_state["last_manual_test"] = {
                    "scenario_count": len(results),
                    "breached_count": breached,
                    "status": "BREACHED" if breached else "SECURED",
                }
                fetch_all_simulations.clear()
                st.rerun()
            except Exception as error:
                st.error(f"Security test failed: {error}")

    if "last_manual_test" in st.session_state:
        last_test = st.session_state["last_manual_test"]
        st.info(
            f"Last assessment: {last_test['scenario_count']} scenario(s), "
            f"{last_test['breached_count']} breach(es), status: "
            f"{last_test['status']}."
        )
        if last_test["breached_count"]:
            st.warning("The last assessment produced one or more breaches.")

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
    findings = build_findings(simulations_data)

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
        st.dataframe(
            [
                {
                    "Simulation": finding["simulation_number"],
                    "Severity": finding["severity"].upper(),
                    "Rule": finding["rule"],
                    "OWASP": finding["owasp"],
                    "Description": finding["description"],
                    "Recommendation": finding["recommendation"],
                }
                for finding in findings
            ],
            width="stretch",
            hide_index=True,
        )

        st.markdown("### Findings by rule")
        st.bar_chart(
            pd.DataFrame(summarize_finding_rules(findings)),
            x="rule",
            y="count",
        )

    latest = merchant_report["latest_simulation"]
    if latest:
        st.markdown(
            f"**Latest test:** Simulation #{latest.get('simulation_number')} "
            f"({latest.get('session_id')})"
        )
    render_test_run_history(simulations_data)

with tab4:
    st.subheader("🧪 Operational Environment Blueprint")
    st.markdown("""
    This control panel interface hooks straight into an optimized backend execution layers:
    - **Backend Engine:** FastAPI REST Architecture (`Uvicorn`)
    - **Data Persistence:** SQL database via SQLModel (SQLite locally, Postgres in production)
    - **Defense Matrix:** 3-Layer Input Filtering (Static Signature + Semantic Intent Firewall + Hardened Prompts)
    - **Red Team Matrix:** Multi-Turn Adaptive Prompt Injection LLM Generator
    """)


if admin_tab is not None:
    with admin_tab:
        render_admin_panel(API_BASE_URL)
