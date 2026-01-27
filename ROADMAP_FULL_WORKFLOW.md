# Full Workflow Solution - Implementation Roadmap

> **Goal**: Transform the platform into a complete customs brokerage workflow solution that justifies $500-2000/month subscription pricing.
>
> **Target**: Licensed customs brokers and brokerage firms in the United States
>
> **Last Updated**: 2026-01-26

---

## Existing Infrastructure (Already Built)

The following components are already implemented and working:

### ✅ Document Processing
- [x] Document upload (single and batch)
- [x] PDF/image text extraction (Docling)
- [x] Vector embeddings generation (OpenAI)
- [x] Document similarity search
- [x] Template-based data extraction (10 templates, 664 usages)
- [x] AI agent pipeline (7 agents: triage, classifier, entity extractor, etc.)

### ✅ Compliance Foundation
- [x] HTS code validation (181 codes in database)
- [x] OFAC SDN screening (18,443 entries)
- [x] NAICS code suggestions
- [x] Party risk assessment
- [x] Compliance screens database

### ✅ Data Models (Partial)
- [x] `ace_entries` table - line-item level entry data
- [x] `customs_entries` table - basic entry header 
- [x] `shipments` table - shipment grouping (5 records)
- [x] `parties` table - normalized party data (14 records)
- [x] `hts_codes` reference table
- [x] `ofac_sdn` reference table

### ✅ Reference Data Services
- [x] Trade compliance service (Section 301, 232, ADD/CVD reference data)
- [x] HTS lookup and validation
- [x] FTA reference data (USMCA, KORUS, etc.)

### ✅ UI Pages (28 routes implemented)
- [x] Batch Upload (/batch-upload)
- [x] Ingest Queue (/ingest)
- [x] Agent Analysis (/agents)
- [x] Review Queue (/review)
- [x] Templates (/templates)
- [x] Trade Compliance (/trade-compliance)
- [x] Compliance Dashboard (/compliance-dashboard)
- [x] ACE Import (/ace-import) - exists but needs enhancement
- [x] Data Fabric (/data-fabric)
- [x] Drawback (/drawback)

---

## Progress Overview

| Phase | Status | Progress |
|-------|--------|----------|
| Phase 1: Core Entry Workflow | ✅ **Complete** | **8/8** |
| Phase 2: Duty & Tariff Calculations | ✅ Complete | 6/6 |
| Phase 3: ACE/ABI Integration | ✅ **Complete** | **7/7** |
| Phase 4: Client Management | 🟡 In Progress | 4/6 |
| Phase 5: Client Portal | 🔴 Not Started | 0/6 |
| Phase 6: Entry Lifecycle Management | 🔴 Not Started | 0/5 |
| Phase 7: Reporting & Analytics | 🔴 Not Started | 0/5 |
| Phase 8: Polish & Production Ready | 🔴 Not Started | 0/7 |
| **TOTAL** | | **25/50** |

---

## Phase 1: Core Entry Workflow

**Objective**: Create the end-to-end journey from document upload to entry creation.

### Task 1.1: Entry Data Model
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P0 (Critical)
- **Effort**: 2 days
- **Dependencies**: None

**Description**: Create database models for customs entries that capture all required CBP 7501 fields.

**Acceptance Criteria**:
- [x] `entries` table with all CBP 7501 header fields (enhanced from customs_entries)
- [x] `entry_lines` table for line-item details (HTS, value, quantity, duty)
- [x] `entry_documents` junction table linking entries to source documents
- [x] `entry_parties` table for all parties (importer, consignee, manufacturer, seller, etc.)
- [x] `entry_status_history` table for tracking status changes
- [x] Proper foreign keys and indexes

**Validation Tests**:
```bash
# 1. Run migration
alembic upgrade head

# 2. Verify tables exist
docker compose exec postgres psql -U postgres -d doc_ingestion -c "\dt customs_entries"
docker compose exec postgres psql -U postgres -d doc_ingestion -c "\dt entry_lines"

# 3. Verify can insert sample entry
curl -X POST http://localhost:8000/api/entries/test-create -H "Content-Type: application/json"
```

---

### Task 1.2: Entry Creation API
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P0 (Critical)
- **Effort**: 3 days
- **Dependencies**: Task 1.1

**Description**: API endpoints for creating, reading, updating customs entries.

**Acceptance Criteria**:
- [x] `POST /api/entries` - Create new entry (draft status)
- [x] `GET /api/entries` - List entries with filtering, pagination
- [x] `GET /api/entries/{id}` - Get single entry with all details
- [x] `PUT /api/entries/{id}` - Update entry
- [x] `DELETE /api/entries/{id}` - Soft delete entry
- [x] `POST /api/entries/{id}/lines` - Add line items
- [x] `POST /api/entries/from-documents` - Create entry from extracted documents

**Validation Tests**:
```bash
# 1. Create entry from extracted document
curl -X POST http://localhost:8000/api/entries/from-documents \
  -H "Content-Type: application/json" \
  -d '{"document_ids": ["<doc_uuid>"]}'

# Expected: Entry created with extracted data populated

# 2. Verify line items populated
curl http://localhost:8000/api/entries/{entry_id}/lines

# 3. Test filtering
curl "http://localhost:8000/api/entries?status=draft&client_id=xxx"
```

---

### Task 1.3: Entry Workflow UI - List View
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P0 (Critical)
- **Effort**: 3 days
- **Dependencies**: Task 1.2

**Description**: Main entry management interface showing all entries with filtering and search.

