"""Quarantine model for tracking documents that failed validation."""
from sqlalchemy import Column, Index, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class Quarantine(BaseModel):
    """Model for quarantining documents that fail validation rules during mapping."""

    __tablename__ = "quarantine"

    file_id = Column(UUID(as_uuid=True), ForeignKey("raw_files.id", ondelete="CASCADE"), nullable=False)
    original_data = Column(JSON, nullable=False)  # Original extracted data
    validation_errors = Column(JSON, nullable=False)  # Array of {field, reason, type}
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String(255), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_quarantine_file_id", "file_id"),
        Index("idx_quarantine_created_at", "created_at"),
        Index("idx_quarantine_reviewed_at", "reviewed_at"),
    )
