"""Pydantic schemas for file versioning responses."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class FileVersionResponse(BaseModel):
    """Response model for a file version."""

    version_id: str
    version_number: int
    file_hash: str
    is_deduplicated: bool
    storage_path: str
    created_at: datetime
    snapshot_id: str
    content_hash: str
    storage_size: int


class FileSnapshotResponse(BaseModel):
    """Response model for a file snapshot."""

    snapshot_id: str
    content_hash: str
    storage_size: int
    created_by: Optional[str] = None
    created_at: datetime


class VersionListResponse(BaseModel):
    """Response model for list of versions."""

    versions: List[FileVersionResponse]
    total_count: int
