"""My chatbots: register, edit and delete the chatbots you test."""

import streamlit as st

from app.ui.common import (
    fetch_targets,
)
from app.ui.targets import render_target_form, render_target_manager


def render(simulations_data):
    st.subheader("🤖 My chatbots")
    render_target_form()
    targets = fetch_targets()
    render_target_manager(targets)
    if not targets:
        st.info("No chatbots registered yet. Add one above to test it.")
