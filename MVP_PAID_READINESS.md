# Paid-Worthy MVP — Critical Path

Branch: `mvp/paid-readiness`  
Goal: A single broker can run a pilot with confidence (security, data integrity, onboarding, and a billable value story).

## P0 — Ship blockers

1. **Database migrations** — ✅ Merge migration `h4i5j6k7l8m9` + marketing tables `i5j6k7l8m9n0`; API entrypoint runs `alembic upgrade head`.
2. **First-run onboarding** — ✅ `SEED_DEMO_USERS=true` in compose; idempotent seed on API lifespan.
3. **Auth consistency** — ✅ Ingest list/detail scoped by uploader; ingest/DLQ/queue/batch/audit UI uses `authFetch`. Remaining raw `fetch` in low-traffic admin pages.
4. **Secrets & defaults** — ✅ Production `SECRET_KEY` validation in config; Flower/pgweb behind `docker compose --profile devtools up`.

## P1 — Pilot trust

5. **Password reset / SMTP** — ✅ Forgot-password sends via `EmailService`; see [`docs/PILOT_SMTP.md`](docs/PILOT_SMTP.md).
6. **HTTPS path** — ✅ [`docs/PILOT_HTTPS.md`](docs/PILOT_HTTPS.md); `setup-ssl.sh` runs from repo root.
7. **Observability** — ✅ `GET /api/health/platform` + Admin Dashboard widget; ingest DLQ link.
8. **E2E in CI** — ✅ [`.github/workflows/e2e.yml`](.github/workflows/e2e.yml) (Compose + Playwright on `main`).

## P2 — Monetization hooks

9. **Organization / client isolation** — ✅ `require_client_scope` on client reports; tests in `test_client_isolation.py`.
10. **Usage metering** — ✅ `client_usage_events` table; upload + ACE transmit; `GET /api/billing/clients/{id}/usage`.
11. **ACE / compliance** — ✅ `ACE_ALLOW_SIMULATION`; production block when false; [`docs/PILOT_ACE.md`](docs/PILOT_ACE.md).

## Post-gap work (2026-10-10)

- **Billing isolation** — ✅ All `/api/billing/clients/{id}/*` + invoice/fee-config routes use `require_client_scope` / `require_invoice_scope`.
- **Template isolation** — ✅ Client template + alias routes scoped; template ownership checked.
- **Email verification** — ✅ Optional `REQUIRE_EMAIL_VERIFICATION`; `/verify-email` UI + portal API.
- **Stripe pilot** — ✅ Optional checkout session + webhook (`STRIPE_*` env); stores subscription on `clients`.
- **Onboarding UX** — ✅ First-login wizard (ported from emergent-gates `OnboardingWizard`, adapted to ingest/review/shipments/compliance).
- **Auth UI** — ✅ Admin error/routing/retry/silver/versions use `authFetch`.
- **Redis exposure** — ✅ Compose binds Redis to `127.0.0.1` by default (`REDIS_PUBLISH_HOST`).

**Not ported from emergent-gates** (different stack / audit-centric product): Mongo clients router, CBP correspondence importer, agent cache/metrics modules — revisit if you merge those codebases.

## Definition of done (paid pilot)

- New customer: invite → register → verify email (when enabled) → upload scenario_1 → review → entry prep without engineer intervention.
- `cd e2e && npm test` green against fresh `docker compose up`.
- Single command migrations on empty DB.
- Security review: no open admin tools on public ports in prod template.

See also: `.gsd/PRODUCTION_READINESS_PLAN.md`, `SECRETS_CHECKLIST.md`, `MVP_USER_GUIDE.md`.
