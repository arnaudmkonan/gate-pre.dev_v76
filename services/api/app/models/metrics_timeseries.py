"""Metrics timeseries model for historical data."""

from sqlalchemy import Column, String, Integer, Numeric, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class MetricsTimeseries(BaseModel):
    """1-minute granularity metrics for historical analysis and trending."""

    __tablename__ = "metrics_timeseries"

    pipeline_id = Column(UUID(as_uuid=True), nullable=True)
    worker_id = Column(UUID(as_uuid=True), nullable=True)
    file_type = Column(String(50), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    throughput = Column(Integer, nullable=True)  # items/minute
    latency_p50 = Column(Integer, nullable=True)  # milliseconds
    latency_p95 = Column(Integer, nullable=True)
    latency_p99 = Column(Integer, nullable=True)
    error_rate = Column(Numeric(5, 2), nullable=True)  # percentage 0-100
    dlq_count = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_metrics_timeseries_pipeline_id", "pipeline_id"),
        Index("idx_metrics_timeseries_worker_id", "worker_id"),
        Index("idx_metrics_timeseries_timestamp", "timestamp"),
        Index("idx_metrics_timeseries_file_type", "file_type"),
    )
