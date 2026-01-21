# Silver Table Node - Quick Start Guide

## Overview
This guide shows how to use the three core stories of the Silver Table node:
1. Upsert Silver Records
2. Validate Normalization
3. Trigger Vectorization

## Prerequisites
- Running API server on `localhost:3000`
- Access to PostgreSQL database with silver_records table
- Valid file IDs from the raw_files table

## Workflow

### Step 1: Upsert Silver Records

**Purpose**: Insert or update normalized records in the silver table with deduplication.

**Endpoint**: `POST /api/metadata/silver/upsert`

**Example Request**:
```bash
curl -X POST http://localhost:3000/api/metadata/silver/upsert \
  -H "Content-Type: application/json" \
  -d '{
    "batch_id": "550e8400-e29b-41d4-a716-446655440000",
    "records": [
      {
        "document_id": "DOC-2024-001",
        "record_id": "REC-001",
        "canonical_id": "DOC-2024-001#REC-001",
        "source_file_id": "550e8400-e29b-41d4-a716-446655440001",
        "file_type": "pdf",
        "size_bytes": 2048,
        "normalized_payload": {
          "content": "Extracted text content...",
          "metadata": {
            "extracted_date": "2024-01-13",
            "page_count": 10
          }
        },
        "title": "Business Report 2024",
        "author": "Finance Team",
        "language": "en",
        "content": "Q1 financial results...",
        "record_metadata": {
          "source": "finance_system",
          "version": "1.0"
        }
      }
    ]
  }'
```

**Response**:
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_records": 1,
  "inserted_count": 1,
  "updated_count": 0,
  "failed_count": 0,
  "processing_time_ms": 125,
  "failed_records": []
}
```

**Key Features**:
- Automatic deduplication by canonical_id
- Supports up to 10,000 records per batch
- Idempotent: same record upserted twice updates once
- Returns detailed failure information for troubleshooting

### Step 2: Validate Normalization

**Purpose**: Validate that records comply with the silver schema before processing.

**Endpoint**: `POST /api/metadata/silver/validate-batch`

**Example Request**:
```bash
curl -X POST http://localhost:3000/api/metadata/silver/validate-batch \
  -H "Content-Type: application/json" \
  -d '{
    "batch_id": "550e8400-e29b-41d4-a716-446655440000",
    "records": [
      {
        "document_id": "DOC-2024-001",
        "record_id": "REC-001",
        "source_file_id": "550e8400-e29b-41d4-a716-446655440001",
        "file_type": "pdf",
        "size_bytes": 2048,
        "normalized_payload": {"content": "..."}
      }
    ]
  }'
```

**Response**:
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_records": 1,
  "passed_count": 1,
  "failed_count": 0,
  "warning_count": 0,
  "validation_time_ms": 45,
  "records": [
    {
      "record_index": 0,
      "document_id": "DOC-2024-001",
      "record_id": "REC-001",
      "status": "pass",
      "errors": [],
      "warnings": []
    }
  ]
}
```

### Step 2a: Get Validation Report

**Purpose**: Retrieve detailed validation results for a batch.

**Endpoint**: `GET /api/metadata/silver/{batch_id}/validation-report`

**Example**:
```bash
curl -X GET http://localhost:3000/api/metadata/silver/550e8400-e29b-41d4-a716-446655440000/validation-report
```

**Response**:
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_records": 100,
  "passed_count": 98,
  "failed_count": 2,
  "warning_count": 5,
  "records": [
    {
      "record_id": "REC-001",
      "document_id": "DOC-2024-001",
      "status": "pass",
      "errors": [],
      "validation_details": {...}
    },
    {
      "record_id": "REC-002",
      "document_id": "DOC-2024-002",
      "status": "fail",
      "errors": {
        "size_bytes": ["File size exceeds maximum allowed (5GB)"]
      }
    }
  ]
}
```

### Step 2b: Get Failed Validations (Optional)

**Purpose**: Retrieve only the failed/warning records for manual review.

**Endpoint**: `GET /api/metadata/silver/{batch_id}/failed-validations?page=1&page_size=20`

**Example**:
```bash
curl -X GET "http://localhost:3000/api/metadata/silver/550e8400-e29b-41d4-a716-446655440000/failed-validations?page=1&page_size=10"
```

**Response**:
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "total": 2,
  "page": 1,
  "page_size": 10,
  "records": [
    {
      "record_id": "REC-045",
      "document_id": "DOC-2024-045",
      "status": "fail",
      "errors": {
        "document_id": ["Required field 'document_id' is missing or empty"]
      },
      "error_message": "Required field 'document_id' is missing or empty"
    }
  ]
}
```

### Step 3: Trigger Vectorization

**Purpose**: Queue records for embedding generation (semantic search).

**Option A: Single Record Vectorization**

**Endpoint**: `POST /api/metadata/silver/{record_id}/trigger-vectorization`

**Example**:
```bash
curl -X POST http://localhost:3000/api/metadata/silver/550e8400-e29b-41d4-a716-446655440002/trigger-vectorization \
  -H "Content-Type: application/json"
```

