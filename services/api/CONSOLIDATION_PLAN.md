# Workflow Consolidation Plan

## Executive Summary

The platform has **two disconnected workflows** that need to be unified:

1. **Document-Driven Workflow**: Upload → Extract → Keys → Shipment → (GAP)
2. **Entry-Driven Workflow**: Manual/ACE Import → Entry → (no document linkage)

This plan consolidates them into a **single unified workflow**:

**Upload → Extract → Keys → Shipment → Entry (auto-created) → Compliance → Filing**

---

## Current State Analysis

### Redundant Models (3 Entry Models!)

| Model | Location | Fields | Status |
|-------|----------|--------|--------|
| `Entry` | `entry.py` | 180+ | Primary - Full CBP 7501 |
| `ACEEntry` | `ace_entry.py` | 20 | Orphaned - No relationships |
| `CustomsEntry` | `gold_records.py` | 15 | Legacy - Minimal |

### Missing Bridges

1. **Shipment → Entry**: No automatic Entry creation from Shipment documents
2. **ACEEntry → Entry**: ACE imports don't create proper Entry records
3. **Document Keys → Entry Fields**: Extracted keys aren't mapped to Entry fields

### Workflow Gaps

```
CURRENT:
┌─────────────────────────────────────────────────────────────────┐
│  Document Workflow                                              │
│  Upload → Extract → Keys → Shipment → [DEAD END]               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Entry Workflow (Separate)                                      │
│  Manual Input/ACE Import → Entry → Compliance → Filing          │
└─────────────────────────────────────────────────────────────────┘

GOAL:
┌─────────────────────────────────────────────────────────────────┐
│  Unified Workflow                                               │
│  Upload → Extract → Keys → Shipment → Entry → Compliance → File │
└─────────────────────────────────────────────────────────────────┘
```

---

## Consolidation Tasks

### Phase 1: Model Consolidation (Foundation)

#### Task 1.1: Deprecate ACEEntry and CustomsEntry
- **Action**: Mark `ACEEntry` and `CustomsEntry` as deprecated
- **Migration**: Create service to migrate ACEEntry data to Entry model
- **Verification**: Count rows migrated, verify no data loss

#### Task 1.2: Add Entry.source_type Field
- **Action**: Add field to track Entry origin
- **Values**: `document_extraction`, `ace_import`, `manual`, `cargowise`
- **Migration**: Alembic migration

#### Task 1.3: Enhance Entry-Shipment Relationship
- **Action**: Make Entry.shipment_id a proper two-way relationship
- **Add**: Shipment.entry relationship (backref exists but unused)
- **Verification**: Query shipment → entries works

### Phase 2: Entry Auto-Creation Service

#### Task 2.1: Create EntryCreationService
- **Action**: New service that creates Entry from Shipment documents
- **Input**: Shipment with linked documents
- **Output**: Draft Entry with pre-populated fields
- **Location**: `app/services/entry_creation_service.py`

#### Task 2.2: Implement Field Mapping
- **Action**: Map extracted document fields to Entry fields
- **Mappings**:
  | Document Field | Entry Field |
  |----------------|-------------|
  | `bol_number` | `bill_of_lading` |
  | `house_bol_number` | `house_bill` |
  | `master_bol_number` | `master_bill` |
  | `container_numbers` | `container_numbers` |
  | `importer_name` | `importer_of_record_name` |
  | `consignee_name` | `ultimate_consignee_name` |
  | `vessel_name` | `vessel_name` |
  | `voyage_number` | `voyage_flight_number` |
  | `port_of_loading` | `foreign_port_of_lading` |
  | `port_of_discharge` | `port_of_entry` |
  | `total_value` | `total_entered_value` |

#### Task 2.3: Implement Line Item Creation
- **Action**: Create EntryLine records from invoice line items
- **Map**: InvoiceLine → EntryLine with HTS codes and values
- **Calculate**: Duties using existing duty_calculator service

### Phase 3: Integration & Triggers

