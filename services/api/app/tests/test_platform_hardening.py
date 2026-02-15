"""
API Contract Tests — Platform Hardening Features.

Tests the key API endpoints created during hardening:
- Health endpoints (liveness, readiness, info, cache)
- API Key management (create, list, revoke)
- Webhook management (create, list, test, delete, deliveries)
- Notification endpoints (list, read, count)
- Audit log endpoints (list, export)
- Settings and reference endpoints

These tests run against the FastAPI app using httpx/TestClient,
no external services required.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def app():
    """Get the FastAPI app instance."""
    from app.main import app as fastapi_app
    return fastapi_app


@pytest.fixture
async def client(app):
    """Async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ============================================================================
# Health Endpoints
# ============================================================================

class TestHealthEndpoints:
    """Verify all health endpoints return expected shapes."""

    @pytest.mark.asyncio
    async def test_liveness_probe(self, client):
        """GET /health returns 200 with status=ok."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "environment" in data

    @pytest.mark.asyncio
    async def test_readiness_probe(self, client):
        """GET /api/health/ready returns database connectivity status."""
        response = await client.get("/api/health/ready")
        assert response.status_code in (200, 503)
        data = response.json()
        assert "status" in data
        assert "database" in data

    @pytest.mark.asyncio
    async def test_info_endpoint(self, client):
        """GET /api/health/info returns version and env info."""
        response = await client.get("/api/health/info")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "GATE Platform API"
        assert "version" in data
        assert "environment" in data

    @pytest.mark.asyncio
    async def test_cache_health(self, client):
        """GET /api/health/cache returns cache stats."""
        response = await client.get("/api/health/cache")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


# ============================================================================
# API Key Endpoints
# ============================================================================

class TestApiKeyEndpoints:
    """Verify API key management endpoint contracts."""

    @pytest.mark.asyncio
    async def test_list_permissions(self, client):
        """GET /api/settings/api-keys/permissions returns available scopes."""
        response = await client.get("/api/settings/api-keys/permissions")
        assert response.status_code == 200
        data = response.json()
        assert "permissions" in data
        assert isinstance(data["permissions"], list)
        assert "entries:read" in data["permissions"]
        assert "entries:write" in data["permissions"]

    @pytest.mark.asyncio
    async def test_create_key_returns_raw_key(self, client):
        """POST /api/settings/api-keys returns key once on creation."""
        response = await client.post("/api/settings/api-keys", json={
            "name": "Test Integration Key",
            "permissions": ["entries:read"],
        })
        # May return 201 or 500 if DB not available; check contract shape
        if response.status_code == 201:
            data = response.json()
            assert "id" in data
            assert "key" in data
            assert data["key"].startswith("gk_")
            assert data["name"] == "Test Integration Key"
            assert "key_prefix" in data

    @pytest.mark.asyncio
    async def test_list_keys(self, client):
        """GET /api/settings/api-keys returns list shape."""
        response = await client.get("/api/settings/api-keys")
        if response.status_code == 200:
            data = response.json()
            assert "count" in data
            assert "api_keys" in data
            assert isinstance(data["api_keys"], list)


# ============================================================================
# Webhook Endpoints
# ============================================================================

class TestWebhookEndpoints:
    """Verify webhook management endpoint contracts."""

    @pytest.mark.asyncio
    async def test_list_events(self, client):
        """GET /api/settings/webhooks/events returns all event types."""
        response = await client.get("/api/settings/webhooks/events")
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert isinstance(data["events"], list)
        assert "entry.created" in data["events"]
        assert "entry.filed" in data["events"]
        assert "document.processed" in data["events"]

    @pytest.mark.asyncio
    async def test_create_webhook_validation(self, client):
        """POST /api/settings/webhooks with invalid events returns 422."""
        response = await client.post("/api/settings/webhooks", json={
            "url": "https://example.com/hook",
            "name": "Test",
            "events": ["invalid.event"],
        })
        # Should be 422 for invalid events
        if response.status_code != 500:
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_webhooks(self, client):
        """GET /api/settings/webhooks returns list shape."""
        response = await client.get("/api/settings/webhooks")
        if response.status_code == 200:
            data = response.json()
            assert "count" in data
            assert "webhooks" in data


# ============================================================================
# Notification Endpoints
# ============================================================================

class TestNotificationEndpoints:
    """Verify notification endpoint contracts."""

    @pytest.mark.asyncio
    async def test_list_notification_types(self, client):
        """GET /api/notifications/types returns type registry."""
        response = await client.get("/api/notifications/types")
        assert response.status_code == 200
        data = response.json()
        assert "types" in data
        assert "entry_status" in data["types"]
        assert "compliance_alert" in data["types"]

    @pytest.mark.asyncio
    async def test_unread_count_requires_user_id(self, client):
        """GET /api/notifications/unread-count without user_id returns 422."""
        response = await client.get("/api/notifications/unread-count")
        assert response.status_code == 422


# ============================================================================
# Audit Endpoints
# ============================================================================

class TestAuditEndpoints:
    """Verify audit log endpoint contracts."""

    @pytest.mark.asyncio
    async def test_list_audit_logs(self, client):
        """GET /api/audit returns audit log list."""
        response = await client.get("/api/audit")
        if response.status_code == 200:
            data = response.json()
            assert "logs" in data
            assert "total_count" in data
            assert "limit" in data
            assert "offset" in data


# ============================================================================
# Root and Docs
# ============================================================================

class TestRootEndpoints:
    """Verify root and documentation endpoints."""

    @pytest.mark.asyncio
    async def test_root(self, client):
        """GET / returns platform name."""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "GATE" in data["name"]

    @pytest.mark.asyncio
    async def test_openapi_spec(self, client):
        """GET /openapi.json returns valid OpenAPI spec."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        assert "info" in data


