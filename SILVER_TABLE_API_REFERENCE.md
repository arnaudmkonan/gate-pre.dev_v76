# Silver Table Node - API Reference

## Base URL
```
/api/metadata
```

## Endpoints Overview

### Silver Records Management

| Method | Endpoint | Purpose | Status |
|--------|----------|---------|--------|
| POST | `/silver/upsert` | Upsert records to silver table | ✅ Existing |
| GET | `/silver/{file_id}` | Get silver record by file ID | ✅ Existing |
| POST | `/silver/validate-batch` | Validate batch of records | ✅ NEW |
| GET | `/silver/{batch_id}/validation-report` | Get validation report | ✅ NEW |
| GET | `/silver/{batch_id}/failed-validations` | Get failed validations | ✅ NEW |
| POST | `/silver/{record_id}/trigger-vectorization` | Trigger single record vectorization | ✅ NEW |
| POST | `/silver/batch/{batch_id}/trigger-vectorization` | Trigger batch vectorization | ✅ NEW |
| GET | `/silver/{file_id}/vectorization-status` | Get vectorization status | ✅ NEW |

### Retry Queue Management (Existing)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/retry-queue` | List retry queue items |
| GET | `/retry-queue/{item_id}` | Get specific retry item |
| PATCH | `/retry-queue/{item_id}` | Update retry item |
| POST | `/retry-queue/{item_id}/retry` | Retry failed processing |

---

## Detailed Endpoint Documentation

### 1. Upsert Silver Records
**Endpoint**: `POST /api/metadata/silver/upsert`
**Status Code**: `202 Accepted`

#### Request Body
```json
{
  "batch_id": "uuid (optional, generated if not provided)",
  "records": [
    {
      "document_id": "string (required, 1-500 chars)",
      "record_id": "string (required, 1-500 chars)",
      "canonical_id": "string (optional, 1-500 chars, for deduplication)",
      "source_file_id": "uuid (required)",
      "file_type": "string (required, 1-50 chars: pdf, csv, json, etc.)",
      "size_bytes": "integer (required, 0-5GB in bytes)",
      "normalized_payload": "object (required, extracted data)",
      "title": "string (optional, max 1000 chars)",
      "author": "string (optional, max 500 chars)",
      "language": "string (optional, ISO 639-1 code, max 20 chars)",
      "content": "string (optional, normalized text content)",
      "extraction_date": "datetime (optional, ISO 8601)",
      "document_date": "datetime (optional, ISO 8601)",
      "record_metadata": "object (optional, custom metadata)"
    }
  ],
  "source_context": "object (optional, batch context)"
}
```

#### Response Body
```json
{
  "batch_id": "uuid",
  "total_records": 10,
  "inserted_count": 8,
  "updated_count": 2,
  "failed_count": 0,
  "processing_time_ms": 234,
  "failed_records": [
    {
      "record_index": 5,
      "document_id": "doc_xyz",
      "record_id": "rec_xyz",
      "error_message": "Required field missing",
      "error_type": "validation_error",
      "field_errors": {
        "title": "Required field"
      }
    }
  ]
}
```

#### Error Responses
- `400 Bad Request`: Batch size exceeds 10,000 records
- `500 Internal Server Error`: Database or processing error

---

### 2. Validate Batch
**Endpoint**: `POST /api/metadata/silver/validate-batch`
**Status Code**: `200 OK`

#### Request Body
```json
{
  "batch_id": "uuid (optional)",
  "records": [
    {
      "document_id": "string (required)",
      "record_id": "string (required)",
      "source_file_id": "uuid (required)",
      "file_type": "string (required)",
      "size_bytes": "integer (required)",
      "normalized_payload": "object (required)"
    }
  ]
}
```

#### Response Body
```json
{
  "batch_id": "uuid",
  "total_records": 100,
  "passed_count": 98,
  "failed_count": 1,
  "warning_count": 1,
  "validation_time_ms": 456,
  "records": [
    {
      "record_index": 0,
      "document_id": "doc_001",
      "record_id": "rec_001",
      "status": "pass",
      "errors": [],
      "warnings": []
    },
    {
      "record_index": 5,
      "document_id": "doc_006",
      "record_id": "rec_006",
      "status": "fail",
      "errors": [
        {
          "field": "size_bytes",
          "message": "File size exceeds maximum allowed (5GB)",
          "type": "constraint_error"
        }
      ],
      "warnings": []
    }
  ]
}
```