#### Task 3.1: Add Shipment → Entry Trigger
- **Action**: When Shipment reaches status=COMPLETE, auto-create Entry
- **Location**: `app/services/auto_linker_service.py` (extend existing)
- **Workflow**: `_check_shipment_completeness()` → `create_entry_from_shipment()`

#### Task 3.2: Modify ACE Import to Use Entry Model
- **Action**: Update ACE import route to create Entry (not ACEEntry)
- **Location**: `app/api/routes/ace_import.py`
- **Set**: `source_type = "ace_import"`

#### Task 3.3: Add Post-Entry-Creation Compliance Hook
- **Action**: Trigger compliance checks after Entry creation
- **Integrate**: PostExtractionService runs on Entry.lines

### Phase 4: Verification Tests (Using Test Documents)

#### Task 4.1: End-to-End Scenario 1 Test
**Single Container, Single Consignee (FCL)**
- **Documents**:
  - `commercial_invoice_scenario_1_consignee1.pdf`
  - `packing_list_scenario_1_consignee1.pdf`
  - `house_bl_scenario_1_consignee1.pdf`
  - `master_bl_scenario_1.pdf`
- **Expected Entry**:
  - `master_bill`: MAEU123456789
  - `house_bill`: FWDR-2024-001
  - `container_numbers`: [MSCU1234567]
  - `importer_of_record_name`: XYZ Electronics Corp
  - `vessel_name`: EVER GIVEN
  - 2 EntryLine records with HTS: 8528.72.6400, 8518.21.0000
  - `total_entered_value`: $37,500 (100×$250 + 500×$25)

#### Task 4.2: End-to-End Scenario 2 Test
**Single Container, Multiple Consignees (LCL)**
- **Documents**: scenario_2 (3 consignees)
- **Expected**: 3 separate Entries, one per HBL
- **Verify**: Each Entry links to correct HBL and Shipment

#### Task 4.3: End-to-End Scenario 3 Test
**Multiple Containers, Single Consignee**
- **Documents**: scenario_3 (2 containers)
- **Expected Entry**:
  - `container_numbers`: [OOLU7654321, OOLU7654322]
  - 2 EntryLine records
  - Values split correctly between containers

#### Task 4.4: Compliance Integration Test
- **Verify**: After Entry creation, compliance checks run automatically
- **Check**: HTS codes validated against reference data
- **Check**: Party names screened against OFAC SDN
- **Check**: High-risk items flagged for review

#### Task 4.5: ACE Import Migration Test
- **Action**: Import ACE CSV, verify Entry created (not ACEEntry)
- **Verify**: Entry.source_type = "ace_import"
- **Verify**: Entry links to existing Shipment if matching BOL

### Phase 5: Cleanup

#### Task 5.1: Remove Deprecated Models
- **Action**: After migration verified, remove `ACEEntry` model
- **Action**: Remove `CustomsEntry` model
- **Note**: Keep for 2 releases with deprecation warning

#### Task 5.2: Consolidate Services
- **Merge**: Multiple metadata services into unified MetadataService
- **Remove**: Redundant party extraction code

---

## Test Document Mappings

### Scenario 1: FCL Single Consignee
```
Documents → Shipment → Entry
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

commercial_invoice_scenario_1_consignee1.pdf ─┐
packing_list_scenario_1_consignee1.pdf ───────┼──→ Shipment ──→ Entry
house_bl_scenario_1_consignee1.pdf ───────────┤    (MBL: MAEU123456789)
master_bl_scenario_1.pdf ─────────────────────┘

Entry Fields:
  entry_type: "01" (Consumption)
  master_bill: "MAEU123456789"
  house_bill: "FWDR-2024-001"
  container_numbers: ["MSCU1234567"]
  vessel_name: "EVER GIVEN"
  voyage_flight_number: "V123E"
  foreign_port_of_lading: "CNSHA"
  port_of_entry: "USLAX"
  importer_of_record_name: "XYZ Electronics Corp"
  total_entered_value: 37500.00

Entry Lines:
  Line 1:
    hts_code: "8528726400"
    product_description: "LED Television 55 inch"
    country_of_origin: "CN"
    quantity_1: 100
    entered_value: 25000.00

  Line 2:
    hts_code: "8518210000"
    product_description: "Bluetooth Speakers Portable"
    country_of_origin: "CN"
    quantity_1: 500
    entered_value: 12500.00
```

