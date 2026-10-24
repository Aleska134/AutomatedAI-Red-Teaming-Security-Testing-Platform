"""Streamlit authentication UI and authenticated HTTP helpers.

Keeps the login/registration/password flows and the admin panel out of the
main dashboard file. The design is intentionally sober: a single centered card
for signed-out users, and a compact profile section in the sidebar.
"""

import requests
import streamlit as st


# Friendly names for the fields the API validates, so messages never show a
# raw key like "company_name".
_FIELD_LABELS = {
    "email": "Email",
    "password": "Password",
    "new_password": "New password",
    "current_password": "Current password",
    "company_name": "Company name",
    "name": "Name",
    "webhook_url": "Webhook URL",
    "token": "Reset token",
    "status": "Status",
}


def _field_label(loc) -> str:
    """Human label for a Pydantic error location (e.g. ['body','password'])."""
    if not loc:
        return "This field"
    key = str(loc[-1])
    return _FIELD_LABELS.get(key, key.replace("_", " ").capitalize())


def _friendly_validation_message(item: dict) -> str:
    """Plain-language message for one Pydantic validation error.

    Uses the stable error ``type`` (e.g. ``string_too_short``) rather than the
    technical ``msg`` so non-technical users never see words like "string" or
    "character". Falls back to a cleaned-up version of the raw message.
    """
    field = _field_label(item.get("loc"))
    err_type = str(item.get("type", ""))
    ctx = item.get("ctx") or {}
    minimum = ctx.get("min_length")

    if err_type == "missing":
        return f"{field} is required."
    if err_type == "string_too_short" and minimum in (None, 0, 1):
        return f"{field} is required."
    if err_type == "string_too_short":
        return f"{field} must be at least {minimum} characters long."
    if err_type == "string_too_long":
        maximum = ctx.get("max_length")
        return f"{field} must be {maximum} characters or fewer."
    if field == "Email":
        return "Please enter a valid email address."
    if field == "Webhook URL" or err_type.startswith("value_error.url"):
        return "Please enter a valid URL starting with http:// or https://."
    if err_type in ("int_parsing", "float_parsing", "int_type", "float_type"):
        return f"{field} must be a number."
    # Last resort: show the raw message but drop Pydantic's "Value error, " prefix.
    raw = str(item.get("msg", "")).replace("Value error, ", "").strip()
    return f"{field}: {raw}" if raw else f"{field} is not valid."


def humanize_error(response, fallback: str = "Something went wrong.") -> str:
    """Turn a FastAPI error response into a friendly, user-facing message.

    FastAPI returns ``detail`` as a plain string for HTTPExceptions, but as a
    list of validation error objects (422) such as
    ``[{"loc": ["body", "password"], "type": "string_too_short", ...}]``.
    Rendering that raw is confusing, so we translate each one into plain
    language a non-technical user can act on.
    """
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        return fallback
    if isinstance(detail, str) and detail.strip():
        return detail
    if isinstance(detail, list):
        messages, seen = [], set()
        for item in detail:
            if not isinstance(item, dict):
                continue
            message = _friendly_validation_message(item)
            if message not in seen:
                seen.add(message)
                messages.append(message)
        if messages:
            return "  ".join(messages)
    return fallback


def _auth_headers() -> dict:
    token = st.session_state.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def api_get(api_base_url: str, path: str, **kwargs):
    return requests.get(f"{api_base_url}{path}", headers=_auth_headers(), **kwargs)


def api_post(api_base_url: str, path: str, json: dict | None = None, **kwargs):
    return requests.post(
        f"{api_base_url}{path}", json=json, headers=_auth_headers(), **kwargs
    )


def api_delete(api_base_url: str, path: str, **kwargs):
    return requests.delete(f"{api_base_url}{path}", headers=_auth_headers(), **kwargs)


def is_authenticated() -> bool:
    return bool(st.session_state.get("access_token"))


def current_role() -> str:
    return st.session_state.get("role", "company")


def current_company() -> dict:
    return st.session_state.get("company", {})


def logout() -> None:
    for key in ("access_token", "role", "company"):
        st.session_state.pop(key, None)


def _store_session(payload: dict) -> None:
    st.session_state["access_token"] = payload["access_token"]
    st.session_state["role"] = payload.get("role", "company")
    st.session_state["company"] = payload.get("company", {})


def _login_form(api_base_url: str) -> None:
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", width="stretch")
    if submitted:
        try:
            response = requests.post(
                f"{api_base_url}/auth/login",
                json={"email": email, "password": password},
                timeout=30,
            )
        except Exception as error:  # noqa: BLE001
            st.error(f"Could not reach the server: {error}")
            return
        if response.status_code == 200:
            _store_session(response.json())
            st.rerun()
        else:
            st.error(humanize_error(response, "Sign in failed."))