#### Validation Rules
| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| document_id | string | ✅ | 1-500 chars, not empty |
| record_id | string | ✅ | 1-500 chars, not empty |
| source_file_id | UUID | ✅ | Valid UUID format |
| file_type | string | ✅ | 1-50 chars, valid type |
| size_bytes | integer | ✅ | 0 - 5,000,000,000 bytes |
| normalized_payload | object | ✅ | Non-empty object |
| title | string | ❌ | Max 1000 chars |
| author | string | ❌ | Max 500 chars |
| language | string | ❌ | Max 20 chars, ISO 639-1 |
| content | string | ❌ | Any length |

---

### 3. Get Validation Report
**Endpoint**: `GET /api/metadata/silver/{batch_id}/validation-report`
**Status Code**: `200 OK` or `404 Not Found`

#### Path Parameters
- `batch_id` (UUID): The batch to get report for

#### Response Body
```json
{
  "batch_id": "uuid",
  "total_records": 100,
  "passed_count": 98,
  "failed_count": 1,
  "warning_count": 1,
  "records": [
    {
      "record_id": "rec_001",
      "document_id": "doc_001",
      "status": "pass",
      "errors": {},
      "validation_details": {
        "record_id": "rec_001",
        "document_id": "doc_001",
        "status": "pass",
        "error_count": 0,
        "warning_count": 0,
        "errors": [],
        "warnings": [],
        "metadata": {}
      },
      "error_message": null
    }
  ]
}
```

#### Error Responses
- `404 Not Found`: No validation records for batch

---

### 4. Get Failed Validations
**Endpoint**: `GET /api/metadata/silver/{batch_id}/failed-validations`
**Status Code**: `200 OK`

#### Path Parameters
- `batch_id` (UUID): The batch to get failures for

#### Query Parameters
- `page` (integer, default: 1): Page number for pagination
- `page_size` (integer, default: 20, max: 100): Records per page

#### Response Body
```json
{
  "batch_id": "uuid",
  "total": 5,
  "page": 1,
  "page_size": 20,
  "records": [
    {
      "record_id": "rec_045",
      "document_id": "doc_045",
      "status": "fail",
      "errors": {
        "document_id": ["Required field 'document_id' is missing or empty"]
      },
      "error_message": "Required field 'document_id' is missing or empty",
      "created_at": "2024-01-13T10:30:00Z"
    }
  ]
}
```

---

### 5. Trigger Single Record Vectorization
**Endpoint**: `POST /api/metadata/silver/{record_id}/trigger-vectorization`
**Status Code**: `202 Accepted`

#### Path Parameters
- `record_id` (UUID): The silver record to vectorize

#### Response Body (Success)
```json
{
  "record_id": "uuid",
  "status": "queued",
  "message": "Record queued for vectorization"
}
```

#### Response Body (Already Embedded)
```json
{
  "record_id": "uuid",
  "status": "already_embedded",
  "embedding_id": "uuid",
  "message": "Record already has embedding"
}
```

#### Response Body (Not Found)
```json
{
  "record_id": "uuid",
  "status": "failed",
  "message": "Silver record not found"
}
```

#### Error Responses
- `404 Not Found`: Record doesn't exist (status: "failed")
- `500 Internal Server Error`: Processing error

---

### 6. Trigger Batch Vectorization
**Endpoint**: `POST /api/metadata/silver/batch/{batch_id}/trigger-vectorization`
**Status Code**: `202 Accepted`

#### Path Parameters
- `batch_id` (UUID): The batch to vectorize

#### Query Parameters
- `limit` (integer, optional): Max records to process

#### Response Body
```json
{
  "batch_id": "uuid",
  "total_records": 100,
  "queued_count": 95,
  "already_embedded_count": 5,
  "failed_count": 0,
  "processing_time_ms": 234
}
```

