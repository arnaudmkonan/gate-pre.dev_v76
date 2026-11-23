# E2E run: SHP-2026-90418

Live walkthrough used to author [`docs/USER_MANUAL.md`](../../USER_MANUAL.md).

## Source document

- `data/test_dataset_2/SHP-2026-90418_40page_bundle.pdf` (40 pages, multi-type bundle)
- Ground truth: `data/test_dataset_2/test_dataset_2_shipments.json` → shipment `SHP-2026-90418`

## Key IDs from this run

| Entity | ID |
|--------|-----|
| Importer client | `4bcfb88c-8054-4aea-b027-01d72f9ca0b7` |
| Client admin user | `4e912ac9-be5b-47bf-924d-2db61f2417cb` |
| Ingest job | `4950ec05-6fdc-4c84-b32e-ef733dbc06fd` |
| Raw file | `ce119583-179b-4c36-9e4d-de93cb3587b5` |
| Shipment | `24ea66e2-c63a-4645-8364-c13ae7752036` |
| ISF | `26a2e13e-e09d-49c8-9037-9960a3ef9c77` |
| Entry | `58db0030-f88f-4596-92f7-0731233ea17c` |

## Fixes applied during the run

1. Celery backlog purged so the 40-page job could leave `pending`
2. `entry_prep_service`: `Client.address_line_1` (was `address_line1`)
3. `shipments.create-entry`: import `timezone`; resolve `raw_files` → `document_metadata` when linking entry documents
4. Earlier session: ISF HTS varchar truncation + latest-ISF query

## Folders

- `artifacts/` — JSON snapshots (job, shipment, prep, entry, duty, ISF, review)
- `exports/` — 7501 PDF/Excel/ACE, CargoWise XML, ISF ABI
- `evidence.json` — timed step log
