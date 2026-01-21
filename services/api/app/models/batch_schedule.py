from sqlalchemy import Column, DateTime, Index, Integer, String, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class BatchSchedule(BaseModel):
    """Batch schedule configuration for ingestion jobs."""

    __tablename__ = "batch_schedules"

    schedule_name = Column(String(255), nullable=False, unique=True)
    cron_expression = Column(String(255), nullable=False)  # e.g., "0 * * * *" for hourly
    interval_seconds = Column(Integer, nullable=True)  # alternative to cron, if specified
    max_concurrency = Column(Integer, default=5, nullable=False)  # max jobs to process in parallel
    batch_size = Column(Integer, default=10, nullable=False)  # jobs per batch
    is_active = Column(Boolean, default=True, nullable=False)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    description = Column(String(500), nullable=True)

    __table_args__ = (
        Index("idx_batch_schedules_is_active", "is_active"),
        Index("idx_batch_schedules_next_run_at", "next_run_at"),
        Index("idx_batch_schedules_schedule_name", "schedule_name"),
    )
