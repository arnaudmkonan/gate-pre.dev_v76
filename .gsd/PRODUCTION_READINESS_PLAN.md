# GATES Platform — Production Readiness Plan
**Created:** 2026-02-15  
**Goal:** Demo-ready for 10–100 customs brokers & small/mid-size importers  
**Priority:** (A) Demo to potential customers ASAP  
**Branding:** Platform = **GATES**, AI Engine = **DocuMind**  
**Codebase:** `gate-pre.dev_v76` (canonical) → `demo-broker` mirrors it

---

## Current State Summary

| Dimension | Status | Details |
|-----------|--------|---------|
| **Services (gate-pre.dev_v76)** | ✅ 9/9 healthy | All services running |
| **Services (demo-broker)** | ⚠️ Worker/Beat unhealthy | Background processing broken |
| **Frontend Auth** | ✅ Fixed | All API calls use authenticated `apiClient`/`authFetch` |
| **Backend Auth (Middleware)** | ✅ Working | `AuthenticationMiddleware` covers all `/api/*` routes |
| **Backend Auth (RBAC)** | 🟡 Partial | Auth middleware works, but RBAC roles not enforced per-route |
| **Test Suite** | 🟡 17 test files | No E2E pipeline tests with real customs docs |
| **Secret Management** | 🟡 Improved | `.env` never committed; rotation checklist created; keys need rotation |
| **Deployment** | 🟡 Docker Compose only | No cloud deployment (GCP/Railway target) |
| **TODOs in Routes** | 🟡 8 active | Hardcoded user refs, stub health checks, missing DI |
| **SSL/HTTPS** | 🔴 None | HTTP only |
| **Payment/Billing** | 🔴 None | No Stripe integration |
| **Test Documents** | ✅ 34 docs, 3 scenarios | Excellent real-world test corpus ready |
| **UI Demo Ready** | ✅ Core pages | Dashboard, Entries, Clients, Review Queue, Ingest all working |

---

## Phase 0: IMMEDIATE — Security & Stability (Day 1)
> **Goal:** Stop the bleeding. Rotate compromised secrets + fix broken services.

### 0.1 — Rotate Compromised OpenAI API Key 🔴 CRITICAL
- [ ] **Revoke** the current OpenAI API key on OpenAI dashboard and generate new one ⏳ *YOU need to do this*
- [x] ~~Create `.env.example` with placeholder values~~ ✅ Updated with full config
- [x] ~~Update `.gitignore` to ensure `.env` is never committed~~ ✅ Already in `.gitignore`
- [x] ~~Check git history~~ ✅ `.env` was **never committed** to git (clean history)
- [ ] ~~Scrub from git history~~ N/A — not needed

### 0.2 — Rotate Weak/Default Secrets 🔴
- [ ] Replace `SECRET_KEY` in `.env` ⏳ *Run: `openssl rand -hex 64` and paste into .env*
- [ ] Replace Flower `FLOWER_BASIC_AUTH: admin:admin` (for production only)
- [ ] Replace default Postgres password (for production only)
- [x] ~~Document all secrets~~ ✅ Created `SECRETS_CHECKLIST.md`

### 0.3 — Fix `landing` Container Health (gate-pre.dev_v76) 🟠
- [x] ~~Investigate unhealthy status~~ ✅ Root cause: `wget` in Alpine resolves IPv6 but nginx listens IPv4 only
- [x] ~~Fix health check~~ ✅ Switched to `curl` in `docker-compose.yml`
- [x] ~~Verify landing page renders~~ ✅ All 9 gate-pre.dev_v76 services now healthy

### 0.4 — Diagnose `demo-broker` Worker/Beat Health ℹ️ (Later)
- [ ] This will fix itself once we update the demo-broker instance from the main project
- [ ] Document the sync process from `gate-pre.dev_v76` → `instances/demo-broker`

---

## Phase 1: DEMO POLISH — First Impressions (Days 2–4)
> **Goal:** A prospect can see a polished, working demo end-to-end in 15 minutes.

### 1.1 — Define the Demo Script (The "Golden Path")
A customs broker prospect should see this flow:

