"""Pydantic schemas for queue job responses."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class QueueJobResponse(BaseModel):
    """Response model for a queue job."""

    job_id: str
    file_id: str
    status: str
    priority: str
    attempts: int
    max_attempts: int
    last_error: Optional[str] = None
    last_attempted_at: Optional[datetime] = None
    created_at: datetime


class QueueListResponse(BaseModel):
    """Response model for list of queue jobs."""

    jobs: List[QueueJobResponse]
    total_count: int
    limit: int
    offset: int


class EnqueueRequest(BaseModel):
    """Request model for enqueueing a file."""

    file_id: str
    file_type: str
    file_size: int
    uploader_id: Optional[str] = None
    priority: str = "normal"  # low, normal, high
