from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class NormalizedMetadata(BaseModel):
    """Normalized metadata schema for silver table."""

    id: Optional[UUID] = None
    file_id: UUID
    title: Optional[str] = None
    author: Optional[str] = None
    dates: Optional[list[datetime]] = None  # List of normalized dates (ISO 8601)
    document_type: Optional[str] = None
    custom_metadata: Optional[dict] = Field(default=None, description="Custom metadata fields")
    source_metadata: Optional[dict] = Field(default=None, description="Raw source metadata for traceability")
    mapping_version: str = Field(default="1.0.0", description="Version of the transformation")

    @field_validator("dates", mode="before")
    def normalize_dates(cls, v):
        """Normalize dates to ISO 8601 format."""
        if not v:
            return v

        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, str):
                    # Try to parse string to datetime
                    try:
                        from dateutil import parser
                        dt = parser.isoparse(item)
                        result.append(dt)
                    except:
                        pass
                elif isinstance(item, datetime):
                    result.append(item)
            return result if result else None
        elif isinstance(v, str):
            try:
                from dateutil import parser
                dt = parser.isoparse(v)
                return [dt]
            except:
                return None
        elif isinstance(v, datetime):
            return [v]

        return None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }


class NormalizedMetadataResponse(BaseModel):
    """Response model for normalized metadata."""

    id: UUID
    file_id: UUID
    title: Optional[str]
    author: Optional[str]
    dates: Optional[list[str]]  # ISO 8601 strings
    document_type: Optional[str]
    custom_metadata: Optional[dict]
    source_metadata: Optional[dict]
    mapping_version: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MetadataReprocessRequest(BaseModel):
    """Request to reprocess metadata for files."""

    file_ids: Optional[list[UUID]] = None
    date_range: Optional[dict] = Field(default=None, description="Date range with start and end")
    status_filter: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=10000)

    class Config:
        json_schema_extra = {
            "example": {
                "file_ids": ["550e8400-e29b-41d4-a716-446655440000"],
                "date_range": {
                    "start": "2024-01-01",
                    "end": "2024-12-31"
                },
                "status_filter": "failed",
                "limit": 100
            }
        }
