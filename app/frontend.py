import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.frontend_auth import (  # noqa: E402 - needs sys.path tweak above
    current_role,
    is_authenticated,
    render_admin_panel,
    render_auth_gate,
    render_sidebar_profile,
)
from app.ui import guide, home, my_chatbots, nav, results, run_tests  # noqa: E402
from app.ui.common import API_BASE_URL, fetch_all_simulations  # noqa: E402

# Configure the core Streamlit page parameters
st.set_page_config(
    page_title="Automated AI Red Teaming Platform",
    page_icon="🛡️",
    layout="wide"
)

# Authentication gate: unauthenticated users see sign in / create account /
# forgot password, and the rest of the dashboard does not render.
if not is_authenticated():
    render_auth_gate(API_BASE_URL)

render_sidebar_profile(API_BASE_URL)

st.title("🛡️ Merchant AI Security Center")
st.markdown("---")

simulations_data = fetch_all_simulations(st.session_state.get("access_token", ""))


def _page(module):
    """Wrap a page module's ``render`` as the zero-argument callable Streamlit wants."""

    def run():
        module.render(simulations_data)

    return run


def _admin_page():
    render_admin_panel(API_BASE_URL)


# -------------------------------------------------------------------
# PAGES (the admin page is only registered for admins)
# -------------------------------------------------------------------
nav.pages.clear()
nav.pages.update(
    home=st.Page(_page(home), title="Home", icon="🏠", url_path="home", default=True),
    tests=st.Page(_page(run_tests), title="Run tests", icon="🧪", url_path="tests"),
    results=st.Page(_page(results), title="Results", icon="📊", url_path="results"),
    chatbots=st.Page(_page(my_chatbots), title="My chatbots", icon="🤖", url_path="chatbots"),
    help=st.Page(_page(guide), title="Help", icon="❓", url_path="help"),
)
if current_role() == "admin":
    nav.pages["admin"] = st.Page(_admin_page, title="Admin", icon="🏢", url_path="admin")

st.navigation(list(nav.pages.values())).run()
