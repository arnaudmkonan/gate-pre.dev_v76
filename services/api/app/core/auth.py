"""
GATE Platform — Centralized Authentication Dependencies.

Provides FastAPI dependencies for route-level authentication.
Integrates with existing ClientPortalAuthService session tokens.
"""
import logging
from typing import Optional, Set

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    FastAPI dependency — extracts and validates the current user.

    Supports two authentication methods:
    1. Session token: Authorization: Bearer <session_token>
    2. API key: X-API-Key: gk_<api_key>  (future — returns system user for now)

    Returns a dict with: id, email, role, client_id, first_name, last_name
    """
    # Try API key first
    if x_api_key:
        user = await _validate_api_key(x_api_key, db)
        if user:
            return user

    # Try session token
    if authorization:
        user = await _validate_session_token(authorization, db)
        if user:
            return user

    raise AuthenticationError("Authentication required. Provide a Bearer token or API key.")


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Optional[dict]:
    """
    Like get_current_user but returns None instead of raising on missing auth.
    Useful for endpoints that behave differently for authenticated vs anonymous.
    """
    try:
        return await get_current_user(authorization, x_api_key, db)
    except AuthenticationError:
        return None


def require_role(*roles: str):
    """
    Dependency factory — ensures user has one of the specified roles.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role("admin"))])
        async def admin_endpoint():
            ...
    """
    async def check(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("role", "")
        if user_role not in roles:
            raise AuthorizationError(
                message=f"Role '{user_role}' does not have access. Required: {', '.join(roles)}",
                required=", ".join(roles),
            )
        return user
    return check


def require_admin():
    """Shorthand for require_role('admin')."""
    return require_role("admin")


# ===========================================================================
# Internal validators
# ===========================================================================

async def _validate_session_token(authorization: str, db: AsyncSession) -> Optional[dict]:
    """Validate a Bearer session token using ClientPortalAuthService."""
    try:
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        token = parts[1]
    except (ValueError, IndexError):
        return None

    # Lazy import to avoid circular imports
    from app.services.client_portal_auth_service import ClientPortalAuthService

    service = ClientPortalAuthService(db)
    user = await service.validate_session(token)

    if not user:
        return None

    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "client_id": str(user.client_id) if user.client_id else None,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "status": user.status,
    }


async def _validate_api_key(api_key: str, db: AsyncSession) -> Optional[dict]:
    """
    Validate an API key by hashing and looking up in the database.

    Returns a user-like dict with api_key_id and permissions on success.
    """
    if not api_key or not api_key.startswith("gk_"):
        return None

    try:
        from app.services.api_key_service import ApiKeyService

        service = ApiKeyService(db)
        return await service.validate_key(api_key)
    except Exception as e:
        logger.error(f"API key validation error: {e}")
        return None
