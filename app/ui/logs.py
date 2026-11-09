"""Conversation logs tab: transcripts, evidence and per-run or combined reports."""


import pandas as pd
import streamlit as st

from app.services.batch_runner import (
    can_combine_runs,
    target_display_name,
)
from app.services.owasp import owasp_label
from app.services.run_report import (
    render_combined_report,
    render_run_report,
)
from app.services.safe_data import as_int, as_records
from app.services.security_scenarios import (
    friendly_test_name,
    strategy_explanation,
)
from app.ui.common import fetch_targets


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


def render(simulations_data):
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
            number = as_int(record["simulation_number"])
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
        selected_sim_num = as_int(selected_record["simulation_number"])

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

        evidence = as_records(selected_record.get("evidence"))
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

        render_tool_events(as_records(selected_record.get("tool_events")))

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
        for message in as_records(selected_record.get("history")):
            if message["role"] == "user":
                with st.chat_message("user", avatar="⚔️"):
                    st.write(message["content"])
            else:
                with st.chat_message("assistant", avatar="🛡️"):
                    st.write(message["content"])
