# Upload API Documentation

## Overview

The Upload API provides endpoints for uploading documents to the ingestion platform. It supports multipart/form-data uploads with metadata, file validation, and idempotency support.

## Endpoints

### POST /api/upload

Upload a document for ingestion.

**Status Code:** `202 Accepted`

#### Request

**Content-Type:** `multipart/form-data`

**Headers:**
- `Idempotency-Key` (optional): Unique key for idempotent uploads. If provided, repeated requests with the same key will return the same `job_id` without creating duplicate storage entries.

**Form Data:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | The document file to upload |
| `source` | String | No | Source identifier (e.g., "crm", "email", "api") |
| `customer_id` | String | No | Customer ID for multi-tenant systems |
| `tags` | String | No | Comma-separated tags for categorization |

**Supported File Types:**
- Text: `.txt`, `.md`, `.json`, `.csv`, `.yml`, `.xml`, `.html`
- Documents: `.pdf`, `.docx`, `.xlsx`, `.pptx`

**Max File Size:** 50MB (configurable via `MAX_UPLOAD_SIZE_MB` env var)

#### Response

**Success Response (202 Accepted):**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_id": "550e8400-e29b-41d4-a716-446655440001",
  "filename": "document.pdf",
  "file_type": "pdf",
  "size": 102400,
  "storage_path": "uploads/document.pdf",
  "status": "pending",
  "message": "File uploaded and queued for ingestion"
}
```

**Field Descriptions:**

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | UUID | Unique identifier for the ingestion job |
| `file_id` | UUID | Unique identifier for the raw file |
| `filename` | String | Original filename |
| `file_type` | String | File extension (pdf, docx, etc.) |
| `size` | Integer | File size in bytes |
| `storage_path` | String | Path in Supabase Storage where file is persisted |
| `status` | String | Current status ("pending", "stored", "failed") |
| `message` | String | Response message |

**Error Responses:**

- `400 Bad Request`: Invalid request body
- `415 Unsupported Media Type`: File type not supported
  ```json
  {
    "detail": "Unsupported file type: .exe. Supported types: txt, md, docx, xlsx, pptx, html, pdf, json, csv, yml, xml"
  }
  ```
- `413 Payload Too Large`: File exceeds maximum size
  ```json
  {
    "detail": "File size 104857600 bytes exceeds maximum 52428800 bytes (50MB)"
  }
  ```
- `500 Internal Server Error`: Server error during upload

### GET /api/upload/{file_id}

Get information about an uploaded file.

**Status Code:** `200 OK`

#### Response

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "filename": "document.pdf",
  "file_type": "pdf",
  "file_size": 102400,
  "storage_path": "uploads/document.pdf",
  "status": "pending",
  "stored_at": null,
  "uploader_id": null,
  "source": "api",
  "customer_id": "cust_123",
  "tags": ["important", "quarterly"],
  "checksum": "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
  "error_message": null,
  "created_at": "2026-01-11T10:00:00Z",
  "updated_at": "2026-01-11T10:00:00Z"
}
```

---

## Idempotency

Idempotent uploads prevent duplicate files when network requests are retried.

### How It Works

1. Client generates a unique `Idempotency-Key` (can be UUID or any unique string)
2. Client includes the key in the `Idempotency-Key` header
3. Server stores the key with the `file_id` and `job_id` in the `upload_idempotency_keys` table
4. If the same key is sent again within 24 hours, the server returns the same `job_id` without creating a new file

### Example

```bash
# First request
curl -X POST http://localhost:8000/api/upload \
  -H "Idempotency-Key: user-123-doc-abc-1234567890" \
  -F "file=@document.pdf" \
  -F "customer_id=cust_123"

# Response
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_id": "550e8400-e29b-41d4-a716-446655440001",
  ...
}

# Retry with same key
curl -X POST http://localhost:8000/api/upload \
  -H "Idempotency-Key: user-123-doc-abc-1234567890" \
  -F "file=@document.pdf" \
  -F "customer_id=cust_123"

# Same response (no duplicate created)
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_id": "550e8400-e29b-41d4-a716-446655440001",
  "message": "File already processed (idempotent request)"
}
```

---

## Integration Examples

### Using cURL

```bash
# Basic upload
curl -X POST http://localhost:8000/api/upload \
  -F "file=@document.pdf"

# Upload with metadata
curl -X POST http://localhost:8000/api/upload \
  -H "Idempotency-Key: $(uuidgen)" \
  -F "file=@document.pdf" \
  -F "source=crm" \
  -F "customer_id=cust_123" \
  -F "tags=invoice,2025"
```

### Using Python

```python
import requests
import uuid

url = "http://localhost:8000/api/upload"

files = {
    'file': open('document.pdf', 'rb'),
}

data = {
    'source': 'crm',
    'customer_id': 'cust_123',
    'tags': 'invoice,quarterly',
}

headers = {
    'Idempotency-Key': str(uuid.uuid4()),
}

response = requests.post(url, files=files, data=data, headers=headers)
print(response.json())
```

### Using JavaScript/TypeScript

```typescript
async function uploadDocument(
  file: File,
  customerId?: string,
  source?: string,
  tags?: string
): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  if (source) formData.append('source', source)
  if (customerId) formData.append('customer_id', customerId)
  if (tags) formData.append('tags', tags)

  const response = await fetch('/api/upload', {
    method: 'POST',
    body: formData,
    headers: {
      'Idempotency-Key': `${customerId}-${file.name}-${Date.now()}`,
    },
  })

  if (!response.ok) {
    throw new Error(await response.text())
  }

  return response.json()
}
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_UPLOAD_SIZE_MB` | 50 | Maximum upload file size in megabytes |
| `SUPABASE_STORAGE_BUCKET` | raw-files | Supabase Storage bucket name |
| `IDEMPOTENCY_TTL_HOURS` | 24 | Time-to-live for idempotency keys |

---

## Storage Flow

1. **Upload Request** → `/api/upload` receives multipart/form-data
2. **Validation** → File type and size are validated
3. **Storage** → File is uploaded to Supabase Storage at `uploads/{filename}`
4. **DB Record** → Raw file record is created in `raw_files` table with status="pending"
5. **Job Creation** → Ingest job is created in `ingest_jobs` table
6. **Idempotency** → If Idempotency-Key header was provided, it's stored in `upload_idempotency_keys` table
7. **Response** → `202 Accepted` with `job_id` and `file_id`

---

## Error Handling

### Common Error Scenarios

**Unsupported File Type**
```json
{
  "detail": "Unsupported file type: .exe. Supported types: txt, md, docx, xlsx, pptx, html, pdf, json, csv, yml, xml"
}
```
**Status:** 415 Unsupported Media Type

**File Too Large**
```json
{
  "detail": "File size 104857600 bytes exceeds maximum 52428800 bytes (50MB)"
}
```
**Status:** 413 Payload Too Large

**Server Error**
```json
{
  "detail": "Failed to upload file"
}
```
**Status:** 500 Internal Server Error

---

## Best Practices

1. **Always include Idempotency-Key** for production uploads to handle network failures gracefully
2. **Use consistent customer_id** for multi-tenant systems to maintain data isolation
3. **Add meaningful tags** for easier document discovery and filtering
4. **Specify source** to track document origin (crm, email, api, web, etc.)
5. **Handle 202 responses** differently from 200 - the file is queued, not immediately processed
6. **Implement retry logic** for transient errors (5xx) with exponential backoff
7. **Monitor upload metrics** (file size, type, duration) for performance optimization
