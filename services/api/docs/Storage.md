# Storage Configuration Guide

## Overview

The Storage system manages file uploads and persistence using Supabase Storage or S3-compatible services. All uploaded files are stored durably with configurable retention, signed URL access, and metadata tracking.

## Architecture

- **Provider**: Supabase Storage (S3-compatible endpoint) or AWS S3
- **Access Control**: Signed URLs with configurable TTL (default: 1 hour)
- **Metadata Tracking**: File size, MIME type, checksum (SHA-256), upload status
- **Supported Types**: txt, docx, xlsx, pptx, html, md, json, csv, yml, xml

## Setup

### Supabase Storage Setup

1. Create a Supabase project at https://supabase.com
2. Go to Storage → New Bucket
3. Create bucket named `raw-files`
4. Note your S3 endpoint: `https://your-project.supabase.co/storage/v1/s3`
5. Generate access key and secret key from Settings → API

### Configuration

Use the Admin UI or CLI to configure storage:

**Admin UI**: Navigate to `/admin/storage-config`

**CLI**:
```bash
python -m app.tools.storage_cli configure \
  --provider supabase \
  --endpoint https://your-project.supabase.co/storage/v1/s3 \
  --bucket raw-files \
  --region us-east-1 \
  --access-key YOUR_KEY \
  --secret-key YOUR_SECRET
```

**Test Connection**:
```bash
python -m app.tools.storage_cli test-connection
```

## API Endpoints

### Upload File
**POST** `/api/storage/upload`

**Request**:
```bash
curl -X POST http://localhost:8000/api/storage/upload \
  -F "file=@document.pdf"
```

**Response** (201):
```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "signed_url": "https://...",
  "expires_at": "2024-01-09T22:00:00Z",
  "size": 1024000,
  "mime_type": "application/pdf",
  "job_id": "abc123xyz"
}
```

**Errors**:
- `400 Bad Request`: File size exceeds limit or unsupported type
- `500 Internal Server Error`: Storage service unavailable

### Get Upload Metadata
**GET** `/api/storage/upload/{file_id}`

**Response** (200):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "file_size": 1024000,
  "mime_type": "application/pdf",
  "checksum": "abc123...",
  "storage_path": "uploads/document.pdf",
  "upload_status": "completed",
  "expires_at": "2024-01-09T22:00:00Z",
  "created_at": "2024-01-09T21:00:00Z",
  "updated_at": "2024-01-09T21:00:00Z"
}
```

### Get Storage Config
**GET** `/api/storage/config`

**Response** (200):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "provider": "supabase",
  "endpoint": "https://your-project.supabase.co/storage/v1/s3",
  "bucket_name": "raw-files",
  "region": "us-east-1",
  "max_file_size_mb": 100,
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Create Storage Config
**POST** `/api/storage/config`

**Request**:
```json
{
  "provider": "supabase",
  "endpoint": "https://your-project.supabase.co/storage/v1/s3",
  "bucket_name": "raw-files",
  "region": "us-east-1",
  "access_key": "YOUR_KEY",
  "secret_key": "YOUR_SECRET",
  "max_file_size_mb": 100
}
```

## Signed URL Behavior

- Generated on each upload with configurable TTL (default: 3600 seconds)
- Expires automatically - accessing expired URLs returns 403
- Format: `https://endpoint/bucket/path?X-Amz-Signature=...`
- Useful for direct client downloads or previews

## Security Considerations

### Access Control
- Files stored in private bucket by default
- Signed URLs only valid for configured TTL
- Direct object access requires valid AWS signature

### Encryption
- Sensitive fields (access_key, secret_key) encrypted at rest
- All uploads use TLS/HTTPS in transit
- Consider enabling S3 server-side encryption

### File Validation
- MIME type validation on upload
- File size limits enforced
- SHA-256 checksums recorded for integrity verification

## Troubleshooting

### "Storage not configured"
Ensure storage configuration exists:
```bash
python -m app.tools.storage_cli show-config
```

### Connection errors
Test storage credentials:
```bash
python -m app.tools.storage_cli test-connection
```

Check your Supabase endpoint and credentials in `config.py`

### Signed URL expired
Re-upload the file or request fresh URL from metadata endpoint

### File size rejected
Check max_file_size_mb in config (default 100MB):
```bash
python -m app.tools.storage_cli show-config
```

## Monitoring

Monitor storage usage via Supabase console:
- Usage tab shows bucket size and request counts
- Set up billing alerts for quota overages

## Retention Policy

Files are retained indefinitely by default. Consider:
- Setting lifecycle rules in Supabase console
- Periodic cleanup of old uploads (based on created_at timestamp)
- Archive strategy for cold storage
