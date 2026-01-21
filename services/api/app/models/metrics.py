from sqlalchemy import Column, String, Float, Index, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSON

from app.models.base import BaseModel


class Metrics(BaseModel):
    """Metrics model for admin dashboard."""

    __tablename__ = "metrics"

    metric_type = Column(String(100), nullable=False)  # pipeline_status, queue_length, throughput, etc.
    value = Column(Float, nullable=False)
    tags = Column(JSON, nullable=True)  # Additional context tags
    metadata = Column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_metrics_type", "metric_type"),
        Index("idx_metrics_created_at", "created_at"),
        Index("idx_metrics_type_created", "metric_type", "created_at"),
    )
