from enum import Enum
from sqlalchemy import Column, Index, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class IngestJobStatus(str, Enum):
    """Ingestion job status enum."""

    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestMode(str, Enum):
    """Ingestion mode enum."""

    QUICK_AUTO = "quick_auto"
    GUIDED_MAPPING = "guided_mapping"
    ADVANCED_BATCH = "advanced_batch"


class IngestJob(BaseModel):
    """Ingestion job for document processing."""

    __tablename__ = "ingest_jobs"

    filename = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)  # txt, md, pdf, docx, xlsx, etc.
    size = Column(Integer, nullable=False)  # in bytes
    uploader_id = Column(String(255), nullable=True)
    status = Column(String(20), default=IngestJobStatus.PENDING, nullable=False)
    storage_path = Column(String(500), nullable=True)  # path in Supabase Storage
    extracted_metadata = Column(JSON, nullable=True)  # extracted metadata (title, mime_type, page_count, etc.)
    error_message = Column(Text, nullable=True)  # last error if failed
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    last_attempted_at = Column(DateTime(timezone=True), nullable=True)
    priority = Column(String(20), default="normal", nullable=False)  # low, normal, high

    # Ingestion mode and settings
    mode = Column(String(50), default=IngestMode.QUICK_AUTO, nullable=True)  # quick_auto, guided_mapping, advanced_batch
    batch_size = Column(Integer, default=10, nullable=True)  # for advanced_batch mode
    schedule_time = Column(DateTime(timezone=True), nullable=True)  # for scheduled processing
    mapping_config = Column(JSON, nullable=True)  # mapping configuration for guided_mapping mode
    progress_percentage = Column(Integer, default=0, nullable=False)  # current progress (0-100)

    __table_args__ = (
        Index("idx_ingest_jobs_status", "status"),
        Index("idx_ingest_jobs_created_at", "created_at"),
        Index("idx_ingest_jobs_uploader_id", "uploader_id"),
        Index("idx_ingest_jobs_status_created_at", "status", "created_at"),
        Index("idx_ingest_jobs_file_type", "file_type"),
        Index("idx_ingest_jobs_mode", "mode"),
    )
