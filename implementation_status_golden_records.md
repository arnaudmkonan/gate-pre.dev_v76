# Golden Records Implementation (DM-015 & DM-016)

## Overview
Successfully implemented the **Golden Records** feature for entity deduplication and master data management. This allows users to identify and merge duplicate Party and Product entities in the Silver Layer.

## Components Implemented

### 1. Backend Service (`app/services/golden_record_service.py`)

**Duplicate Detection:**
- `find_party_duplicates()`: Uses fuzzy matching (SequenceMatcher) to find similar Party records
- `find_product_duplicates()`: Uses description and HS code matching for Products
- Matching signals:
  - Tax ID match (100% confidence)
  - Exact name match (100%)
  - Alias overlap (95%)
  - Name in alias (92%)
  - Fuzzy name match (calculated ratio)

**Merge Operations:**
- `merge_parties(survivor_id, victim_id)`: Absorbs victim into survivor
  - Combines alias lists
  - Updates EntityLinks to point to survivor
  - Sets victim's `golden_record_id` to survivor
  - Creates audit trail via EntityLink with `link_type="merged_into"`
- `merge_products()`: Similar logic for Products
- `split_party()`: Undoes a merge by clearing `golden_record_id`

**Statistics:**
- `get_golden_record_stats()`: Returns counts of total, merged, and unique entities

### 2. API Endpoints (`app/api/routes/data_fabric.py`)

| Endpoint | Method | Description |
|:---|:---|:---|
| `/golden-records/stats` | GET | Get merge statistics |
| `/golden-records/duplicates/parties` | GET | Find party duplicates |
| `/golden-records/duplicates/products` | GET | Find product duplicates |
| `/golden-records/merge/parties` | POST | Merge two parties |
| `/golden-records/merge/products` | POST | Merge two products |
| `/golden-records/split/parties/{id}` | POST | Undo a merge |

### 3. Frontend UI (`apps/web/src/pages/DataFabricPage.tsx`)

**New "Duplicates" Tab:**
- Shows stats cards: Total/Merged/Unique counts for Parties and Products
- Lists potential duplicate pairs with:
  - Side-by-side comparison cards
  - Similarity percentage and match reason
  - "Merge (Keep A)" action button
- Visual feedback for merge operations (loading, success states)
- Empty state when no duplicates are found

**API Client (`apps/web/src/lib/api/data-fabric.ts`):**
- Added TypeScript interfaces: `GoldenRecordStats`, `DuplicateCandidate`, `MergeResult`
- Added API methods: `getGoldenRecordStats()`, `findPartyDuplicates()`, `findProductDuplicates()`, `mergeParties()`, `mergeProducts()`

## Data Model

The `golden_record_id` field on `Party` and `Product` models is used to track merges:
- `NULL`: Entity is a unique/master record
- `UUID`: Points to the survivor entity this record was merged into

## How It Works

1. **Detection**: System compares all entities using fuzzy matching algorithms
2. **Review**: User sees duplicate candidates in the UI with similarity scores
3. **Merge**: User clicks "Merge (Keep A)" to combine records
   - Survivor keeps its canonical name
   - Victim's name and aliases are added to survivor's alias list
   - All links (from extractions) pointing to victim are updated to survivor
4. **Audit**: An EntityLink record with `link_type="merged_into"` is created for traceability

## Testing

```bash
# Get stats
curl http://localhost:8000/api/data-fabric/golden-records/stats

# Find duplicates (with 80% similarity threshold)
curl "http://localhost:8000/api/data-fabric/golden-records/duplicates/parties?min_similarity=0.8"

# Merge two parties
curl -X POST http://localhost:8000/api/data-fabric/golden-records/merge/parties \
  -H "Content-Type: application/json" \
  -d '{"survivor_id": "uuid1", "victim_id": "uuid2"}'
```

## Next Steps

1. **Automated Detection**: Run duplicate detection as a background job after entity resolution
2. **ML Matching**: Use vector embeddings for semantic similarity (beyond fuzzy string matching)
3. **Bulk Merge**: Allow selecting multiple duplicates and merging in batch
4. **Threshold Config**: Make similarity thresholds configurable per customer