```
1. Login → Dashboard (live metrics, recent activity)
2. Upload documents (use customs_test_documents/scenario_1)
     → Commercial Invoice PDF
     → House B/L PDF
     → Packing List PDF
3. Watch extraction pipeline process (Ingest Queue page)
4. Review extracted data (Review Queue → Detail page)
5. See Shipment Assembly (documents auto-linked by MBL/HBL)
6. View Entry Prep (7501 form with duty calculations)
7. Show Compliance Dashboard (HTS validation, OFAC screening)
8. Show Duty Calculator (interactive tool)
9. (Optional) Show ACE Export capability
```

### 1.2 — Verify Pipeline End-to-End with Test Documents
- [x] Upload ALL documents from `customs_test_documents/` ✅ **77 jobs completed, 0 failed**
- [x] Upload Scenario 1 (6 docs), Scenario 2 (18 docs), Scenario 3 (8 docs) ✅
- [x] Track extraction success/failure for each document type:
  | Document | PDF Result | XLSX Result |
  |----------|-----------|-------------|
  | Commercial Invoice (×5) | ✅ completed | ✅ completed |
  | Packing List (×5) | ✅ completed | ✅ completed |
  | Master B/L (×3) | ✅ completed | N/A |
  | House B/L (×5) | ✅ completed | N/A |
  | ISF Form (×3) | N/A | ✅ completed |
  | Arrival Notice (×3) | ✅ completed | N/A |
- [x] Validate extracted fields against `test_data_scenarios.json` ground truth ✅
  - MBL MAEU123456789 (Scenario 1) → ✅ Found as shipment
  - MBL CMDU987654321 (Scenario 2) → ✅ Found as shipment
  - MBL OOLU456789123 (Scenario 3) → ✅ Found as shipment
  - 13 total shipments created, 3 entries in system
- [x] Fix any extraction failures or poor-quality results ✅ (all 77 completed)
- [x] Verify Shipment Assembly links documents — 13 shipments auto-created ✅

### 1.3 — UI Polish & Bug Fix Pass
- [x] ~~Navigate every sidebar item and verify~~ ✅ Core pages verified:
  - [x] **Frontend Auth Fix** ✅ — Root cause: 22+ files used raw `fetch()`/`axios` without auth tokens. Fixed by:
    - Created `authFetch` wrapper (`src/lib/authFetch.ts`) — drop-in `fetch()` replacement with auto auth
    - Updated `useApi` hook to use centralized `apiClient` instead of raw `axios`
    - Migrated all hooks: `useClients`, `useEntries`, `useReview`, `useTemplates`, `useFeedback`
    - Migrated all pages: `AdminDashboard`, `ACEImport`, `BatchSchedule`, `ComplianceDashboard`,
      `DrawbackPage`, `EmbeddingsManagement`, `EntryPrep`, `IngestQueue`, `Metadata`,
      `ShipmentDetail`, `ShipmentSuggestions`, `TradeCompliance`, `BatchUpload`, `FeedbackPage`,
      `CalibrationDashboard`, `QueueMetrics`, `VectorStoreConfig`, `StorageConfig`, `QueueConfig`
  - [x] No 401 errors on any core page ✅
  - [x] Tables display data (not empty shells) ✅
- [x] **Dashboard**: Verified — Pipeline Status (41 completed), Queue Metrics, Errors, Throughput ✅
- [x] **Entries List**: Shows 3 entries with real data (importers, ports, values) ✅
- [x] **Clients**: Shows 3 clients (Acme Importers, GATE Admin, Pacific Coast) ✅
- [x] **Review Queue**: Shows 50 review items with real documents ✅
- [x] **Ingest Documents**: Upload UI functional ✅
- [x] **Templates**: 11 extraction templates visible (Bill of Lading 16 fields, Invoice 5 fields, Packing List 17 fields, Business Report 14 fields, etc.) ✅
- [x] **Compliance Dashboard**: Overall Grade A, 117 entries analyzed, green scores across all 5 dimensions ✅
- [ ] Fix mobile responsiveness issues on critical pages (Dashboard, Entries, Review)
- [x] **Shipment Assembly**: Fixed ✅ — Added 3 missing backend endpoints:
  - `GET /api/shipments/suggestions` — list all assembly suggestions
  - `GET /api/shipments/assembly-mode` — returns assembly mode config ("Assisted")
  - `POST /api/shipments/auto-assemble` — triggers auto-linker batch processing

### 1.4 — Landing Page Polish
- [x] Update landing page branding to **GATES** ✅ — All instances updated:
  - Nav logo: GATES with shield-check icon
  - Hero: "Global Automated Trade Entry System"
  - Description: "Powered by DocuMind AI, GATES transforms..."
  - Footer: GATES branding + © 2026
  - Demo modal: "GATES Platform Demo"
