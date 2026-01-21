from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# Ingest Batch Schemas
class IngestBatchCreate(BaseModel):
    """Create a batch ingestion job."""

    batch_name: str = Field(..., description="Name of the batch", min_length=1, max_length=500)
    file_ids: list[UUID] = Field(..., description="List of file IDs to ingest")
    created_by: Optional[str] = Field(None, description="User ID who created this batch")
    scheduled_for: Optional[datetime] = Field(None, description="Schedule for later processing")
    max_concurrent_jobs: int = Field(default=5, ge=1, le=20, description="Max concurrent jobs")
    metadata: Optional[dict] = Field(None, description="Custom batch metadata")


class IngestFileResponse(BaseModel):
    """Individual file in a batch response."""

    id: UUID
    batch_id: UUID
    file_id: UUID
    file_type: str
    status: str  # queued, processing, success, failed, retry
    routing_decision: Optional[str] = None
    attempts: int
    max_attempts: int
    last_error: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IngestBatchResponse(BaseModel):
    """Batch ingestion job response."""

    id: UUID
    batch_name: str
    status: str  # pending, processing, completed, failed, partial
    file_count: int
    success_count: int
    failure_count: int
    created_by: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    max_concurrent_jobs: int
    batch_metadata: Optional[dict] = None
    error_message: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BatchStatusResponse(BaseModel):
    """Complete batch status with file details."""

    batch: IngestBatchResponse
    files: list[IngestFileResponse]


# Silver Record Schemas
class SilverRecordCreate(BaseModel):
    """Create a silver/normalized record."""

    file_id: UUID
    raw_content: Optional[dict] = None
    title: Optional[str] = None
    author: Optional[str] = None
    extraction_date: Optional[datetime] = None
    document_date: Optional[datetime] = None
    file_type: str
    size_bytes: int
    language: Optional[str] = None
    content: Optional[str] = None
    record_metadata: Optional[dict] = None


class SilverRecordResponse(BaseModel):
    """Normalized silver record response."""

    id: UUID
    file_id: UUID
    raw_content: Optional[dict] = None
    title: Optional[str] = None
    author: Optional[str] = None
    extraction_date: Optional[datetime] = None
    document_date: Optional[datetime] = None
    file_type: str
    size_bytes: int
    language: Optional[str] = None
    content: Optional[str] = None
    record_metadata: Optional[dict] = None
    processing_status: str  # pending, completed, failed
    processing_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Retry Queue Schemas
class RetryQueueItemResponse(BaseModel):
    """Retry queue item response."""

    id: UUID
    file_id: UUID
    error_type: str
    error_message: str
    processing_attempt: int
    last_retry_at: Optional[datetime] = None
    manual_notes: Optional[str] = None
    status: str  # pending_review, processing, resolved, archived
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RetryQueueUpdate(BaseModel):
    """Update retry queue item."""

    manual_notes: Optional[str] = None
    status: Optional[str] = None


class RetryQueueListResponse(BaseModel):
    """Paginated retry queue response."""

    total: int
    page: int
    page_size: int
    items: list[RetryQueueItemResponse]


class RetryQueueRetryRequest(BaseModel):
    """Request to manually retry a failed item."""

    notes: Optional[str] = Field(None, description="Optional notes about the retry")


# Vector Embedding Schemas
class VectorEmbeddingResponse(BaseModel):
    """Vector embedding response."""

    id: UUID
    file_id: UUID
    embedding_metadata: Optional[dict] = None
    section_index: Optional[int] = None
    content_preview: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Metadata Response
class MetadataMapperResponse(BaseModel):
    """Metadata mapping result."""

    file_id: UUID
    title: Optional[str] = None
    author: Optional[str] = None
    file_type: str
    language: Optional[str] = None
    processing_steps: list[str]
    checksum: Optional[str] = None
    facets: Optional[dict] = None
    created_at: datetime


# Batch Status Summary
class BatchStatusSummary(BaseModel):
    """Summary of batch processing status."""

    total_batches: int
    pending: int
    processing: int
    completed: int
    failed: int
    partial: int
    total_files: int
    total_success: int
    total_failure: int
