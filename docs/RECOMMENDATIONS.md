# Recommendations

Findings from the project review and the reasoning behind the
[roadmap](ROADMAP.md).

## Strengths to keep

- **LLM for language, deterministic code for rules.** Checkout confirmation and
  customer scoping are enforced by the backend, not by the prompt.
- **Deterministic evidence overrides the LLM judge**, and provider refusals are
  not treated as proof of security.
- **Fail-closed shield** and bounded LLM timeouts.
- Small PRs, CI on a Python matrix, offline tests, clear README.

## Remaining risks

| Risk | Why it matters | Planned fix |
| :--- | :--- | :--- |
| In-memory auth rate limits | Per process; behind a proxy the client IP must come from trusted proxy headers | Shared store (e.g. Redis) and proxy config at deploy (Phase 4) |
| DNS rebinding on webhooks | Host can resolve public at check time, private at request time | Pin the resolved IP for the request |
| Shared demo inventory | Sandbox carts are per company, but product stock is global | Per-tenant catalog or reset per run |

## Evaluation quality

- The semantic shield inspects only the latest message, so multi-turn attacks
  that build context gradually can slip through. Consider classifying a window
  of recent turns.
- The scope-boundary check matches English phrases; a chatbot replying in
  another language is always flagged. Use a rubric-based LLM judge or
  per-language markers.
- The adaptive attacker can run against external targets, but tool-call
  evidence (e.g. applied discounts) is only available for the built-in
  Defender; external targets are judged on their replies and reported metadata.

## Business rules come from the customer

Only the company knows its real coupons and limits; they live in its store
backend (applied through tools), not in the system prompt. Saving them on the
target gives the platform ground truth: a reply naming an unknown coupon or a
discount above the declared maximum is a deterministic breach (OWASP LLM08
Excessive Agency / LLM09 Misinformation). If the target also reports what it
actually applied in `metadata`, claims can be compared with actions.

## Attack coverage

Prefer scenarios that end in a deterministic proof over ones that need the Judge's
opinion. Next additions: indirect injection hidden in tool output (product reviews,
order notes), the same attacks obfuscated or in other languages, requests for
another customer's data, replies containing executable HTML/links, and tool abuse
(negative quantities, acting on orders the user does not own). Later: invented
policies (extend `business_rules` with forbidden promises), unbounded output
length, and brand safety. LLM03, LLM04 and LLM08 cannot be tested from a webhook.

## Future: LLM vs LLM (reference chatbot with a real model)

**Goal.** Today the reference chatbot (AI-Chatbot) is keyword-based, so an
LLM attacker can only "win" by hitting exact phrases. A real model behind the
same data and tools makes the demo look like a real company's chatbot. Keep the
keyword mode for tests and CI (free and deterministic).

**Which model to use where.**

| Where | Model source | Why |
| --- | --- | --- |
| CI / unit tests | Keyword mode (no LLM) | Free and deterministic |
| Local development | Ollama, *only on a capable machine* (Apple Silicon, 16 GB+ for 7-8B models) | $0 per run |
| Heroku demo | Commercial API, cheapest tier (Gemini Flash, GPT mini-class) | Heroku cannot host models |

Hosted open models (for example Groq or OpenRouter) also expose
OpenAI-compatible APIs, often with free or very cheap tiers. Check current
pricing before relying on one.

**Step by step (when credits/hardware allow).**

1. *Platform:* add an `openai_compatible` provider to `app/agents/llm_provider.py`
   reading `LLM_BASE_URL` + `LLM_MODEL` (Ollama is `http://localhost:11434/v1`).
   Allow choosing the provider per role (attacker / judge) so the attacker can be
   cheap and the judge stronger.
2. *AI-Chatbot:* add `LLM_ENABLED=true` (the `llm_enabled` metadata flag already
   exists). The model gets a system prompt with the store rules and the tools
   `search_products`, `get_order(order_id)`, `get_customer(name)`, `get_reviews(sku)`
   over the existing SQLite mock data. Pick a model with tool calling (Qwen 2.5,
   Llama 3.1, Gemini Flash, GPT mini-class).
3. *Weak vs hardened stays in code, not in the prompt:* weak tools skip the
   ownership check (IDOR); hardened tools enforce it and strip instruction-like
   text from reviews. That keeps the demo honest: hardened resists because of
   real controls, not a lucky prompt.
4. Keep reporting `applied_coupons` / `actions_taken` in metadata and register
   the canaries as `protected_values`, so leaks stay provable by exact match.
5. Fall back to keyword mode if the provider fails, marking
   `provider_status: "fallback"` (never counted as secure).
6. Tests: mock the LLM client; one optional, manually-run smoke test against the
   real provider.

**Cost controls for the public demo.** Cap turns (already ≤5), per-account daily
run limits, cheapest models, short history (already 20 turns), and a few
pre-recorded showcase runs so visitors can see results without spending credits.

**Later (optional):** fine-tune a small open model (LoRA) as a specialized
attacker using transcripts the platform already stores.

## Deployment: Heroku + Neon

A good fit for this project: Heroku is covered by the GitHub Student Developer
Pack credits, and Neon offers a free serverless Postgres tier that is plenty
for a demo. Check both providers' current plan limits before launch.

Prerequisites and gotchas:

- **Postgres is required.** Heroku dyno filesystems are ephemeral, so a local
  SQLite file would be wiped on every restart/deploy. Set `DATABASE_URL` to the
  Neon connection string (the app already accepts Heroku's `postgres://`).
- **Use Neon's pooled connection string** with `sslmode=require`. Neon scales
  to zero when idle, so expect a short cold start on the first request; keep
  connection pool sizes small.
- **Two processes, two apps.** A Heroku app exposes one `web` process, so run
  the API and the Streamlit dashboard as separate Heroku apps:
  - API `Procfile`: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
    (auth rate limits key on the client IP; configure uvicorn's proxy headers
    so it sees the real IP behind Heroku's router, not a spoofable one)
  - Dashboard `Procfile`: `web: streamlit run app/frontend.py --server.port $PORT --server.address 0.0.0.0`
  - Set `API_BASE_URL` on the dashboard app to the API app's URL.
- **Config vars, never committed:** `APP_ENV=production`, `JWT_SECRET_KEY`
  (32+ chars), `TARGET_ENCRYPTION_KEY`, `DATABASE_URL`, LLM API keys, and
  `ADMIN_EMAIL`/`ADMIN_PASSWORD`. Keep `ALLOW_PRIVATE_WEBHOOKS` unset.
- **Pin the Python version** (`.python-version`) so builds are reproducible
  (dependency versions are already pinned).
- **Demo safety:** set spending limits on LLM API keys before sharing a public
  URL (auth rate limiting is already in place).

## Keep it maintainable

Avoid microservices, Kubernetes, complex queues, or a React rewrite until there
are real users. Prefer quality of attacks over quantity of strategies.