**Acceptance Criteria**:
- [x] Route `/entries` showing list of all entries
- [x] Columns: Entry #, Client, Port, Status, Est. Duty, ETA, Last Updated
- [x] Status chips with colors (Draft=gray, Ready=blue, Filed=green, etc.)
- [x] Filters: Status, Client, Date Range, Port
- [x] Search by entry number, BOL, container
- [x] Bulk actions: Select multiple, bulk status change (partial)
- [x] "New Entry" button prominently displayed

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Navigate to /entries
[ ] Verify entries load from API
[ ] Filter by status works
[ ] Search by entry number works
[ ] Click row navigates to detail
[ ] New Entry button works
[ ] Pagination works for 50+ entries
```

**Files Created**:
- `apps/web/src/pages/EntriesListPage.tsx`
- `apps/web/src/hooks/useEntries.ts`

---

### Task 1.4: Entry Workflow UI - Detail/Edit View
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P0 (Critical)
- **Effort**: 4 days
- **Dependencies**: Task 1.3

**Description**: Full entry editing interface with all CBP 7501 fields organized in tabs.

**Acceptance Criteria**:
- [x] Route `/entries/{id}` with full entry form
- [x] Tab 1: Header (entry type, port, entry date, importer, consignee)
- [x] Tab 2: Parties (parties list with roles)
- [x] Tab 3: Line Items (HTS, description, value, quantity, duty - with add modal)
- [x] Tab 4: Documents (linked documents list)
- [x] Tab 5: History (status changes, audit trail)
- [x] Validation errors highlighted inline
- [x] Calculate totals button
- [x] Duty breakdown sidebar
- [x] Quick action buttons (Submit for Review, Edit, etc.)

**Files Created**:
- `apps/web/src/pages/EntryDetailPage.tsx`
- `apps/web/src/pages/NewEntryPage.tsx`

---

### Task 1.5: Document-to-Entry Linking
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P0 (Critical)
- **Effort**: 2 days
- **Dependencies**: Task 1.2

**Description**: Ability to link multiple documents to an entry and auto-populate fields.

**Acceptance Criteria**:
- [x] Enhanced API to link documents with auto-population
- [x] Extraction suggestions from linked documents
- [x] Conflict detection when fields differ across documents
- [x] Documents can be unlinked from entry
- [x] Apply suggestion endpoint for field updates
- [x] useDocumentLinking React hook

**Files Created/Modified**:
- `services/api/app/api/routes/entries.py` - Enhanced document endpoints
- `apps/web/src/hooks/useEntries.ts` - Added useDocumentLinking hook

---

### Task 1.6: Entry Validation Engine
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P1 (High)
- **Effort**: 3 days
- **Dependencies**: Task 1.4

**Description**: Validation rules engine that checks entry completeness and correctness before filing.

**Acceptance Criteria**:
- [x] Required field validation (all CBP mandatory fields)
- [x] HTS code format and chapter validation
- [x] Value reasonableness check (unit value vs. historical)
- [x] Party validation (importer of record format check)
- [x] ADD/CVD applicability check based on HTS + country
- [x] Section 301 applicability check for China origin
- [x] Validation summary with severity (Error, Warning, Info)
- [x] Enhanced API response with filing_ready status

**Files Created**:
- `services/api/app/services/entry_validation_service.py`

---

### Task 1.7: Shipment-to-Entry Workflow
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P1 (High)
- **Effort**: 2 days
- **Dependencies**: Task 1.5

**Description**: Create entry from an existing shipment (group of documents).

**Acceptance Criteria**:
- [x] `POST /api/shipments/{id}/create-entry` endpoint
- [x] Creates entry linked to shipment via `shipment_id`
- [x] Auto-populates from highest-confidence extractions
- [x] Links all shipment documents to entry
- [x] Field mapping for importer, exporter, vessel, carrier, etc.
- [x] Suggestions for low-confidence fields
- [x] `GET /api/shipments/{id}/entry` to check if entry exists

**Files Modified**:
- `services/api/app/api/routes/shipments.py` - Added create-entry endpoint

---

### Task 1.8: Quick Entry Creation Wizard
- [x] **Status**: ✅ Complete (2026-01-27)
- **Priority**: P2 (Medium)
- **Effort**: 2 days
- **Dependencies**: Task 1.4

**Description**: Step-by-step wizard for manual entry creation without documents.

**Acceptance Criteria**:
- [x] Route `/entries/new` with 4-step wizard
- [x] Step 1: Entry Type, Port, Entry Date, Mode of Transport, BOL
- [x] Step 2: Importer (with client lookup), Consignee, Exporter
- [x] Step 3: Line Items (add/remove, HTS, description, qty, value)
- [x] Step 4: Review & Create with full summary
- [x] Can save as draft at any step
- [x] Back/Next navigation with validation
- [x] Progress indicator with checkmarks for completed steps
- [x] Real-time value calculations for line items

**Files Modified**:
- `apps/web/src/pages/NewEntryPage.tsx` - Transformed to 4-step wizard
- `apps/web/src/hooks/useEntries.ts` - Added line_items support
- `services/api/app/api/routes/entries.py` - Added line_items in create_entry

**Features**:
- Step validation with error display
- Client search/select from database
- Line item management with value calculations
- Summary table with totals

---

## Phase 2: Duty & Tariff Calculations

**Objective**: Accurate duty, tax, and fee calculations for all entry types.

### Task 2.1: Duty Calculator Service
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P0 (Critical)
- **Effort**: 3 days
- **Dependencies**: None

**Description**: Backend service that calculates duties given HTS, value, quantity, and country.

**Acceptance Criteria**:
- [x] `DutyCalculatorService` class
- [x] `calculate_duty(hts_code, value, quantity, country_of_origin)` method
- [x] Supports ad valorem rates (% of value)
- [x] Supports specific rates ($/unit)
- [x] Supports compound rates (% + $/unit)
- [x] Returns breakdown: base_duty, section_301, section_232, add_cvd
- [x] Uses `hts_codes` table for base rates
- [x] Uses trade compliance service for 301/232/ADD/CVD

**Validation Tests**:
```python
# Test cases:
# 1. HTS 8471.30.01 (laptops from China) - Free + 25% Section 301
result = duty_calc.calculate("8471.30.01", value=1000, qty=1, country="CN")
assert result.base_duty == 0
assert result.section_301 == 250  # 25% of $1000

# 2. HTS with specific rate
result = duty_calc.calculate("9403.20.00", value=500, qty=10, country="VN")
# Verify specific rate applied per unit

# 3. Compound rate
result = duty_calc.calculate("xxxx.xx.xx", value=100, qty=5, country="MX")
# Verify both components calculated
```

---

### Task 2.2: MPF & HMF Calculation
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P0 (Critical)
- **Effort**: 1 day
- **Dependencies**: Task 2.1

**Description**: Calculate Merchandise Processing Fee and Harbor Maintenance Fee.

**Acceptance Criteria**:
- [x] MPF = 0.3464% of value (min $29.66, max $575.35) for formal entries
- [x] MPF = $2.18 per line for informal entries
- [x] HMF = 0.125% of value for imports
- [x] Correctly identifies entry type for MPF calculation
- [x] Includes in total duty calculation

**Validation Tests**:
```python
# 1. Formal entry $10,000 value
result = duty_calc.calculate_fees(value=10000, entry_type="formal")
assert result.mpf == 34.64  # 0.3464% of $10,000

# 2. Formal entry $1,000,000 value (hits max)
result = duty_calc.calculate_fees(value=1000000, entry_type="formal")
assert result.mpf == 575.35  # Max cap

