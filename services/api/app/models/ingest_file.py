from enum import Enum
from sqlalchemy import Column, Index, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class IngestFileStatus(str, Enum):
    """Ingestion file status enum."""

    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"


class IngestFile(BaseModel):
    """Track individual file ingestion within a batch."""

    __tablename__ = "ingest_files"

    batch_id = Column(UUID(as_uuid=True), ForeignKey("ingest_batches.id"), nullable=False)
    file_id = Column(UUID(as_uuid=True), ForeignKey("raw_files.id"), nullable=False)
    file_type = Column(String(50), nullable=False)  # txt, pdf, docx, xlsx, etc.
    status = Column(String(20), default=IngestFileStatus.QUEUED, nullable=False)
    routing_decision = Column(String(255), nullable=True)  # agent type that will process this file
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    last_error = Column(Text, nullable=True)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    celery_task_id = Column(String(255), nullable=True)  # for tracking Celery task

    __table_args__ = (
        Index("idx_ingest_files_batch_id", "batch_id"),
        Index("idx_ingest_files_file_id", "file_id"),
        Index("idx_ingest_files_status", "status"),
        Index("idx_ingest_files_file_type", "file_type"),
        Index("idx_ingest_files_batch_id_status", "batch_id", "status"),
    )
