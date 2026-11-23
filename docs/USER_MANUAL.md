# GATE User Manual

**Customs intake → review → 7501 / ISF / CargoWise workbench**

Version grounded in live walkthrough: **SHP-2026-90418** (40-page multi-document PDF)  
Evidence folder: [`docs/e2e-runs/SHP-2026-90418/`](e2e-runs/SHP-2026-90418/)  
Last verified: 22 Nov 2026

---

## What GATE is (and is not)

| GATE does | GATE does not (v1 pilot) |
|-----------|---------------------------|
| Ingest trade PDFs/emails and extract structured fields | Unsupervised final HTS classification |
| Human review queue for low-confidence extractions | Live CBP filing unless ACE SFTP is separately configured |
| Assemble shipments; prepare **CBP Form 7501** drafts | Replace your certified ABI software |
| Generate **ISF-10** ABI drafts | Guarantee PGA auto-clearance |
| Export **7501 PDF / Excel**, **ACE JSON**, **CargoWise XML** | Multi-tenant SaaS for unrelated brokerages on one instance |

**Say this to brokers:** GATE is an AI intake + compliance triage + entry-prep workbench. You file to CBP with your existing ABI / ACE circuit.

---

## Roles

| Role | Typical user | Can do |
|------|--------------|--------|
| `admin` / `broker_admin` | Brokerage administrator | Clients, invites, ingest, review, shipments, entries, exports, settings |
| `broker_staff` | Licensed broker / entry writer | Same ops workbench (no org-admin user mgmt) |
| `client_admin` | Importer compliance manager | View own company, limited portal |
| `user` / `readonly` | Importer staff | Scoped read / light actions |

---

## End-to-end journey (worked example)

This section follows a **real run** using:

- **Importer:** Helios Precision Instruments Inc. (EIN / IOR `77-4910283`)
- **Bundle:** `data/test_dataset_2/SHP-2026-90418_40page_bundle.pdf` (40 pages, mixed document types)
- **Shipment ref:** `SHP-2026-90418`
- **Master BOL:** `MAEU664190821`
- **Container:** `MAEU7738291`
- **Port used in walkthrough:** `3001` (Seattle)

### Bundle map (why this file matters)

One PDF contains many customs document types:

| Pages | Document type |
|------:|---------------|
| 1 | Pre-alert / intake cover |
| 2 | ISF 10+2 data worksheet |
| 3–14 | Commercial Invoice (12 pages) |
| 15–28 | Packing List (14 pages) |
| 29–31 | Master Ocean Bill of Lading |
| 32–34 | Certificates of Origin (TW/VN, MX, JP/CN) |
| 35 | FDA medical device / prior notice |
| 36 | USDA APHIS botanical permit |
| 37 | FCC equipment authorization |
| 38 | Aluminum extrusion mill / origin statement |
| 39 | Arrival notice & terminal LFD |
| 40 | POA & continuous bond verification |

---

## 1. Sign in (broker)

1. Open the app → **Login**
2. Enter brokerage admin email / password
3. You land on **Workbench** (`/dashboard`)

**Workbench shows:** attention counts (review pending, shipments ready for prep, ingest processing/failed), recent review/shipments/entries, and quick actions.

**Walkthrough result:** broker profile reported `ace_mode: simulation`, CargoWise company `BROKER`, HTS seed available.

---

## 2. Onboard an importer client

**UI:** Clients → New client  
**API:** `POST /api/clients`

Minimum useful fields:

- Legal / display name  
- EIN and/or IOR number  
- Address, email, phone  
- Primary port (4-digit CBP port)  
- Internal code (optional)

Then set status to **active**.

**Walkthrough result**

| Field | Value |
|-------|-------|
| Client ID | `4bcfb88c-8054-4aea-b027-01d72f9ca0b7` |
| Name | Helios Precision Instruments Inc. |
| Status | `active` |
| IOR | `77-4910283` |

---

## 3. Invite & register a client user

**UI:** Clients → Users / Invite → share registration link  
**API:**

1. `POST /api/portal/invitations` with `email`, `client_id`, `role` (`client_admin`)
2. User opens `/register?token=…`
3. `POST /api/portal/accept-invitation` with name + password

**Walkthrough result:** Ava Nguyen registered as `client_admin` for Helios and could view the company record.

> Importer portal users do **not** replace broker entry writers. Customs prep remains a brokerage workflow.

---

## 4. Upload a multi-document PDF

**UI:** Ingest / Upload → drop the PDF → wait for job completion  
**API:** `POST /api/upload` (multipart) → poll `GET /api/ingest/jobs/{job_id}`

Expect statuses: `pending` → `processing` → `completed`.

**Walkthrough result**

| Field | Value |
|-------|-------|
| Filename | `SHP-2026-90418_40page_bundle.pdf` |
| Job ID | `4950ec05-6fdc-4c84-b32e-ef733dbc06fd` |
| File ID (`raw_files`) | `ce119583-179b-4c36-9e4d-de93cb3587b5` |
| Pages extracted | **40** (native text PDF) |
| Final status | `completed` |

