from datetime import datetime
from enum import Enum
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSON

from app.models.base import BaseModel


class QueueJobPriority(str, Enum):
    """Job priority enum."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class QueueJobStatus(str, Enum):
    """Queue job status enum."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class QueueJob(BaseModel):
    """Persistent queue job for ingestion pipeline."""

    __tablename__ = "queue_job"

    file_id = Column(UUID(as_uuid=True), ForeignKey("upload_metadata.id"), nullable=False)
    uploader_id = Column(String(255), nullable=True)
    file_type = Column(String(20), nullable=False)  # txt, docx, xlsx, etc.
    file_size = Column(Integer, nullable=False)  # in bytes
    priority = Column(String(20), default=QueueJobPriority.NORMAL, nullable=False)
    status = Column(String(20), default=QueueJobStatus.QUEUED, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    last_error = Column(Text, nullable=True)
    last_attempted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_queue_job_file_id", "file_id"),
        Index("idx_queue_job_priority", "priority"),
        Index("idx_queue_job_status", "status"),
        Index("idx_queue_job_created_at", "created_at"),
        Index("idx_queue_job_priority_created_at", "priority", "created_at"),
    )
