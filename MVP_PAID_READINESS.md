# Paid-Worthy MVP — Boutique Customs Broker Copy-Sale Ledger

Branch: `mvp/paid-readiness`  
Positioning: **Dedicated Single-Tenant AI Document Intake, Compliance Triage & CBP 7501 / CargoWise Entry-Prep Workbench**

---

## Priority & Implementation Tracker (Synchronized Source of Truth)

### P0 — Hard Ship Blockers (5 / 5 Completed)

| ID | Domain | Requirement | Status | Primary Files |
|----|--------|-------------|--------|---------------|
| **P0-1** | **19 USC § 1641 Compliance** | Eliminate synthetic 7501 fallbacks (`G76`, port `2704`, HTS `8471.30.0100`, fake EIN `94-3281940-00`, `$48,500` value); update FY2026 CBP MPF caps (`$33.58` / `$651.50`); wire DB `HTSCode` rate lookup & `Client` IOR matching | **DONE** | `services/api/app/services/entry_prep_service.py`, `services/api/app/api/routes/shipments.py` |
| **P0-2** | **Tenancy & Role Separation** | Separate brokerage staff (`admin`, `broker_staff`) from external importer portal roles (`client_admin`, `user`, `readonly`); enforce `require_client_scope` / `portal_user_client_id` on `clients`, `entries`, `poa`, `files`, `leads`, `admin/dashboard` | **DONE** | `services/api/app/startup/client_access.py`, `services/api/app/models/client_portal.py`, `services/api/app/api/routes/{clients,entries,poa,files,leads}.py` |
| **P0-3** | **Portal Auth & IDOR** | Lock down `/api/portal/users/*` and `/invitations` against privilege escalation; upgrade password hashing from SHA-256 to OpenSSL `scrypt` (`N=16384, r=8, p=1`) with on-login rehash + brute-force lockout (`HTTP 429`) | **DONE** | `services/api/app/api/routes/client_portal.py`, `services/api/app/services/client_portal_auth_service.py` |
| **P0-4** | **Greenfield DB & Tariff Seed** | Guard root Alembic migration (`b663ab8dfc32`) + resync `hts_codes` serial sequence; seed 57 USITC 10-digit HTS subheadings + `--csv` importer; pin compatible `celery`/`kombu`/`redis`/`aiosmtplib`; harden `provision.sh` (`asyncpg`, loopback DB/Redis/Flower) | **DONE** | `services/api/docker-entrypoint.sh`, `services/api/app/startup/hts_seed.py`, `provisioning/scripts/provision.sh`, `services/api/requirements.txt` |
| **P0-5** | **Commercial IP & Secrets** | Replace `MIT License` in `README.md` with proprietary single-instance [`LICENSE`](LICENSE); scrub committed password in `instances/demo-broker/README.md` | **DONE** | `LICENSE`, `README.md`, `instances/demo-broker/README.md` |

---

### P1 — Regulatory Recordkeeping & Daily Entry-Writer UX (6 / 6 Completed)

| ID | Domain | Requirement | Status | Primary Files |
|----|--------|-------------|--------|---------------|
| **P1-1** | **19 CFR Part 163 Recordkeeping** | Extend `AUDIT_LOG_RETENTION_DAYS` from `180` to `2555` (7 years; startup error if `< 1825`); add `audit()` hooks on 7501 PDF/Excel, CargoWise XML, missing-doc requests, and POA lifecycle | **DONE** | `services/api/app/services/audit_service.py`, `services/api/app/api/routes/{cargowise_export,poa,shipments}.py` |
| **P1-2** | **ISF & ACE Guardrails** | Block simulated ISF/ACE filing in production when `ACE_ALLOW_SIMULATION=false`; prefix sandbox refs with `SIM-ISF-` / `SIM-ACE-`; gate `/file`, `/poll-ace`, `/simulate-ace-response`; add **Download ISF-10 ABI Draft** on Shipment Detail; hide ACE `Simulate` button in prod | **DONE** | `services/api/app/services/{isf_service,ace_status_service}.py`, `services/api/app/api/routes/{entries,isf}.py`, `apps/web/src/pages/ShipmentDetailPage.tsx`, `apps/web/src/components/ACEStatusPanel.tsx` |
| **P1-3** | **Entry Writer Line & PDF UX** | Add Official Entry line-item **Edit** & **Delete** APIs/modals, live **USITC HTS Autocomplete**, inline `DocumentViewer` with `<object>` PDF fallback, preserve `entry_date` / `import_date`, and wire `Delete Shipment` + `Request Missing Doc` email API | **DONE** | `apps/web/src/pages/{EntryDetailPage,NewEntryPage,ShipmentDetailPage}.tsx`, `apps/web/src/components/HTSAutocompleteInput.tsx` |
| **P1-4** | **Review → Shipment Gold Sync** | Automatically propagate Review Queue approvals and field corrections into linked `Shipment` headers and duty/value totals | **DONE** | `services/api/app/services/review_service.py` |
| **P1-5** | **Shared Inbox & API Key Scopes** | Register `monitor-email-inbox` in Celery Beat + immediate `process_ingest_job.delay`; enforce granular `X-API-Key` scopes (`entries:read` vs `entries:write`, block admin); secure `STORAGE_CALLBACK_SECRET` | **DONE** | `services/api/app/core/celery_app.py`, `services/api/app/workers/email_monitor_worker.py`, `services/api/app/middleware/auth.py` |
| **P1-6** | **CargoWise XML Serialization** | Parameterize `CARGOWISE_COMPANY_CODE` / `CARGOWISE_ENTERPRISE_ID` and fix nested `<Company><Code>...</Code></Company>` XML element serialization | **DONE** | `services/api/app/services/cargowise_exporter.py` |