**Ops note:** If many Celery beat/backlog tasks pile up, ingest can sit in `pending`. Clear or prioritize the worker queue, then re-queue `process_ingest_job` for the job ID. Workbench `ingest_processing` / `ingest_failed` counters help spot this.

---

## 5. Review queue (HITL)

**UI:** Review → open item → Original / Extracted Text / Download → Approve

**API:**

- List: `GET /api/review/queue`
- Detail: `GET /api/review/item/{id}`
- Approve: `POST /api/review/item/{id}/approve` with `{ "reviewer": "you@broker.com", "notes": "…" }`

**Walkthrough result:** Bundle produced review items (reason: low automated confidence). Both Helios review items were approved.

Use review when:

- Confidence is low  
- PGA / ADD-CVD flags need human eyes (this dataset expects CN aluminum ADD/CVD attention)  
- Multi-origin lines need COO confirmation

---

## 6. Create / open the shipment

**UI:** Shipments → New (or accept an assembly suggestion) → set BOL / importer / reference

**API:**

- Create: `POST /api/shipments`
- Update: `PATCH /api/shipments/{id}`
- Link file: `POST /api/shipments/{id}/link/{raw_file_id}`
- Auto-assemble: `POST /api/shipments/auto-assemble`

**Important:** shipment document links use **`raw_files.id`** (the upload `file_id`), not the review `document_metadata` id.

**Walkthrough result**

| Field | Value |
|-------|-------|
| Shipment ID | `24ea66e2-c63a-4645-8364-c13ae7752036` |
| Name / ref | `SHP-2026-90418 — Helios Precision Instruments` |
| BOL | `MAEU664190821` |
| Importer | Helios Precision Instruments Inc. |
| Linked raw file | `ce119583-…` |

---

## 7. Request a missing document

**UI:** Shipment detail → **Request Doc** → pick type from catalog → optional note → send

**API:** `POST /api/shipments/{id}/request-document`  
Catalog: `GET /api/reference-data/document-types` (CI, packing list, BOL, arrival notice, POA, PGA cert, COO, ISF worksheet, …)

If SMTP is configured, email goes to the importer contact. Reply-To can carry `[GATE-DOCREQ:…]` so IMAP auto-links the reply.

**Walkthrough result:** Arrival Notice request to `imports@helios-precision.example` → `email_dispatched: true` (dev SMTP path).

---

## 8. Generate ISF (10+2) draft

**UI:** Shipment detail → **Generate ISF** → **Download ISF-10 ABI Draft**

**API:**

- `POST /api/isf/from-shipment/{shipment_id}`
- `GET /api/isf/{isf_id}/abi-message`

**Walkthrough result**

| Field | Value |
|-------|-------|
| ISF ID | `26a2e13e-e09d-49c8-9037-9960a3ef9c77` |
| ISF number | `ISF-2611222332-4D28` |
| Status | `draft` |
| Message type | `ISF-10` |

Treat the ABI file as a **draft for your ABI software**, not as proof of CBP transmission.

Artifact: `docs/e2e-runs/SHP-2026-90418/exports/helios_isf_abi.json`

---

## 9. Prepare CBP Form 7501

**UI:** Shipment → **Prepare 7501** → review importer / transport / lines / warnings → export

**API:**

- Prep: `GET /api/entries/prep/{shipment_id}`
- Validate: `POST /api/entries/prep/{shipment_id}/validate`
- Export: `POST /api/entries/prep/{shipment_id}/export?format=pdf|excel|ace`

**Walkthrough result**

- Importer resolved: Helios Precision Instruments Inc.
- Line items prepared: **10**
- Validation: `is_valid: true` with warnings (e.g. configure `BROKER_FILER_CODE`; verify apportioned line values)
- Exports saved:
  - `helios_7501_prep.pdf`
  - `helios_7501_prep.xlsx`
  - `helios_7501_prep.ace.json`

**Broker checklist on this screen**

1. Confirm filer code (set `BROKER_FILER_CODE` in env)  
2. Confirm port / BOL / IOR EIN  
3. Spot-check HTS + COO per line (mixed origins in this shipment)  
4. Export PDF + Excel for ABI handoff  

---

## 10. Save as official entry + CargoWise

**UI:** Prep screen → **Save as Official Entry** → Entry detail → Export CargoWise XML

**API:**

- `POST /api/shipments/{id}/create-entry`
- `POST /api/export/cargowise/{entry_id}`
- `GET /api/export/cargowise/{entry_id}/download`

**Walkthrough result**

| Field | Value |
|-------|-------|
| Entry ID | `58db0030-f88f-4596-92f7-0731233ea17c` |
| Lines created | 10 |
| Port | `3001` |
| CargoWise XML | `helios_cargowise.xml` (~6.9 KB) |

Import/validate the XML in your CargoWise sandbox using the pilot `CARGOWISE_COMPANY_CODE` / enterprise ID.

---

## 11. ACE file (simulation vs live)

**UI:** Entry detail → File / Transmit (behavior depends on env)

**API:**

