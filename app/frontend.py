import sys
import os
from pathlib import Path

import streamlit as st
import requests
import pandas as pd
import plotly.express as px

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.merchant_reporting import (
    build_findings,
    build_merchant_report,
    summarize_finding_rules,
)
from app.services.security_scenarios import get_categories, get_scenarios

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

st.title("🛡️ Merchant AI Security Center")
st.markdown("---")

# -------------------------------------------------------------------
# FETCH DATA FROM BACKEND API
# -------------------------------------------------------------------
@st.cache_data(ttl=2)  # Cache updates quickly to allow fast iteration
def fetch_all_simulations():
    """Queries FastAPI to pull all local JSON history logs."""
    try:
        response = requests.get(f"{API_BASE_URL}/simulations")
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


def run_security_test(strategy, turns):
    """Run one merchant-requested security test through the existing API."""
    response = requests.post(
        f"{API_BASE_URL}/simulation/loop",
        json={"turns": turns, "strategy": strategy, "history": []},
        timeout=180,
    )
    if response.status_code != 200:
        raise RuntimeError(response.text)
    return response.json()


def run_webhook_scope_test(webhook_url, auth_token):
    """Run the low-friction scope boundary probe against a merchant endpoint."""
    response = requests.post(
        f"{API_BASE_URL}/integrations/webhook/test",
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


simulations_data = fetch_all_simulations()

# -------------------------------------------------------------------
# MAIN DASHBOARD PANELS
# -------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "📊 Analytics Dashboard",
        "💬 Conversation Logs Explorer",
        "🏪 Merchant Security View",
        "🧪 System Specs",
    ]
)

with tab1:
    st.subheader("📊 Security Analytics Summary")
    
    if not simulations_data:
        st.info("No logs detected in local database. Run your first simulation from the sidebar control panel!")
    else:
        # Convert JSON objects into a Pandas DataFrame for swift graphing metrics
        df = pd.DataFrame(simulations_data)
        
        # Calculate summary numbers
        total_runs = len(df)
        breached_count = df['breached'].sum()
        secured_count = total_runs - breached_count
        avg_defense = df['defense_efficiency_score'].mean()
        deterministic_breaches = int(
            df.get("deterministic_breach", pd.Series(False, index=df.index)).fillna(False).sum()
        )
        tool_event_count = sum(
            len(record.get("tool_events", [])) for record in simulations_data
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
                df, 
                x='simulation_number', 
                y='attacker_aggression_level', 
                markers=True,
                labels={'simulation_number': 'Simulation ID', 'attacker_aggression_level': 'Aggression Score (1-5)'},
                title="Adversarial Aggression Volatility"
            )
            st.plotly_chart(fig_line, width="stretch")

with tab2:
    st.subheader("💬 Session Transcript Records")
    
    if not simulations_data:
        st.info("No recorded transcripts available yet.")
    else:
        df_logs = pd.DataFrame(simulations_data).sort_values(by="simulation_number", ascending=False)
        
        # Build a drop-down menu matching our chronological numbering indexes
        session_options = [f"Simulation #{int(float(row['simulation_number']))} (ID: {row['session_id']})" for _, row in df_logs.iterrows()]
        selected_session_str = st.selectbox("Select a security log to inspect:", options=session_options)
        
        # Extract selected session number integer from string selection
        selected_sim_num = int(float(selected_session_str.split("#")[1].split(" ")[0]))
        selected_record = next(item for item in simulations_data if item["simulation_number"] == selected_sim_num)
        
        # Render Audit Report metadata block
        st.markdown(f"#### 🧑‍⚖️ Auditor Report Summary for Simulation #{selected_sim_num}")
        c_a, c_b, c_c = st.columns(3)
        status_color = "🔴 BREACHED" if selected_record["breached"] else "🟢 SECURED"
        c_a.markdown(f"**Compliance Status:** {status_color}")
        c_b.markdown(f"**Attacker Aggression Level:** `{selected_record['attacker_aggression_level']}/5`")
        c_c.markdown(f"**Defense Efficiency Score:** `{selected_record['defense_efficiency_score']}/10`")
        
        st.info(f"**Technical Audit Analysis:**\n{selected_record['analysis']}")
        st.caption(f"Keywords Flagged: {', '.join(selected_record['attack_vector_keywords'])}")

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
    - **Data Persistence:** TinyDB Local Document JSON Engine (`local_db.json`)
    - **Defense Matrix:** 3-Layer Input Filtering (Static Signature + Semantic Intent Firewall + Hardened Prompts)
    - **Red Team Matrix:** Multi-Turn Adaptive Prompt Injection LLM Generator
    """)