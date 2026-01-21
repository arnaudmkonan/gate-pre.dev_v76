from datetime import datetime
from enum import Enum
from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSON

from app.models.base import BaseModel


class ResourceType(str, Enum):
    """Resource type enum for audit logging."""

    FILE = "file"
    VERSION = "version"
    UPLOAD = "upload"


class AuditAction(str, Enum):
    """Audit action enum."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    DOWNLOAD = "download"


class AuditLog(BaseModel):
    """Immutable audit log for compliance and traceability."""

    __tablename__ = "audit_log"

    resource_type = Column(String(50), nullable=False)  # file, version, upload
    resource_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(50), nullable=False)  # create, update, delete, download
    actor_id = Column(String(255), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    changes = Column(JSON, nullable=True)  # what changed
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_audit_log_resource_id", "resource_id"),
        Index("idx_audit_log_action", "action"),
        Index("idx_audit_log_actor_id", "actor_id"),
        Index("idx_audit_log_timestamp", "timestamp"),
        Index("idx_audit_log_resource_id_action_timestamp", "resource_id", "action", "timestamp"),
    )