# 3. HMF calculation
assert result.hmf == 1250.00  # 0.125% of $1,000,000
```

---

### Task 2.3: ADD/CVD Rate Application
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P0 (Critical)
- **Effort**: 2 days
- **Dependencies**: Task 2.1

**Description**: Apply antidumping and countervailing duty rates when applicable.

**Acceptance Criteria**:
- [x] AddCvdOrder model with sample data for common orders
- [x] AddCvdLookupService with HTS + country lookup
- [x] Lookup returns ADD rate, CVD rate, and combined rate
- [x] Calculates duty amounts when value provided
- [x] Returns case numbers for entry documentation
- [x] Fallback to sample data when database table missing
- [x] API endpoint `/api/tools/duty-calculator/add-cvd/{hts}/{country}`
- [x] List orders endpoint `/api/tools/duty-calculator/add-cvd-orders`

**Files Created**:
- `services/api/app/models/add_cvd_orders.py`
- `services/api/app/services/add_cvd_service.py`

---

### Task 2.4: FTA/Preference Program Rates
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P1 (High)
- **Effort**: 2 days
- **Dependencies**: Task 2.1

**Description**: Apply preferential duty rates for FTA-qualified goods.

**Acceptance Criteria**:
- [x] Support USMCA (Mexico, Canada)
- [x] Support KORUS (Korea)
- [x] Support CAFTA-DR (6 countries)
- [x] Support GSP where applicable
- [x] FTA eligibility checker by HTS + country
- [x] Certificate of origin requirements returned
- [x] Display savings vs. MFN rate
- [x] Compare FTA options across countries
- [x] 20 FTA countries supported

**Files Created**:
- `services/api/app/services/fta_rate_service.py`

**API Endpoints**:
- `GET /api/tools/duty-calculator/fta/{country}` - Check FTA eligibility
- `GET /api/tools/duty-calculator/fta-countries` - List FTA countries
- `POST /api/tools/duty-calculator/compare-fta` - Compare sourcing options

---

### Task 2.5: Total Landed Cost Calculator
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P1 (High)
- **Effort**: 2 days
- **Dependencies**: Tasks 2.1-2.4

**Description**: Calculate total cost including all duties, taxes, and fees.

**Acceptance Criteria**:
- [x] Combine: Base Duty + Section 301 + Section 232 + ADD/CVD + MPF + HMF
- [x] Per-line calculation and entry totals
- [x] Breakdown view: value, each duty component, total
- [x] Unit cost calculation (landed cost per unit)
- [x] Currency conversion support (foreign invoice)
- [x] Effective duty rate percentage
- [x] FTA savings integration

**Files Created**:
- `services/api/app/services/landed_cost_service.py`

**API Endpoints**:
- `POST /api/tools/duty-calculator/landed-cost` - Full entry calculation
- `GET /api/tools/duty-calculator/landed-cost/quick` - Single item lookup

---

### Task 2.6: Duty Calculator UI
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P0 (Critical)
- **Effort**: 2 days
- **Dependencies**: Task 2.5

**Description**: UI for standalone duty calculation and entry duty display.

**Acceptance Criteria**:
- [x] Route `/tools/duty-calculator` for quick lookups
- [x] Input: HTS, Value, Quantity, Country, FTA (optional)
- [x] Output: Full breakdown with all duty components
- [x] CBP fees calculation (MPF + HMF)
- [x] Running total displayed prominently
- [x] Landed cost and per-unit calculation
- [x] Quick HTS code selection
- [x] Country selector with Section 301 indicator

**Files Created**:
- `apps/web/src/pages/DutyCalculatorPage.tsx`

---

## Phase 3: ACE/ABI Integration

**Objective**: Enable direct filing to CBP's Automated Commercial Environment.

### Task 3.1: CBP 7501 Generator
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P0 (Critical)
- **Effort**: 3 days
- **Dependencies**: Phase 1 complete

**Description**: Generate CBP Form 7501 (Entry Summary) in required format.

**Acceptance Criteria**:
- [x] Generate 7501 from entry data
- [x] All mandatory fields populated
- [x] Line items formatted correctly
- [x] Duty calculations included
- [x] PDF version for review
- [x] Matches official CBP 7501 layout (header, importer, transport, lines, totals)
- [x] Signature/certification section
- [x] JSON preview option for validation

**Files Created**:
- `services/api/app/services/cbp7501_generator.py`

**API Endpoints**:
- `GET /api/entries/{id}/export/cbp7501` - Generate PDF (default) or JSON preview
- `GET /api/entries/{id}/export/summary` - Full entry summary JSON

---

### Task 3.2: ABI Message Format Generator
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P0 (Critical)
- **Effort**: 5 days
- **Dependencies**: Task 3.1

**Description**: Generate ABI-format messages for ACE transmission.

**Acceptance Criteria**:
- [x] Generate SE (Entry Summary) ABI message
- [x] Generate AD (Add Entry) message for new entries
- [x] Generate RM (Replace Entry) message for amendments
- [x] ISF 10+2 message structure (data model ready)
- [x] Proper record layout per CBP CATAIR (fixed-width 80-char)
- [x] Validate message before transmission
- [x] Store message for audit in ace_response field
- [x] Record types: 10 (Header), 20 (Port), 30 (BOL), 40 (Container), 50 (Line), 60 (Party), 90 (Totals)

**Files Created**:
- `services/api/app/services/abi_generator.py`

**API Endpoints**:
- `GET /api/entries/{id}/export/abi` - Generate ABI message (JSON or raw text)
- `POST /api/entries/{id}/file/abi` - Generate, validate, store, and mark ready for filing

---

### Task 3.3: ACE Portal Account Linking
- [x] **Status**: ✅ Complete (2026-01-27)
- **Priority**: P0 (Critical)
- **Effort**: 2 days
- **Dependencies**: None

**Description**: Allow users to link their ACE Portal credentials/filer code.

**Acceptance Criteria**:
- [x] User settings page for ACE credentials at `/settings/ace`
- [x] Store filer code (3-letter) and port code (4-digit)
- [x] Validation for filer code format (3 uppercase letters)
- [x] Validation for port code format (4 digits)
- [x] Validation for surety code format (3 digits)
- [x] Support multiple filer codes per organization (brokers with multiple importers)
- [x] Primary configuration (filer code, port, username, environment)
- [x] Default bond configuration (type, surety code)
- [x] Filing preferences (auto-file, dual approval)
- [x] Notification settings (email, events to notify on)

**Files Created**:
- `services/api/app/models/ace_settings.py` - ACESettings and FilerCode models
- `services/api/app/api/routes/ace_settings.py` - ACE Settings API routes
- `apps/web/src/hooks/useACESettings.ts` - React hooks for ACE settings
- `apps/web/src/pages/ACESettingsPage.tsx` - ACE Settings UI page

**API Endpoints**:
- `GET /api/settings/ace` - Get ACE settings
- `POST /api/settings/ace` - Create ACE settings
- `PUT /api/settings/ace` - Update ACE settings
- `POST /api/settings/ace/filer-codes` - Add filer code
- `PUT /api/settings/ace/filer-codes/{id}` - Update filer code
- `DELETE /api/settings/ace/filer-codes/{id}` - Delete filer code
- `POST /api/settings/ace/validate/filer-code` - Validate filer code format
- `POST /api/settings/ace/validate/port-code` - Validate port code format


---

### Task 3.4: ACE Status Tracking
- [x] **Status**: ✅ Complete (2026-01-27)
- **Priority**: P1 (High)
- **Effort**: 3 days
- **Dependencies**: Task 3.2

**Description**: Track entry status in ACE and display in application.

**Acceptance Criteria**:
- [x] Poll ACE for entry status updates (simulated for demo)
- [x] Status: Filed, Accepted, Rejected, Intensive Exam, Released, Liquidated
- [x] Display status in entry list and detail (ACEStatusPanel component)
- [x] Notifications on status change (via status history)
- [x] Store rejection reasons with CBP error codes (15 common error codes)
- [x] Re-submit capability for rejected entries
- [x] Status simulation for testing/demo purposes

**Files Created**:
- `services/api/app/services/ace_status_service.py` - ACE Status Service with polling simulation
- `apps/web/src/hooks/useACEStatus.ts` - React hooks for ACE status tracking
- `apps/web/src/components/ACEStatusPanel.tsx` - ACE Status display panel

**API Endpoints**:
- `GET /api/entries/{id}/ace-status` - Get ACE status for entry
- `POST /api/entries/{id}/file` - Submit entry to ACE
- `POST /api/entries/{id}/poll-ace` - Simulate polling ACE for status
- `POST /api/entries/{id}/resubmit` - Resubmit rejected entry
- `GET /api/entries/pending-status/list` - Get entries pending status updates
- `POST /api/entries/{id}/simulate-ace-response` - Simulate ACE response for testing


---

### Task 3.5: Entry Amendment Workflow
- [x] **Status**: ✅ Complete (2026-01-27)
- **Priority**: P1 (High)
- **Effort**: 2 days
- **Dependencies**: Task 3.2

**Description**: Support post-filing amendments (PSC, Value corrections, etc.).

**Acceptance Criteria**:
- [x] Identify which fields changed from original filing
- [x] Generate amendment ABI message (RM record type)
- [x] Track amendment history (stored in entry.ace_response)
- [x] Calculate duty change (owe more or refund)
- [x] Prior disclosure flag for penalty mitigation

**Files Created**:
- `services/api/app/services/entry_amendment_service.py` - Complete amendment service

**API Endpoints**:
- `POST /api/entries/{id}/amend/preview` - Preview amendment changes
- `POST /api/entries/{id}/amend` - Create amendment with changes
- `POST /api/entries/{id}/amend/{amendment_id}/apply` - Apply amendment to entry
- `POST /api/entries/{id}/amend/generate-abi` - Generate ABI RM message
- `GET /api/entries/{id}/amendments` - Get amendment history
- `POST /api/entries/{id}/amend/quick` - Quick single-field amendment

**Features**:
- Amendment types: value_correction, classification, origin, quantity, party, rate, fta
- Amendment reasons: clerical_error, incorrect_value, cbp_request, audit_finding, voluntary_disclosure
- Duty impact calculation (increase or refund)
- Prior disclosure support for penalty mitigation
- Full ABI RM message generation for CBP submission


---

### Task 3.6: ISF (10+2) Filing
- [x] **Status**: ✅ Complete (2026-01-27)
- **Priority**: P1 (High)
- **Effort**: 3 days
- **Dependencies**: Task 3.2

**Description**: Generate and file Importer Security Filing (ISF / 10+2).

**Acceptance Criteria**:
- [x] `isf_filings` table to track ISF separate from entry
- [x] Auto-populate ISF from shipment or entry documents
- [x] 10 importer data elements captured
- [x] Flexible filing for amendments (not all data known initially)
- [x] ISF timing validation (24 hours before vessel departure)
- [x] Match ISF to entry when filed

**Files Created**:
- `services/api/app/models/isf_filing.py` - ISF model with 10 elements + transport data
- `services/api/app/services/isf_service.py` - Complete ISF service
- `services/api/app/api/routes/isf.py` - ISF API routes

**API Endpoints**:
- `POST /api/isf` - Create new ISF filing
- `GET /api/isf` - List ISF filings
- `GET /api/isf/{id}` - Get ISF details
- `PUT /api/isf/{id}` - Update ISF
- `POST /api/isf/{id}/validate` - Validate ISF for filing
- `POST /api/isf/{id}/file` - Submit ISF to CBP
- `POST /api/isf/{id}/amend` - File ISF amendment
- `POST /api/isf/{id}/match-entry/{entry_id}` - Link ISF to entry
- `GET /api/isf/{id}/abi-message` - Generate ISF-10 ABI message
- `POST /api/isf/from-shipment/{id}` - Create ISF from shipment
- `POST /api/isf/from-entry/{id}` - Create ISF from entry

**10 Importer Elements Tracked**:
1. Seller name and address
2. Buyer name and address
3. Importer of record number
4. Consignee number(s)
5. Manufacturer (supplier) name and address
6. Ship to party name and address
7. Country of origin
8. Commodity HTS-6 (6-digit codes)
9. Container stuffing location
10. Consolidator (stuffer) name and address


---

### Task 3.7: Broker Permit & Bond Management
- [x] **Status**: ✅ Complete (2026-01-27)
- **Priority**: P2 (Medium)
- **Effort**: 2 days
- **Dependencies**: Task 3.3

**Description**: Track broker license, permits, and bonds.

**Acceptance Criteria**:
- [x] Store broker license number(s)
- [x] Track continuous bond information
- [x] Single transaction bond tracking
- [x] Bond sufficiency warnings (10% of annual duties, min $50k)
- [x] License renewal reminders (expiration tracking)
- [x] Port permit tracking

**Files Created**:
- `services/api/app/models/broker_management.py` - License, Permit, Bond models
- `services/api/app/services/broker_management_service.py` - Complete management service
- `services/api/app/api/routes/broker_management.py` - API endpoints

**API Endpoints**:
- `POST /api/broker/licenses` - Create license
- `GET /api/broker/licenses` - List licenses
- `GET /api/broker/licenses/{id}` - Get license details
- `PUT /api/broker/licenses/{id}` - Update license
- `POST /api/broker/licenses/{id}/renew` - Renew license
- `POST /api/broker/licenses/{id}/permits` - Add port permit
- `GET /api/broker/licenses/{id}/permits` - List permits
- `POST /api/broker/bonds` - Create bond
- `GET /api/broker/bonds` - List bonds
- `GET /api/broker/bonds/{id}/sufficiency` - Check bond sufficiency
- `GET /api/broker/warnings` - Get expiration warnings
- `POST /api/broker/validate-entry` - Validate broker can file
- `GET /api/broker/stats` - Get statistics

**Features**:
- Bond types: Continuous, Single Transaction, Drawback, FTZ, Carrier
- Surety company codes (10 common surety companies)
- Bond activity codes (1-10 CBP codes)
- Expiration warnings for licenses and bonds
- Bond sufficiency calculation (10% rule)
- Port permit validation


---

## Phase 4: Client Management

**Objective**: Multi-tenant support for brokers serving multiple importer clients.

### Task 4.1: Client/Importer Data Model
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P0 (Critical)
- **Effort**: 2 days
- **Dependencies**: None

**Description**: Database models for managing multiple importer clients.

**Acceptance Criteria**:
- [x] `clients` table (importer companies) - full profile with compliance, financial fields
- [x] `client_contacts` table (people at client companies)
- [x] `client_settings` table (preferences per client)
- [x] `client_bonds` table (bond info per client with expiration tracking)
- [x] Client linked to entries via client_id
- [x] Support IOR number, EIN, DUNS, CBP assigned number
- [x] C-TPAT, Known Importer, Trusted Trader flags
- [x] Full CRUD API with search, filtering

**Files Created**:
- `services/api/app/models/client.py`
- `services/api/app/api/routes/clients.py`

**API Endpoints**:
- `POST /api/clients` - Create client
- `GET /api/clients` - List clients (with search/filter)
- `GET /api/clients/{id}` - Get client details
- `PATCH /api/clients/{id}` - Update client
- `DELETE /api/clients/{id}` - Soft delete (terminate)
- `POST /api/clients/{id}/contacts` - Add contact
- `GET /api/clients/{id}/contacts` - List contacts
- `POST /api/clients/{id}/bonds` - Add bond
- `GET /api/clients/{id}/bonds` - List bonds (with expiration warnings)
- `GET /api/clients/{id}/settings` - Get settings
- `PATCH /api/clients/{id}/settings` - Update settings
- `GET /api/clients/{id}/stats` - Entry statistics

---

### Task 4.2: Client Management UI
- [x] **Status**: ✅ Complete (2026-01-26)
- **Priority**: P0 (Critical)
- **Effort**: 3 days
- **Dependencies**: Task 4.1

**Description**: CRUD interface for managing clients.

**Acceptance Criteria**:
- [x] Route `/clients` - list all clients with grid layout, search, filtering
- [x] Route `/clients/{id}` - client detail with tabs (Profile, Contacts, Bonds, Entries, Settings)
- [x] Route `/clients/new` - new client creation form
- [x] Client profile: name, addresses, contacts, IOR, bonds
- [x] Link to client's entries via Entries tab
- [x] Archive/deactivate client capability (soft delete)
- [x] Add contacts directly from client detail
- [x] Add bonds directly from client detail
- [x] Edit mode for client profile

**Files Created**:
- `apps/web/src/hooks/useClients.ts` - React hooks for client API
- `apps/web/src/pages/ClientsListPage.tsx` - Clients grid listing
- `apps/web/src/pages/ClientDetailPage.tsx` - Client detail with tabs
- `apps/web/src/pages/NewClientPage.tsx` - New client form

**Routes Added to App.tsx**:
- `/clients` - Clients list
- `/clients/new` - New client form
- `/clients/:clientId` - Client detail
- `/clients/:clientId/edit` - Client edit (uses detail page)

---

### Task 4.3: Client-Specific Templates
- [x] **Status**: ✅ Complete (2026-01-27)
- **Priority**: P1 (High)
- **Effort**: 2 days
- **Dependencies**: Tasks 4.1, Phase 1

**Description**: Allow custom extraction templates per client.

**Acceptance Criteria**:
- [x] Templates can be assigned to specific clients
- [x] Client's documents use client-specific templates first
- [x] Fall back to global templates if no client match
- [x] Per-client field mappings (e.g., Client A calls it "PO Number", Client B calls it "Order Number")

**Files Created**:
- `services/api/app/services/client_template_service.py` - Template and alias service
- `services/api/app/api/routes/client_templates.py` - API endpoints

**API Endpoints**:
- `GET /api/clients/{id}/templates` - List client templates
- `POST /api/clients/{id}/templates` - Create client template
- `POST /api/clients/{id}/templates/from-global/{template_id}` - Copy global template for client
- `PUT /api/clients/{id}/templates/{template_id}` - Update template
- `DELETE /api/clients/{id}/templates/{template_id}` - Delete template
- `POST /api/clients/{id}/templates/{template_id}/field-mappings` - Add field mapping
- `GET /api/clients/{id}/templates/{template_id}/field-mappings` - Get mappings
- `GET /api/clients/{id}/field-aliases` - Get field aliases
- `POST /api/clients/{id}/field-aliases` - Set field alias
- `GET /api/clients/{id}/resolve-template?document_type=X` - Resolve template for document
- `GET /api/clients/global-templates` - List global templates


---

### Task 4.4: Client Document Preferences
- [x] **Status**: ✅ Complete (2026-01-27)
- **Priority**: P2 (Medium)
- **Effort**: 1 day
- **Dependencies**: Task 4.1

**Description**: Store client preferences for document handling.

**Acceptance Criteria**:
- [x] Default port of entry per client
- [x] Preferred entry type
- [x] Auto-apply FTA when applicable
- [x] Client-specific HTS code aliases
- [x] Default payment terms

**Files Created**:
- `services/api/app/services/client_preferences_service.py` - Preferences service
- `services/api/app/api/routes/client_preferences.py` - API endpoints

**API Endpoints**:
- `GET /api/clients/{id}/preferences` - Get all preferences
- `PATCH /api/clients/{id}/preferences` - Update preferences
- `PUT /api/clients/{id}/preferences/port` - Set default port
- `PUT /api/clients/{id}/preferences/entry-type` - Set default entry type
- `PUT /api/clients/{id}/preferences/fta` - Set FTA preferences
- `GET /api/clients/{id}/hts-aliases` - Get HTS aliases
- `POST /api/clients/{id}/hts-aliases` - Add HTS alias
- `DELETE /api/clients/{id}/hts-aliases/{code}` - Remove alias
- `GET /api/clients/{id}/hts-aliases/resolve?code=X` - Resolve HTS
- `POST /api/clients/{id}/apply-defaults` - Apply defaults to entry


---

### Task 4.5: Client Reporting
- [ ] **Status**: Not Started
- **Priority**: P1 (High)
- **Effort**: 2 days
- **Dependencies**: Tasks 4.1, Phase 1

**Description**: Generate reports per client for their review.

**Acceptance Criteria**:
- [ ] Entry summary report by date range
- [ ] Duty paid report (for client's records)
- [ ] Import history by HTS chapter
- [ ] Year-to-date statistics
- [ ] Export to PDF and Excel

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Navigate to /clients/{id}/reports
[ ] Generate "Entry Summary - Q1 2026"
[ ] Verify PDF contains all Q1 entries
[ ] Export to Excel → opens in Excel correctly
```

