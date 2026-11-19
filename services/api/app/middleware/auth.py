"""
GATE Platform — Authentication Middleware.

Enforces authentication on all /api/* routes except explicitly excluded paths.
Validates the session token and attaches user info to request.state.
"""
import logging
import re
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Routes that do NOT require authentication
# Format: (method, regex_pattern)
AUTH_EXEMPT_ROUTES = [
    # Health endpoints
    ("GET", r"^/health$"),
    ("GET", r"^/api/health/(ready|info|cache)$"),
    ("GET", r"^/$"),
    ("GET", r"^/docs"),
    ("GET", r"^/redoc"),
    ("GET", r"^/openapi\.json$"),

    # Auth flow — must be accessible without token
    ("POST", r"^/api/portal/login$"),
    ("POST", r"^/api/portal/register$"),
    ("POST", r"^/api/portal/password/forgot$"),
    ("POST", r"^/api/portal/password/reset$"),
    ("POST", r"^/api/portal/accept-invitation$"),
    ("GET", r"^/api/portal/invitations/[^/]+$"),
    ("GET", r"^/api/portal/reference/roles$"),
    ("POST", r"^/api/portal/verify-email$"),
    ("POST", r"^/api/portal/resend-verification$"),
    ("POST", r"^/api/billing/stripe/webhook$"),
    ("POST", r"^/api/callbacks/storage$"),

    # Landing analytics — POST event ingest is public; GET analytics requires auth
    ("POST", r"^/api/analytics/landing"),

    # Lead capture — public
    ("POST", r"^/api/leads/?$"),

    # API version discovery — public
    ("GET", r"^/api/versions$"),
]

# Pre-compile patterns for performance
_compiled_exemptions = [(method, re.compile(pattern)) for method, pattern in AUTH_EXEMPT_ROUTES]


def _is_exempt(method: str, path: str) -> bool:
    """Check if a request path is exempt from authentication."""
    for exempt_method, pattern in _compiled_exemptions:
        if method == exempt_method and pattern.match(path):
            return True
    return False


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces authentication on protected routes.

    For path starting with /api/, checks for valid Bearer token or API key.
    Sets request.state.user with user info if authenticated.
    Returns 401 for unauthenticated requests to protected routes.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        method = request.method

        # Skip auth for exempt routes
        if _is_exempt(method, path):
            return await call_next(request)

        # Skip auth for non-API routes (static files, etc.)
        if not path.startswith("/api/") and path != "/health":
            return await call_next(request)

        # Extract token
        authorization = request.headers.get("Authorization", "")
        api_key = request.headers.get("X-API-Key", "")

        user = None

        # Try session token
        if authorization.startswith("Bearer "):
            token = authorization[7:]
            user = await self._validate_token(token, request)

        # Try API key
        elif api_key.startswith("gk_"):
            user = await self._validate_api_key(api_key, request)

        if user is None:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "AUTHENTICATION_REQUIRED",
                        "message": "Authentication required. Provide a valid Bearer token or API key.",
                    }
                },
            )

        # Enforce fine-grained scope checks when caller authenticates via X-API-Key
        if user.get("role") == "api_key":
            missing_scope = check_api_key_permission(
                method=method,
                path=path,
                permissions=user.get("permissions") or [],
            )
            if missing_scope:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "INSUFFICIENT_API_KEY_SCOPE",
                            "message": f"API key lacks required permission: {missing_scope}",
                        }
                    },
                )

        # Attach user to request state so route handlers can access it
        request.state.user = user
        return await call_next(request)

    async def _validate_token(self, token: str, request: Request) -> Optional[dict]:
        """Validate a session token and return user info."""
        try:
            from app.core.database import AsyncSessionLocal
            from app.services.client_portal_auth_service import ClientPortalAuthService

            async with AsyncSessionLocal() as db:
                service = ClientPortalAuthService(db)
                user = await service.validate_session(token)
                if user:
                    return {
                        "id": str(user.id),
                        "email": user.email,
                        "role": user.role,
                        "client_id": str(user.client_id) if user.client_id else None,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                    }
        except Exception as e:
            logger.error(f"Token validation error: {e}")

        return None

    async def _validate_api_key(self, api_key: str, request: Request) -> Optional[dict]:
        """Validate an API key via ApiKeyService."""
        try:
            from app.core.database import AsyncSessionLocal
            from app.services.api_key_service import ApiKeyService

            async with AsyncSessionLocal() as db:
                service = ApiKeyService(db)
                return await service.validate_key(api_key)
        except Exception as e:
            logger.error(f"API key validation error: {e}")

        return None


def check_api_key_permission(method: str, path: str, permissions: list[str]) -> Optional[str]:
    """
    Verify an API key's granted permission scopes cover the requested HTTP method and route prefix.
    Returns None if permitted, or the missing scope name when forbidden.
    """
    perms = set(permissions or [])
    is_read = method.upper() in ("GET", "HEAD", "OPTIONS")

    if path.startswith(("/api/admin", "/api/portal", "/api/leads", "/api/api-keys")):
        return "broker_session_required"

    if path.startswith("/api/webhooks"):
        return None if "webhooks:manage" in perms else "webhooks:manage"

    if path.startswith("/api/export"):
        return None if ("entries:read" in perms or "entries:write" in perms) else "entries:read"

    if path.startswith(("/api/entries", "/api/entry-prep", "/api/isf", "/api/ace")):
        needed = "entries:read" if is_read else "entries:write"
        return None if (needed in perms or "entries:write" in perms) else needed

    if path.startswith("/api/shipments"):
        needed = "shipments:read" if is_read else "shipments:write"
        return None if (needed in perms or "shipments:write" in perms) else needed

    if path.startswith(("/api/upload", "/api/ingest", "/api/files", "/api/storage", "/api/review")):
        needed = "documents:read" if is_read else "documents:write"
        return None if (needed in perms or "documents:write" in perms) else needed

    if path.startswith(("/api/clients", "/api/poa", "/api/billing")):
        if not is_read:
            return "broker_session_required"
        return None if "clients:read" in perms else "clients:read"

    if path.startswith(("/api/compliance", "/api/trade-compliance", "/api/pga", "/api/duty-calculator")):
        return None if "compliance:read" in perms else "compliance:read"

    if path.startswith("/api/reference-data"):
        return None if "reference:read" in perms else "reference:read"

    return None if is_read else "broker_session_required"

