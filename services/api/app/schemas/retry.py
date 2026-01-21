"""Pydantic schemas for retry operations."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class RetryJobRequest(BaseModel):
    """Request to retry one or multiple failed jobs."""

    job_ids: List[str] = Field(..., min_items=1, max_items=100)
    mode_override: Optional[str] = None
    mapping_override: Optional[Dict[str, Any]] = None


class RetryResponse(BaseModel):
    """Response for a single retry operation."""

    job_id: str
    retry_id: str
    new_job_id: str
    status: str
    message: Optional[str] = None


class RetryBulkResponse(BaseModel):
    """Response for bulk retry operations."""

    retried_count: int
    failed_count: int
    results: List[RetryResponse]
    errors: Optional[List[Dict[str, str]]] = None


class RetryJobResponse(BaseModel):
    """Response schema for a retry job."""

    id: str
    original_job_id: str
    retry_count: int
    status: str
    created_at: datetime
    updated_at: datetime
    error_reason: Optional[str] = None
    mode_override: Optional[str] = None
    mapping_override: Optional[str] = None

    class Config:
        from_attributes = True


class RetryHistoryResponse(BaseModel):
    """Response for retry history of a job."""

    job_id: str
    total_retries: int
    retries: List[RetryJobResponse]


class RetryBulkRequest(BaseModel):
    """Request for bulk retry operations."""

    job_ids: List[str] = Field(..., min_items=1, max_items=100, description="Up to 100 job IDs to retry")
    mode_override: Optional[str] = None
    mapping_override: Optional[Dict[str, Any]] = None