---

### Task 4.6: Client Billing/Invoicing
- [ ] **Status**: Not Started
- **Priority**: P2 (Medium)
- **Effort**: 3 days
- **Dependencies**: Tasks 4.1, Phase 1

**Description**: Track billable work and generate invoices to clients.

**Acceptance Criteria**:
- [ ] Per-entry fee configuration (flat or percentage)
- [ ] Track billable line items (entries filed, amendments, ISFs)
- [ ] Generate invoice from billing items
- [ ] Invoice PDF with breakdown
- [ ] Track payment status
- [ ] Integration ready for QuickBooks/Xero (future)

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Configure client fee = $125/entry
[ ] File 5 entries for client
[ ] Generate invoice → shows 5 × $125 = $625
[ ] Mark invoice paid → status updates
```

---

## Phase 5: Client Portal

**Objective**: Allow importer clients to log in and view their imports.

### Task 5.1: Client User Authentication
- [ ] **Status**: Not Started
- **Priority**: P1 (High)
- **Effort**: 3 days
- **Dependencies**: Task 4.1

**Description**: Separate authentication for client users.

**Acceptance Criteria**:
- [ ] Client users can register/login
- [ ] Client users linked to their company
- [ ] Role-based access: Client Admin, Client User, Client Read-Only
- [ ] Client users can only see their company's data
- [ ] Broker can invite client users via email

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Broker invites client user via email
[ ] Client user clicks link → sets password
[ ] Client user logs in → only sees their data
[ ] Try to access other client's entry → denied
```

