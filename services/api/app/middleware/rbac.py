"""
DEPRECATED — middleware/rbac.py

This module is superseded by app.core.auth, which provides real database-backed
authentication and role checking.

This shim re-exports the same symbols so any remaining code that imports from
here continues to work, but all references should be migrated to app.core.auth:

    # Old (deprecated)
    from app.middleware.rbac import admin_required, role_required

    # New (canonical)
    from app.core.auth import require_admin, require_role, get_current_user

Background: The original rbac.py read roles from plain HTTP headers
(X-User-Roles, X-User-ID) which any client can spoof.  app.core.auth
validates bearer tokens and API keys against the database.

This file will be removed in a future release.
"""
import warnings

warnings.warn(
    "app.middleware.rbac is deprecated. Import from app.core.auth instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export canonical equivalents under the old names so callers don't break.
from app.core.auth import (  # noqa: E402
    require_admin,
    require_role,
    get_current_user,
    get_optional_user,
)

# Old names → canonical equivalents
admin_required = require_admin
role_required = require_role


def permission_required(required_permissions):
    """
    Deprecated stub.  Map to require_role for backwards compatibility.

    The original implementation read permissions from a spoofable HTTP header.
    Use require_role() from app.core.auth for proper database-backed checks.
    """
    warnings.warn(
        "permission_required() is deprecated and has no real implementation. "
        "Use require_role() from app.core.auth instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return require_role(*required_permissions)


async def get_user_from_request(request):
    """
    Deprecated stub.  The original version read from spoofable headers.
    Use get_current_user() from app.core.auth as a FastAPI Depends().
    """
    warnings.warn(
        "get_user_from_request() reads from spoofable headers and is insecure. "
        "Use Depends(get_current_user) from app.core.auth instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return None


__all__ = [
    "admin_required",
    "role_required",
    "permission_required",
    "get_user_from_request",
]
