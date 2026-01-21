from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class JobStatus(str, Enum):
    """Job status enum."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRIED = "retried"


class JobType(str, Enum):
    """Job type enum."""

    EXTRACTION = "extraction"
    VECTORIZATION = "vectorization"
    METADATA = "metadata"


class JobLog(BaseModel):
    """Job execution log model."""

    __tablename__ = "job_log"

    job_id = Column(String(255), nullable=False, unique=True)
    upload_metadata_id = Column(UUID(as_uuid=True), ForeignKey("upload_metadata.id"), nullable=False)
    job_type = Column(String(50), default=JobType.EXTRACTION, nullable=False)
    status = Column(String(20), default=JobStatus.PENDING, nullable=False)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    attempts = Column(Integer, default=1, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_job_log_job_id", "job_id"),
        Index("idx_job_log_upload_metadata_id", "upload_metadata_id"),
        Index("idx_job_log_status", "status"),
        Index("idx_job_log_created_at", "created_at"),
    )
