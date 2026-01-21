# Storage Callbacks Documentation

## Overview

Storage callbacks are webhooks that notify the ingestion platform when files are successfully stored or when storage fails. The platform processes these callbacks to update file status and enqueue extraction tasks.

## Endpoint

### POST /api/callbacks/storage

Handle storage event callbacks from Supabase Storage or S3.

**Status Code:** `200 OK` on success

#### Request

**Content-Type:** `application/json`

**Headers:**
- `X-Signature-256` (required): HMAC-SHA256 signature of the request body for authentication

**Body:**

```json
{
  "path": "uploads/document.pdf",
  "status": "stored",
  "error_message": null
}
```

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` or `storage_path` | String | Yes | Path to file in storage bucket |
| `status` | String | Yes | One of: `stored` (success), `failed` |
| `error_message` | String | No | Error description if status is "failed" |

#### Response

**Success Response (200 OK):**

```json
{
  "success": true,
  "message": "Callback processed",
  "file_id": "550e8400-e29b-41d4-a716-446655440001",
  "storage_path": "uploads/document.pdf"
}
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | Boolean | True if callback was processed successfully |
| `message` | String | Human-readable message |
| `file_id` | UUID | ID of the raw file that was updated |
| `storage_path` | String | Path to the stored file |

**Error Responses:**

- `400 Bad Request`: Invalid payload or missing fields
  ```json
  {
    "detail": "Missing storage_path in callback payload"
  }
  ```
- `401 Unauthorized`: Invalid or missing signature
  ```json
  {
    "detail": "Invalid signature"
  }
  ```
- `500 Internal Server Error`: Server error during processing
  ```json
  {
    "detail": "Failed to process callback"
  }
  ```

---

## Signature Validation

### How It Works

1. Server and Supabase share a secret key
2. Supabase computes HMAC-SHA256 signature: `HMAC-SHA256(secret, raw_request_body)`
3. Supabase includes signature in `X-Signature-256` header
4. Server validates by computing the same signature
5. If signatures match, the callback is trusted

### Signing Algorithm

```python
import hashlib
import hmac

def compute_signature(secret: str, payload: str) -> str:
    """Compute HMAC-SHA256 signature."""
    return hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
```

### Security

- Use **constant-time comparison** (`hmac.compare_digest`) to prevent timing attacks
- **Never expose the secret** in logs or error messages
- Rotate secrets regularly in production
- Only accept callbacks from your Supabase instance

---

## Callback Flow

```
┌─────────────┐
│ Supabase    │
│ Storage     │
└──────┬──────┘
       │
       │ File upload complete
       │ POST /api/callbacks/storage
       │ (with HMAC signature)
       │
       ▼
┌─────────────────────────────────┐
│ Storage Callback Endpoint       │
│ (validate signature)            │
└──────┬──────────────────────────┘
       │
       │ Signature valid?
       │
       ├─ No → 401 Unauthorized
       │
       └─ Yes
          │
          ▼
    ┌─────────────────────────┐
    │ Update raw_files        │
    │ status = "stored"       │
    │ stored_at = now()       │
    └─────┬───────────────────┘
          │
          ▼
    ┌─────────────────────────┐
    │ Create document_metadata│
    │ status = "pending"      │
    └─────┬───────────────────┘
          │
          ▼
    ┌─────────────────────────┐
    │ Enqueue extraction task │
    │ (Celery/Redis)          │
    └─────────────────────────┘
```

---

## Idempotency

Callbacks are idempotent: processing the same callback multiple times is safe.

- If `raw_files.status` is already "stored", the callback is skipped
- No duplicate extraction tasks are created
- Returns `200 OK` with message "File already processed (idempotent)"

---

## Retry Policy

If callback processing fails:

1. **First attempt:** Immediate processing
2. **Failure detected:** Increment `retry_count`
3. **Retry delays:**
   - Retry 1: 5 seconds
   - Retry 2: 25 seconds (5^2)
   - Retry 3: 125 seconds (5^3)
4. **Max retries:** 3 (configurable)
5. **Final failure:** Admin notification sent

### Retry Configuration

| Config | Default | Description |
|--------|---------|-------------|
| `MAX_RETRIES` | 3 | Maximum retry attempts |
| `RETRY_BASE` | 5 | Base for exponential backoff (seconds) |

---

## Setup with Supabase Storage

### 1. Generate Webhook Secret

```bash
# Generate a strong random secret
openssl rand -hex 32
# Output: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6...
```

