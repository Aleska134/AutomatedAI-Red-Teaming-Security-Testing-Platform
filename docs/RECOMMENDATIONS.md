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
| No auth rate limiting | Password brute force / reset spam | Phase 2 |
| DNS rebinding on webhooks | Host can resolve public at check time, private at request time | Pin the resolved IP for the request |
| TinyDB under concurrency | FastAPI runs sync endpoints in a thread pool; concurrent writes can corrupt `local_db.json` | SQLite (Phase 2) |
| Shared demo inventory | Sandbox carts are per company, but product stock is global | Per-tenant catalog or reset per run |
| Synchronous simulations | Up to ~3 LLM calls per turn inside one HTTP request | Background tasks (Phase 2) |

## Evaluation quality

- The semantic shield inspects only the latest message, so multi-turn attacks
  that build context gradually can slip through. Consider classifying a window
  of recent turns.
- The scope-boundary check matches English phrases; a chatbot replying in
  another language is always flagged. Use a rubric-based LLM judge or
  per-language markers.
- External targets get a single fixed probe. Running the adaptive attacker
  against them is the highest-value next feature.

## Deployment: Heroku + Neon

A good fit for this project: Heroku is covered by the GitHub Student Developer
Pack credits, and Neon offers a free serverless Postgres tier that is plenty
for a demo. Check both providers' current plan limits before launch.

Prerequisites and gotchas:

- **Postgres is required first.** Heroku dyno filesystems are ephemeral, so
  `local_db.json` would be wiped on every restart/deploy. Finish the SQLModel
  migration (Phase 2) and read the connection string from `DATABASE_URL`.
- **Use Neon's pooled connection string** with `sslmode=require`. Neon scales
  to zero when idle, so expect a short cold start on the first request; keep
  connection pool sizes small.
- **Two processes, two apps.** A Heroku app exposes one `web` process, so run
  the API and the Streamlit dashboard as separate Heroku apps:
  - API `Procfile`: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - Dashboard `Procfile`: `web: streamlit run app/frontend.py --server.port $PORT --server.address 0.0.0.0`
  - Set `API_BASE_URL` on the dashboard app to the API app's URL.
- **Config vars, never committed:** `APP_ENV=production`, `JWT_SECRET_KEY`
  (32+ chars), `TARGET_ENCRYPTION_KEY`, `DATABASE_URL`, LLM API keys, and
  `ADMIN_EMAIL`/`ADMIN_PASSWORD`. Keep `ALLOW_PRIVATE_WEBHOOKS` unset.
- **Pin the Python version** (`.python-version`) and dependency versions so
  builds are reproducible.
- **Demo safety:** set spending limits on LLM API keys and add auth rate
  limiting (Phase 2) before sharing a public URL.

## Keep it maintainable

Avoid microservices, Kubernetes, complex queues, or a React rewrite until there
are real users. Prefer quality of attacks over quantity of strategies.