---

### Task 5.2: Client Dashboard
- [ ] **Status**: Not Started
- **Priority**: P1 (High)
- **Effort**: 2 days
- **Dependencies**: Task 5.1

**Description**: Home screen for client users showing their import status.

**Acceptance Criteria**:
- [ ] Summary cards: Pending, In Progress, Released
- [ ] Recent entries list
- [ ] Shipments in transit
- [ ] Alerts/notifications
- [ ] Quick actions: View Entry, Download Documents

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Log in as client user
[ ] Dashboard shows only their entries
[ ] Click entry → can view (read-only)
[ ] Cannot see other clients' data
```

---

### Task 5.3: Document Request Workflow
- [ ] **Status**: Not Started
- **Priority**: P1 (High)
- **Effort**: 2 days
- **Dependencies**: Task 5.1

**Description**: Allow broker to request documents from clients.

**Acceptance Criteria**:
- [ ] Broker creates document request (e.g., "Need Certificate of Origin")
- [ ] Client receives email notification
- [ ] Client logs in and uploads document
- [ ] Broker notified of upload
- [ ] Document automatically linked to entry

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Broker requests document for entry
[ ] Client receives email
[ ] Client logs in → sees request
[ ] Client uploads document
[ ] Broker sees document attached to entry
```

---

