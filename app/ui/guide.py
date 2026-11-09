"""Help: how testing works and how to read the results."""

import streamlit as st

from app.ui.targets import render_target_fields_help


def render(simulations_data):
    st.subheader("❓ Help")
    st.markdown("### How testing works")
    st.markdown(
        "- Each **test** is a simulated attack conversation (1-5 turns) against your chatbot.\n"
        "- Pick the chatbot and the tests on **Run tests**; a full assessment runs every test.\n"
        "- The result of each test is **Breached**, **Held** or **Inconclusive**.\n"
        "- **Inconclusive** means the test could not be judged (for example a provider "
        "outage). It is never counted as secure."
    )
    st.markdown("### Reading the results")
    st.markdown(
        "- **Results › Findings** lists every problem once, with what happened and how to fix it.\n"
        "- **Results › History & reports** has each run's conversation, evidence and a "
        "downloadable report (print it to PDF).\n"
        "- **Results › Compare chatbots** shows which chatbot resisted and which fell."
    )
    st.markdown("### Connecting a chatbot")
    render_target_fields_help()
