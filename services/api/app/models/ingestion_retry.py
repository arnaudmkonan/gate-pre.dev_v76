from enum import Enum
from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class ErrorClassification(str, Enum):
    """Error classification for retry logic."""

    TRANSIENT = "transient"  # Will be retried
    PERMANENT = "permanent"  # Will move to DLQ


class IngestionRetry(BaseModel):
    """Retry tracking for failed ingestion jobs."""

    __tablename__ = "ingestion_retries"

    job_id = Column(UUID(as_uuid=True), ForeignKey("ingest_jobs.id"), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    error_message = Column(Text, nullable=False)
    error_classification = Column(String(20), nullable=False)  # transient or permanent
    retry_delay = Column(Integer, nullable=False)  # seconds until next retry
    next_retry_at = Column(DateTime(timezone=True), nullable=False)
    retry_jitter = Column(Integer, default=0, nullable=False)  # jitter applied in seconds

    __table_args__ = (
        Index("idx_ingestion_retries_job_id", "job_id"),
        Index("idx_ingestion_retries_next_retry_at", "next_retry_at"),
        Index("idx_ingestion_retries_classification", "error_classification"),
    )