#### Error Responses
- `500 Internal Server Error`: Batch processing error

---

### 7. Get Vectorization Status
**Endpoint**: `GET /api/metadata/silver/{file_id}/vectorization-status`
**Status Code**: `200 OK` or `404 Not Found`

#### Path Parameters
- `file_id` (UUID): The file to check status for

#### Response Body (Embedded)
```json
{
  "record_id": "uuid",
  "file_id": "uuid",
  "status": "embedded",
  "embedding_count": 3,
  "embeddings": [
    {
      "id": "uuid",
      "created_at": "2024-01-13T10:30:00Z",
      "section_index": 0
    },
    {
      "id": "uuid",
      "created_at": "2024-01-13T10:30:01Z",
      "section_index": 1
    }
  ]
}
```

#### Response Body (Pending)
```json
{
  "record_id": "uuid",
  "file_id": "uuid",
  "status": "pending",
  "embedding_count": 0,
  "embeddings": []
}
```

#### Error Responses
- `404 Not Found`: No silver record for file

---

## Error Response Format

All error responses follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common HTTP Status Codes
- `200 OK`: Successful synchronous operation
- `202 Accepted`: Successful asynchronous operation
- `400 Bad Request`: Invalid input or validation error
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Unexpected server error

---

## Status Values

### Validation Status
- `pass`: All validations passed
- `fail`: One or more validations failed
- `warning`: Validations passed but with warnings

### Vectorization Status
- `queued`: Record is queued for vectorization
- `pending`: Record is pending vectorization
- `embedded`: Record has embeddings
- `already_embedded`: Record already has embeddings
- `not_found`: Record doesn't exist
- `failed`: Operation failed

### Record Processing Status
- `pending`: Initial state, awaiting processing
- `completed`: Processing complete, record in silver table
- `vectorization_pending`: Queued for vectorization
- `vectorization_complete`: Embeddings generated
- `failed`: Processing failed

---

## Request/Response Examples

### Python
```python
import requests
import json

# Upsert batch
batch = {
    "batch_id": "550e8400-e29b-41d4-a716-446655440000",
    "records": [{
        "document_id": "DOC-001",
        "record_id": "REC-001",
        "source_file_id": "550e8400-e29b-41d4-a716-446655440001",
        "file_type": "pdf",
        "size_bytes": 2048,
        "normalized_payload": {"content": "Text..."}
    }]
}

response = requests.post(
    "http://localhost:3000/api/metadata/silver/upsert",
    json=batch
)
print(response.json())

# Validate batch
response = requests.post(
    "http://localhost:3000/api/metadata/silver/validate-batch",
    json=batch
)
print(response.json())

# Trigger vectorization
response = requests.post(
    "http://localhost:3000/api/metadata/silver/batch/550e8400-e29b-41d4-a716-446655440000/trigger-vectorization"
)
print(response.json())
```

### JavaScript/Node.js
```javascript
// Upsert batch
const batch = {
  batch_id: "550e8400-e29b-41d4-a716-446655440000",
  records: [{
    document_id: "DOC-001",
    record_id: "REC-001",
    source_file_id: "550e8400-e29b-41d4-a716-446655440001",
    file_type: "pdf",
    size_bytes: 2048,
    normalized_payload: { content: "Text..." }
  }]
};

const response = await fetch("http://localhost:3000/api/metadata/silver/upsert", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(batch)
});

console.log(await response.json());
```

---

## Rate Limiting & Quotas

- **Batch size limit**: Max 10,000 records per upsert
- **Query limit**: Default 100 results, max 1000
- **Pagination limit**: Max 100 records per page
- **Processing timeout**: 30 seconds per batch operation

---

## Changelog

### Version 1.0 (Current)
- ✅ Upsert Silver Records
- ✅ Validate Normalization with detailed error reporting
- ✅ Trigger Vectorization with status tracking
- ✅ Comprehensive API endpoints with pagination
- ✅ Full audit logging integration

### Planned Features
- Real-time vectorization progress tracking
- Batch vectorization with parallel processing
- Custom validation rule DSL
- Advanced monitoring and analytics
