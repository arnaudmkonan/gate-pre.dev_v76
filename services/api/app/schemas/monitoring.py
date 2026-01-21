"""Pydantic schemas for monitoring endpoints."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field


class ConnectivityStatus(BaseModel):
    """Connectivity status for storage, queue, and database."""

    storage: str = Field(default="unknown")  # ok, error
    queue: str = Field(default="unknown")
    database: str = Field(default="unknown")


class ErrorLog(BaseModel):
    """An individual error log entry."""

    timestamp: datetime
    message: str
    file_id: Optional[UUID] = None
    error_type: Optional[str] = None


class MonitoringStatusResponse(BaseModel):
    """Health status for a pipeline or worker."""

    id: UUID
    pipeline_id: Optional[UUID] = None
    worker_id: Optional[UUID] = None
    status: str  # healthy, degraded, failed
    last_checked_at: datetime
    connectivity_status: Optional[ConnectivityStatus] = None
    error_message: Optional[str] = None
    recent_errors: Optional[List[ErrorLog]] = None
    affected_file_ids: Optional[List[UUID]] = None
    created_at: datetime
    updated_at: datetime


class HealthCheckResult(BaseModel):
    """Result of a health check probe."""

    passed: bool
    component: str  # storage, queue, database
    message: str
    timestamp: datetime


class HealthCheckProbeRequest(BaseModel):
    """Request to run a health check probe."""

    components: Optional[List[str]] = Field(default=["storage", "queue", "database"])


class HealthCheckProbeResponse(BaseModel):
    """Response from health check probe."""

    overall_health: str  # healthy, degraded, failed
    results: List[HealthCheckResult]
    timestamp: datetime
