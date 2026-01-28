# GATE API Reference

## Base URL

- **Development**: `http://localhost:8000/api`
- **Production**: `https://your-domain.com/api`

---

## Authentication

All API requests require authentication using Bearer tokens:

```bash
curl -X GET https://your-domain.com/api/entries \
  -H "Authorization: Bearer your-token-here"
```

---

## Endpoints

### Entries

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/entries` | List all entries |
| POST | `/entries` | Create new entry |
| GET | `/entries/{id}` | Get entry details |
| PUT | `/entries/{id}` | Update entry |
| DELETE | `/entries/{id}` | Delete entry |
| POST | `/entries/{id}/submit` | Submit for filing |
| GET | `/entries/{id}/lines` | Get entry line items |
| POST | `/entries/{id}/lines` | Add line item |

#### Create Entry

```bash
POST /api/entries

{
  "entry_type": "consumption",
  "port_of_entry": "4601",
  "importer_of_record_number": "12-3456789",
  "client_id": "uuid-here",
  "line_items": [
    {
      "line_number": 1,
      "hts_code": "8471.30.0100",
      "country_of_origin": "CN",
      "entered_value": 10000,
      "quantity": 100
    }
  ]
}
```

Response:
```json
{
  "id": "uuid",
  "entry_number": "123-1234567-8",
  "status": "draft",
  "created_at": "2026-01-27T12:00:00Z"
}
```

---

### Clients

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/clients` | List all clients |
| POST | `/clients` | Create new client |
| GET | `/clients/{id}` | Get client details |
| PUT | `/clients/{id}` | Update client |
| DELETE | `/clients/{id}` | Delete client |
| GET | `/clients/{id}/entries` | Get client entries |
| GET | `/clients/{id}/summary` | Get client summary stats |

---

### ISF (10+2)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/isf` | List ISF filings |
| POST | `/isf` | Create new ISF |
| GET | `/isf/{id}` | Get ISF details |
| PUT | `/isf/{id}` | Update ISF |
| POST | `/isf/{id}/submit` | Submit to CBP |
| POST | `/isf/{id}/amend` | Amend ISF |

---

### Duty Calculator

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tools/duty-calculator/calculate` | Calculate single line duty |
| POST | `/tools/duty-calculator/entry` | Calculate full entry |
| POST | `/tools/duty-calculator/fees` | Calculate MPF/HMF |
| GET | `/tools/duty-calculator/hts/{code}` | Get HTS info |
| GET | `/tools/duty-calculator/fta/eligibility` | Check FTA eligibility |
| GET | `/tools/duty-calculator/fta/countries` | List FTA countries |
| GET | `/tools/duty-calculator/add-cvd` | Check ADD/CVD |

#### Calculate Duty

```bash
POST /api/tools/duty-calculator/calculate

{
  "hts_code": "8471.30.0100",
  "value": 10000,
  "country_of_origin": "CN",
  "quantity": 100
}
```

Response:
```json
{
  "base_duty_rate": 0.0,
  "base_duty": 0.0,
  "section_301_rate": 0.25,
  "section_301_duty": 2500.0,
  "total_duty": 2500.0,
  "warnings": ["Section 301 tariffs apply to China origin"]
}
```

---

### Entry Lifecycle

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/lifecycle/liquidations` | Get liquidation tracking |
| POST | `/lifecycle/liquidations` | Create liquidation tracking |
| GET | `/lifecycle/protests` | List protests |
| POST | `/lifecycle/protests` | Create protest |
| GET | `/lifecycle/drawback` | List drawback claims |
| POST | `/lifecycle/drawback` | Create drawback claim |

---

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analytics/dashboard` | Get dashboard metrics |
| GET | `/analytics/entries` | Entry analytics |
| GET | `/analytics/compliance` | Compliance scorecard |
| GET | `/analytics/schedules` | List scheduled reports |
| POST | `/analytics/schedules` | Create scheduled report |
| GET | `/analytics/export` | Export data |

---

### Subscriptions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/subscriptions/tiers` | Get available tiers |
| GET | `/subscriptions/{org_id}` | Get org subscription |
| POST | `/subscriptions/{org_id}/upgrade` | Upgrade plan |
| POST | `/subscriptions/{org_id}/cancel` | Cancel subscription |

---

### Help & Onboarding

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/help` | Get help center |
| GET | `/help/search?q=` | Search articles |
| GET | `/help/article/{slug}` | Get article |
| GET | `/onboarding/{user_id}` | Get onboarding progress |
| POST | `/onboarding/{user_id}/complete-step` | Complete step |

---

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic health check |
| GET | `/health/detailed` | Detailed health with components |
| GET | `/health/ready` | Kubernetes readiness probe |
| GET | `/health/live` | Kubernetes liveness probe |

---

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "ENTRY_NOT_FOUND",
    "message": "Entry with ID xyz not found",
    "details": {}
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request data |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Permission denied |
| `NOT_FOUND` | 404 | Resource not found |
| `ENTRY_LIMIT_REACHED` | 403 | Subscription limit |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |

---

## Pagination

List endpoints support pagination:

```bash
GET /api/entries?limit=50&offset=0
```

Response includes:
```json
{
  "count": 50,
  "total": 1234,
  "offset": 0,
  "limit": 50,
  "entries": [...]
}
```

---

## Filtering

Most list endpoints support filtering:

```bash
GET /api/entries?status=draft&client_id=uuid&date_from=2026-01-01
```

---

## Rate Limits

- **Free**: 60 requests/minute
- **Starter**: 120 requests/minute
- **Professional**: 300 requests/minute
- **Enterprise**: 1000 requests/minute

Rate limit headers:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1706400000
```

---

## Webhooks

Configure webhooks to receive real-time events:

### Events

| Event | Description |
|-------|-------------|
| `entry.created` | New entry created |
| `entry.filed` | Entry submitted to CBP |
| `entry.accepted` | CBP accepted entry |
| `entry.rejected` | CBP rejected entry |
| `isf.accepted` | ISF accepted |
| `payment.success` | Payment received |
| `payment.failed` | Payment failed |

### Webhook Payload

```json
{
  "event": "entry.accepted",
  "timestamp": "2026-01-27T12:00:00Z",
  "data": {
    "entry_id": "uuid",
    "entry_number": "123-1234567-8"
  }
}
```

---

## SDKs

### Python

```python
from gate import GateClient

client = GateClient(api_key="your-key")

# Create entry
entry = client.entries.create(
    entry_type="consumption",
    port_of_entry="4601",
    lines=[...]
)

# Calculate duty
duty = client.calculator.calculate(
    hts_code="8471.30.0100",
    value=10000,
    country="CN"
)
```

### JavaScript

```javascript
import { GateAPI } from '@gate/sdk';

const gate = new GateAPI({ apiKey: 'your-key' });

// Create entry
const entry = await gate.entries.create({
  entryType: 'consumption',
  portOfEntry: '4601',
  lines: [...]
});
```

---

*Last Updated: 2026-01-27*
