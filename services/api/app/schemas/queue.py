from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CeleryConfigCreate(BaseModel):
    """Create Celery config request."""

    redis_host: str = Field(..., description="Redis host")
    redis_port: int = Field(default=6379, ge=1, le=65535)
    redis_password: Optional[str] = None
    worker_concurrency: int = Field(default=4, ge=1, le=100)
    task_timeout: int = Field(default=3600, ge=60, le=86400)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_backoff: bool = Field(default=True)


class CeleryConfigResponse(BaseModel):
    """Celery config response."""

    id: UUID
    redis_host: str
    redis_port: int
    worker_concurrency: int
    task_timeout: int
    max_retries: int
    retry_backoff: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JobStatusResponse(BaseModel):
    """Queue status response."""

    pending: int = Field(..., description="Pending jobs count")
    running: int = Field(..., description="Running jobs count")
    failed: int = Field(..., description="Failed jobs count")


class JobLogResponse(BaseModel):
    """Job log response."""

    id: UUID
    job_id: str
    upload_metadata_id: Optional[UUID]
    job_type: str
    status: str
    retry_count: int
    attempts: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class JobPageResponse(BaseModel):
    """Paginated job response."""

    total: int
    page: int
    page_size: int
    items: list[JobLogResponse]


class DLQResponse(BaseModel):
    """Dead letter queue response."""

    id: UUID
    job_id: str
    error_message: str
    final_exception: str
    created_at: datetime
    marked_resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobRetryRequest(BaseModel):
    """Job retry request."""

    job_id: str = Field(..., description="Job ID to retry")
