# Automated AI Red Teaming & Security Testing Platform

An automated, asynchronous **Bot-vs-Bot security testing engine** designed to stress-test LLM customer service agents against linguistic vulnerabilities, prompt injection, and social engineering tactics.

## 🚀 Overview

As generative AI agents are deployed into production environments (such as E-commerce, healthcare, and support), they become primary targets for adversarial manipulation. This platform automates the process of **AI Red Teaming** by simulating multi-turn conversations between an **Attacker Bot** (programmed to exploit vulnerabilities) and a **Target Bot** (the defense agent), audited by an independent **Judge Bot**.

### Core Architecture
- **Target Bot (The Defendant):** A simulated retail agent with strict business rules (e.g., maximum 10% discount limits, strict return windows, and hidden system prompts).
- **Attacker Bot (The Hacker):** An adversarial agent leveraging social engineering, authority hijacking, and prompt injection templates to force compliance failure.
- **Judge Bot (The Auditor):** An automated cybersecurity compliance inspector that analyzes transcripts deterministically and outputs a structured **Pydantic/JSON** risk report.

---

## 🛠️ Tech Stack

- **Backend:** Python, FastAPI, Uvicorn
- **AI Infrastructure:** OpenAI API (Asynchronous clients with Structured Outputs)
- **Data Validation:** Pydantic v2
- **Environment Management:** Python Dotenv

---

## 🔧 Installation & Local Setup

1. **Clone the Repository:**
   ```bash
   git clone [https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git)
   cd AutomatedAI-Red-Teaming-Security-Testing-Platform

Set up virtual environment
    python3 -m venv venv
    source venv/bin/activate

Install Dependencies
    pip install -r requirements.txt

Configure Environment Variables: 
    Create a .env file in the root directory:
    OPENAI_API_KEY=your_openai_key

🖥️ Running the Application
1. Terminal Simulation (CLI)
To execute a rapid, raw multi-turn bot-vs-bot simulation directly inside your terminal, run:

python3 -m app.services.orchestrator

2. REST API Server (FastAPI)
To launch the backend API server with automated interactive Swagger documentation:

uvicorn app.main:app --reload

Once active, visit the interactive dashboard at: ⁠http://127.0.0.1:8000/docs⁠

