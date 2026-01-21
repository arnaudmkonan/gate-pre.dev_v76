from enum import Enum
from sqlalchemy import Column, Index, Integer, String, Text, DateTime, JSON, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class RawFileStatus(str, Enum):
    """Raw file status enum."""

    PENDING = "pending"
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    STORED = "stored"
    FAILED = "failed"
    ERROR = "error"


class RawFile(BaseModel):
    """Raw file model for uploaded documents."""

    __tablename__ = "raw_files"

    filename = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)  # txt, docx, xlsx, pptx, html, md, json, csv, yml, xml
    file_size = Column(Integer, nullable=False)  # in bytes
    storage_path = Column(String(500), nullable=False)  # path in Supabase Storage
    mime_type = Column(String(100), nullable=True)  # MIME type of file
    status = Column(String(20), default=RawFileStatus.PENDING, nullable=False)
    stored_at = Column(DateTime(timezone=True), nullable=True)
    uploader_id = Column(String(255), nullable=True)
    source = Column(String(255), nullable=True)
    customer_id = Column(String(255), nullable=True)
    tags = Column(JSON, nullable=True)  # tags as JSON array
    checksum = Column(String(256), nullable=True)  # SHA-256 checksum
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    # Batch processing fields
    batch_id = Column(UUID(as_uuid=True), ForeignKey("ingest_batches.id"), nullable=True)
    chunk_index = Column(Integer, nullable=True)  # for chunked files: 0-based index
    total_chunks = Column(Integer, nullable=True)  # total number of chunks for this file
    assembly_metadata = Column(JSON, nullable=True)  # metadata for reassembling chunked files

    __table_args__ = (
        Index("idx_raw_files_status", "status"),
        Index("idx_raw_files_customer_id", "customer_id"),
        Index("idx_raw_files_created_at", "created_at"),
        Index("idx_raw_files_batch_id", "batch_id"),
        Index("idx_raw_files_status_customer_id", "status", "customer_id"),
    )
