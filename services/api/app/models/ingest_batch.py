from enum import Enum
from sqlalchemy import Column, Index, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class IngestBatchStatus(str, Enum):
    """Ingestion batch status enum."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # some files succeeded, some failed


class IngestBatch(BaseModel):
    """Batch job for ingesting multiple files."""

    __tablename__ = "ingest_batches"

    batch_name = Column(String(500), nullable=False)
    status = Column(String(20), default=IngestBatchStatus.PENDING, nullable=False)
    file_count = Column(Integer, default=0, nullable=False)
    success_count = Column(Integer, default=0, nullable=False)
    failure_count = Column(Integer, default=0, nullable=False)
    created_by = Column(String(255), nullable=True)
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    max_concurrent_jobs = Column(Integer, default=5, nullable=False)
    batch_metadata = Column(JSON, nullable=True)  # custom batch metadata
    error_message = Column(String(500), nullable=True)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_ingest_batches_status", "status"),
        Index("idx_ingest_batches_created_at", "created_at"),
        Index("idx_ingest_batches_created_by", "created_by"),
        Index("idx_ingest_batches_scheduled_for", "scheduled_for"),
        Index("idx_ingest_batches_status_created_at", "status", "created_at"),
    )
