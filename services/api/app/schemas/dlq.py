"""Pydantic schemas for DLQ endpoints."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field


class DLQEntryCreate(BaseModel):
    """Create a DLQ entry."""

    file_id: UUID
    pipeline: str
    error_type: str
    error_message: str
    retry_count: int = 0
    metadata: Optional[Dict[str, Any]] = None


class DLQEntryResponse(BaseModel):
    """Response for a DLQ entry."""

    id: UUID
    file_id: UUID
    pipeline: str
    error_type: str
    error_message: str
    retry_count: int
    last_retry_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    archived: bool
    archived_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class DLQFilterQuery(BaseModel):
    """Query filters for DLQ entries."""

    file_id: Optional[UUID] = None
    error_type: Optional[str] = None
    pipeline: Optional[str] = None
    archived: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


class DLQListResponse(BaseModel):
    """Response for DLQ list query."""

    entries: List[DLQEntryResponse]
    total: int
    limit: int
    offset: int


class DLQRequeueRequest(BaseModel):
    """Request to requeue a DLQ entry."""

    dlq_entry_id: UUID
    apply_new_policy: bool = True


class DLQRequeueResponse(BaseModel):
    """Response from requeue action."""

    success: bool
    dlq_entry_id: UUID
    job_id: Optional[UUID] = None
    message: str
    timestamp: datetime


class DLQArchiveRequest(BaseModel):
    """Request to archive a DLQ entry."""

    dlq_entry_id: UUID


class DLQArchiveResponse(BaseModel):
    """Response from archive action."""

    success: bool
    dlq_entry_id: UUID
    message: str
    timestamp: datetime
