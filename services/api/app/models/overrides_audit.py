from sqlalchemy import Column, Index, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class OverridesAudit(BaseModel):
    """Audit trail for admin file routing overrides."""

    __tablename__ = "overrides_audit"

    admin_id = Column(String(255), nullable=False)  # User ID of admin
    file_id = Column(UUID(as_uuid=True), nullable=False)  # File being overridden
    prev_agent_id = Column(String(255), ForeignKey("agent_registry.agent_id"), nullable=True)  # Previous agent
    new_agent_id = Column(String(255), ForeignKey("agent_registry.agent_id"), nullable=False)  # New agent
    reason = Column(Text, nullable=True)  # Admin reason for override
    prev_routing_decision = Column(String(255), nullable=True)  # Previous routing decision (e.g., "extension")
    decision_confidence = Column(Float, nullable=True)  # Confidence score of original decision

    __table_args__ = (
        Index("idx_overrides_audit_admin_id", "admin_id"),
        Index("idx_overrides_audit_file_id", "file_id"),
        Index("idx_overrides_audit_prev_agent_id", "prev_agent_id"),
        Index("idx_overrides_audit_new_agent_id", "new_agent_id"),
        Index("idx_overrides_audit_created_at", "created_at"),
    )
