# UI & Database Cleanup Audit

**Date:** 2026-02-01  
**Status:** Audit Complete, Migration Script Created

## Executive Summary

The audit of the GATE Platform UI and database revealed that **all core pages are already wired to real data** - the apparent "mock data" was actually test data in the database. The main cleanup opportunity is consolidating **95+ unused database tables** that are either legacy, redundant, or placeholders.

---

## UI Pages Status

### ✅ Fully Functional (Wired to Real Data)

| Page | API Endpoint | Database Tables | Row Count |
|------|--------------|-----------------|-----------|
| **Dashboard** | `/api/admin/dashboard/` | `ingest_jobs`, `queue_job`, `errors_raw` | Real-time metrics |
| **Ingest Documents** | `/api/upload`, `/api/ingest/*` | `document_metadata`, `ingest_jobs` | 79 docs, 3 jobs |
| **Review Queue** | `/api/review/*` | `review_queue`, `review_actions` | 70 items, 10 actions |
| **Templates** | `/api/templates/*` | `extraction_templates` | 10 templates |
| **Batch Upload** | `/api/batch/*` | `batch_jobs` | 3 batches |
| **Customs Entries** | `/api/entries` | `entries`, `entry_lines`, etc. | 3 entries |
| **Clients** | `/api/clients` | `clients`, `client_settings` | 2 clients |
| **Compliance Dashboard** | `/api/compliance/*` | `extraction_results` (analytics) | 117 entries analyzed |
| **Duty Calculator** | `/api/tools/duty-calculator/*` | Live calculation API | Standalone tool |

### ⚠️ Pages with Limited/No Data (But Properly Wired)

| Page | Status | Recommendation |
|------|--------|----------------|
| **ACE Import** | API wired, no data | Needs ACE integration or remove |
| **Duty Drawback** | API wired, no claims | Future feature or remove |
| **Data Fabric** | Visualization page | Already shows entity connections |
| **Trade Compliance** | API wired | Working with limited data |
| **AI Agents** | Agent status page | Working |
| **Feedback Analytics** | API wired | Limited feedback data |
| **Calibration** | API wired | Limited calibration data |

### 🔧 Admin/System Pages

All system pages (Monitoring, Metrics, Alerts, DLQ, etc.) are properly wired but show minimal data since the system is healthy.

---

## Database Tables Audit

### Tables WITH Data (Keep - 12 Core Tables)

| Table | Rows | Purpose |
|-------|------|---------|
| `extraction_results` | 370 | Core extraction storage |
| `document_metadata` | 79 | Document metadata |
| `review_queue` | 70 | Human review items |
| `extraction_templates` | 10 | Template definitions |
| `review_actions` | 10 | Review action log |
| `document_embeddings` | 5 | Vector embeddings |
| `entries` | 3 | Customs entries |
| `ingest_jobs` | 3 | Ingestion tracking |
| `batch_jobs` | 3 | Batch processing |
| `raw_files` | 3 | File storage refs |
| `clients` | 2 | Client management |
| `client_settings` | 2 | Client preferences |
| `upload_idempotency_keys` | 1 | Upload deduplication |

### Tables to Archive (95+ Empty Tables)

Categories of unused tables:

1. **Redundant Medallion Layers** (5 tables)
   - `raw_metadata`, `raw_extractions`, `raw_vectors`, `silver_metadata`, `silver_records`
   - Replaced by unified `extraction_results`

2. **Duplicate Tables** (3 tables)
   - `customs_entries` (duplicate of `entries`)
   - `dlq_entries` (duplicate of `dead_letter_queue`)
   - `batches` (duplicate of `batch_jobs`)

3. **Legacy Billing/Notifications** (6 tables)
   - `billable_items`, `client_invoices`, `client_fee_configs`
   - `client_notifications`, `client_user_sessions`, `client_users`

4. **Unused Entry Lifecycle** (5 tables)
   - `entry_liquidations`, `entry_protests`, `reconciliation_entries`
   - `prior_disclosures`, `compliance_screens`

5. **Unused Shipping/ISF** (4 tables)
   - `shipments`, `shipment_documents`, `isf_amendments`, `isf_filings`

6. **Unused Admin/Org** (4 tables)
   - `organizations`, `organization_subscriptions`
   - `portal_invitations`, `onboarding_progress`

7. **Unused Reference Data** (2 tables)
   - `naics_codes`, `hts_codes` (loaded but unused)

8. **Unused Workflow** (15+ tables)
   - Various retry, queue, config, and tracking tables

---

## Migration Script Created

**File:** `services/api/migrations/versions/cleanup_unused_tables.py`

### What It Does

1. **Archives** (not deletes) unused tables by renaming with `_deprecated` suffix
2. **Preserves** all tables with data or active usage
3. **Fully reversible** - `downgrade()` restores original names

### How to Run

```bash
# From services/api directory
cd services/api
alembic upgrade head

# To rollback if needed
alembic downgrade cleanup_unused_001
```

### Safety Features

- Tables are renamed, not dropped
- Checks for existing archives before renaming
- Logs all actions
- Full downgrade support

---

## Recommendations

### Immediate Actions ✅

1. **Don't run migration yet** - Review with team first
2. **Keep current UI** - All pages are properly wired
3. **Focus on data population** - Add more test entries/clients to see pages fully populated

### Short-term (This Week)

1. **Review migration script** and adjust table list as needed
2. **Run migration in dev** after backup
3. **Update alembic version** chain properly

### Medium-term (Next Sprint)

1. **Remove unused model files** for archived tables
2. **Clean up unused API routes** if any
3. **Consider removing sidebar items** for truly unused features:
   - ACE Import (unless ACE integration planned)
   - Duty Drawback (unless drawback feature planned)

---

## Conclusion

The GATE Platform UI is in **better shape than expected**:
- All core pages are properly wired to real APIs
- The "mock data" issue was actually real test data
- Database has 12 active tables and 95+ unused tables ready for cleanup

The main cleanup task is running the migration to archive unused tables, followed by removing corresponding model files if desired.
