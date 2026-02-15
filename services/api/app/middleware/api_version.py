"""
GATE Platform — API Versioning Middleware.

Provides URL-based API versioning (/api/v1/) while maintaining
backward compatibility with unversioned /api/ routes.

Strategy:
  - /api/v1/entries  → canonical versioned URL (preferred for integrations)
  - /api/entries     → still works (backward compat, adds deprecation notice)
  - /health, /docs   → unversioned (infrastructure endpoints)

The middleware strips the version prefix before routing, so all
existing route handlers continue to work without modification.
"""
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Current supported version
CURRENT_API_VERSION = "v1"
SUPPORTED_VERSIONS = ["v1"]

# Routes that should NOT be versioned
UNVERSIONED_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
)


class ApiVersionMiddleware(BaseHTTPMiddleware):
    """
    API versioning middleware.

    - /api/v1/entries → routes to /api/entries (strips version prefix)
    - /api/entries    → routes as-is (backward compat, adds deprecation header)
    - Adds X-API-Version header to all /api/* responses
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.scope["path"]

        # Skip non-API routes
        if not path.startswith("/api/"):
            response = await call_next(request)
            return response

        # Skip health/infra endpoints under /api/
        if path.startswith("/api/health"):
            response = await call_next(request)
            response.headers["X-API-Version"] = CURRENT_API_VERSION
            return response

        # Handle versioned requests: /api/v1/entries → /api/entries
        api_version = None
        for version in SUPPORTED_VERSIONS:
            prefix = f"/api/{version}/"
            if path.startswith(prefix):
                api_version = version
                # Rewrite URL to strip version prefix
                new_path = "/api/" + path[len(prefix):]
                request.scope["path"] = new_path
                break

        response = await call_next(request)

        # Add version header
        response.headers["X-API-Version"] = api_version or CURRENT_API_VERSION

        # If request was unversioned, add deprecation notice
        if api_version is None and path.startswith("/api/"):
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = "2026-12-31"
            response.headers["Link"] = f'</api/{CURRENT_API_VERSION}{path[4:]}>; rel="successor-version"'

        return response