### Scenario 2: LCL Multiple Consignees
```
MBL: CMDU987654321 ──→ Shipment

HBL: FWDR-2024-002 ──→ Entry 1 (Fashion Imports LLC)
HBL: FWDR-2024-003 ──→ Entry 2 (Midwest Parts Co)
HBL: FWDR-2024-004 ──→ Entry 3 (Pacific Hardware Inc)

Each Entry has:
  - master_bill: CMDU987654321 (shared)
  - house_bill: respective HBL
  - container_numbers: ["TCLU9876543"] (shared)
  - Different importer, lines, values
```

### Scenario 3: FCL Multiple Containers
```
Documents ──→ Shipment ──→ Entry
              (MBL: OOLU456789123)

Entry Fields:
  house_bill: "FWDR-2024-005"
  container_numbers: ["OOLU7654321", "OOLU7654322"]
  importer_of_record_name: "Furniture World Distribution"

Entry Lines (with container allocation):
  Line 1: Wooden Dining Tables - 75 in each container
  Line 2: Wooden Chairs - 300 in each container
```

---

## Verification Checklist

### Model Consolidation
- [ ] ACEEntry marked deprecated
- [ ] Entry.source_type field added
- [ ] Migration created and tested
- [ ] Existing ACEEntry data migrated

### Entry Auto-Creation
- [ ] EntryCreationService implemented
- [ ] Field mapping complete
- [ ] EntryLine creation from InvoiceLine works
- [ ] Duty calculation integrated

### Integration
- [ ] Shipment COMPLETE → Entry trigger works
- [ ] ACE import creates Entry (not ACEEntry)
- [ ] Compliance checks run after Entry creation
- [ ] Documents linked via EntryDocument

### End-to-End Tests
- [ ] Scenario 1: FCL single consignee passes
- [ ] Scenario 2: LCL multiple consignees passes
- [ ] Scenario 3: Multiple containers passes
- [ ] Compliance screening verified
- [ ] ACE import verified

---

## Implementation Order

1. **Task 1.2**: Add Entry.source_type (no breaking changes)
2. **Task 2.1-2.3**: EntryCreationService (new service, no conflicts)
3. **Task 3.1**: Shipment → Entry trigger (enables auto-creation)
4. **Task 4.1-4.5**: Verification tests (validate everything works)
5. **Task 3.2**: Modify ACE import (depends on service being ready)
6. **Task 1.1, 5.1**: Deprecate/remove old models (cleanup)

---

## Files to Create/Modify

### New Files
- `app/services/entry_creation_service.py` - Core entry creation logic
- `app/tests/integration/test_document_to_entry_flow.py` - E2E tests
- `alembic/versions/xxx_add_entry_source_type.py` - Migration

### Modified Files
- `app/models/entry.py` - Add source_type field
- `app/models/ace_entry.py` - Add deprecation warning
- `app/services/auto_linker_service.py` - Add Entry trigger
- `app/api/routes/ace_import.py` - Use Entry model
- `app/workers/agent_processor.py` - Trigger post-entry compliance

---

## Success Metrics

1. **Single Workflow**: All documents flow to Entries automatically
2. **No Orphaned Data**: Every Entry has source tracking
3. **Complete Linking**: Documents ↔ Shipment ↔ Entry fully connected
4. **Test Coverage**: All 3 scenarios pass with test documents
5. **Compliance Integration**: Auto-screening on every Entry

---

## Risk Mitigation

1. **Data Loss**: Keep ACEEntry for 2 releases before removal
2. **Breaking Changes**: New fields are nullable by default
3. **Performance**: Entry creation is async (Celery task)
4. **Rollback**: Each phase can be rolled back independently