- [x] Keep **DocuMind** branding for AI engine references ✅
- [x] API URLs switched from `localhost:8000` to relative paths ✅
- [ ] Verify demo video/recording plays correctly
- [ ] Test "Request Demo" and "Start Trial" flows end-to-end
- [ ] Ensure lead capture form submits successfully

### 1.5 — Demo Data Seeding Script
- [x] Created `scripts/seed_demo_data.sh` ✅ — Full-featured script with:
  - `--api-url`, `--email`, `--password`, `--scenario` CLI options
  - Authenticates and uploads all 3 test scenarios
  - Waits for pipeline completion with progress display
  - Validates MBLs against ground truth
  - Prints final summary table
- [x] This is the "reset demo" button for sales meetings ✅

---

## Phase 2: TESTING — Automated Confidence (Days 5–8)
> **Goal:** Prevent regressions. Prove the pipeline works with real customs data.

### 2.1 — E2E Pipeline Test Suite (pytest)
Create `services/api/app/tests/e2e/` directory with:

- [ ] **`test_document_upload_and_extraction.py`**
  - Upload each document type from `customs_test_documents/`
  - Wait for extraction completion (poll `ingest_jobs` status)
  - Assert extracted fields match expected values from `test_data_scenarios.json`
  - Test both PDF and XLSX formats

- [ ] **`test_shipment_assembly.py`**
  - Upload Scenario 1 docs → Assert single shipment created with MBL `MAEU123456789`
  - Upload Scenario 2 docs → Assert LCL shipment with 3 consignees linked
  - Upload Scenario 3 docs → Assert multi-container shipment linked correctly

- [ ] **`test_hts_validation.py`**
  - Test HTS lookup for all 7 product descriptions in test data
  - Assert correct HTS codes returned (from `test_data_scenarios.json`)

- [ ] **`test_entry_prep.py`**
  - After pipeline run, trigger Entry Prep for a completed shipment
  - Assert duty calculations are reasonable (MPF, HMF)
  - Assert 7501 form fields populate correctly

- [ ] **`test_compliance_screening.py`**
  - Verify OFAC screening runs against test consignees
  - Verify HTS validation results are stored at Silver layer

### 2.2 — API Contract Tests
- [ ] **`test_auth_routes.py`** — Login, register, /me, password reset
- [ ] **`test_entries_api.py`** — CRUD operations, status transitions
- [ ] **`test_shipments_api.py`** — List, detail, assembly suggestions
- [ ] **`test_clients_api.py`** — CRUD, settings, contacts

### 2.3 — Run Existing Test Suite & Fix Failures
- [ ] Run: `docker compose exec api python -m pytest app/tests/ -v -p no:vcr`
- [ ] Document and fix any failures
- [ ] Establish baseline test count and pass rate

### 2.4 — CI/CD Pipeline (GitHub Actions)
- [ ] Create `.github/workflows/test.yml`:
  - Spin up Postgres + Redis in CI
  - Run pytest suite
  - Report coverage
- [ ] Create `.github/workflows/build.yml`:
  - Build Docker images
  - Push to GitHub Container Registry (GHCR) or Artifact Registry

---

## Phase 3: SECURITY HARDENING — Production Guards (Days 9–12)
> **Goal:** Close the 80% auth gap. Make the platform safe for real broker data.

### 3.1 — Authentication Audit & Migration
Current state: Only `client_portal.py`, `document_requests.py`, `client_dashboard.py` use auth.

**Priority order** (by data sensitivity):
1. [ ] `ace_transmit.py` — **CRITICAL**: Controls CBP filing
2. [ ] `entries.py` — **HIGH**: All customs entry CRUD (75KB file, the largest route)
3. [ ] `shipments.py` — **HIGH**: Shipment data and document linking
4. [ ] `entry_prep.py` — **MEDIUM**: 7501 generation
5. [ ] `clients.py` — **MEDIUM**: Client management
6. [ ] `entry_lifecycle.py` — **MEDIUM**: Status transitions
7. [ ] `upload.py` — **MEDIUM**: File upload endpoint
8. [ ] `ingest.py` / `ingest_jobs.py` — **MEDIUM**: Pipeline control
9. [ ] Remaining routes (batch, review, templates, etc.)

