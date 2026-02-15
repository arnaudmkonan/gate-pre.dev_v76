"""
GATE Platform — API Key Model.

Stores hashed API keys for third-party integrations and service-to-service calls.
Keys are prefixed with 'gk_' and the raw key is only shown once on creation.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class ApiKey(Base):
    """Client API key for programmatic access."""
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("client_users.id"), nullable=True)

    # Key identification
    name = Column(String(255), nullable=False)
    key_prefix = Column(String(12), nullable=False)  # First 8 chars for display: "gk_a1b2..."
    key_hash = Column(String(128), nullable=False, unique=True)  # SHA-256 hash

    # Permissions & rate limiting
    permissions = Column(JSON, nullable=True, default=list)  # ["entries:read", "entries:write", ...]
    rate_limit_tier = Column(String(50), default="starter")  # starter, professional, enterprise

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True)  # None = never expires
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def is_expired(self) -> bool:
        """Check if key has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if key is active and not expired."""
        return self.is_active and not self.is_expired
