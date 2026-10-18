# Development guide

How to keep building this project on your own. Plan: [ROADMAP.md](ROADMAP.md) ·
reasoning: [RECOMMENDATIONS.md](RECOMMENDATIONS.md).

## Status

Phases 1–3 are done: security hardening, SQLModel/Postgres, Docker, background
runs, webhook targets, business rules and canaries, OWASP mapping, 10 attack
scenarios, EN/ES reports, and a grounded Judge rubric. Next: **Phase 4**.

## Two repositories

| Repo | Role | Run |
| --- | --- | --- |
| this one | Platform: API (FastAPI), dashboard (Streamlit), attacker, Judge | `uvicorn app.main:app --reload` + `streamlit run app/frontend.py` |
| `AI-Chatbot` | Reference target, keyword-based (no LLM), hardened 8100 / weak 8101 | `./scripts/run_both.sh` |

How to test end to end (free or with credits): README, "How to test it".

## Where things live

| You want to… | Edit |
| --- | --- |
| Add an attack strategy | `app/domain.py` (`AttackStrategy`), `app/agents/attacker.py` (`ATTACK_STRATEGIES` + `LOCAL_TEST_PAYLOADS`) |
| Add a scenario to the dashboard | `app/services/security_scenarios.py` |
| Add a deterministic rule | `app/services/security_evaluation.py`, then map it in `app/services/owasp.py` |
| Add a Judge criterion | `RUBRIC` in `app/agents/judge.py` (reuse a rule id) |
| Recommendations / report texts | `app/services/merchant_reporting.py`, `app/services/run_report.py` (EN + ES) |
| Per-target business rules | `BusinessRules` in `app/schemas.py`, `evaluate_business_rules` |
| LLM provider (OpenAI/Gemini) | `app/agents/llm_provider.py` |

New rule checklist: rule in evaluation → OWASP mapping → `RULE_TITLES` and
`RECOMMENDATIONS_ES` in `run_report.py` → English recommendation in
`merchant_reporting.py` → test. `tests/test_run_report.py` and
`tests/test_owasp_mapping.py` fail if you forget a mapping or title.

## Workflow (one step = one PR)

```bash
git checkout main && git pull
git checkout -b feature/<short-name>
# ...change code + tests + README...
OPENAI_API_KEY=x venv/bin/python -m pytest -p no:warnings   # all tests must pass
venv/bin/ruff check app tests                               # lint must pass
git commit -am "Clear message" && git push -u origin HEAD
gh pr create --base main
```

- Branch from an up-to-date `main` and merge the previous PR first. Stacked
  PRs merged into each other instead of `main` before (#9/#10).
- Tests never call a real LLM: mock `generate_json` / `generate_text` with
  `monkeypatch` (see `tests/test_judge_rubric.py`). This costs no credits.
- Tick the ROADMAP checkbox and update the README in the same PR.
- CI (GitHub Actions) runs tests and builds Docker on every PR; wait for green.

## Local gotchas

- `ALLOW_PRIVATE_WEBHOOKS=true` in `.env` lets you target `localhost`. Restart
  the backend after editing `.env`. Never set it on Heroku (SSRF).
- In Docker, the chatbot URL is `http://host.docker.internal:8101/api/v1/chat`.
- The dashboard in Docker and the one from VS Code use different databases:
  sign in and activate your company in each.
- Without LLM credits the attacker uses local payloads and the Judge is skipped;
  deterministic rules still prove leaks against the weak bot.

## Next step: Gemini tool-calling

Goal: the built-in Defender (`app/agents/defender.py`) uses its commerce tools
(`app/services/commerce_tools.py`) with `LLM_PROVIDER=gemini`, not only OpenAI.

1. Read how `defender.py` calls OpenAI with `tools=COMMERCE_TOOL_DEFINITIONS`
   and loops over `tool_calls`.
2. In `llm_provider.py` add `generate_with_tools(system, messages, tools)` that
   returns a neutral shape: `{"text": str | None, "tool_calls": [{"id", "name",
   "arguments": dict}]}`. OpenAI branch: current code. Gemini branch: convert the
   tool definitions to `types.FunctionDeclaration` (google-genai SDK) and read
   `function_call` parts from the response.
3. Make `defender.py` use only that neutral shape, so it no longer knows which
   provider is active. Keep `execute_commerce_tool` and the checkout
   confirmation guard unchanged (they are the security controls).
4. Tests: mock `generate_with_tools` to return a tool call and check the
   Defender executes it and records the `tool_event`. No credits needed.
5. Try it live once with 1 turn to save credits.

## After that (Phase 4)

Deploy to Heroku + Neon (see RECOMMENDATIONS, "Deployment"), protect credits
(cheap model, daily run limit per account, pre-recorded showcase runs), then the
README demo GIF, architecture diagram and the write-up. Later idea: an LLM mode
for the reference chatbot (RECOMMENDATIONS, "Future: LLM vs LLM").
