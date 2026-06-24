import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# Configure the core Streamlit page parameters
st.set_page_config(
    page_title="Automated AI Red Teaming Platform",
    page_icon="🛡️",
    layout="wide"
)

API_BASE_URL = "http://127.0.0.1:8000/api/v1"

st.title("🛡️ Automated AI Red Teaming & Security Testing Platform")
st.markdown("---")

# -------------------------------------------------------------------
# SIDEBAR: Control Center
# -------------------------------------------------------------------
st.sidebar.header("🕹️ Simulation Controller")

# Selection menu for the offensive attack vectors
attack_strategy = st.sidebar.selectbox(
    "Select Attack Vector Strategy:",
    options=["social_engineering", "authority_override", "jailbreak_dan", "roleplay_hypothetical"],
    index=0
)

# Number of conversation rounds to run per simulation batch
simulation_turns = st.sidebar.slider(
    "Conversation Turns:",
    min_value=1,
    max_value=5,
    value=3
)

trigger_simulation = st.sidebar.button("🚀 Trigger Attack Simulation", use_container_width=True)

# -------------------------------------------------------------------
# FETCH DATA FROM BACKEND API
# -------------------------------------------------------------------
@st.cache_data(ttl=2)  # Cache updates quickly to allow fast iteration
def fetch_all_simulations():
    """Queries FastAPI to pull all local JSON history logs."""
    try:
        response = requests.get(f"{API_BASE_URL}/simulations")
        if response.status_code == 200:
            return response.json().get("data", [])
        return []
    except Exception:
        return []

simulations_data = fetch_all_simulations()

# -------------------------------------------------------------------
# ACTION: Trigger Simulation Pipeline
# -------------------------------------------------------------------
if trigger_simulation:
    with st.spinner("🤖 Simulating multi-turn AI battle in background... please wait..."):
        payload = {
            "turns": simulation_turns,
            "strategy": attack_strategy,
            "history": []
        }
        try:
            res = requests.post(f"{API_BASE_URL}/simulation/loop", json=payload)
            if res.status_code == 200:
                st.success(f"Simulation completed successfully! Record saved.")
                # Refresh data array instantly after pipeline execution
                st.rerun()
            else:
                st.error(f"Error executing pipeline: {res.text}")
        except Exception as e:
            st.error(f"Failed to connect to FastAPI backend: {str(e)}")

# -------------------------------------------------------------------
# MAIN DASHBOARD PANELS
# -------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📊 Analytics Dashboard", "💬 Conversation Logs Explorer", "🧪 System Specs"])

with tab1:
    st.subheader("📊 Security Analytics Summary")
    
    if not simulations_data:
        st.info("No logs detected in local database. Run your first simulation from the sidebar control panel!")
    else:
        # Convert JSON objects into a Pandas DataFrame for swift graphing metrics
        df = pd.DataFrame(simulations_data)
        
        # Calculate summary numbers
        total_runs = len(df)
        breached_count = df['breached'].sum()
        secured_count = total_runs - breached_count
        avg_defense = df['defense_efficiency_score'].mean()
        
        # Display KPIs in crisp metric columns
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Simulations Run", total_runs)
        col2.metric("Successful Breaches 🚨", breached_count, delta=int(breached_count), delta_color="inverse")
        col3.metric("Defenses Held 🛡️", secured_count)
        col4.metric("Avg Defense Efficiency", f"{avg_defense:.2f} / 10")
        
        st.markdown("---")
        
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.markdown("### Compliance Breach Status")
            fig_pie = px.pie(
                df, 
                names='breached', 
                color='breached',
                color_discrete_map={True: '#EF553B', False: '#636EFA'},
                labels={'breached': 'Is Breached'},
                hole=0.4
            )
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with col_g2:
            st.markdown("### Attacker Aggression Trends over Time")
            fig_line = px.line(
                df, 
                x='simulation_number', 
                y='attacker_aggression_level', 
                markers=True,
                labels={'simulation_number': 'Simulation ID', 'attacker_aggression_level': 'Aggression Score (1-5)'},
                title="Adversarial Aggression Volatility"
            )
            st.plotly_chart(fig_line, use_container_width=True)

with tab2:
    st.subheader("💬 Session Transcript Records")
    
    if not simulations_data:
        st.info("No recorded transcripts available yet.")
    else:
        df_logs = pd.DataFrame(simulations_data).sort_values(by="simulation_number", ascending=False)
        
        # Build a drop-down menu matching our chronological numbering indexes
        session_options = [f"Simulation #{int(float(row['simulation_number']))} (ID: {row['session_id']})" for _, row in df_logs.iterrows()]
        selected_session_str = st.selectbox("Select a security log to inspect:", options=session_options)
        
        # Extract selected session number integer from string selection
        selected_sim_num = int(float(selected_session_str.split("#")[1].split(" ")[0]))
        selected_record = next(item for item in simulations_data if item["simulation_number"] == selected_sim_num)
        
        # Render Audit Report metadata block
        st.markdown(f"#### 🧑‍⚖️ Auditor Report Summary for Simulation #{selected_sim_num}")
        c_a, c_b, c_c = st.columns(3)
        status_color = "🔴 BREACHED" if selected_record["breached"] else "🟢 SECURED"
        c_a.markdown(f"**Compliance Status:** {status_color}")
        c_b.markdown(f"**Attacker Aggression Level:** `{selected_record['attacker_aggression_level']}/5`")
        c_c.markdown(f"**Defense Efficiency Score:** `{selected_record['defense_efficiency_score']}/10`")
        
        st.info(f"**Technical Audit Analysis:**\n{selected_record['analysis']}")
        st.caption(f"Keywords Flagged: {', '.join(selected_record['attack_vector_keywords'])}")
        
        st.markdown("#### 💬 Dialogue Transcript")
        # Paint the dialogue elements dynamically using chat blocks
        for message in selected_record["history"]:
            if message["role"] == "user":
                with st.chat_message("user", avatar="⚔️"):
                    st.write(message["content"])
            else:
                with st.chat_message("assistant", avatar="🛡️"):
                    st.write(message["content"])

with tab3:
    st.subheader("🧪 Operational Environment Blueprint")
    st.markdown("""
    This control panel interface hooks straight into an optimized backend execution layers:
    - **Backend Engine:** FastAPI REST Architecture (`Uvicorn`)
    - **Data Persistence:** TinyDB Local Document JSON Engine (`local_db.json`)
    - **Defense Matrix:** 3-Layer Input Filtering (Static Signature + Semantic Intent Firewall + Hardened Prompts)
    - **Red Team Matrix:** Multi-Turn Adaptive Prompt Injection LLM Generator
    """)