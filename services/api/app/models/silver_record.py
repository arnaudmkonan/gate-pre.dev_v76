from sqlalchemy import Column, Index, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class SilverRecord(BaseModel):
    """Normalized/silver schema record for processed documents."""

    __tablename__ = "silver_records"

    file_id = Column(UUID(as_uuid=True), ForeignKey("raw_files.id"), nullable=False)
    canonical_id = Column(String(500), nullable=True, unique=True)  # unique identifier for deduplication
    batch_id = Column(UUID(as_uuid=True), nullable=True)  # batch this record was upserted in
    raw_record_hash = Column(String(64), nullable=True)  # SHA256 hash of raw content for deduplication
    raw_content = Column(JSON, nullable=True)  # original raw extracted content
    title = Column(String(1000), nullable=True)
    author = Column(String(500), nullable=True)
    extraction_date = Column(DateTime(timezone=True), nullable=True)  # when document was created/modified
    document_date = Column(DateTime(timezone=True), nullable=True)  # document's own date field
    file_type = Column(String(50), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    language = Column(String(20), nullable=True)  # detected language code
    content = Column(Text, nullable=True)  # normalized/cleaned content
    record_metadata = Column(JSON, nullable=True)  # source_id, checksum, processing_steps, facets
    vector_store_id = Column(String(500), nullable=True)  # reference to vector store embedding
    processing_status = Column(String(20), default="pending", nullable=False)
    processing_error = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_silver_records_file_id", "file_id"),
        Index("idx_silver_records_canonical_id", "canonical_id"),
        Index("idx_silver_records_batch_id", "batch_id"),
        Index("idx_silver_records_raw_record_hash", "raw_record_hash"),
        Index("idx_silver_records_file_type", "file_type"),
        Index("idx_silver_records_language", "language"),
        Index("idx_silver_records_created_at", "created_at"),
        Index("idx_silver_records_processing_status", "processing_status"),
        Index("idx_silver_records_batch_hash", "batch_id", "raw_record_hash"),
    )
