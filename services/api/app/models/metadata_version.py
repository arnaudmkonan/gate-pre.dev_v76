"""Metadata model with versioning support."""

from enum import Enum
from sqlalchemy import Column, Index, String, Text, DateTime, JSON, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.models.base import BaseModel


class MetadataStatus(str, Enum):
    """Metadata status enum."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class DocumentMetadataVersion(BaseModel):
    """Versioned document metadata with lineage tracking."""

    __tablename__ = "document_metadata_versions"

    file_id = Column(UUID(as_uuid=True), ForeignKey("raw_files.id"), nullable=False)
    version = Column(Integer, nullable=False, default=1)  # Version number
    status = Column(String(20), nullable=False, default=MetadataStatus.ACTIVE)  # active, superseded, failed

    # Core metadata fields
    title = Column(String(500), nullable=True)
    author = Column(String(255), nullable=True)
    created_at_doc = Column(DateTime(timezone=True), nullable=True)  # Document creation date (ISO 8601)
    modified_at_doc = Column(DateTime(timezone=True), nullable=True)  # Document modification date (ISO 8601)
    language = Column(String(10), nullable=True)  # ISO 639-1 language code
    file_type = Column(String(50), nullable=False)

    # Entity extraction
    entities = Column(JSON, nullable=True)  # Array of {name, type, confidence}
    low_confidence_entities = Column(JSON, nullable=True)  # Entities with confidence < 0.5

    # File integrity
    checksum = Column(String(256), nullable=True)  # SHA-256 checksum
    file_size_bytes = Column(Integer, nullable=True)

    # Audit trail
    extraction_timestamp = Column(DateTime(timezone=True), nullable=True)
    metadata_generated_at = Column(DateTime(timezone=True), nullable=True)
    audit_flag = Column(String(100), nullable=True)  # Flag for manual review if needed
    audit_notes = Column(Text, nullable=True)

    # Lineage
    lineage = Column(JSON, nullable=True)  # raw_file_id, extraction_id, etc.

    __table_args__ = (
        Index("idx_metadata_versions_file_id", "file_id"),
        Index("idx_metadata_versions_file_id_version", "file_id", "version"),
        Index("idx_metadata_versions_status", "status"),
        Index("idx_metadata_versions_created_at", "created_at"),
        Index("idx_metadata_versions_language", "language"),
    )
