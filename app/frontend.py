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
    api_delete,
    api_get,
    api_patch,
    api_post,
    current_role,
    humanize_error,
    is_authenticated,
    render_admin_panel,
    render_auth_gate,
    render_sidebar_profile,
)
from app.services.batch_runner import (  # noqa: E402
    can_combine_runs,
    collect_scenario_results,
    target_display_name,
)
from app.services.merchant_reporting import (  # noqa: E402
    build_findings,
    build_merchant_report,
    conclusive_runs,
    finished_runs,
    group_findings,
)
from app.services.owasp import owasp_label  # noqa: E402
from app.services.run_report import (  # noqa: E402
    render_combined_report,
    render_run_report,
)
from app.services.security_scenarios import (  # noqa: E402
    friendly_test_name,
    get_categories,
    get_scenarios,
    scenarios_for_target,
    select_scenarios,
    strategy_explanation,
)

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


SEVERITY_COLORS = {"CRITICAL": "#b42318", "HIGH": "#ef6820", "MEDIUM": "#f79009", "LOW": "#98a2b3"}


def style_chart(fig, height=280):
    """Compact, transparent layout shared by every dashboard chart."""
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, x=0, title_text=""),
        font=dict(size=12),
    )
    return fig


def run_security_test(strategy, turns, target_id=None, poll_interval=2, max_wait=300):
    """Queue one security test, then poll its run until it finishes."""
    payload = {"turns": turns, "strategy": strategy, "history": []}
    if target_id:
        payload["target_id"] = target_id
    response = api_post(API_BASE_URL, "/simulation/loop", json=payload, timeout=30)
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


def _split_list(raw):
    """Comma-separated text field -> list of non-empty values."""
    return [item.strip() for item in raw.split(",") if item.strip()]


def fetch_targets():
    response = api_get(API_BASE_URL, "/targets", timeout=30)
    return response.json() if response.status_code == 200 else []


def _join_list(values):
    """List of values -> comma-separated text for a pre-filled input."""
    return ", ".join(values) if values else ""


def delete_target_request(target_id: str):
    """Delete a saved target by id. Returns the HTTP response."""
    return api_delete(API_BASE_URL, f"/targets/{target_id}", timeout=30)


def _render_target_fields_help():
    """Plain-language help for the target fields, for non-technical users."""
    with st.expander("❓ How do I fill this in?"):
        st.markdown(
            """
**Name** — any label you want, so you can recognize this chatbot later.

**Webhook URL** — the address where your chatbot receives messages
(it should start with `https://`).

**Bearer token** — a secret key some chatbots require. If your chatbot does
not need one, leave it empty.

**Valid coupons** — the discount codes your store really offers. Type as many
as you like, **separated by commas**. Example: `TECH10, SAVE20, WELCOME15`.

**Max discount %** — the highest discount your chatbot is allowed to give.

**Forbidden actions** — things your chatbot should never do, **separated by
commas**. Example: `issue_refund, change_price`.

**Protected values** — private details that should never appear in a reply
(like another customer's email or an internal code), **separated by commas**.
            """
        )


def _business_rules_inputs(prefix, *, coupons="", max_discount=10, forbidden="", protected=""):
    """Shared business-rule inputs for the create and edit forms."""
    st.caption("Business rules (optional, comma-separated)")
    coupons_in = st.text_input(
        "Valid coupons", value=coupons, placeholder="TECH10, SAVE20", key=f"{prefix}-coupons"
    )
    max_in = st.number_input("Max discount %", 0, 100, int(max_discount), key=f"{prefix}-maxd")
    forbidden_in = st.text_input(
        "Forbidden actions", value=forbidden,
        placeholder="issue_refund, change_price", key=f"{prefix}-forbidden",
    )
    protected_in = st.text_input(
        "Protected values (canaries)", value=protected,
        placeholder="jordan.demo@techmart.local, CNRY-8841", key=f"{prefix}-protected",
    )
    return {
        "valid_coupons": _split_list(coupons_in) or None,
        "max_discount_percent": int(max_in),
        "forbidden_actions": _split_list(forbidden_in),
        "protected_values": _split_list(protected_in),
    }