### Task 5.4: Entry Approval Workflow
- [ ] **Status**: Not Started
- **Priority**: P2 (Medium)
- **Effort**: 2 days
- **Dependencies**: Task 5.1

**Description**: Allow clients to review and approve entries before filing.

**Acceptance Criteria**:
- [ ] Entry status: "Pending Client Approval"
- [ ] Client reviews entry details
- [ ] Client approves or requests changes
- [ ] Changes trigger notification to broker
- [ ] Audit trail of approval/changes

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Broker submits entry for client approval
[ ] Client receives notification
[ ] Client approves → status changes to "Ready to File"
[ ] Client requests change → broker notified
```

---

### Task 5.5: Client Notifications
- [ ] **Status**: Not Started
- **Priority**: P2 (Medium)
- **Effort**: 2 days
- **Dependencies**: Task 5.1

**Description**: Keep clients informed of entry progress.

**Acceptance Criteria**:
- [ ] Email notifications for: Entry Filed, Entry Released, Exam Required, Issues
- [ ] In-app notification center
- [ ] Notification preferences (what to receive, frequency)
- [ ] SMS option for critical alerts (future)

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Entry filed → client receives email
[ ] Entry released → client receives email
[ ] Client disables "Entry Filed" notifications → no email
```

---

### Task 5.6: Client Mobile View
- [ ] **Status**: Not Started
- **Priority**: P3 (Low)
- **Effort**: 2 days
- **Dependencies**: Tasks 5.1-5.2

**Description**: Mobile-responsive client portal.

**Acceptance Criteria**:
- [ ] Client dashboard works on mobile
- [ ] Entry list scrolls properly
- [ ] Document upload works from mobile
- [ ] No horizontal scroll required
- [ ] Touch-friendly buttons

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Open client portal on mobile browser
[ ] Dashboard loads correctly
[ ] Can navigate to entry
[ ] Can upload document from phone
```

---

## Phase 6: Entry Lifecycle Management

**Objective**: Complete entry lifecycle from filing through liquidation.

### Task 6.1: Liquidation Tracking
- [ ] **Status**: Not Started
- **Priority**: P1 (High)
- **Effort**: 2 days
- **Dependencies**: Phase 1

**Description**: Track entry liquidation status and dates.

**Acceptance Criteria**:
- [ ] Calculate liquidation deadline (314 days + extensions)
- [ ] Track liquidation status from CBP
- [ ] Alert when approaching deadline
- [ ] Record final liquidated duty amount
- [ ] Track refunds or additional duty owed

**Validation Tests**:
```bash
# Get liquidation dates
curl http://localhost:8000/api/entries/{id}/liquidation