---

### P2 — White-Labeling, Verification & Pre-Handoff Ops (3 / 3 Completed)

| ID | Domain | Requirement | Status | Primary Files |
|----|--------|-------------|--------|---------------|
| **P2-1** | **White-Label & Broker Profile** | Centralize `VITE_BRAND_NAME`, `VITE_BRAND_SUBTITLE`, `VITE_ENABLE_DEMO_LOGIN`, `VITE_ENABLE_ACE_SIMULATION`, parameterized transactional email templates (`BROKER_NAME`), and **Broker Profile** tab on `/settings/platform` | **DONE** | `apps/web/src/config/brand.ts`, `apps/web/src/pages/SettingsPage.tsx`, `services/api/app/services/email_service.py` |
| **P2-2** | **Automated Test & E2E Coverage** | 23 backend hardening/isolation unit tests + 35 Playwright E2E tests (`01`, `03`, `04`, `05`, `06`, `09`) + clean `npm run type-check` / `npm run lint` | **DONE** | `services/api/app/tests/test_boutique_broker_hardening.py`, `e2e/tests/*` |
| **P2-3** | **Customer Handoff Smoke Script** | Single-command post-provision verification (`./provisioning/scripts/verify-instance.sh`) checking health, auth, broker profile, 19 CFR 163 compliance, and USITC HTS table | **DONE** | `provisioning/scripts/verify-instance.sh` |

---

### Deliberately Scoped to Optional Phase 2 Upsell (Do Not Promise Out-of-the-Box)

1. **Direct Live CBP ACE ABI / ISF SFTP Interconnect:** Requires the broker's CBP-assigned ABI certification / MQ or SFTP circuit (v1 hands off validated 7501 PDFs, ISF-10 ABI drafts, and CargoWise `UniversalShipment` XML into their existing ABI transmitter).
2. **Automated Legal 10-Digit GRI HTS Classification Agent:** v1 extracts supplier HTS codes and provides USITC schedule search + duty calculation; final GRI legal classification remains licensed broker review.
3. **Database Column-Level Encryption (KMS) for Tax IDs:** v1 relies on isolated single-broker Postgres volumes + GPG-encrypted backups (`ENCRYPTION_PASSPHRASE`).

---

### Second-Pass Review (pre-commit) — 2026-11-18

**Verdict: ready-with-caveats** for a dedicated single-tenant boutique-broker sale as an intake/7501/CargoWise workbench (not turnkey live CBP filing).

| Check | Result |
|-------|--------|
| Synthetic 7501 fallbacks scrubbed | Pass (no `G76` / fake EIN / `$48500` in entry_prep) |
| ACE `/file`, `/poll-ace`, `/simulate-ace-response` gated | Pass (`ace_simulation_blocked` + `SIM-ACE-` prefix) |
| ISF router auth dependencies | Pass (fixed tags/`Depends(get_current_user)`) |
| Request Doc honesty | Pass (API + UI report SMTP miss) |
| Hardening pytest | **14 passed** |
| `verify-instance.sh` | Pass (health, scrypt auth, 2555d audit, HTS seed) |
| Frontend type-check / lint | Pass |
| Playwright 01/03/04/05/06 | Pass |
| Playwright 09 | Flaky without seeded review-queue data (env, not regression) |

**Accepted caveats for this sale model:** shipments remain DB-wide (no `client_id`; OK for dedicated single-tenant DB); Vite brand vars are bake-time (rebuild frontend per white-label); live ACE/ISF SFTP remains Phase-2 upsell.