def render_target_manager(targets):
    """List saved targets, each with Edit and Delete controls."""
    if not targets:
        return
    with st.expander("🗂️ Manage saved targets"):
        st.caption("Edit a target (for example, add more coupons) or remove duplicates.")
        for target in targets:
            tid = target["target_id"]
            left, mid, right = st.columns([5, 1, 1])
            left.markdown(f"**{target['name']}**")
            left.caption(target["webhook_url"])
            if mid.button("Edit", key=f"edit-btn-{tid}"):
                # Toggle an inline edit form for this target.
                st.session_state[f"editing-{tid}"] = not st.session_state.get(
                    f"editing-{tid}", False
                )
            if right.button("Delete", key=f"del-{tid}"):
                response = delete_target_request(tid)
                if response.status_code == 204:
                    st.success(f"Deleted '{target['name']}'.")
                    st.rerun()
                else:
                    st.error(humanize_error(response, "Could not delete target."))

            if st.session_state.get(f"editing-{tid}", False):
                _render_edit_target_form(target)


def _render_edit_target_form(target):
    """Inline form to edit an existing target, pre-filled with its values."""
    tid = target["target_id"]
    rules = target.get("business_rules") or {}
    _render_target_fields_help()
    with st.form(f"edit_target_{tid}"):
        name = st.text_input("Name", value=target["name"], key=f"{tid}-name")
        url = st.text_input("Webhook URL", value=target["webhook_url"], key=f"{tid}-url")
        token = st.text_input("Bearer token", type="password", key=f"{tid}-token")
        # The token note is always visible because clearing it can break auth.
        if target.get("has_auth_token"):
            st.caption(
                "🔑 Leave the token empty to keep the current one. "
                "Type a new value only if you want to replace it."
            )
            clear_token = st.checkbox(
                "Remove the saved token (send requests without authentication)",
                key=f"{tid}-cleartoken",
            )
        else:
            st.caption("🔑 This target has no saved token. Add one only if your chatbot needs it.")
            clear_token = False
        rules_payload = _business_rules_inputs(
            tid,
            coupons=_join_list(rules.get("valid_coupons")),
            max_discount=rules.get("max_discount_percent") or 10,
            forbidden=_join_list(rules.get("forbidden_actions")),
            protected=_join_list(rules.get("protected_values")),
        )
        if st.form_submit_button("Save changes"):
            payload = {
                "name": name,
                "webhook_url": url,
                "auth_token": token or None,
                "clear_auth_token": clear_token,
                "business_rules": rules_payload,
            }
            response = api_patch(API_BASE_URL, f"/targets/{tid}", json=payload, timeout=30)
            if response.status_code == 200:
                st.success(f"Updated '{name}'.")
                st.session_state[f"editing-{tid}"] = False
                st.rerun()
            else:
                st.error(humanize_error(response, "Could not update target."))


