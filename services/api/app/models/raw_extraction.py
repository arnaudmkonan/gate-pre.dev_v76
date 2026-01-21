from enum import Enum
from sqlalchemy import Column, Index, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class ExtractionStatus(str, Enum):
    """Extraction status enum."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    PARTIAL = "partial"  # Successfully extracted but with errors/missing sections
    FAILED = "failed"


class RawExtraction(BaseModel):
    """Store raw extracted content before normalization."""

    __tablename__ = "raw_extractions"

    file_id = Column(UUID(as_uuid=True), ForeignKey("raw_files.id"), nullable=False)
    extractor_version = Column(String(50), nullable=False)  # version of extractor used
    extraction_timestamp = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default=ExtractionStatus.PENDING, nullable=False)

    # Raw extracted content
    raw_content = Column(JSON, nullable=True)  # {"text": "...", "tables": [...], "metadata": {...}}
    extracted_text = Column(Text, nullable=True)  # full extracted text
    extracted_tables = Column(JSON, nullable=True)  # array of table structures
    extracted_metadata = Column(JSON, nullable=True)  # metadata from extraction
    embedded_objects = Column(JSON, nullable=True)  # references to images, embedded files, etc.

    # Error handling
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)  # structured error info

    # Lineage
    lineage = Column(JSON, nullable=True)  # {"raw_id": "...", "silver_id": "...", "vector_ids": [...]}

    __table_args__ = (
        Index("idx_raw_extractions_file_id", "file_id"),
        Index("idx_raw_extractions_status", "status"),
        Index("idx_raw_extractions_created_at", "created_at"),
        Index("idx_raw_extractions_extractor_version", "extractor_version"),
    )
