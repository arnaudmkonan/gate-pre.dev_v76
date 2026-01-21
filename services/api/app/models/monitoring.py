"""Monitoring and health check models."""

from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSON

from app.models.base import BaseModel


class MonitoringMetrics(BaseModel):
    """Real-time health status of pipelines and workers."""

    __tablename__ = "monitoring_metrics"

    pipeline_id = Column(UUID(as_uuid=True), nullable=True)
    worker_id = Column(UUID(as_uuid=True), nullable=True)
    status = Column(String(50), nullable=False, default="unknown")  # healthy, degraded, failed
    last_checked_at = Column(DateTime(timezone=True), nullable=False)
    connectivity_status = Column(JSON, nullable=True)  # {storage: ok/error, queue: ok/error, database: ok/error}
    error_message = Column(String(1000), nullable=True)
    recent_errors = Column(JSON, nullable=True)  # Array of error logs
    affected_file_ids = Column(JSON, nullable=True)  # Array of file IDs

    __table_args__ = (
        Index("idx_monitoring_metrics_pipeline_id", "pipeline_id"),
        Index("idx_monitoring_metrics_worker_id", "worker_id"),
        Index("idx_monitoring_metrics_status", "status"),
        Index("idx_monitoring_metrics_last_checked", "last_checked_at"),
    )