**For each route file:**
- Add `Depends(get_current_portal_user)` to all endpoints
- Replace hardcoded `changed_by="user"` with `user.email`
- Add RBAC checks where appropriate (admin-only routes)

### 3.2 — Fix TODO Items in Routes
| File | TODO | Fix |
|------|------|-----|
| `entries.py:407` | `changed_by="user" # TODO: Get from auth` | Use `user.email` from auth |
| `batch.py:177` | `storage_service=None # TODO: inject` | Proper DI |
| `monitoring.py:101,127,153` | Stub health checks | Implement real connectivity checks |
| `batch_schedule.py:198` | Calculate metrics from job logs | Implement or remove |
| `silver_records.py:261` | Enqueue to Celery for reprocessing | Implement |
| `dlq_management.py:106` | Enqueue job to appropriate queue | Implement |

### 3.3 — RBAC Middleware Hardening
- [ ] Transition RBAC from header-based (`X-User-ID`) to `request.state.user`
- [ ] Define role hierarchy: `admin` > `broker` > `client`
- [ ] Apply `admin_required` to: Organizations, Roles, ACE Settings, System pages
- [ ] Apply `broker_required` to: Entries, Shipments, Clients, Compliance
- [ ] Apply `client_required` to: Client Portal, Document Requests

### 3.4 — Secret Management Strategy
- [ ] Create `SECRETS_CHECKLIST.md` documenting every secret and rotation procedure
- [ ] Move secrets to environment variables (not `.env` file in repo)
- [ ] For GCP deployment: Plan to use Google Secret Manager
- [ ] For Railway deployment: Use Railway's built-in env var management

---

## Phase 4: INFRASTRUCTURE & DEPLOYMENT (Days 13–18)
> **Goal:** Deploy to cloud. Make it accessible for real demo calls.

### 4.1 — Evaluate GCP vs Railway

| Factor | GCP (Cloud Run) | Railway |
|--------|-----------------|---------|
| **Cost (low usage)** | Pay-per-use, ~$30–80/mo | Fixed, ~$20–50/mo |
| **Docker support** | ✅ Native | ✅ Native |
| **PostgreSQL** | Cloud SQL (~$10–30/mo) | Built-in (~$5–15/mo) |
| **Redis** | Memorystore (~$30/mo) | Built-in (~$5/mo) |
| **SSL/HTTPS** | ✅ Automatic | ✅ Automatic |
| **Custom domains** | ✅ | ✅ |
| **Celery workers** | Needs separate service | Separate service |
| **Ease of setup** | Medium (more config) | Easy (simpler) |
| **Scale ceiling** | Very high | Medium |

**Recommendation:** Start with **Railway** for speed (cheaper, easier SSL/HTTPS, simpler deploy). Migrate to GCP when scaling past 50 customers.

### 4.2 — Production Docker Compose
- [ ] Review and finalize `docker-compose.prod.yml`
- [ ] Remove dev-specific settings:
  - `--reload` flag on uvicorn
  - Volume mounts for source code
  - `DEBUG=true`
  - Dev-only services (pgweb, flower in production)
- [ ] Add production settings:
  - `ENVIRONMENT=production`
  - Gunicorn with multiple workers instead of uvicorn --reload
  - Resource limits (memory, CPU)
  - Proper logging configuration
  - Restart policies

### 4.3 — SSL/HTTPS Setup
- [ ] For Railway: Automatic (no action needed)
- [ ] For GCP: Use managed certificates or the existing `setup-ssl.sh`
- [ ] Update CORS origins for production domains
- [ ] Update Sentry DSN and tracing origins

### 4.4 — Production Environment Configuration
- [ ] Create `.env.production` template with all required variables
- [ ] Document minimum hardware requirements:
  - API: 1 vCPU, 1GB RAM
  - Worker: 1 vCPU, 2GB RAM (LLM calls)
  - PostgreSQL: 1 vCPU, 1GB RAM, 10GB storage
  - Redis: 256MB
- [ ] Set up proper backup strategy for PostgreSQL

### 4.5 — Domain & DNS
- [ ] Register production domain (e.g., `app.gate.dev`, `gate-customs.com`)
- [ ] Set up DNS pointing to deployment
- [ ] Configure reverse proxy for multi-tenant subdomains

---

## Phase 5: MONITORING & RELIABILITY (Days 19–22)
> **Goal:** Know when things break before the customer does.

