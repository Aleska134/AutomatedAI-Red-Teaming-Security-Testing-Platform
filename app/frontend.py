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
from app.ui import analytics, logs, merchant  # noqa: E402
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
    analytics.render(simulations_data)

with tab2:
    logs.render(simulations_data)

with tab3:
    merchant.render(simulations_data)

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
