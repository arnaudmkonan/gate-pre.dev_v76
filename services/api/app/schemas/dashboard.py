from typing import List, Dict, Optional
from pydantic import BaseModel


class PipelineStatusResponse(BaseModel):
    """Pipeline status response."""

    status: str  # idle, running, paused, error
    active_jobs: int
    completed_jobs: int
    failed_jobs: int


class QueueLengthResponse(BaseModel):
    """Queue length response."""

    pending: int
    running: int
    failed: int
    total: int


class ErrorSummary(BaseModel):
    """Error summary item."""

    id: str
    error_type: str
    message: str
    timestamp: str
    file_id: Optional[str]


class RecentErrorsResponse(BaseModel):
    """Recent errors response."""

    errors: List[ErrorSummary]
    total_errors_24h: int


class ThroughputMetric(BaseModel):
    """Throughput metric point."""

    timestamp: str
    files_processed: int


class ThroughputResponse(BaseModel):
    """Throughput metrics response."""

    metrics: List[ThroughputMetric]
    average_files_per_hour: float


class DashboardDataResponse(BaseModel):
    """Complete dashboard data response."""

    pipeline_status: PipelineStatusResponse
    queue_length: QueueLengthResponse
    recent_errors: RecentErrorsResponse
    throughput: ThroughputResponse
    timestamp: str