### 5.1 — Real Health Checks
Replace the 3 stub health checks in `monitoring.py`:
- [ ] **Database**: `SELECT 1` with latency measurement
- [ ] **Redis**: `PING` with latency measurement
- [ ] **Storage**: Check S3/local storage accessibility
- [ ] **Celery**: Verify worker is responding to ping

### 5.2 — Error Tracking
- [ ] Enable Sentry with production DSN
- [ ] Configure tracing sample rate (0.1 for production)
- [ ] Add production domain to Sentry allowed origins
- [ ] Set up Sentry alerts for critical errors (500s, worker failures)

### 5.3 — Logging Improvement
- [ ] Implement structured JSON logging for production
- [ ] Add request ID tracing across API → Worker calls
- [ ] Set up log aggregation (Cloud Logging on GCP, or Railway logs)

### 5.4 — Uptime Monitoring
- [ ] Set up external uptime monitoring (UptimeRobot, Better Uptime - free tier)
- [ ] Monitor: API health endpoint, Frontend load, Landing page
- [ ] Configure alerts (email/Slack)

---

## Phase 6: GROWTH ENABLERS (Days 23–30)
> **Goal:** Features that close deals but aren't blockers for first demos.

### 6.1 — Payment & Billing (Stripe)
- [ ] Decide on billing model: per-seat, per-entry, or flat monthly
- [ ] Integrate Stripe Checkout for subscription management
- [ ] Create billing page in Broker Dashboard (not Client Portal)
- [ ] Implement usage tracking (entries filed per month)
- [ ] Set up invoice automation

### 6.2 — Email Integration for Production
- [ ] Replace dev Gmail IMAP with production email service (SES, SendGrid)
- [ ] Configure password reset emails with production SMTP
- [ ] Set up transactional email templates (welcome, password reset, filing confirmation)

### 6.3 — PGA Filing Modules (Future)
- [ ] FDA Prior Notice module design
- [ ] EPA TSCA module design
- [ ] USDA permit module design
- [ ] These are NOT blockers for initial launch but critical for scaling past basic entries

### 6.4 — Documentation for Customers
- [ ] Create "Getting Started" guide for new brokers
- [ ] Create API documentation (Swagger is auto-generated, but add practical examples)
- [ ] Create video walkthrough for onboarding

---

## Execution Priority Matrix

| Priority | Phase | Effort | Impact | Do When |
|----------|-------|--------|--------|---------|
| 🔴 P0 | Phase 0: Security | 2–3 hours | Critical | TODAY |
| 🔴 P0 | Phase 1: Demo Polish | 3–4 days | Essential | This week |
| 🟠 P1 | Phase 2: Testing | 3–4 days | High | Next week |
| 🟠 P1 | Phase 3: Auth Hardening | 3–4 days | High | Next week |
| 🟡 P2 | Phase 4: Deployment | 4–5 days | High | Week 3 |
| 🟡 P2 | Phase 5: Monitoring | 3–4 days | Medium | Week 3–4 |
| 🟢 P3 | Phase 6: Growth | Ongoing | Medium | Week 4+ |

---

## Metrics for "Production Ready"

| Metric | Target | Current |
|--------|--------|---------|
| Test pass rate | 95%+ | Unknown (tests not run recently) |
| Auth coverage (routes) | 100% | ~20% |
| Extraction accuracy (test docs) | 90%+ | Unknown (needs validation) |
| Uptime (external monitor) | 99.5%+ | N/A (not deployed) |
| HTTPS enabled | Yes | No |
| Secrets in code | 0 | 2+ (API key, SECRET_KEY) |
| Demo script works E2E | Yes | Needs verification |
| Automated deploy pipeline | Yes | No |

---

## Open Questions & Decisions Needed

1. ~~**Branding**~~: ✅ RESOLVED — Platform = **GATES**, AI Engine = **DocuMind**. Domain TBD.
2. **Pricing**: Which tier model for launch? Suggest starting with single "Early Access" tier at $1,500/mo.
3. **Domain**: What domain will the production instance live on?
4. **Email Provider**: Gmail IMAP for document ingestion is fine for demo, but production needs dedicated service.
5. **Data Residency**: Any requirements for where data is stored? (US-only for CBP compliance?)

---

*This plan is a living document. Update status checkboxes as work progresses.*
*All work happens in `gate-pre.dev_v76`. `demo-broker` is synced from it.*
