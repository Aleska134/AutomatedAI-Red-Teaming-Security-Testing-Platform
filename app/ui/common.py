"""Shared API access, cached data loaders and chart styling for every tab."""

import os
import time

import streamlit as st

from app.frontend_auth import (
    api_get,
    api_post,
)

# Optional: URL of a deliberately vulnerable demo chatbot offered on Home for
# first-time users. Leave unset to hide the "try the sample chatbot" button.
SAMPLE_CHATBOT_URL = os.getenv("SAMPLE_CHATBOT_URL", "").strip()

API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000/api/v1",
).rstrip("/")



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


def viewer_timezone():
    """The browser's IANA time zone name, or None when Streamlit cannot tell."""
    try:
        return st.context.timezone
    except Exception:  # noqa: BLE001 - older Streamlit, tests, no browser
        return None


def fetch_targets():
    response = api_get(API_BASE_URL, "/targets", timeout=30)
    return response.json() if response.status_code == 200 else []


SEVERITY_COLORS = {"CRITICAL": "#b42318", "HIGH": "#ef6820", "MEDIUM": "#f79009", "LOW": "#98a2b3"}


SEVERITY_ICONS = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}


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
