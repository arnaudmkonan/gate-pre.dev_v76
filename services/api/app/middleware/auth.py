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

    # Landing analytics — public
    ("GET", r"^/api/analytics/landing"),
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
