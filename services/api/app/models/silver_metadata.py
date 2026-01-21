from sqlalchemy import Column, Index, String, DateTime, ForeignKey, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class SilverMetadata(BaseModel):
    """Normalized metadata for processed documents."""

    __tablename__ = "silver_metadata"

    file_id = Column(UUID(as_uuid=True), ForeignKey("raw_files.id"), nullable=False)
    title = Column(String(1000), nullable=True)
    author = Column(String(500), nullable=True)
    date = Column(DateTime(timezone=True), nullable=True)
    document_type = Column(String(100), nullable=True)
    metadata_json = Column(JSON, nullable=True)  # Custom metadata and normalized values
    mapping_version = Column(String(50), nullable=True)  # Version of transformation
    # Metadata service fields
    content_hash = Column(String(256), nullable=True)
    normalized_tags = Column(JSON, nullable=True, default=[])
    status = Column(String(50), nullable=True, default="success")  # success or quarantined
    quarantine_reason = Column(String, nullable=True)
    mapping_summary = Column(String, nullable=True)
    language = Column(String(10), nullable=True)  # e.g., 'en', 'fr', 'de'
    page_count = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_silver_metadata_file_id", "file_id"),
        Index("idx_silver_metadata_document_type", "document_type"),
        Index("idx_silver_metadata_created_at", "created_at"),
        Index("idx_silver_metadata_date", "date"),
        Index("idx_silver_metadata_status", "status"),
        Index("idx_silver_metadata_language", "language"),
    )