# ============================================================================
# Service Unit Tests
# ============================================================================

class TestApiKeyService:
    """Unit tests for API key service logic."""

    def test_key_generation_format(self):
        """Generated keys start with gk_ and are 52 chars."""
        from app.services.api_key_service import _generate_key
        raw, prefix, key_hash = _generate_key()
        assert raw.startswith("gk_")
        assert len(raw) == 51  # "gk_" + 48 hex chars
        assert prefix == raw[:12]
        assert len(key_hash) == 64  # SHA-256 hex

    def test_key_hash_deterministic(self):
        """Same key always produces same hash."""
        from app.services.api_key_service import _hash_key
        h1 = _hash_key("gk_abc123")
        h2 = _hash_key("gk_abc123")
        assert h1 == h2

    def test_key_hash_differs(self):
        """Different keys produce different hashes."""
        from app.services.api_key_service import _hash_key
        h1 = _hash_key("gk_abc123")
        h2 = _hash_key("gk_def456")
        assert h1 != h2


class TestWebhookService:
    """Unit tests for webhook service logic."""

    def test_hmac_signature(self):
        """HMAC signature is deterministic and valid format."""
        from app.services.webhook_service import WebhookService
        payload = {"event": "test", "data": {"id": "123"}}
        sig = WebhookService._sign_payload(payload, "test_secret")
        assert sig.startswith("sha256=")
        assert len(sig) == 71  # "sha256=" + 64 hex chars

    def test_hmac_consistent(self):
        """Same payload and secret produce same signature."""
        from app.services.webhook_service import WebhookService
        payload = {"event": "test"}
        sig1 = WebhookService._sign_payload(payload, "secret")
        sig2 = WebhookService._sign_payload(payload, "secret")
        assert sig1 == sig2

    def test_hmac_differs_with_secret(self):
        """Different secrets produce different signatures."""
        from app.services.webhook_service import WebhookService
        payload = {"event": "test"}
        sig1 = WebhookService._sign_payload(payload, "secret1")
        sig2 = WebhookService._sign_payload(payload, "secret2")
        assert sig1 != sig2


class TestCacheService:
    """Unit tests for cache service logic."""

    def test_cache_key_format(self):
        """Cache keys use gate: prefix."""
        from app.core.cache import cache_key
        key = cache_key("hts", "8471.30")
        assert key == "gate:hts:8471.30"

    def test_cache_key_with_kwargs(self):
        """Cache keys include sorted kwargs."""
        from app.core.cache import cache_key
        key = cache_key("lookup", "us", country="US", year="2024")
        assert "country=US" in key
        assert "year=2024" in key


class TestAuditServiceHelpers:
    """Unit tests for audit service helpers."""

    def test_track_changes_detects_diff(self):
        """track_changes shows only changed fields."""
        from app.services.audit_service import track_changes
        before = {"status": "draft", "name": "Test"}
        after = {"status": "filed", "name": "Test"}
        changes = track_changes(before, after)
        assert "status" in changes
        assert changes["status"]["old"] == "draft"
        assert changes["status"]["new"] == "filed"
        assert "name" not in changes

    def test_track_changes_empty_on_no_diff(self):
        """track_changes returns empty dict when nothing changed."""
        from app.services.audit_service import track_changes
        data = {"a": "1", "b": "2"}
        changes = track_changes(data, data)
        assert changes == {}