# Expected: deadline, status, refund/owe amount
```

---

### Task 6.2: Protest & Petition Tracking  
- [ ] **Status**: Not Started
- **Priority**: P2 (Medium)
- **Effort**: 2 days
- **Dependencies**: Task 6.1

**Description**: Track protests filed against CBP decisions.

**Acceptance Criteria**:
- [ ] Create protest from entry
- [ ] Track protest status
- [ ] 180-day protest deadline warning
- [ ] Link to Court of International Trade if escalated
- [ ] Store protest decision

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Entry liquidated at higher duty
[ ] Create protest → saved
[ ] Protest deadline calculated
[ ] Status updated when resolved
```

---

### Task 6.3: Reconciliation Entries
- [ ] **Status**: Not Started
- **Priority**: P2 (Medium)
- **Effort**: 3 days
- **Dependencies**: Phase 1

**Description**: Support reconciliation program entries.

**Acceptance Criteria**:
- [ ] Flag entry for reconciliation
- [ ] Track flagged elements (value, classification, etc.)
- [ ] Generate reconciliation entry summary
- [ ] 21-month reconciliation deadline tracking
- [ ] Link reconciliation entry to original entries

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Create entry flagged for recon (value)
[ ] After 6 months, file reconciliation
[ ] Correct value applied
[ ] Duty difference calculated
```

---

### Task 6.4: Drawback Tracking
- [ ] **Status**: Not Started
- **Priority**: P2 (Medium)
- **Effort**: 3 days
- **Dependencies**: Phase 1

**Description**: Track duty drawback eligibility and claims.

**Acceptance Criteria**:
- [ ] Mark goods as drawback-eligible on import
- [ ] Track export/destruction for drawback claim
- [ ] Calculate potential drawback (99% of duty paid)
- [ ] Generate drawback claim summary
- [ ] Track claim status with CBP

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Import entry marked drawback-eligible
[ ] Record export of same goods
[ ] Drawback claim calculated
[ ] Claim filed → status tracked
```

---

### Task 6.5: Prior Disclosure Management
- [ ] **Status**: Not Started
- **Priority**: P2 (Medium)
- **Effort**: 2 days
- **Dependencies**: Phase 1

**Description**: Manage voluntary disclosures for compliance issues.

**Acceptance Criteria**:
- [ ] Create prior disclosure case
- [ ] Link affected entries
- [ ] Calculate duty loss and potential penalty
- [ ] Track disclosure status with CBP
- [ ] Penalty mitigation calculator (shows savings)

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Create disclosure for 5 entries
[ ] System calculates total duty owed
[ ] Shows max penalty vs. mitigated penalty
[ ] Disclosure filed → status tracks
```

---

## Phase 7: Reporting & Analytics

**Objective**: Provide insights and reports for brokers and clients.

### Task 7.1: Entry Analytics Dashboard
- [ ] **Status**: Not Started
- **Priority**: P1 (High)
- **Effort**: 3 days
- **Dependencies**: Phase 1, Phase 4

**Description**: Analytics dashboard for business insights.

**Acceptance Criteria**:
- [ ] Route `/analytics`
- [ ] Entries by month (chart)
- [ ] Duty paid by month (chart)
- [ ] Top 10 HTS codes by value
- [ ] Top 10 clients by entries
- [ ] Port activity distribution
- [ ] Entry processing time metrics

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Navigate to /analytics
[ ] Charts load with real data
[ ] Change date range → charts update
[ ] Export to PDF works
```

---

### Task 7.2: Compliance Score Dashboard
- [ ] **Status**: Not Started
- **Priority**: P1 (High)
- **Effort**: 2 days
- **Dependencies**: Phase 4

**Description**: Compliance health metrics per client.

**Acceptance Criteria**:
- [ ] Overall compliance score per client
- [ ] Breakdown: Classification accuracy, Value accuracy, Origin claims
- [ ] Trend over time
- [ ] Comparison to industry benchmarks
- [ ] Issue hotspots (which products have most issues)

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Navigate to /clients/{id}/compliance
[ ] Score calculated from entry history
[ ] Details show category breakdown
[ ] Trend chart shows 12-month history
```

---

### Task 7.3: CBP Report Generation
- [ ] **Status**: Not Started
- **Priority**: P1 (High)
- **Effort**: 2 days
- **Dependencies**: Phase 1, Phase 4

**Description**: Generate reports in CBP-required formats.

**Acceptance Criteria**:
- [ ] Annual importer activity summary
- [ ] CBP record-keeping compliance report
- [ ] Port director requested data export
- [ ] CF28/CF29 response document generator
- [ ] ISF compliance summary

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Generate annual summary for client
[ ] All entries included
[ ] Totals match actual filed entries
[ ] Format acceptable for CBP audit
```

---

### Task 7.4: Automated Scheduled Reports
- [ ] **Status**: Not Started
- **Priority**: P2 (Medium)
- **Effort**: 2 days
- **Dependencies**: Tasks 7.1-7.3

**Description**: Schedule and auto-send recurring reports.

**Acceptance Criteria**:
- [ ] Create report schedule (daily, weekly, monthly)
- [ ] Select recipients
- [ ] Auto-generate and email reports
- [ ] Report history stored
- [ ] Pause/resume schedules

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Create weekly report schedule
[ ] Wait for scheduled time
[ ] Report generated and emailed
[ ] Check report in history
```

---

### Task 7.5: Export to CSV/Excel
- [ ] **Status**: Not Started
- **Priority**: P1 (High)
- **Effort**: 1 day
- **Dependencies**: Phase 1

**Description**: Export any data grid to CSV/Excel.

**Acceptance Criteria**:
- [ ] All list views have "Export" button
- [ ] Export respects current filters
- [ ] CSV download immediate
- [ ] Excel includes proper formatting
- [ ] Large exports handled (1000+ rows)

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Navigate to /entries
[ ] Apply filter (last 30 days)
[ ] Click Export → CSV
[ ] Verify file downloads
[ ] Open in Excel → data correct
```

---

## Phase 8: Polish & Production Ready

**Objective**: Prepare for paying customers.

