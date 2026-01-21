"""Retry policy model for per-pipeline configuration."""

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class RetryPolicy(BaseModel):
    """Per-pipeline retry configuration with exponential backoff options."""

    __tablename__ = "retry_policies"

    pipeline_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    policy_type = Column(String(50), nullable=False, default="exponential")  # exponential, fixed, linear, none
    max_attempts = Column(Integer, nullable=False, default=3)
    base_delay_ms = Column(Integer, nullable=False, default=1000)
    max_delay_ms = Column(Integer, nullable=False, default=60000)
    jitter = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("idx_retry_policies_pipeline_id", "pipeline_id"),
        UniqueConstraint("pipeline_id", name="uq_retry_policies_pipeline_id"),
    )