### 2. Configure Environment Variables

```bash
# In .env file
STORAGE_CALLBACK_SECRET="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6..."
STORAGE_CALLBACK_URL="https://your-domain.com/api/callbacks/storage"
```

### 3. Set Up Webhook in Supabase

```bash
# Using Supabase CLI
supabase functions deploy storage-webhook

# Or configure manually in Supabase dashboard:
# 1. Go to Storage → Buckets → raw-files
# 2. Click "Events"
# 3. Add webhook:
#    - Event: "object.finalized" (file upload complete)
#    - HTTP method: POST
#    - URL: https://your-domain.com/api/callbacks/storage
#    - Headers: Include X-Signature-256
```

### 4. Test Webhook

```bash
# Test signature validation
curl -X POST http://localhost:8000/api/callbacks/storage \
  -H "Content-Type: application/json" \
  -H "X-Signature-256: $(echo -n '{"path":"test.pdf","status":"stored"}' | openssl dgst -sha256 -hmac 'dev-secret' | cut -d' ' -f2)" \
  -d '{"path":"test.pdf","status":"stored"}'
```

---

## Integration Examples

### Supabase Webhook Payload

```json
{
  "type": "INSERT",
  "table": "objects",
  "record": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "bucket_id": "raw-files",
    "name": "document.pdf",
    "owner": "550e8400-e29b-41d4-a716-446655440001",
    "owner_id": "550e8400-e29b-41d4-a716-446655440002",
    "metadata": {
      "mimetype": "application/pdf",
      "cacheControl": "max-age=3600"
    },
    "updated_at": "2026-01-11T10:00:00Z",
    "created_at": "2026-01-11T10:00:00Z",
    "last_accessed_at": "2026-01-11T10:00:00Z",
    "path_tokens": ["uploads", "document.pdf"]
  }
}
```

**Transform to callback format:**

```python
def supabase_webhook_to_callback(payload: dict) -> dict:
    """Convert Supabase webhook to callback format."""
    record = payload['record']
    path_tokens = record.get('path_tokens', [])
    storage_path = '/'.join(path_tokens) if path_tokens else record['name']

    return {
        'path': storage_path,
        'status': 'stored',
        'error_message': None,
    }
```

### Using S3 Event Notifications

For S3-compatible storage (e.g., MinIO):

```python
import hashlib
import json
from fastapi import Request

async def handle_s3_event(request: Request) -> dict:
    """Handle S3 PUT Object event."""
    body = await request.body()
    event = json.loads(body)

    # Extract file path from S3 event
    s3_event = event['Records'][0]['s3']
    bucket = s3_event['bucket']['name']
    key = s3_event['object']['key']

    return {
        'path': key,
        'status': 'stored',
        'error_message': None,
    }
```

---

## Monitoring

### Metrics to Track

- **Callback arrival rate**: Events per minute
- **Processing latency**: Time from callback receipt to extraction task enqueue
- **Error rate**: Failed callbacks
- **Retry rate**: Callbacks that required retries
- **Storage path distribution**: Which files are uploaded most

### Example Logging

```python
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

logger.info(
    "Callback processed",
    extra={
        'file_id': str(raw_file.id),
        'storage_path': storage_path,
        'status': raw_file.status,
        'processing_time_ms': (datetime.now() - start_time).total_seconds() * 1000,
    }
)
```

---

## Troubleshooting

### Common Issues

**Signature validation fails:**
- Verify `STORAGE_CALLBACK_SECRET` matches Supabase secret
- Check raw request body matches signed payload (no modifications)
- Ensure secret is not URL-encoded or modified

**Callbacks not arriving:**
- Check Supabase webhook configuration and URL
- Verify firewall/network allows inbound requests
- Check Supabase logs for webhook delivery errors

**Raw file not found:**
- Ensure raw file was created before callback sent
- Check file `storage_path` matches callback `path`

**Extraction tasks not queued:**
- Verify Redis/Celery broker is running
- Check task enqueue logs for errors
- Verify Celery worker is running

---

## Best Practices

1. **Validate signatures** on all callbacks (non-negotiable)
2. **Log all callbacks** for audit and debugging
3. **Monitor callback latency** - should be <10 seconds
4. **Implement dead-letter queue** for failed callbacks
5. **Use exponential backoff** for retries
6. **Rotate secrets** every 90 days
7. **Test webhook setup** before production deployment
8. **Keep `STORAGE_CALLBACK_SECRET`** in secure vault (Secrets Manager, 1Password, etc.)
