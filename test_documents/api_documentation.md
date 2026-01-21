# Technical API Documentation

## Overview

The Document Ingestion Platform provides a comprehensive REST API for uploading, processing, and searching documents. This documentation covers all available endpoints and their usage.

## Authentication

All API requests require authentication using a Bearer token:

```
Authorization: Bearer <your-api-token>
```

## Endpoints

### Upload Document

**POST** `/api/storage/upload`

Upload a document for processing. Supports multiple file formats including PDF, DOCX, TXT, and more.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` - The document to upload

**Response:**
```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "signed_url": "https://storage.example.com/...",
  "expires_at": "2024-01-09T22:00:00Z",
  "job_id": "abc123xyz"
}
```

### Search Documents

**GET** `/api/vector-store/search`

Search for documents using semantic similarity.

**Parameters:**
- `query` (required): Search query text
- `limit` (optional): Maximum results (default: 10)
- `threshold` (optional): Similarity threshold (0-1)

**Response:**
```json
{
  "results": [
    {
      "content_chunk": "User authentication is handled via OAuth 2.0...",
      "similarity_score": 0.92,
      "document_id": "doc-123",
      "metadata": {
        "filename": "auth-guide.pdf",
        "page": 5
      }
    }
  ],
  "query_time_ms": 245
}
```

### Get Queue Status

**GET** `/api/queue/status`

Get the current status of the processing queue.

**Response:**
```json
{
  "pending": 5,
  "running": 2,
  "failed": 1,
  "completed": 150
}
```

## Error Handling

All errors follow a standard format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid file format",
    "details": {
      "supported_formats": ["pdf", "docx", "txt", "md"]
    }
  }
}
```

## Rate Limits

- Standard tier: 100 requests/minute
- Premium tier: 1000 requests/minute

Exceeded rate limits return HTTP 429 with a `Retry-After` header.

## Webhooks

Configure webhooks to receive notifications when document processing completes:

**POST** `/api/webhooks`

```json
{
  "url": "https://your-server.com/webhook",
  "events": ["document.processed", "document.failed"]
}
```

---

*Last updated: January 2026*
