# GATE Architecture & Data Flow

Dedicated **single-tenant** customs-broker workbench: AI document intake, compliance triage, CBP 7501 / ISF / CargoWise entry prep.  
Live ACE/ISF SFTP is optional (Phase 2); default production mode is **export-only**.

Related: [PILOT_ONBOARDING.md](PILOT_ONBOARDING.md) · [PILOT_ACE.md](PILOT_ACE.md) · [PILOT_SMTP.md](PILOT_SMTP.md)

---

## 1. System architecture

```mermaid
flowchart TB
  subgraph Actors["Actors"]
    Broker["Broker staff<br/>admin / broker_staff"]
    Importer["Importer / client portal"]
    ABI["Broker ABI / CargoWise<br/>external transmitter"]
  end

  subgraph Edge["Client edge"]
    Web["apps/web<br/>React + Vite :3000"]
    Landing["Landing site :8080"]
  end

  subgraph Runtime["Instance runtime Docker Compose"]
    API["services/api<br/>FastAPI :8000"]
    Worker["Celery worker"]
    Beat["Celery beat"]
    Redis[("Redis<br/>broker + cache")]
    PG[("PostgreSQL 16<br/>+ pgvector")]
    Store[("Object storage<br/>local / Supabase S3")]
  end

  subgraph External["External services"]
    OpenAI["OpenAI<br/>extract + embeddings"]
    SMTP["SMTP outbound"]
    IMAP["IMAP shared inbox"]
    ACE["ACE SFTP optional<br/>Phase-2 upsell"]
  end

  Broker --> Web
  Importer --> Web
  Web --> API
  Landing --> API

  API --> PG
  API --> Redis
  API --> Store
  API --> OpenAI
  API --> SMTP
  API --> ACE

  Beat --> Redis
  Worker --> Redis
  Worker --> PG
  Worker --> Store
  Worker --> OpenAI
  Worker --> IMAP

  API -->|"7501 PDF/XLS<br/>ISF ABI draft<br/>CargoWise XML"| ABI
  SMTP -->|"Request Missing Doc<br/>GATE-DOCREQ token"| Importer
  Importer -->|"reply + attachment"| IMAP
```

### Runtime components

| Component | Role |
|-----------|------|
| `apps/web` | Broker UI: **Workbench** home (`/dashboard`), ingest, review, shipments, 7501 prep, settings; **System Health** under System (`/admin/dashboard`) |
| `services/api` | FastAPI routes, auth (scrypt portal sessions), exports |
| Celery worker | Ingest, extract, embed, assemble, email monitor |
| Celery beat | Schedules `email.monitor_inbox` and other periodic jobs |
| PostgreSQL + pgvector | Operational data + embeddings |
| Redis | Celery broker/result backend |
| Storage | Local volume or Supabase S3-compatible bucket |

---

## 2. End-to-end data flow

```mermaid
flowchart LR
  subgraph Ingest["1. Ingest"]
    U1["UI upload /api/upload"]
    U2["IMAP monitor<br/>email.monitor_inbox"]
    U3["IngestJob PENDING"]
    U1 --> U3
    U2 -->|"parse GATE-DOCREQ"| U3
  end

  subgraph Pipeline["2. Celery pipeline"]
    P1["process_ingest_job<br/>extract text"]
    P2["DocumentMetadata<br/>+ embeddings"]
    P3["trade extraction<br/>review queue"]
    P4["shipment assembly<br/>auto-link"]
    P5["entity resolution<br/>gold layer"]
    U3 --> P1 --> P2 --> P3
    P2 --> P4
    P2 --> P5
  end

  subgraph Workbench["3. Broker workbench"]
    W1["Review Queue<br/>approve / correct"]
    W2["Shipment gold record"]
    W3["Request Missing Doc<br/>document_types catalog"]
    W4["ISF 10+2 draft"]
    W5["Prepare 7501<br/>HTS lookup / MPF"]
    W6["Official Entry"]
    P3 --> W1 --> W2
    P4 --> W2
    P5 --> W2
    W2 --> W3
    W2 --> W4
    W2 --> W5 --> W6
  end

  subgraph Export["4. Handoff exports"]
    E1["7501 PDF / Excel"]
    E2["ISF-10 ABI draft"]
    E3["CargoWise UniversalShipment XML"]
    E4["Live ACE transmit<br/>blocked unless SFTP + allow"]
    W6 --> E1
    W4 --> E2
    W6 --> E3
    W6 -.-> E4
  end

  W3 -->|"SMTP + Reply-To IMAP"| U2
```

### Lakehouse layers (conceptual)

| Layer | Stores | Examples |
|-------|--------|----------|
| Bronze | Raw uploads / jobs | `ingest_jobs`, storage objects |
| Silver | Extracted / resolved entities | `document_metadata`, parties, extraction results |
| Gold | Broker work objects | `shipments`, `entries`, review queue, ISF |

---

## 3. Missing-document reply correlation

```mermaid
sequenceDiagram
  participant B as Broker UI
  participant API as FastAPI
  participant SMTP as SMTP
  participant I as Importer
  participant IMAP as IMAP monitor
  participant W as Celery worker
  participant DB as Postgres

  B->>API: POST /shipments/{id}/request-document
  API->>DB: load document_types + audit
  API->>SMTP: email subject [GATE-DOCREQ:{shipment_id}]<br/>Reply-To = EMAIL_IMAP_USER
  SMTP->>I: document request + instructions template
  I->>IMAP: reply with PDF attachment
  IMAP->>W: create IngestJob<br/>metadata.gate_docreq_shipment_id
  W->>DB: DocumentMetadata completed
  W->>DB: ShipmentDocument link<br/>GATE_DOCREQ / AUTO
  B->>API: GET /shipments/{id}/documents
  API->>B: reply doc now linked
```

**Requirements for auto-link:** `EMAIL_IMAP_*` configured, importer replies (or forwards) so the monitored inbox receives the attachment **and** the subject still contains `[GATE-DOCREQ:{uuid}]`.

---

## 4. Key API / worker map

| Concern | Entry points |
|---------|----------------|
| Workbench home | `GET /api/workbench/summary` → `/dashboard` |
| Auth | `/api/portal/login` (scrypt), API keys with scopes |
| Upload | `/api/upload`, storage callbacks |
| Review | `/api/review/*` |
| Shipments | `/api/shipments/*`, `POST .../request-document` |
| Doc type catalog | `GET /api/reference-data/document-types` |
| Entries / 7501 | `/api/entries/*`, prep + PDF/Excel/CargoWise export |
| ISF | `/api/isf/*` (simulation gated in production) |
| Workers | `process_ingest_job`, `extract_trade_document`, `process_shipment_assembly`, `email.monitor_inbox` |

---

## 5. Production safety defaults (pilot)

| Setting | Pilot value | Effect |
|---------|-------------|--------|
| `ENVIRONMENT` | `production` | Enables production guards |
| `ACE_ALLOW_SIMULATION` | `false` | Blocks fake ACE/ISF “filed” states |
| `ACE_SFTP_ENABLED` | `false` | Export-only until live circuit |
| `AUDIT_LOG_RETENTION_DAYS` | `2555` | 19 CFR Part 163 (7 years) |
| `SEED_DEMO_USERS` | `false` | No demo logins on customer instance |
