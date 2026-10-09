# GATE Platform — Playwright E2E

End-to-end coverage for three surfaces:

| Surface | URL (default) | Specs |
|---------|----------------|--------|
| **Platform UI** | http://localhost:3000 | `01`–`04`, `08` |
| **Commercial landing** | http://localhost:8080 | `06` |
| **Backend API** | http://localhost:8000 | `05`, `07` |

## Prerequisites

```bash
docker compose up -d   # postgres, redis, api, worker, beat, frontend, landing
```

Requires a valid `OPENAI_API_KEY` in `.env` for full document extraction pipeline tests.

## Run

```bash
cd e2e
npm install
npx playwright install chromium
npm test
npm run report   # HTML report
```

Demo users are seeded automatically (`admin@example.com` / `adminpassword`).

## Demo documents

Pipeline tests use files under `data/demo_documents/`:

- **Scenario 1** (`scenario_1/`) — full backend golden path (API upload + Celery poll)
- **TECH0892 text trio** — faster platform UI upload flow
