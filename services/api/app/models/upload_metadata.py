from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class UploadStatus(str, Enum):
    """Upload status enum."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadMetadata(BaseModel):
    """Upload metadata model (raw table)."""

    __tablename__ = "upload_metadata"

    filename = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # in bytes
    mime_type = Column(String(100), nullable=False)
    checksum = Column(String(64), nullable=False)  # SHA-256 hex
    storage_path = Column(String(500), nullable=False)
    storage_config_id = Column(UUID(as_uuid=True), ForeignKey("storage_config.id"), nullable=False)
    upload_status = Column(String(20), default=UploadStatus.PENDING, nullable=False)
    error_message = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_upload_metadata_storage_config_id", "storage_config_id"),
        Index("idx_upload_metadata_upload_status", "upload_status"),
        Index("idx_upload_metadata_created_at", "created_at"),
    )
