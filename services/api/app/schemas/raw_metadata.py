"""Pydantic schemas for raw metadata endpoints."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RawMetadataCreate(BaseModel):
    """Request schema for creating raw metadata."""

    filename: str = Field(..., description="Name of the file")
    file_size: int = Field(..., description="Size in bytes")
    checksum: str = Field(..., description="SHA-256 checksum of file")
    storage_location: str = Field(..., description="Path in Supabase Storage")
    uploader_id: Optional[str] = Field(None, description="ID of uploader")
    file_type: Optional[str] = Field(None, description="File type/extension")


class UploadEventResponse(BaseModel):
    """Response schema for upload event."""

    id: UUID
    raw_metadata_id: UUID
    upload_timestamp: datetime
    event_type: str  # 'new' or 'duplicate'
    user_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class RawMetadataResponse(BaseModel):
    """Response schema for raw metadata with timestamps."""

    id: UUID
    filename: str
    file_size: int
    checksum: str
    storage_location: str
    uploader_id: Optional[str]
    file_type: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RawMetadataQueryResponse(BaseModel):
    """Response schema for raw metadata query with upload events."""

    metadata: RawMetadataResponse
    is_duplicate: bool
    upload_event: UploadEventResponse


class RawMetadataListResponse(BaseModel):
    """Paginated response for raw metadata list."""

    total: int
    page: int
    page_size: int
    items: list[RawMetadataResponse]
