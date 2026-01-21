from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSON

from app.models.base import BaseModel


class DeadLetterQueue(BaseModel):
    """Dead letter queue for failed jobs."""

    __tablename__ = "dead_letter_queue"

    job_log_id = Column(UUID(as_uuid=True), ForeignKey("job_log.id"), nullable=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("ingest_jobs.id"), nullable=True)
    original_filename = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=False)
    last_error_traceback = Column(Text, nullable=True)
    final_exception = Column(String(500), nullable=True)
    retry_history = Column(JSON, nullable=True)  # List of retry attempts
    failure_count = Column(Integer, default=1, nullable=False)
    manual_notes = Column(Text, nullable=True)
    status = Column(String(50), default="pending_review", nullable=False)  # pending_review, archived
    marked_resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_dlq_job_log_id", "job_log_id"),
        Index("idx_dlq_job_id", "job_id"),
        Index("idx_dlq_status", "status"),
        Index("idx_dlq_created_at", "created_at"),
    )