- File: `POST /api/entries/{entry_id}/file`
- Simulate response (dev): `POST /api/entries/{entry_id}/simulate-ace-response` with `{ "ace_status": "accepted" }`
- Live transmit path (when SFTP configured): `POST /api/ace/transmit/entry/{entry_id}`

**Walkthrough (dev simulation)**

1. File → `mode: simulation`, status `filed` / ACE `submitted`  
2. Simulate accepted → status `accepted`

**Production pilot:** set `ACE_ALLOW_SIMULATION=false` and keep SFTP off until the broker’s circuit is ready. Product should export drafts only—no fake “filed with CBP” success.

---

## 12. Duty calculator & HTS lookup

**UI:** Tools → Duty Calculator; HTS search on prep lines

**API:**

- `POST /api/tools/duty-calculator/calculate`  
  Body: `{ "hts_code": "9018199560", "value": 2337.5, "quantity": 55, "country_of_origin": "TW" }`
- `GET /api/reference-data/hts/search?query=8517.62&limit=5`

**Walkthrough:** calculated MED-201 (`9018.19.9560`, TW) and MET-509 (`7604.29.5090`, CN) for ADD/CVD awareness.

---

## Screen map (broker daily path)

```
Login → Workbench (/dashboard)
         ├─ Clients          onboard importer + invite users
         ├─ Ingest / Upload  drop multi-doc PDF / email attachments
         ├─ Review           approve / correct extractions
         ├─ Shipments        assemble, request docs, ISF, Prepare 7501
         ├─ Entries          official entry, CW XML, ACE file/export
         ├─ Duty Calculator  line / landed-cost estimates
         └─ System Health    queue, storage, vector (admin)
```

---

## Multi-document PDF tips

1. Prefer native-text PDFs when possible (this bundle: 40/40 native). Scanned siblings need OCR time.  
2. After ingest, open **Extracted Text** and confirm each section header (Invoice / PL / BOL / PGA / POA).  
3. Link the upload **`file_id`** to the shipment.  
4. Use **Request Doc** only for truly missing pieces—don’t re-request types already inside the bundle unless you need an amended original.  
5. Expect HITL on mixed-origin / PGA / aluminum lines even when extraction looks “complete.”

---

## Configuration checklist (before first client)

| Setting | Purpose |
|---------|---------|
| `BROKER_FILER_CODE` | 3-char CBP filer on 7501 / ISF |
| `BROKER_NAME` / brand vars | White-label UI |
| `CARGOWISE_COMPANY_CODE` / `CARGOWISE_ENTERPRISE_ID` | CW XML |
| SMTP + IMAP | Doc requests, password resets, reply auto-link |
| `ACE_ALLOW_SIMULATION` / SFTP | Live vs export-only |
| OpenAI (or configured LLM) key | Extraction quality |

See also: [PILOT_ONBOARDING.md](PILOT_ONBOARDING.md) · [PILOT_ACE.md](PILOT_ACE.md) · [PILOT_SMTP.md](PILOT_SMTP.md) · [ARCHITECTURE.md](ARCHITECTURE.md)

---

## Troubleshooting (from this run)

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| Upload stays `pending` | Celery backlog / beat flood | Worker listens `-Q ingest,celery`; uploads go to `ingest`. Run `./provisioning/scripts/preflight_smoke.sh`. If still stuck: `docker exec docingestion_worker celery -A app.core.celery_app purge -f` then re-upload |
| “Document link” FK error | Used metadata id instead of `raw_files` id | Link with upload `file_id` |
| Prep warns missing filer | `BROKER_FILER_CODE` empty | Set env and restart API |
| Entry create fails on documents | raw_file vs metadata FK mismatch | Fixed in create-entry resolver; upgrade API |
| ACE “must be ready_to_file” | Entry already filed/released | Expected lifecycle; use a draft entry |
| Duty calc 422 `value` required | Wrong field name | Send `value`, not `entered_value` |

---

## Walkthrough artifact index

| Artifact | Path |
|----------|------|
| Full evidence JSON | `docs/e2e-runs/SHP-2026-90418/evidence.json` |
| 7501 PDF / Excel / ACE | `docs/e2e-runs/SHP-2026-90418/exports/helios_7501_prep.*` |
| CargoWise XML | `docs/e2e-runs/SHP-2026-90418/exports/helios_cargowise.xml` |
| ISF ABI draft | `docs/e2e-runs/SHP-2026-90418/exports/helios_isf_abi.json` |
| Shipment / entry / prep JSON | `docs/e2e-runs/SHP-2026-90418/artifacts/` |

---

## Acceptance script (copy for pilot day-1)

1. Login → Workbench loads  
2. Create importer client + invite one user  
3. Upload `SHP-2026-90418_40page_bundle.pdf` → job `completed`, 40 pages  
4. Review → open → approve at least one item  
5. Shipment created/linked with BOL `MAEU664190821`  
6. Request Doc sends (or clear SMTP message)  
7. Generate ISF + download ABI draft  
8. Prepare 7501 → export PDF + Excel  
9. Save official entry → download CargoWise XML  
10. Confirm ACE behavior matches pilot mode (simulation off in production)

**Pilot success:** broker completes 1–10 on their own docs without a blocker ticket.
