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

## Keep it maintainable

Avoid microservices, Kubernetes, complex queues, or a React rewrite until there
are real users. Prefer quality of attacks over quantity of strategies.
