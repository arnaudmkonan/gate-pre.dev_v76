from enum import Enum
from sqlalchemy import Column, Index, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class RoutingStatus(str, Enum):
    """Routing status enum."""

    PENDING = "pending"
    ROUTED = "routed"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class RoutingMethod(str, Enum):
    """Routing decision method."""

    EXTENSION = "extension"
    MIME_TYPE = "mime_type"
    CONTENT_SNIFFER = "content_sniffer"
    FALLBACK = "fallback"


class RoutingDecision(BaseModel):
    """Track per-file routing decisions and audit trail."""

    __tablename__ = "routing_decisions"

    file_id = Column(UUID(as_uuid=True), ForeignKey("raw_files.id"), nullable=False)
    detected_type = Column(String(50), nullable=False)  # txt, pdf, docx, xlsx, etc.
    chosen_agent = Column(String(255), nullable=False)  # agent ID or name
    routing_method = Column(String(50), nullable=False)  # extension, mime_type, content_sniffer, fallback
    confidence = Column(Float, nullable=False)  # 0.0 to 1.0
    reason = Column(Text, nullable=False)  # explanation of routing decision
    status = Column(String(20), default=RoutingStatus.PENDING, nullable=False)  # pending, routed, unsupported, failed
    routed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)  # error details if status is failed or unsupported

    __table_args__ = (
        Index("idx_routing_decisions_file_id", "file_id"),
        Index("idx_routing_decisions_status", "status"),
        Index("idx_routing_decisions_created_at", "created_at"),
        Index("idx_routing_decisions_detected_type", "detected_type"),
        Index("idx_routing_decisions_chosen_agent", "chosen_agent"),
    )
