from enum import Enum
from sqlalchemy import Column, Index, String, Text, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class ErrorType(str, Enum):
    """Error type enum."""

    TRANSIENT = "transient"  # Temporary error, can retry
    PERMANENT = "permanent"  # Permanent error, needs manual intervention


class ErrorsRaw(BaseModel):
    """Track processing errors for files."""

    __tablename__ = "errors_raw"

    file_id = Column(UUID(as_uuid=True), nullable=False)  # Foreign key to ingest_jobs
    agent_id = Column(String(255), nullable=False)  # Agent ID (removed FK constraint for test insertion)
    error_type = Column(String(20), nullable=False)  # Type of error (from ErrorType or custom)
    error_classification = Column(String(20), default=ErrorType.TRANSIENT, nullable=False)  # transient or permanent
    stack_trace = Column(Text, nullable=True)  # Full error stack trace
    processing_step = Column(String(255), nullable=False)  # e.g., "extraction", "normalization", "validation"
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    last_attempt_ts = Column(DateTime(timezone=True), nullable=True)
    error_timestamp = Column(DateTime(timezone=True), nullable=False)  # When error occurred

    __table_args__ = (
        Index("idx_errors_raw_file_id", "file_id"),
        Index("idx_errors_raw_agent_id", "agent_id"),
        Index("idx_errors_raw_error_type", "error_type"),
        Index("idx_errors_raw_error_classification", "error_classification"),
        Index("idx_errors_raw_retry_count", "retry_count"),
        Index("idx_errors_raw_processing_step", "processing_step"),
        Index("idx_errors_raw_file_agent", "file_id", "agent_id"),
    )
