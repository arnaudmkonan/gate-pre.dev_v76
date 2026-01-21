from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UploadRequest(BaseModel):
    """Upload request schema."""

    source: Optional[str] = Field(None, description="Source of the document")
    customer_id: Optional[str] = Field(None, description="Customer ID")
    tags: Optional[list[str]] = Field(None, description="Tags for the document")


class UploadResponse(BaseModel):
    """Upload response schema with job ID."""

    job_id: UUID = Field(..., description="Ingestion job ID")
    file_id: UUID = Field(..., description="Raw file ID")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File type extension")
    size: int = Field(..., description="File size in bytes")
    storage_path: str = Field(..., description="Path in storage")
    status: str = Field(default="pending", description="File status")
    message: str = Field(default="File uploaded and queued for ingestion", description="Response message")


class RawFileResponse(BaseModel):
    """Raw file response schema."""

    id: UUID
    filename: str
    file_type: str
    file_size: int
    storage_path: str
    status: str
    stored_at: Optional[datetime]
    uploader_id: Optional[str]
    source: Optional[str]
    customer_id: Optional[str]
    tags: Optional[list[str]]
    checksum: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