def _register_form(api_base_url: str) -> None:
    st.caption(
        "New companies start in a pending state. An administrator activates "
        "your account before you can run security tests."
    )
    with st.form("register_form"):
        company_name = st.text_input("Company name")
        email = st.text_input("Work email")
        password = st.text_input("Password (min. 8 characters)", type="password")
        submitted = st.form_submit_button("Create account", width="stretch")
    if submitted:
        try:
            response = requests.post(
                f"{api_base_url}/auth/register",
                json={
                    "company_name": company_name,
                    "email": email,
                    "password": password,
                },
                timeout=30,
            )
        except Exception as error:  # noqa: BLE001
            st.error(f"Could not reach the server: {error}")
            return
        if response.status_code == 201:
            _store_session(response.json())
            st.success("Account created. Your company is pending activation.")
            st.rerun()
        else:
            st.error(humanize_error(response, "Registration failed."))


def _forgot_password_form(api_base_url: str) -> None:
    st.caption("Enter your email to receive a password reset token.")
    with st.form("forgot_form"):
        email = st.text_input("Email")
        submitted = st.form_submit_button("Send reset token", width="stretch")
    if submitted:
        try:
            response = requests.post(
                f"{api_base_url}/auth/forgot-password",
                json={"email": email},
                timeout=30,
            )
        except Exception as error:  # noqa: BLE001
            st.error(f"Could not reach the server: {error}")
            return
        data = response.json()
        st.info(data.get("message", "Request received."))
        # The API never returns the token; in development it is printed to the
        # backend log until an email service is wired in.
        st.caption("Local development: copy the token from the backend server log.")

    st.markdown("---")
    with st.form("reset_form"):
        token = st.text_input("Reset token")
        new_password = st.text_input("New password (min. 8 characters)", type="password")
        submitted = st.form_submit_button("Reset password", width="stretch")
    if submitted:
        try:
            response = requests.post(
                f"{api_base_url}/auth/reset-password",
                json={"token": token, "new_password": new_password},
                timeout=30,
            )
        except Exception as error:  # noqa: BLE001
            st.error(f"Could not reach the server: {error}")
            return
        if response.status_code == 200:
            st.success("Password reset. You can sign in now.")
        else:
            st.error(humanize_error(response, "Reset failed."))


def render_auth_gate(api_base_url: str) -> None:
    """Render the signed-out screen and stop the app until authenticated."""
    st.title("🛡️ Merchant AI Security Center")
    st.caption("Sign in to run automated AI red-teaming tests against your chatbot.")
    _, center, _ = st.columns([1, 2, 1])
    with center:
        sign_in, create, recover = st.tabs(["Sign in", "Create account", "Forgot password"])
        with sign_in:
            _login_form(api_base_url)
        with create:
            _register_form(api_base_url)
        with recover:
            _forgot_password_form(api_base_url)
    st.stop()


def render_sidebar_profile(api_base_url: str) -> None:
    """Render the signed-in profile controls in the sidebar."""
    company = current_company()
    with st.sidebar:
        st.markdown("### 👤 Profile")
        st.write(f"**{company.get('name', 'Company')}**")
        status = company.get("status", "unknown")
        st.caption(f"Status: {status} · Role: {current_role()}")

        with st.expander("Change password"):
            with st.form("change_pw_form"):
                current = st.text_input("Current password", type="password")
                new = st.text_input("New password (min. 8 characters)", type="password")
                submitted = st.form_submit_button("Update password")
            if submitted:
                response = api_post(
                    api_base_url,
                    "/auth/change-password",
                    json={"current_password": current, "new_password": new},
                    timeout=30,
                )
                if response.status_code == 200:
                    st.success("Password updated.")
                else:
                    st.error(humanize_error(response, "Update failed."))

        if st.button("Sign out", width="stretch"):
            logout()
            st.rerun()


def render_admin_panel(api_base_url: str) -> None:
    """Admin-only view: list companies and activate/suspend them."""
    st.subheader("🏢 Registered companies")
    st.caption("Approve, suspend, or reactivate company accounts.")

    response = api_get(api_base_url, "/admin/companies", timeout=30)
    if response.status_code != 200:
        st.error("Could not load companies. Are you signed in as an admin?")
        return

    companies = response.json()
    if not companies:
        st.info("No companies have registered yet.")
        return

    for company in companies:
        with st.container(border=True):
            cols = st.columns([3, 2, 2, 2])
            cols[0].markdown(f"**{company['name']}**")
            cols[0].caption(company["company_id"])
            status = company["status"]
            badge = {"active": "🟢", "pending": "🟡", "suspended": "🔴"}.get(status, "⚪")
            cols[1].markdown(f"{badge} {status}")
            if cols[2].button("Activate", key=f"act-{company['company_id']}"):
                _set_status(api_base_url, company["company_id"], "active")
            if cols[3].button("Suspend", key=f"sus-{company['company_id']}"):
                _set_status(api_base_url, company["company_id"], "suspended")


def _set_status(api_base_url: str, company_id: str, status: str) -> None:
    response = api_post(
        api_base_url,
        f"/admin/companies/{company_id}/status",
        json={"status": status},
        timeout=30,
    )
    if response.status_code == 200:
        st.success(f"Company set to {status}.")
        st.rerun()
    else:
        st.error(humanize_error(response, "Update failed."))
