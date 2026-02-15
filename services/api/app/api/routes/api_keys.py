"""
API Key management routes.

Endpoints for creating, listing, and revoking API keys.
"""
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.api_key_service import ApiKeyService, PERMISSION_SCOPES

router = APIRouter(prefix="/api/settings/api-keys", tags=["API Keys"])


# ==================== Schemas ====================

class ApiKeyCreate(BaseModel):
    """Create a new API key."""
    name: str
    permissions: Optional[List[str]] = None
    rate_limit_tier: str = "starter"
    expires_at: Optional[datetime] = None


class ApiKeyResponse(BaseModel):
    """API key response (never includes raw key)."""
    id: str
    name: str
    key_prefix: str
    permissions: List[str]
    rate_limit_tier: str
    is_active: bool
    created_at: str
    expires_at: Optional[str] = None
    last_used_at: Optional[str] = None
    revoked_at: Optional[str] = None


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Response when a key is first created (includes raw key)."""
    key: str  # Only shown once!


# ==================== Endpoints ====================

@router.get("/permissions")
async def list_permissions():
    """List all available permission scopes."""
    return {"permissions": PERMISSION_SCOPES}


@router.post("", status_code=201)
async def create_api_key(
    request: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new API key.

    ⚠️ The raw key is only shown ONCE in this response — store it securely!
    """
    service = ApiKeyService(db)

    try:
        api_key, raw_key = await service.create_key(
            name=request.name,
            permissions=request.permissions,
            rate_limit_tier=request.rate_limit_tier,
            expires_at=request.expires_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return ApiKeyCreatedResponse(
        id=str(api_key.id),
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        key=raw_key,
        permissions=api_key.permissions or [],
        rate_limit_tier=api_key.rate_limit_tier,
        is_active=api_key.is_active,
        created_at=api_key.created_at.isoformat(),
        expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
    )


@router.get("")
async def list_api_keys(
    include_revoked: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for the current user/client."""
    service = ApiKeyService(db)
    keys = await service.list_keys(include_revoked=include_revoked)

    return {
        "count": len(keys),
        "api_keys": [
            ApiKeyResponse(
                id=str(k.id),
                name=k.name,
                key_prefix=k.key_prefix,
                permissions=k.permissions or [],
                rate_limit_tier=k.rate_limit_tier,
                is_active=k.is_active,
                created_at=k.created_at.isoformat(),
                expires_at=k.expires_at.isoformat() if k.expires_at else None,
                last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
                revoked_at=k.revoked_at.isoformat() if k.revoked_at else None,
            ).dict()
            for k in keys
        ],
    }


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key. This action is irreversible."""
    from uuid import UUID

    service = ApiKeyService(db)
    revoked = await service.revoke_key(UUID(key_id))
    if not revoked:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"revoked": True}
