"""Raw metadata model for tracking raw file metadata and deduplication."""
from sqlalchemy import Column, Index, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class RawMetadata(BaseModel):
    """Model for tracking raw file metadata (filename, size, checksum, storage location, etc.)."""

    __tablename__ = "raw_metadata"

    filename = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # in bytes
    checksum = Column(String(256), nullable=False, unique=True)  # SHA-256 checksum
    storage_location = Column(String(500), nullable=False)  # path in Supabase Storage
    uploader_id = Column(String(255), nullable=True)
    file_type = Column(String(50), nullable=True)

    __table_args__ = (
        Index("idx_raw_metadata_checksum", "checksum"),
        Index("idx_raw_metadata_uploader_id", "uploader_id"),
        Index("idx_raw_metadata_file_type", "file_type"),
        Index("idx_raw_metadata_created_at", "created_at"),
        Index("idx_raw_metadata_checksum_uploader", "checksum", "uploader_id"),
    )
