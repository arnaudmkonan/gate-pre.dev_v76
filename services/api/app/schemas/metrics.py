"""Pydantic schemas for metrics endpoints."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, Field


class MetricsIngestRequest(BaseModel):
    """Request to ingest metrics data."""

    pipeline_id: Optional[UUID] = None
    worker_id: Optional[UUID] = None
    file_type: Optional[str] = None
    timestamp: datetime
    throughput: Optional[int] = None
    latency_p50: Optional[int] = None
    latency_p95: Optional[int] = None
    latency_p99: Optional[int] = None
    error_rate: Optional[Decimal] = None
    dlq_count: Optional[int] = None


class MetricsResponse(BaseModel):
    """Response for metrics data point."""

    id: UUID
    pipeline_id: Optional[UUID] = None
    worker_id: Optional[UUID] = None
    file_type: Optional[str] = None
    timestamp: datetime
    throughput: Optional[int] = None
    latency_p50: Optional[int] = None
    latency_p95: Optional[int] = None
    latency_p99: Optional[int] = None
    error_rate: Optional[Decimal] = None
    dlq_count: Optional[int] = None
    created_at: datetime


class TimeRange(BaseModel):
    """Time range specification."""

    value: int  # 1, 24, 7, 30
    unit: str  # h, d (hours, days)


class MetricsQueryRequest(BaseModel):
    """Request to query metrics."""

    pipeline_id: Optional[UUID] = None
    worker_id: Optional[UUID] = None
    file_type: Optional[str] = None
    time_range: str = "24h"  # 1h, 24h, 7d, 30d
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class MetricsQueryResponse(BaseModel):
    """Response from metrics query."""

    metrics: List[MetricsResponse]
    count: int
    time_range: str
    query_timestamp: datetime


class AnomalyDetectionConfig(BaseModel):
    """Configuration for anomaly detection."""

    enabled: bool = True
    baseline_window_days: int = 7
    deviation_threshold_percent: float = 20.0  # Alert if deviation > 20%
    min_data_points: int = 5


class AnomalyResponse(BaseModel):
    """Response for detected anomaly."""

    metric_type: str
    current_value: float
    baseline_value: float
    deviation_percent: float
    severity: str  # low, medium, high
    timestamp: datetime
