from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSON

from app.models.base import BaseModel


class FileSnapshot(BaseModel):
    """Immutable snapshot of raw file with content-addressed storage."""

    __tablename__ = "file_snapshot"

    file_id = Column(UUID(as_uuid=True), ForeignKey("upload_metadata.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=False)  # SHA-256 hex
    snapshot_path = Column(String(500), nullable=False)
    storage_size = Column(Integer, nullable=False)  # in bytes
    created_by = Column(String(255), nullable=True)  # uploader_id
    dedup_info = Column(JSON, nullable=True)  # dedup info, etc.

    __table_args__ = (
        Index("idx_file_snapshot_file_id", "file_id"),
        Index("idx_file_snapshot_content_hash", "content_hash"),
        Index("idx_file_snapshot_created_at", "created_at"),
    )
