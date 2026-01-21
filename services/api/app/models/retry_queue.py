from enum import Enum
from sqlalchemy import Column, Index, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class RetryQueueStatus(str, Enum):
    """Retry queue status enum."""

    PENDING_REVIEW = "pending_review"
    PROCESSING = "processing"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class RetryQueue(BaseModel):
    """Queue for failed mapping and processing records."""

    __tablename__ = "retry_queue"

    file_id = Column(UUID(as_uuid=True), ForeignKey("raw_files.id"), nullable=False)
    error_type = Column(String(100), nullable=False)  # mapping_error, embedding_error, etc.
    error_message = Column(Text, nullable=False)
    processing_attempt = Column(Integer, default=1, nullable=False)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)
    manual_notes = Column(Text, nullable=True)
    status = Column(String(20), default=RetryQueueStatus.PENDING_REVIEW, nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_retry_queue_file_id", "file_id"),
        Index("idx_retry_queue_status", "status"),
        Index("idx_retry_queue_created_at", "created_at"),
        Index("idx_retry_queue_error_type", "error_type"),
        Index("idx_retry_queue_status_created_at", "status", "created_at"),
    )
