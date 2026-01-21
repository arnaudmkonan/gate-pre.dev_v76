from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class StorageConfigCreate(BaseModel):
    """Create storage config request."""

    provider: str = Field(..., description="Storage provider: 'supabase' or 's3'")
    endpoint: str = Field(..., description="Storage endpoint URL")
    bucket_name: str = Field(..., description="Bucket name")
    region: str = Field(..., description="AWS region")
    access_key: str = Field(..., description="Access key")
    secret_key: str = Field(..., description="Secret key")
    max_file_size_mb: int = Field(default=100, ge=1, le=5000)


class StorageConfigUpdate(BaseModel):
    """Update storage config request."""

    provider: Optional[str] = None
    endpoint: Optional[str] = None
    bucket_name: Optional[str] = None
    region: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    max_file_size_mb: Optional[int] = Field(None, ge=1, le=5000)
    is_active: Optional[bool] = None


class StorageConfigResponse(BaseModel):
    """Storage config response."""

    id: UUID
    provider: str
    endpoint: str
    bucket_name: str
    region: str
    max_file_size_mb: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UploadResponse(BaseModel):
    """File upload response."""

    file_id: UUID
    signed_url: str
    expires_at: datetime
    size: int
    mime_type: str
    job_id: Optional[str] = None


class UploadMetadataResponse(BaseModel):
    """Upload metadata response."""

    id: UUID
    filename: str
    file_size: int
    mime_type: str
    checksum: str
    storage_path: str
    upload_status: str
    error_message: Optional[str] = None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