**Response**:
```json
{
  "record_id": "550e8400-e29b-41d4-a716-446655440002",
  "status": "queued",
  "message": "Record 550e8400-e29b-41d4-a716-446655440002 queued for vectorization"
}
```

**Option B: Batch Vectorization**

**Endpoint**: `POST /api/metadata/silver/batch/{batch_id}/trigger-vectorization`

**Example**:
```bash
curl -X POST http://localhost:3000/api/metadata/silver/batch/550e8400-e29b-41d4-a716-446655440000/trigger-vectorization \
  -H "Content-Type: application/json"
```

**Response**:
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_records": 100,
  "queued_count": 98,
  "already_embedded_count": 2,
  "failed_count": 0,
  "processing_time_ms": 234
}
```

### Step 3a: Check Vectorization Status (Optional)

**Purpose**: Check if a record has been vectorized.

**Endpoint**: `GET /api/metadata/silver/{file_id}/vectorization-status`

**Example**:
```bash
curl -X GET http://localhost:3000/api/metadata/silver/550e8400-e29b-41d4-a716-446655440001/vectorization-status
```

**Response**:
```json
{
  "record_id": "550e8400-e29b-41d4-a716-446655440002",
  "file_id": "550e8400-e29b-41d4-a716-446655440001",
  "status": "embedded",
  "embedding_count": 1,
  "embeddings": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440003",
      "created_at": "2024-01-13T10:30:00Z",
      "section_index": 0
    }
  ]
}
```

## Complete Workflow Example

```bash
#!/bin/bash

# 1. Prepare batch ID
BATCH_ID="550e8400-e29b-41d4-a716-446655440000"
FILE_ID="550e8400-e29b-41d4-a716-446655440001"

# 2. Upsert records
echo "Step 1: Upserting silver records..."
UPSERT=$(curl -s -X POST http://localhost:3000/api/metadata/silver/upsert \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "batch_id": "$BATCH_ID",
  "records": [{
    "document_id": "DOC-001",
    "record_id": "REC-001",
    "source_file_id": "$FILE_ID",
    "file_type": "pdf",
    "size_bytes": 2048,
    "normalized_payload": {"content": "Sample"},
    "title": "Test Doc",
    "language": "en"
  }]
}
EOF
)
echo "Upsert result: $UPSERT"

# 3. Validate batch
echo -e "\nStep 2: Validating normalization..."
VALIDATE=$(curl -s -X POST http://localhost:3000/api/metadata/silver/validate-batch \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "batch_id": "$BATCH_ID",
  "records": [{
    "document_id": "DOC-001",
    "record_id": "REC-001",
    "source_file_id": "$FILE_ID",
    "file_type": "pdf",
    "size_bytes": 2048,
    "normalized_payload": {"content": "Sample"}
  }]
}
EOF
)
echo "Validation result: $VALIDATE"

# 4. Trigger vectorization
echo -e "\nStep 3: Triggering vectorization..."
VECTORIZE=$(curl -s -X POST http://localhost:3000/api/metadata/silver/batch/$BATCH_ID/trigger-vectorization)
echo "Vectorization result: $VECTORIZE"

echo -e "\nWorkflow complete!"
```

## Common Error Scenarios

### Validation Fails
```json
{
  "failed_count": 2,
  "records": [{
    "status": "fail",
    "errors": {
      "size_bytes": ["File size exceeds maximum allowed (5GB)"],
      "language": ["Field 'language' must be of type string"]
    }
  }]
}
```

**Solution**: Review failed validations, correct data, and retry upsert.

### Record Already Vectorized
```json
{
  "status": "already_embedded",
  "embedding_id": "550e8400-e29b-41d4-a716-446655440003"
}
```

**Solution**: Normal - record was already processed. Use the embedding_id.

### Invalid File ID
```json
{
  "status": "failed",
  "message": "No silver record found for file ..."
}
```

**Solution**: Ensure file_id exists in raw_files table and has silver record.

## Monitoring

### Check Processing Status
```bash
# Get validation report for batch
curl http://localhost:3000/api/metadata/silver/{batch_id}/validation-report

# Get failed validations
curl "http://localhost:3000/api/metadata/silver/{batch_id}/failed-validations?page=1"

# Check vectorization status
curl http://localhost:3000/api/metadata/silver/{file_id}/vectorization-status
```

### Verify in Database
```sql
-- Check silver records
SELECT * FROM silver_records WHERE batch_id = 'batch_id_here';

-- Check validation results
SELECT * FROM normalization_validation
WHERE batch_id = 'batch_id_here'
AND validation_status = 'fail';

-- Check embeddings
SELECT * FROM vector_embeddings WHERE file_id = 'file_id_here';
```

## Performance Tips

1. **Batch Size**: Use batches of 100-1000 records for optimal throughput
2. **Validation**: Run validation immediately after upsert to catch errors early
3. **Vectorization**: Vectorize in batches with the limit parameter
4. **Monitoring**: Check failed validations before vectorization

## Support

For issues or questions:
1. Check validation errors for specific field issues
2. Review failed validations for patterns
3. Check database logs for system errors
4. Consult SILVER_TABLE_IMPLEMENTATION.md for detailed documentation
