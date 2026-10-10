# 🛡️ Automated AI Red Teaming & Security Testing Platform

An automated, asynchronous **Bot-vs-Bot security testing engine** designed to stress-test LLM customer service agents against linguistic vulnerabilities, prompt injection, and social engineering tactics.

## 🚀 Overview

As generative AI agents are deployed into production environments, they become primary targets for adversarial manipulation. This platform automates the process of **AI Red Teaming** by simulating multi-turn conversations between an **Attacker Bot** (programmed to exploit vulnerabilities) and a **Target Bot** (the defense agent), audited by an independent **Judge Bot**.

This project demonstrates advanced concepts in AI Engineering, Backend Architecture, and Cybersecurity, featuring a multi-layered defense system and a real-time analytics dashboard.

### 🏗️ Core Architecture

The system operates on a three-agent architecture designed to simulate and evaluate real-world adversarial attacks:

| Agent | Role | Description |
| :--- | :--- | :--- |
| **Target Bot (Defender)** | The Defendant | A simulated retail agent with strict business rules (maximum 10% discount and a 30-day return window) protected by a 3-layer security shield. |
| **Attacker Bot (Hacker)** | The Attacker | An adversarial agent leveraging social engineering, authority hijacking, and prompt injection templates. |
| **Judge Bot (Auditor)** | The Auditor | An automated cybersecurity compliance inspector that outputs a structured risk report. |

### 🛡️ Multi-Layered Defense System

The `Target Bot` is protected by a robust, multi-tiered security architecture:

1.  **Layer 1: Static Signature Engine:** A regex-based pre-filter that flags obvious prompt injection keywords (e.g., "ignore previous instructions").
2.  **Layer 2: Semantic Input Shield:** A dedicated LLM firewall that evaluates the semantic intent to catch sneaky social engineering or jailbreaks.
3.  **Layer 3: Hardened Core Engine:** The final processing layer executing strict system instructions with defensive alignment.

## 🛠️ Tech Stack

-   **Backend:** Python, FastAPI, Uvicorn
-   **AI Infrastructure:** OpenAI API (`gpt-4o-mini`) with Structured Outputs
-   **Data Validation:** Pydantic v2
-   **Database:** TinyDB (Local JSON Document Engine)
-   **Frontend Dashboard:** Streamlit, Pandas, Plotly

## 🔧 Installation & Local Setup

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/Aleska134/AutomatedAI-Red-Teaming-Security-Testing-Platform.git
    cd AutomatedAI-Red-Teaming-Security-Testing-Platform
    ```

2.  **Set up virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    Create a `.env` file in the root directory:
    ```env
    OPENAI_API_KEY=your_openai_api_key_here
    ```

## 🖥️ Running the Application

### 1. Start the Backend API (FastAPI)
```bash
uvicorn app.main:app --reload
```


*Docs available at: `http://127.0.0.1:8000/docs`*

### 2. Start the Security Dashboard (Streamlit )
```bash
streamlit run app/frontend.py
```

## 📊 Dashboard Features

- **Simulation Controller:** Select attack vectors like *Social Engineering*, *Authority Override*, or *Jailbreak DAN*.
- **Analytics Dashboard:** Visual representation of compliance breaches and defense efficiency metrics.
- **Transcript Explorer:** Detailed logs of every interaction with technical audit analysis and flagged keywords.
