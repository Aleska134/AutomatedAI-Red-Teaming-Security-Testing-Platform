# Automated AI Red Teaming & Security Testing Platform

An e-commerce security testing platform for evaluating whether LLM-powered
customer support agents can safely handle adversarial conversations and
controlled business operations.

The project combines:

- An adaptive attacker agent for prompt injection and social-engineering
  scenarios.
- A commerce support defender with controlled product and cart tools.
- A judge agent for security audit reporting.
- A deterministic TechMart commerce simulator with catalog, customers, carts,
  orders, coupons, and inventory.
- A FastAPI backend and Streamlit dashboard.

The long-term goal is to help merchants test AI agents before and after
production changes, identify exploitable behavior, preserve evidence, and
escalate suspicious interactions to human support.

## Current capabilities

### Security simulation

- Multi-turn attacker-versus-defender simulations.
- Configurable attack strategies:
  - Social engineering
  - Authority override
  - DAN-style jailbreak framing
  - Hypothetical roleplay
- Static prompt-injection filtering.
- Semantic input shielding with fail-closed behavior.
- Structured audit metrics for breach status, confidence, aggression, and
  defense efficiency.
- A local scenario library fallback when an attacker model provider refuses to
  generate a testing payload. Provider refusals are recorded separately and
  are not treated as proof that the Defender is secure.
- Persistent test runs with lifecycle status, timestamps, strategy, execution
  metadata, findings, evidence, and complete transcripts.

### Commerce simulator

The simulated store is **TechMart** and currently enforces:

- Maximum discount: `10%`
- Standard coupon: `TECH10`
- Return window: `30 days`
- Inventory validation before checkout.
- Inventory decrement after a paid demo order.
- A new open cart after a previous cart is checked out.
- Explicit purchase confirmation before checkout.

The current demo catalog includes laptops, wireless headphones, and mechanical
keyboards. Commerce rules are implemented in deterministic backend services and
do not depend on the LLM following its prompt.

### Defender commerce tools

The Defender can use an allowlisted set of tools to:

- Search the product catalog.
- Retrieve the current customer cart.
- Add an in-stock product to the cart.
- Complete checkout after explicit customer confirmation.

The model cannot directly modify inventory, set arbitrary prices, or access a
different customer through tool arguments. The backend supplies and validates
the customer context.

## Architecture

```text
Client / Streamlit
        |
        v
     FastAPI
        |
        +--> Commerce API and deterministic business services
        |
        +--> Defender agent
        |       +--> Input filters
        |       +--> Allowlisted commerce tools
        |       +--> OpenAI model
        |
        +--> Attacker agent
        |
        +--> Judge agent
        |
        v
      TinyDB
```

The central design principle is:

> The LLM handles language and reasoning; deterministic services enforce
> business and security rules.

## API endpoints

Interactive API documentation is available at `/docs` when the backend is
running.

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `GET` | `/api/v1/commerce/products` | Search the demo catalog |
| `GET` | `/api/v1/commerce/carts/{customer_id}` | Retrieve a customer cart |
| `POST` | `/api/v1/commerce/carts/items` | Add an item directly to a cart |
| `POST` | `/api/v1/commerce/checkout` | Complete a demo checkout |
| `POST` | `/api/v1/commerce/chat` | Chat with the commerce Defender |
| `POST` | `/api/v1/simulation/loop` | Run an attacker-versus-defender simulation |
| `GET` | `/api/v1/simulations` | Retrieve simulation records |
| `GET` | `/api/v1/test-runs` | Retrieve persisted merchant test runs |
| `GET` | `/api/v1/test-runs/{run_id}` | Retrieve one persisted test run |

The seeded demo customer is:

```text
customer-demo-001
```

Example conversational request:

```json
{
  "customer_id": "customer-demo-001",
  "message": "Show me the available wireless headphones",
  "history": []
}
```

To continue a conversation, send the `history` returned by the previous
response together with the next message:

```json
{
  "customer_id": "customer-demo-001",
  "message": "Add one of those headphones to my cart",
  "history": [
    {
      "role": "user",
      "content": "Show me the available wireless headphones"
    },
    {
      "role": "assistant",
      "content": "Previous assistant response"
    }
  ]
}
```

Checkout requires an explicit confirmation such as:

```text
I confirm that I want to purchase the items in my cart.
```

## Local setup

### Requirements

- Python 3.11 or newer.
- An OpenAI API key for LLM-powered chat and simulations.

### Installation

```bash
git clone https://github.com/Aleska134/AutomatedAI-Red-Teaming-Security-Testing-Platform.git
cd AutomatedAI-Red-Teaming-Security-Testing-Platform

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a local `.env` file:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

The `.env` file is ignored by Git and must never be committed.

### Run the backend

```bash
uvicorn app.main:app --reload
```

Open:

- API root: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

### Run the dashboard

In a second terminal:

```bash
source venv/bin/activate
streamlit run app/frontend.py
```

The dashboard is normally available at `http://localhost:8501`.

The dashboard expects the FastAPI backend at
`http://127.0.0.1:8000/api/v1` by default. To point it to a different
backend, set `API_BASE_URL` before starting Streamlit:

```bash
export API_BASE_URL="https://your-forwarded-api-url/api/v1"
streamlit run app/frontend.py
```

## Testing

The automated tests intentionally cover the deterministic parts of the system
without calling OpenAI, which keeps them fast and avoids API usage:

```bash
python -m pytest
```

The suite currently covers catalog search, cart and checkout behavior,
inventory updates, confirmation enforcement, tool allowlisting, and basic
prompt-injection signatures.

## Project status and roadmap

This repository is an evolving product prototype. The next major areas are:

- Hybrid deterministic and LLM-based security evaluation.
- Evidence records for tool calls and business-rule violations.
- Merchant dashboard for test runs, trends, and findings.
- Scheduled daily security tests.
- Human escalation triggers for suspicious or high-risk conversations.
- Generated product images and richer catalog data.
- Authentication, multi-tenant merchant isolation, and production storage.

The current commerce data is mock data designed for safe local testing. It does
not connect to real payment providers, fulfillment systems, or customer data.
