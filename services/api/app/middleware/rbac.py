"""Role-Based Access Control (RBAC) middleware and dependencies."""

from typing import Optional, Set
from fastapi import HTTPException, status, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db


class RBACConfig:
    """Configuration for RBAC checks."""

    def __init__(self, required_roles: Optional[Set[str]] = None, required_permissions: Optional[Set[str]] = None):
        self.required_roles = required_roles or set()
        self.required_permissions = required_permissions or set()


async def get_user_from_request(request: Request) -> Optional[dict]:
    """
    Extract user information from request headers or context.

    In a real application, this would extract from JWT tokens or session.
    For now, we use request headers for testing purposes.
    """
    # Check for user context in request state (set by auth middleware)
    if hasattr(request.state, "user"):
        return request.state.user

    # For development/testing, check headers
    user_id = request.headers.get("X-User-ID")
    user_roles = request.headers.get("X-User-Roles", "").split(",") if request.headers.get("X-User-Roles") else []
    user_permissions = request.headers.get("X-User-Permissions", "").split(",") if request.headers.get("X-User-Permissions") else []

    if not user_id:
        return None

    return {
        "user_id": user_id,
        "roles": [r.strip() for r in user_roles if r.strip()],
        "permissions": [p.strip() for p in user_permissions if p.strip()],
    }


def admin_required():
    """
    Dependency that checks if user has 'admin' role or 'admin' permission.

    Returns:
        dict: User information if authorized

    Raises:
        HTTPException: 403 Forbidden if user lacks admin role/permission
    """
    async def check_admin(
        request: Request,
        session: AsyncSession = Depends(get_db),
    ) -> dict:
        user = await get_user_from_request(request)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No user context found. Authentication required.",
            )

        # Check if user has 'admin' role or 'admin' permission
        has_admin_role = "admin" in user.get("roles", [])
        has_admin_permission = "admin" in user.get("permissions", [])

        if not (has_admin_role or has_admin_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role or permission required to access this resource.",
            )

        return user

    return check_admin


def role_required(required_roles: Set[str]):
    """
    Dependency factory that checks if user has one of the required roles.

    Args:
        required_roles: Set of role names required for access

    Returns:
        dict: User information if authorized

    Raises:
        HTTPException: 403 Forbidden if user lacks required role
    """
    async def check_role(
        request: Request,
        session: AsyncSession = Depends(get_db),
    ) -> dict:
        user = await get_user_from_request(request)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No user context found. Authentication required.",
            )

        user_roles = set(user.get("roles", []))
        if not user_roles & required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of these roles required: {', '.join(required_roles)}",
            )

        return user

    return check_role


def permission_required(required_permissions: Set[str]):
    """
    Dependency factory that checks if user has one of the required permissions.

    Args:
        required_permissions: Set of permission names required for access

    Returns:
        dict: User information if authorized

    Raises:
        HTTPException: 403 Forbidden if user lacks required permission
    """
    async def check_permission(
        request: Request,
        session: AsyncSession = Depends(get_db),
    ) -> dict:
        user = await get_user_from_request(request)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No user context found. Authentication required.",
            )

        user_permissions = set(user.get("permissions", []))
        if not user_permissions & required_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of these permissions required: {', '.join(required_permissions)}",
            )

        return user

    return check_permission
