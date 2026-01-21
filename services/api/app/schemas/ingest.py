from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class IngestJobCreate(BaseModel):
    """Create ingest job request."""

    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File type (txt, pdf, md, docx, xlsx, etc.)")
    size: int = Field(..., ge=1, description="File size in bytes")
    uploader_id: Optional[str] = Field(None, description="ID of uploader")


class IngestJobResponse(BaseModel):
    """Ingest job response."""

    id: UUID
    filename: str
    file_type: str
    size: int
    status: str
    uploader_id: Optional[str]
    storage_path: Optional[str]
    extracted_metadata: Optional[dict]
    error_message: Optional[str]
    attempts: int
    max_attempts: int
    priority: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UploadResponse(BaseModel):
    """File upload response."""

    file_id: UUID
    job_id: UUID
    filename: str
    storage_path: str
    file_type: str
    agent_id: Optional[str] = None
    routing_confidence: Optional[float] = None
    routing_method: Optional[str] = None
    message: str = "File uploaded and job queued successfully"


class IngestJobListResponse(BaseModel):
    """Paginated ingest jobs response."""

    total: int
    page: int
    page_size: int
    items: list[IngestJobResponse]


class IngestQueueStatusResponse(BaseModel):
    """Ingest queue status summary."""

    pending: int = Field(..., description="Pending jobs count")
    processing: int = Field(..., description="Processing jobs count")
    completed: int = Field(..., description="Completed jobs count")
    failed: int = Field(..., description="Failed jobs count")


class RetryRequest(BaseModel):
    """Retry a failed job request."""

    job_id: UUID = Field(..., description="Job ID to retry")


class DLQItemResponse(BaseModel):
    """Dead letter queue item response."""

    id: UUID
    job_id: UUID
    filename: Optional[str]
    error_message: str
    retry_history: Optional[list]
    failure_count: int
    manual_notes: Optional[str]
    status: str  # pending_review, archived
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DLQReprocessRequest(BaseModel):
    """Request to reprocess a DLQ item."""

    dlq_id: UUID = Field(..., description="DLQ item ID to reprocess")


class BatchScheduleCreate(BaseModel):
    """Create batch schedule request."""

    schedule_name: str = Field(..., description="Unique schedule name")
    cron_expression: str = Field(..., description="Cron expression for schedule")
    max_concurrency: int = Field(default=5, ge=1, le=100, description="Max concurrent jobs")
    batch_size: int = Field(default=10, ge=1, le=500, description="Jobs per batch")
    description: Optional[str] = Field(None, description="Optional description")


class BatchScheduleUpdate(BaseModel):
    """Update batch schedule request."""

    schedule_name: Optional[str] = None
    cron_expression: Optional[str] = None
    max_concurrency: Optional[int] = Field(None, ge=1, le=100)
    batch_size: Optional[int] = Field(None, ge=1, le=500)
    is_active: Optional[bool] = None
    description: Optional[str] = None


class BatchScheduleResponse(BaseModel):
    """Batch schedule response."""

    id: UUID
    schedule_name: str
    cron_expression: str
    max_concurrency: int
    batch_size: int
    is_active: bool
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BatchMetricsResponse(BaseModel):
    """Batch execution metrics response."""

    schedule_id: UUID
    schedule_name: str
    total_jobs_processed: int
    execution_time_seconds: int
    jobs_succeeded: int
    jobs_failed: int
    last_run_at: datetime
    average_job_time_seconds: float


class MetadataResponse(BaseModel):
    """Extracted metadata response."""

    filename: str
    mime_type: Optional[str]
    page_count: Optional[int]
    language: Optional[str]
    title: Optional[str]
    extracted_text_preview: Optional[str]
    file_size_bytes: int
    extraction_time_seconds: float
