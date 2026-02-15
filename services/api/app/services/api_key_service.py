"""
GATE Platform — API Key Service.

Handles generation, validation, and revocation of API keys.
Keys use the format: gk_<48 hex chars>
Only the hash is stored; the raw key is returned once on creation.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey

logger = logging.getLogger(__name__)

# All available permission scopes
PERMISSION_SCOPES = [
    "entries:read",
    "entries:write",
    "shipments:read",
    "shipments:write",
    "documents:read",
    "documents:write",
    "clients:read",
    "compliance:read",
    "reference:read",
    "webhooks:manage",
]


def _hash_key(raw_key: str) -> str:
    """SHA-256 hash of a raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _generate_key() -> tuple[str, str, str]:
    """
    Generate a new API key.

    Returns: (raw_key, key_prefix, key_hash)
    """
    raw = f"gk_{secrets.token_hex(24)}"
    prefix = raw[:12]  # "gk_a1b2c3d4" for display
    key_hash = _hash_key(raw)
    return raw, prefix, key_hash


class ApiKeyService:
    """Manages API key lifecycle."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_key(
        self,
        name: str,
        client_id: Optional[UUID] = None,
        created_by: Optional[UUID] = None,
        permissions: Optional[List[str]] = None,
        rate_limit_tier: str = "starter",
        expires_at: Optional[datetime] = None,
    ) -> tuple[ApiKey, str]:
        """
        Create a new API key.

        Returns: (ApiKey model, raw_key)
        The raw_key is only available at creation time — it cannot be retrieved later.
        """
        # Validate permissions
        if permissions:
            invalid = [p for p in permissions if p not in PERMISSION_SCOPES]
            if invalid:
                raise ValueError(f"Invalid permissions: {invalid}. Valid: {PERMISSION_SCOPES}")
        else:
            # Default: read-only across all resources
            permissions = [s for s in PERMISSION_SCOPES if s.endswith(":read")]

        raw_key, prefix, key_hash = _generate_key()

        api_key = ApiKey(
            name=name,
            key_prefix=prefix,
            key_hash=key_hash,
            client_id=client_id,
            created_by=created_by,
            permissions=permissions,
            rate_limit_tier=rate_limit_tier,
            expires_at=expires_at,
        )
        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)

        logger.info(f"API key created: name={name}, prefix={prefix}, client={client_id}")
        return api_key, raw_key

    async def validate_key(self, raw_key: str) -> Optional[dict]:
        """
        Validate an API key and return user-like dict.

        Returns None if the key is invalid, expired, or revoked.
        Updates last_used_at on successful validation.
        """
        if not raw_key or not raw_key.startswith("gk_"):
            return None

        key_hash = _hash_key(raw_key)

        result = await self.db.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash)
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            return None

        if not api_key.is_valid:
            logger.debug(f"API key {api_key.key_prefix}... is inactive or expired")
            return None

        # Update last_used_at
        api_key.last_used_at = datetime.now(timezone.utc)
        await self.db.commit()

        return {
            "id": f"apikey:{api_key.id}",
            "email": f"api-key-{api_key.key_prefix}@system",
            "role": "api_key",
            "client_id": str(api_key.client_id) if api_key.client_id else None,
            "first_name": "API",
            "last_name": api_key.name,
            "api_key_id": str(api_key.id),
            "permissions": api_key.permissions or [],
            "rate_limit_tier": api_key.rate_limit_tier,
        }

    async def list_keys(
        self,
        client_id: Optional[UUID] = None,
        include_revoked: bool = False,
    ) -> List[ApiKey]:
        """List API keys, optionally filtered by client."""
        q = select(ApiKey)
        if client_id:
            q = q.where(ApiKey.client_id == client_id)
        if not include_revoked:
            q = q.where(ApiKey.is_active == True)
        result = await self.db.execute(q.order_by(ApiKey.created_at.desc()))
        return list(result.scalars().all())

    async def revoke_key(self, key_id: UUID) -> bool:
        """Revoke an API key."""
        result = await self.db.execute(
            select(ApiKey).where(ApiKey.id == key_id)
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            return False

        api_key.is_active = False
        api_key.revoked_at = datetime.now(timezone.utc)
        await self.db.commit()

        logger.info(f"API key revoked: {api_key.key_prefix}... (name={api_key.name})")
        return True

    async def get_key(self, key_id: UUID) -> Optional[ApiKey]:
        """Get a single API key by ID."""
        result = await self.db.execute(
            select(ApiKey).where(ApiKey.id == key_id)
        )
        return result.scalar_one_or_none()
