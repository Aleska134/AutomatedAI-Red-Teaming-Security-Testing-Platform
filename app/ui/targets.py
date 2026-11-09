"""Registering, editing and deleting the chatbots (targets) a company tests."""


import streamlit as st

from app.frontend_auth import (
    api_delete,
    api_patch,
    api_post,
    humanize_error,
)
from app.ui.common import API_BASE_URL


def _split_list(raw):
    """Comma-separated text field -> list of non-empty values."""
    return [item.strip() for item in raw.split(",") if item.strip()]


def _join_list(values):
    """List of values -> comma-separated text for a pre-filled input."""
    return ", ".join(values) if values else ""


def delete_target_request(target_id: str):
    """Delete a saved target by id. Returns the HTTP response."""
    return api_delete(API_BASE_URL, f"/targets/{target_id}", timeout=30)


def render_target_fields_help():
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
    render_target_fields_help()
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
        render_target_fields_help()
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
