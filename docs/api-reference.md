# GATE Platform — API Reference

## Overview

The GATE (Global Automated Trade Entry) Platform API provides programmatic access to
customs brokerage operations: filing entries, managing clients, processing documents,
and monitoring compliance.

**Base URL:** `http://localhost:8000` (development)

**Authentication:** Two methods supported:
1. **Session Token:** `Authorization: Bearer <token>` — obtained via `/api/v1/portal/login`
2. **API Key:** `X-API-Key: gk_<key>` — obtained via Settings > API Keys

## API Versioning

All endpoints are available under versioned URLs:

| URL Pattern | Status | Notes |
|-------------|--------|-------|
| `/api/v1/entries` | ✅ **Canonical** | Preferred for all integrations |
| `/api/entries` | ⚠️ Deprecated | Works but adds `Deprecation: true` header |
| `/health`, `/docs` | Unversioned | Infrastructure endpoints, always stable |

**Version discovery:**
```
GET /api/versions
→ { "current": "v1", "supported": ["v1"], "deprecation_policy": "..." }
```

**Response headers on all `/api/*` responses:**
- `X-API-Version: v1` — version that served the request
- `Deprecation: true` — present on unversioned calls
- `Sunset: 2026-12-31` — when unversioned URLs will stop working
- `Link: </api/v1/...>; rel="successor-version"` — canonical versioned URL

---

## Health & Status

### `GET /health`
Lightweight liveness probe. No external dependencies checked.

**Response:**
```json
{ "status": "ok", "environment": "development" }
```

### `GET /api/health/ready`
Readiness probe. Checks database connectivity.

**Response (200):**
```json
{ "status": "ok", "database": "connected", "table_count": 42 }
```

**Response (503):**
```json
{ "status": "degraded", "database": "error", "error": "connection refused" }
```

### `GET /api/health/info`
Operational info for dashboards.

**Response:**
```json
{
  "name": "GATE Platform API",
  "version": "0.2.0",
  "environment": "production",
  "python_version": "3.10.12",
  "table_count": 42
}
```

### `GET /api/health/cache`
Redis cache statistics.

**Response:**
```json
{ "status": "ok", "keys": 156, "used_memory": "2.34M" }
```

---

## Authentication

### `POST /api/portal/login`
Authenticate and obtain a session token.

**Request:**
```json
{ "email": "user@example.com", "password": "s3cret" }
```

**Response (200):**
```json
{
  "token": "sess_abc123...",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "role": "admin",
    "first_name": "Jane",
    "last_name": "Doe"
  }
}
```

### `POST /api/portal/register`
Register a new user account.

### `POST /api/portal/password/forgot`
Request a password reset email.

### `POST /api/portal/password/reset`
Reset password using a reset token.

---

## API Keys

### `GET /api/settings/api-keys/permissions`
List all available permission scopes.

**Response:**
```json
{
  "permissions": [
    "entries:read", "entries:write",
    "shipments:read", "shipments:write",
    "documents:read", "documents:write",
    "clients:read", "compliance:read",
    "reference:read", "webhooks:manage"
  ]
}
```

### `POST /api/settings/api-keys`
Create a new API key. ⚠️ The raw key is only shown once!

**Request:**
```json
{
  "name": "CargoWise Integration",
  "permissions": ["entries:read", "entries:write"],
  "rate_limit_tier": "starter"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "name": "CargoWise Integration",
  "key": "gk_a1b2c3d4e5...",
  "key_prefix": "gk_a1b2c3d4",
  "permissions": ["entries:read", "entries:write"],
  "rate_limit_tier": "starter",
  "is_active": true,
  "created_at": "2026-02-07T02:45:00Z"
}
```

### `GET /api/settings/api-keys`
List all API keys.

### `DELETE /api/settings/api-keys/{key_id}`
Revoke an API key (irreversible).

---

## Webhooks

### `GET /api/settings/webhooks/events`
List all subscribable event types.

### `POST /api/settings/webhooks`
Register a new webhook endpoint.

**Request:**
```json
{
  "name": "TMS Integration",
  "url": "https://tms.example.com/webhooks/gate",
  "events": ["entry.created", "entry.filed", "entry.accepted"]
}
```

**Response (201):** Includes a signing `secret` (only shown once) for HMAC-SHA256 verification.

### `POST /api/settings/webhooks/{id}/test`
Send a test webhook.

### `GET /api/settings/webhooks/{id}/deliveries`
Get delivery history for a webhook.

### `DELETE /api/settings/webhooks/{id}`
Delete a webhook endpoint.

#### Webhook Payload Format
```json
{
  "event": "entry.filed",
  "timestamp": "2026-02-07T02:45:00Z",
  "data": {
    "entry_id": "uuid",
    "entry_number": "ENT-2026-001234"
  }
}
```

#### Signature Verification
Each webhook includes an `X-Gate-Signature` header with HMAC-SHA256:
```
X-Gate-Signature: sha256=<hex_digest>
```
Verify by computing `HMAC-SHA256(JSON.stringify(payload, sort_keys=True), secret)`.

---

## Customs Entries

### `GET /api/entries`
List entries with filtering and pagination.

### `POST /api/entries`
Create a new customs entry.

### `GET /api/entries/{id}`
Get entry detail.

### `PUT /api/entries/{id}`
Update entry fields.

### `POST /api/entries/{id}/file`
Submit entry to ACE for filing.

---

## Clients

### `GET /api/clients`
List clients.

### `POST /api/clients`
Create a new client.

### `GET /api/clients/{id}`
Get client detail.

---

## Notifications

### `GET /api/notifications`
List notifications for a user. Query params: `user_id`, `unread_only`, `limit`, `offset`.

### `GET /api/notifications/unread-count`
Get unread count. Query param: `user_id`.

### `POST /api/notifications/{id}/read`
Mark a notification as read.

### `POST /api/notifications/read-all`
Mark all notifications as read.

---

## Audit Logs

### `GET /api/audit`
Query audit logs. Query params: `resource_id`, `action`, `resource_type`, `limit`, `offset`.

### `POST /api/audit/export`
Export audit logs with date range filtering.

---

## Rate Limiting

The API uses tiered token-bucket rate limiting:

| Tier | Requests/min | Burst |
|------|-------------|-------|
| Starter | 60 | 10 |
| Professional | 300 | 50 |
| Enterprise | 1000 | 200 |

Rate limit headers are returned on every response:
- `X-RateLimit-Limit`: Max requests per window
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Tier`: Current tier

---

## Error Responses

All errors follow a consistent format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Entry number is required",
    "details": { "field": "entry_number" }
  }
}
```

Common error codes:
- `AUTHENTICATION_REQUIRED` (401)
- `AUTHORIZATION_ERROR` (403)
- `NOT_FOUND` (404)
- `VALIDATION_ERROR` (422)
- `RATE_LIMITED` (429)
- `INTERNAL_ERROR` (500)
