from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class FileVersion(BaseModel):
    """File version record with snapshot reference and deduplication info."""

    __tablename__ = "file_version"

    upload_metadata_id = Column(UUID(as_uuid=True), ForeignKey("upload_metadata.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey("file_snapshot.id"), nullable=False)
    file_hash = Column(String(64), nullable=False)  # SHA-256 hex
    is_deduplicated = Column(Boolean, default=False, nullable=False)
    storage_path = Column(String(500), nullable=False)
    content_hash_id = Column(String(64), nullable=True)  # for dedup lookup

    __table_args__ = (
        Index("idx_file_version_upload_metadata_id", "upload_metadata_id"),
        Index("idx_file_version_snapshot_id", "snapshot_id"),
        Index("idx_file_version_file_hash", "file_hash"),
        Index("idx_file_version_created_at", "created_at"),
    )
