from sqlalchemy import Column, Index, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class DLQEntry(BaseModel):
    """Dead-letter queue entry for failed batch items."""

    __tablename__ = "dlq_entries"

    batch_id = Column(UUID(as_uuid=True), ForeignKey("batches.id"), nullable=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("raw_files.id"), nullable=False)
    error_reason = Column(Text, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)

    __table_args__ = (
        Index("idx_dlq_entries_batch_id", "batch_id"),
        Index("idx_dlq_entries_file_id", "file_id"),
        Index("idx_dlq_entries_created_at", "created_at"),
    )