def render_target_form():
    """Register an external chatbot (webhook) with its business rules."""
    with st.expander("➕ Register a chatbot target"):
        _render_target_fields_help()
        with st.form("create_target", clear_on_submit=True):
            name = st.text_input("Name", placeholder="TechMart weak")
            url = st.text_input(
                "Webhook URL",
                placeholder="https://your-chatbot.onrender.com/api/v1/chat",
            )
            token = st.text_input("Bearer token (optional)", type="password")
            st.caption("🔑 Only needed if your chatbot requires one. You can edit or add it later.")
            rules_payload = _business_rules_inputs("create")
            if st.form_submit_button("Save target"):
                payload = {
                    "name": name,
                    "webhook_url": url,
                    "auth_token": token or None,
                    "business_rules": rules_payload,
                }
                response = api_post(API_BASE_URL, "/targets", json=payload, timeout=30)
                if response.status_code == 201:
                    st.success(f"Target '{name}' saved.")
                else:
                    st.error(humanize_error(response, "Could not save target."))


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
    # Inconclusive runs (e.g. provider outage) are not evidence of a held defense.
    completed_runs = conclusive_runs(simulations_data)
    skipped_runs = len(finished_runs(simulations_data)) - len(completed_runs)

    if not simulations_data:
        st.info("No test runs yet. Open the 🏪 Merchant Security View tab and run your first assessment!")
    elif not completed_runs:
        st.info(
            "Simulations exist but none have completed yet. Run a completed "
            "simulation to populate the analytics charts."
        )
    else:
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

        # Numbers restart per company (admins see several "#1"), so the label
        # leads with the friendly test name so the user can tell runs apart at
        # a glance, and the company (for admins) disambiguates.
        def _session_label(record):
            company = f" · {record['company_name']}" if record.get("company_name") else ""
            number = int(float(record["simulation_number"]))
            test_name = friendly_test_name(record.get("strategy", "")) or "Test"
            return f"#{number} · {test_name}{company}"

        records_by_id = {item["session_id"]: item for item in transcript_records}

        # --- Build a combined report from saved runs ---------------------- #
        # Lets the user re-create a combined report any time from runs already
        # stored (so it is never lost after the next assessment). The runs must
        # belong to the SAME target: mixing chatbots in one summary would make
        # the counts meaningless. Comparing two chatbots is a separate, explicit
        # feature.
        with st.expander("📑 Build a combined report from saved tests"):
            st.caption(
                "Pick two or more tests of the **same chatbot** to download one "
                "report covering all of them."
            )

            # Fetch targets here: this tab renders before the tab where the
            # merchant view loads them, so we cannot rely on that variable.
            saved_targets = fetch_targets()
            target_names_by_id = {t["target_id"]: t["name"] for t in saved_targets}

            def _target_name(record):
                return target_display_name(record, target_names_by_id)

            chosen_ids = st.multiselect(
                "Tests to include",
                options=list(df_logs["session_id"]),
                format_func=lambda sid: (
                    f"{_session_label(records_by_id[sid])} — {_target_name(records_by_id[sid])}"
                ),
                key="combined_pick",
            )
            chosen_runs = [records_by_id[sid] for sid in chosen_ids]
            can_combine, reason = can_combine_runs(chosen_runs)
            if not can_combine and len(chosen_runs) < 2:
                st.info(reason)
            elif not can_combine:
                # Enforce same-chatbot rule, explicitly.
                st.warning(
                    reason + " Comparing two chatbots is a separate feature."
                )
            else:
                picked_lang_col, picked_btn_col = st.columns([1, 2])
                picked_lang = picked_lang_col.selectbox(
                    "Report language",
                    options=["en", "es"],
                    format_func={"en": "English", "es": "Español"}.get,
                    key="picked_combined_lang",
                )
                picked_btn_col.download_button(
                    f"⬇️ Download combined report ({len(chosen_runs)} tests)",
                    data=render_combined_report(chosen_runs, picked_lang),
                    file_name=f"assessment-report-{picked_lang}.html",
                    mime="text/html",
                )
        selected_session_id = st.selectbox(
            "Select a security log to inspect:",
            options=list(df_logs["session_id"]),
            format_func=lambda session_id: _session_label(records_by_id[session_id]),
        )
        selected_record = records_by_id[selected_session_id]
        selected_sim_num = int(float(selected_record["simulation_number"]))

        # Render Audit Report metadata block
        selected_strategy = selected_record.get("strategy", "")
        selected_test_name = friendly_test_name(selected_strategy) or "Test"
        st.markdown(
            f"#### 🧑‍⚖️ Auditor Report Summary — #{selected_sim_num}: {selected_test_name}"
        )
        selected_explanation = strategy_explanation(selected_strategy)
        if selected_explanation:
            st.caption(f"ℹ️ {selected_explanation}")
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
        st.dataframe(
            [
                {
                    "Seen in": ", ".join(f"#{n}" for n in finding["simulations"]),
                    "Times": finding["count"],
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