### Task 8.1: User Onboarding Flow
- [ ] **Status**: Not Started
- **Priority**: P1 (High)
- **Effort**: 2 days
- **Dependencies**: All previous phases

**Description**: Guide new users through setup.

**Acceptance Criteria**:
- [ ] First-login wizard
- [ ] Step 1: Company profile setup
- [ ] Step 2: ACE credentials
- [ ] Step 3: First client setup
- [ ] Step 4: Upload sample document
- [ ] Step 5: Create first entry
- [ ] Skip/resume capability
- [ ] Contextual help throughout

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Create new account
[ ] Wizard starts automatically
[ ] Complete all steps
[ ] Can skip and resume later
[ ] Help tooltips visible
```

---

### Task 8.2: Help Documentation
- [ ] **Status**: Not Started
- **Priority**: P1 (High)
- **Effort**: 3 days
- **Dependencies**: All previous phases

**Description**: Comprehensive help documentation.

**Acceptance Criteria**:
- [ ] In-app help center (/help)
- [ ] Getting started guide
- [ ] Feature documentation for each major area
- [ ] Video tutorials (optional)
- [ ] FAQ section
- [ ] Search functionality

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Navigate to /help
[ ] Search for "entry" → relevant results
[ ] Getting started guide complete
[ ] Each feature has documentation
```

---

### Task 8.3: Error Handling & User Feedback
- [ ] **Status**: Not Started
- **Priority**: P1 (High)
- **Effort**: 2 days
- **Dependencies**: All previous phases

**Description**: Graceful error handling throughout.

**Acceptance Criteria**:
- [ ] All API errors show user-friendly messages
- [ ] No raw stack traces shown to users
- [ ] Form validation errors inline
- [ ] Loading states for all async operations
- [ ] Retry capability for failed operations
- [ ] Global error boundary for React

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Disconnect network → friendly error shown
[ ] Submit invalid form → inline errors
[ ] API returns 500 → user-friendly message
[ ] Long operation → loading spinner shown
```

---

### Task 8.4: Performance Optimization
- [ ] **Status**: Not Started
- **Priority**: P1 (High)
- **Effort**: 2 days
- **Dependencies**: All previous phases

**Description**: Ensure application is fast.

**Acceptance Criteria**:
- [ ] Entry list loads in < 500ms
- [ ] Entry detail loads in < 300ms
- [ ] Document preview loads progressively
- [ ] Large PDF handling (100+ pages)
- [ ] Lazy loading for heavy components
- [ ] Database queries optimized (indexes reviewed)

**Validation Tests**:
```bash
# Performance tests
curl -o /dev/null -s -w "%{time_total}\n" http://localhost:8000/api/entries
# Should be < 0.5s

# Load test
ab -n 100 -c 10 http://localhost:8000/api/entries
# 95th percentile < 500ms
```

---

### Task 8.5: Security Audit
- [ ] **Status**: Not Started
- **Priority**: P0 (Critical)
- **Effort**: 2 days
- **Dependencies**: All previous phases

**Description**: Security review before launch.

**Acceptance Criteria**:
- [ ] All endpoints require authentication
- [ ] Client data isolated (no cross-client access)
- [ ] SQL injection protection verified
- [ ] XSS protection verified
- [ ] CSRF protection enabled
- [ ] Sensitive data encrypted at rest
- [ ] HTTPS enforced in production
- [ ] Audit log for sensitive operations

**Validation Tests**:
```bash
# Test unauthorized access
curl http://localhost:8000/api/entries
# Should return 401

# Test cross-client access
# (as client A, try to access client B's entry)
# Should return 403

# SQL injection test
curl "http://localhost:8000/api/entries?client_id='; DROP TABLE entries;--"
# Should not execute SQL
```

---

### Task 8.6: Deployment & Infrastructure
- [ ] **Status**: Not Started
- **Priority**: P0 (Critical)
- **Effort**: 3 days
- **Dependencies**: All previous phases

**Description**: Production deployment setup.

**Acceptance Criteria**:
- [ ] Docker production configuration
- [ ] Environment variable management
- [ ] Database backup automated (daily)
- [ ] Log aggregation setup
- [ ] Health check endpoints
- [ ] Automatic SSL certificate renewal
- [ ] Blue-green deployment capability
- [ ] Rollback procedure documented

**Validation Tests**:
```bash
# Health check
curl http://localhost:8000/health
# Should return 200 OK

# Verify backups
ls /backups/*.sql

# SSL check
curl -I https://production-domain.com
```

---

### Task 8.7: Subscription & Billing
- [ ] **Status**: Not Started
- **Priority**: P0 (Critical)
- **Effort**: 3 days
- **Dependencies**: None

**Description**: Implement subscription billing for the service.

**Acceptance Criteria**:
- [ ] Stripe integration for payments
- [ ] Subscription tiers: Starter, Professional, Enterprise
- [ ] Usage tracking (entries/month)
- [ ] Upgrade/downgrade capability
- [ ] Invoice generation
- [ ] Payment failure handling
- [ ] Trial period support (14 days)

**Validation Tests**:
```
Manual Testing Checklist:
[ ] Sign up → 14-day trial starts
[ ] Add payment method
[ ] Trial ends → card charged
[ ] Upgrade plan → prorated charge
[ ] Cancel → access until period end
```

---

## Summary

### Total Tasks: 50

| Phase | Tasks | Est. Days |
|-------|-------|-----------|
| Phase 1: Core Entry Workflow | 8 | 20 |
| Phase 2: Duty Calculations | 6 | 13 |
| Phase 3: ACE/ABI Integration | 7 | 20 |
| Phase 4: Client Management | 6 | 13 |
| Phase 5: Client Portal | 6 | 13 |
| Phase 6: Entry Lifecycle | 5 | 12 |
| Phase 7: Reporting & Analytics | 5 | 10 |
| Phase 8: Polish & Production | 7 | 17 |
| **TOTAL** | **50** | **~118 days** |

### Suggested Milestones

| Milestone | Phases | Duration | Goal |
|-----------|--------|----------|------|
| **Alpha** | 1, 2 | 6 weeks | Basic entry workflow with duty calc |
| **Beta** | 3, 4 | 6 weeks | ACE export + client management |
| **RC1** | 5, 6 | 5 weeks | Client portal + lifecycle |
| **Launch** | 7, 8 | 5 weeks | Reporting + production ready |

---

## Notes & Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-26 | Created roadmap | Full workflow solution to justify $500+/mo pricing |
| | | |

---

*Last updated: 2026-01-26*
