# Metadata API Documentation

## Overview

The Metadata API provides endpoints to retrieve and search document metadata including extraction results, detected language, text snippets, and vector store references.

## Endpoints

### GET /api/metadata

Query metadata with filtering and pagination.

**Status Code:** `200 OK` (when results found) or `204 No Content` (when not yet available)

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `job_id` | UUID | No | - | Filter by specific job ID (exact match) |
| `document_id` | UUID | No | - | Filter by specific document ID (exact match) |
| `customer_id` | String | No | - | Filter by customer ID |
| `file_type` | String | No | - | Filter by file type (pdf, docx, txt, etc.) |
| `ingestion_status` | String | No | - | Filter by status (pending, extracting, completed, failed) |
| `page` | Integer | No | 1 | Page number (1-indexed) |
| `page_size` | Integer | No | 20 | Items per page (max 100) |

#### Response - Success (200 OK)

```json
{
  "total": 42,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "job_id": "550e8400-e29b-41d4-a716-446655440001",
      "filename": "quarterly_report.pdf",
      "file_type": "pdf",
      "size": 2048576,
      "uploader": "user@example.com",
      "ingestion_status": "completed",
      "extracted_text_snippet": "Q4 2025 Financial Results: Revenue increased 15% YoY to $50M. Operating margin improved to 22%...",
      "detected_language": "en",
      "vector_store_id": "vec_550e8400-e29b-41d4",
      "raw_storage_path": "uploads/quarterly_report.pdf",
      "extraction_timestamp": "2026-01-11T10:30:00Z",
      "extractor_agent_version": "v1.2.1",
      "page_count": 45,
      "mime_type": "application/pdf",
      "title": "Q4 2025 Financial Results",
      "author": "Finance Team",
      "subject": "Quarterly Results",
      "keywords": ["financial", "q4", "2025", "results"],
      "customer_id": "cust_123",
      "source": "crm",
      "tags": ["important", "quarterly", "financial"],
      "created_at": "2026-01-11T10:00:00Z",
      "updated_at": "2026-01-11T10:30:00Z"
    }
  ]
}
```

#### Response - Not Yet Available (204 No Content)

When metadata for a specific job is not yet available (extraction still in progress):

```
HTTP/1.1 204 No Content
Retry-After: 5
```

**Headers:**
- `Retry-After`: Seconds to wait before retrying (typically 5-30)

#### Response - No Results (200 OK)

```json
{
  "total": 0,
  "page": 1,
  "page_size": 20,
  "items": []
}
```

---

### GET /api/metadata/{metadata_id}

Get metadata for a specific document by ID.

**Status Code:** `200 OK`

#### Response

Same as the item object from the list endpoint:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "job_id": "550e8400-e29b-41d4-a716-446655440001",
  "filename": "document.pdf",
  "file_type": "pdf",
  ...
}
```

#### Errors

- `204 No Content`: Metadata not yet available (with `Retry-After` header)
- `404 Not Found`: Document doesn't exist

---

## Field Reference

### Response Fields

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | UUID | No | Unique metadata record ID |
| `job_id` | UUID | No | Ingestion job ID |
| `filename` | String | No | Original document filename |
| `file_type` | String | No | File extension (pdf, docx, txt, etc.) |
| `size` | Integer | No | File size in bytes |
| `uploader` | String | Yes | Email or ID of uploader |
| `ingestion_status` | String | No | One of: pending, extracting, completed, failed |
| `extracted_text_snippet` | String | Yes | First ~1000 chars of extracted text |
| `detected_language` | String | Yes | ISO 639-1 language code (en, es, fr, etc.) |
| `vector_store_id` | String | Yes | ID in vector store (for semantic search) |
| `raw_storage_path` | String | Yes | Path in Supabase Storage |
| `extraction_timestamp` | DateTime | Yes | When extraction completed |
| `extractor_agent_version` | String | Yes | Version of extraction agent used |
| `page_count` | Integer | Yes | Number of pages (for PDFs/documents) |
| `mime_type` | String | Yes | MIME type (application/pdf, etc.) |
| `title` | String | Yes | Document title from metadata |
| `author` | String | Yes | Document author |
| `subject` | String | Yes | Document subject |
| `keywords` | Array[String] | Yes | Keywords extracted from document |
| `customer_id` | String | Yes | Customer ID for multi-tenancy |
| `source` | String | Yes | Document source (crm, email, api, etc.) |
| `tags` | Array[String] | Yes | User-provided tags |
| `created_at` | DateTime | No | When metadata record was created |
| `updated_at` | DateTime | No | When metadata was last updated |

### Status Values

| Status | Description |
|--------|-------------|
| `pending` | File uploaded, waiting for extraction |
| `extracting` | Extraction in progress |
| `completed` | Extraction successful |
| `failed` | Extraction failed |

---

## Usage Examples

### Query by Job ID

```bash
curl "http://localhost:8000/api/metadata?job_id=550e8400-e29b-41d4-a716-446655440001"
```

### Query by Customer ID with Pagination

```bash
curl "http://localhost:8000/api/metadata?customer_id=cust_123&page=2&page_size=10"
```

### Filter by File Type and Status

```bash
curl "http://localhost:8000/api/metadata?file_type=pdf&ingestion_status=completed&page_size=50"
```

### Get Metadata by ID

```bash
curl "http://localhost:8000/api/metadata/550e8400-e29b-41d4-a716-446655440000"
```

---

## Integration Examples

### Python

```python
import requests
from typing import Optional, List
from uuid import UUID

class MetadataClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    def get_metadata(
        self,
        job_id: Optional[UUID] = None,
        customer_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """Get metadata with filters and pagination."""
        params = {
            'page': page,
            'page_size': page_size,
        }
        if job_id:
            params['job_id'] = str(job_id)
        if customer_id:
            params['customer_id'] = customer_id

        response = requests.get(
            f"{self.base_url}/api/metadata",
            params=params,
        )

        if response.status_code == 204:
            print("Metadata not yet available. Retry after 5 seconds.")
            return None

        response.raise_for_status()
        return response.json()

# Usage
client = MetadataClient()
result = client.get_metadata(customer_id="cust_123", page_size=50)
```

### JavaScript/TypeScript

```typescript
interface MetadataResponse {
  id: string
  job_id: string
  filename: string
  file_type: string
  size: number
  ingestion_status: string
  extracted_text_snippet?: string
  detected_language?: string
  vector_store_id?: string
  // ... other fields
}

interface MetadataListResponse {
  total: number
  page: number
  page_size: number
  items: MetadataResponse[]
}

async function queryMetadata(
  jobId?: string,
  customerId?: string,
  fileType?: string,
  page: number = 1,
  pageSize: number = 20
): Promise<MetadataListResponse> {
  const params = new URLSearchParams()
  if (jobId) params.append('job_id', jobId)
  if (customerId) params.append('customer_id', customerId)
  if (fileType) params.append('file_type', fileType)
  params.append('page', page.toString())
  params.append('page_size', pageSize.toString())

  const response = await fetch(`/api/metadata?${params.toString()}`)

  if (response.status === 204) {
    console.log('Metadata not yet available')
    return null
  }

  return response.json()
}

// Usage
const results = await queryMetadata(
  undefined,
  'cust_123',
  'pdf',
  1,
  50
)
```

### cURL with Retry Logic

```bash
#!/bin/bash

JOB_ID="550e8400-e29b-41d4-a716-446655440001"
MAX_RETRIES=5
RETRY_DELAY=5

for ((i=0; i<MAX_RETRIES; i++)); do
  response=$(curl -w "\n%{http_code}" \
    "http://localhost:8000/api/metadata?job_id=$JOB_ID")

  http_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | head -n-1)

  if [ "$http_code" = "200" ]; then
    echo "Success:"
    echo "$body" | jq .
    exit 0
  elif [ "$http_code" = "204" ]; then
    echo "Not ready yet (attempt $((i+1))/$MAX_RETRIES)"
    if [ $i -lt $((MAX_RETRIES-1)) ]; then
      sleep $RETRY_DELAY
    fi
  else
    echo "Error: $http_code"
    exit 1
  fi
done

echo "Metadata not available after $MAX_RETRIES attempts"
exit 1
```

---

## Performance Characteristics

### Response Times

- **Typical query:** <500ms
- **Large result set (1000+ items):** <2s
- **Not-yet-available (204):** <100ms

### Indexes

The following database indexes optimize query performance:

```sql
CREATE INDEX idx_document_metadata_job_id ON document_metadata(job_id);
CREATE INDEX idx_document_metadata_customer_id ON document_metadata(customer_id);
CREATE INDEX idx_document_metadata_ingestion_status ON document_metadata(ingestion_status);
CREATE INDEX idx_document_metadata_file_type ON document_metadata(file_type);
CREATE INDEX idx_document_metadata_created_at ON document_metadata(created_at);
CREATE INDEX idx_document_metadata_customer_status ON document_metadata(customer_id, ingestion_status);
```

---

## Availability Semantics

### Metadata Lifecycle

1. **File Uploaded** → Raw file created, status="pending"
2. **Storage Callback** → Raw file status="stored"
3. **Extraction Started** → Metadata created, status="pending"
4. **Extraction In Progress** → Metadata status="extracting"
5. **Extraction Complete** → Metadata status="completed", `extracted_text_snippet` populated
6. **Extraction Failed** → Metadata status="failed"

### When to Expect 204 No Content

- File just uploaded (<1 second)
- Extraction queue backlogged (high volume)
- Extraction task crashed/retrying

### Retry Strategy

```
┌─ Query metadata
│
├─ 200 OK: Metadata available ✓
│
├─ 204 No Content: Not ready
│  └─ Wait (Retry-After header)
│     └─ Retry in 5-30 seconds
│
└─ 404 Not Found: Document doesn't exist
   └─ Check job_id is correct
```

---

## Authorization

Currently, metadata endpoints don't require authentication. In production:

- Add authentication middleware (JWT, OAuth2, API keys)
- Implement row-level security (RLS) for multi-tenant systems
- Check `customer_id` matches authenticated user/org

```python
async def get_metadata(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get metadata with authorization check."""
    metadata = await MetadataQueryService.query_by_job_id(session, job_id)

    if not metadata:
        raise HTTPException(status_code=404)

    # Verify user has access to this customer
    if metadata.customer_id and metadata.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    return MetadataResponse.from_orm(metadata)
```

---

## Best Practices

1. **Handle 204 responses** with retry logic (exponential backoff)
2. **Cache metadata locally** if querying repeatedly
3. **Use customer_id filter** to isolate tenant data
4. **Set reasonable page sizes** (20-100 items)
5. **Monitor latency** and optimize indexes if needed
6. **Log failed extractions** for debugging
7. **Implement timeouts** on retry loops (e.g., max 10 retries)
8. **Use vector_store_id** for semantic search integration

---

## Troubleshooting

### No Results Even After Upload

- Check upload succeeded (got 202 Accepted with job_id)
- Verify extraction task is queued (check Redis/Celery logs)
- Wait a few seconds (extraction can take 5-30 seconds)

### Always Getting 204 No Content

- Check extraction worker is running
- Check Redis connection is healthy
- Look for errors in extraction task logs

### Partial Results

- Extraction may still be in progress
- Retry after a few seconds
- Check extraction logs for errors
