"""Model for tracking retry job attempts."""
from enum import Enum
from sqlalchemy import Column, Index, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class RetryJobStatus(str, Enum):
    """Retry job status enum."""

    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RetryJob(BaseModel):
    """Model for tracking retry attempts of failed ingestion jobs."""

    __tablename__ = "retry_jobs"

    original_job_id = Column(UUID(as_uuid=True), ForeignKey("ingest_jobs.id", ondelete="CASCADE"), nullable=False)
    retry_count = Column(Integer, default=1, nullable=False)
    status = Column(String(20), default=RetryJobStatus.PENDING, nullable=False)
    error_reason = Column(Text, nullable=True)  # reason for original failure
    mode_override = Column(String(50), nullable=True)  # optional mode override for retry
    mapping_override = Column(String(500), nullable=True)  # optional mapping override
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # soft delete support

    __table_args__ = (
        Index("idx_retry_jobs_original_job_id", "original_job_id"),
        Index("idx_retry_jobs_status", "status"),
        Index("idx_retry_jobs_created_at", "created_at"),
    )
