# Roadmap

Strategy: **secure → credible → sellable.** No new features until the platform
itself is secure; a security tool with security holes undermines itself.

## Phase 1 — Close security gaps ✅

- [x] Reset token never returned by `/auth/forgot-password`; stored hashed.
- [x] Commerce endpoints authenticated; customer derived from the token.
- [x] Configurable database location (now `DATABASE_URL`); tests use a temporary database.
- [x] App refuses to start without a strong `JWT_SECRET_KEY` outside development.
- [x] SSRF protection for webhooks (public IPs only, no redirects).
- [x] Provider outages produce **inconclusive** runs, not "secure" ones.
- [x] Password change/reset revokes existing JWTs.
- [x] Target auth tokens encrypted at rest.
- [x] Purchase intent alone no longer authorizes checkout.

## Phase 2 — Solid, maintainable foundation ✅

- [x] Replace TinyDB with SQLModel: SQLite locally, Neon Postgres in production
      (selected by `DATABASE_URL`; safe under concurrency).
- [x] Pin dependency versions; add `ruff` lint to CI.
- [x] `docker compose up` runs backend + dashboard with one command.
- [x] Run simulations in the background (`BackgroundTasks`); poll run status.
- [x] Rate-limit login, register, and forgot-password.
- [x] Replace deprecated `@app.on_event` with a `lifespan` handler.

## Phase 3 — Differentiators (what makes it a product)

- [x] Run the adaptive multi-turn attacker against **external webhook targets**,
      not just the built-in Defender.
- [x] Per-target **business rules** declared by the company (valid coupons, max
      discount, forbidden actions) checked deterministically against replies and
      metadata, so invented or unauthorized discounts are proven breaches.
- [x] Map every finding to the **OWASP Top 10 for LLM Applications** (LLM01, …).
- [ ] Downloadable per-run report (HTML/PDF): severity, evidence, remediation.
- [ ] Broaden attack coverage, each scenario with its own deterministic rule:
      indirect prompt injection via tool output (LLM01), obfuscated / multilingual
      attacks (LLM01), another customer's data (LLM02), dangerous output such as
      `<script>` or `javascript:` links (LLM05), and tool abuse — negative
      quantities, editing or cancelling someone else's order (LLM06).
- [ ] LLM judge with an explicit rubric so evaluation works in any language.
- [ ] Defender tool-calling through the provider layer (Gemini support).

## Phase 4 — Portfolio launch

- [ ] Deploy on **Heroku** (GitHub Student Pack credits) + **Neon** Postgres (free
      tier) with a public demo account and sample data. See
      [deployment notes](RECOMMENDATIONS.md#deployment-heroku--neon).
- [ ] README: demo GIF, architecture diagram, threat model section.
- [ ] Short write-up: "I built a tool that attacks AI chatbots — here's what I found."

## Phase 5 — Commercialization (only if Phase 3 lands well)

- [ ] GitHub Action: run attacks on every PR to a customer's chatbot ("CI for LLM security").
- [ ] Usage-based plans and Stripe billing.
- [ ] Validate demand first: talk to 5–10 startups that ship chatbots.
