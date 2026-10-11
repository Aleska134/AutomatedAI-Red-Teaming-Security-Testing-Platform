"""Streamlit authentication UI and authenticated HTTP helpers.

Keeps the login/registration/password flows and the admin panel out of the
main dashboard file. The design is intentionally sober: a single centered card
for signed-out users, and a compact profile section in the sidebar.
"""

import requests
import streamlit as st


def _auth_headers() -> dict:
    token = st.session_state.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def api_get(api_base_url: str, path: str, **kwargs):
    return requests.get(f"{api_base_url}{path}", headers=_auth_headers(), **kwargs)


def api_post(api_base_url: str, path: str, json: dict | None = None, **kwargs):
    return requests.post(
        f"{api_base_url}{path}", json=json, headers=_auth_headers(), **kwargs
    )


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
            st.error(response.json().get("detail", "Sign in failed."))


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
            st.error(response.json().get("detail", "Registration failed."))


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
        # In local/dev the token is returned directly so the flow is usable.
        if data.get("reset_token"):
            st.code(data["reset_token"], language="text")
            st.caption("Copy this token into the 'Reset password' tab.")

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
            st.error(response.json().get("detail", "Reset failed."))


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
                    st.error(response.json().get("detail", "Update failed."))

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
        st.error(response.json().get("detail", "Update failed."))
