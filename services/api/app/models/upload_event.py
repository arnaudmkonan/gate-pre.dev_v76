"""Upload events model for tracking deduplication and upload history."""
from enum import Enum
from sqlalchemy import Column, Index, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class UploadEventType(str, Enum):
    """Upload event type enum."""

    NEW = "new"
    DUPLICATE = "duplicate"


class UploadEvent(BaseModel):
    """Model for tracking upload events linked to raw metadata."""

    __tablename__ = "upload_events"

    raw_metadata_id = Column(UUID(as_uuid=True), ForeignKey("raw_metadata.id", ondelete="CASCADE"), nullable=False)
    upload_timestamp = Column(DateTime(timezone=True), nullable=False)
    event_type = Column(String(50), nullable=False)  # new, duplicate
    user_id = Column(String(255), nullable=True)

    __table_args__ = (
        Index("idx_upload_events_raw_metadata_id", "raw_metadata_id"),
        Index("idx_upload_events_event_type", "event_type"),
        Index("idx_upload_events_upload_timestamp", "upload_timestamp"),
    )
