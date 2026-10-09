# Paid-Worthy MVP — Critical Path

Branch: `mvp/paid-readiness`  
Goal: A single broker can run a pilot with confidence (security, data integrity, onboarding, and a billable value story).

## P0 — Ship blockers

1. **Database migrations** — Merge Alembic heads; migrate `leads`, `landing_page_events`, and any missing tables via `alembic upgrade head` (no manual SQL in E2E setup).
2. **First-run onboarding** — Seed demo admin/client users on API startup or compose init; document production admin bootstrap (no manual Docker Python).
3. **Auth consistency** — Finish migrating admin/ingest components to `authFetch`; audit API routes for tenant/client scoping on list/read/write.
4. **Secrets & defaults** — Enforce strong `SECRET_KEY` in prod; remove or gate Flower/pgweb defaults behind dev profile.

## P1 — Pilot trust

5. **Password reset / SMTP** — Working email flow for real users (Resend/SMTP env documented and tested).
6. **HTTPS path** — Document or automate TLS for compose/provisioning (`provisioning/scripts/setup-ssl.sh` validated).
7. **Observability** — Health dashboard reflects worker/beat/queue; DLQ visible and actionable in UI with auth.
8. **E2E in CI** — Run Playwright against compose in GitHub Actions (or nightly) with seeded DB.

## P2 — Monetization hooks

9. **Organization / client isolation** — Hard guarantees in API + tests for cross-tenant leakage.
10. **Usage metering** — Count documents processed, extractions, ACE exports per client (Stripe/metronome later).
11. **ACE / compliance** — Clear “demo vs production” flags; no silent stubs on transmit paths.

## Definition of done (paid pilot)

- New customer: register → verify email → upload scenario_1 → review → entry prep without engineer intervention.
- `cd e2e && npm test` green against fresh `docker compose up`.
- Single command migrations on empty DB.
- Security review: no open admin tools on public ports in prod template.

See also: `.gsd/PRODUCTION_READINESS_PLAN.md`, `SECRETS_CHECKLIST.md`, `MVP_USER_GUIDE.md`.
