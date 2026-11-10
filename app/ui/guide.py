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
    st.markdown("### Your data")
    st.markdown(
        "- **Only test chatbots you own or may test.** When you add one, we record who "
        "confirmed that and when.\n"
        "- **What we send to your chatbot:** only the simulated attack messages of the "
        "tests you run.\n"
        "- **What we store:** test conversations, findings and reports, saved under your "
        "company account. Only your company and the platform administrators can see them.\n"
        "- **Access tokens** for your chatbot are stored encrypted.\n"
        "- **AI providers:** if the platform has an AI provider configured (OpenAI or "
        "Gemini), the attacker and the judge send test conversations to it to write "
        "attacks and evaluate replies. Without one, built-in attacks and fixed rules are "
        "used.\n"
        "- **Deleting:** you can delete a chatbot under My chatbots. Nothing is deleted "
        "automatically and past test results cannot be deleted from the dashboard yet; "
        "ask the administrator to remove them."
    )
    st.markdown("### Connecting a chatbot")
    render_target_fields_help()
