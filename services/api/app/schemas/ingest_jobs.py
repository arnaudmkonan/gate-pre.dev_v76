"""Pydantic schemas for ingestion jobs."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class IngestModeEnum(str):
    """Ingestion mode options."""
    QUICK_AUTO = "quick_auto"
    GUIDED_MAPPING = "guided_mapping"
    ADVANCED_BATCH = "advanced_batch"


class MappingFieldConfig(BaseModel):
    """Configuration for a single mapping field."""
    field_name: str
    field_type: str  # text, date, select
    mapped_to: Optional[str] = None
    example_value: Optional[str] = None


class MappingConfig(BaseModel):
    """Mapping configuration for guided_mapping mode."""
    document_type: Optional[str] = None
    date: Optional[str] = None
    reference: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None


class BatchSettings(BaseModel):
    """Batch settings for advanced_batch mode."""
    batch_size: int = Field(default=10, ge=1, le=100)
    schedule_type: str = Field(default="immediate")  # immediate or scheduled
    schedule_time: Optional[datetime] = None


class IngestJobResponse(BaseModel):
    """Response schema for an ingestion job."""
    id: str
    filename: str
    file_type: str
    size: int
    status: str
    created_at: datetime
    updated_at: datetime
    uploader_id: Optional[str] = None
    storage_path: Optional[str] = None
    extracted_metadata: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    attempts: int
    max_attempts: int
    last_attempted_at: Optional[datetime] = None
    priority: str

    # Mode and settings
    mode: str = "quick_auto"
    batch_size: Optional[int] = None
    schedule_time: Optional[datetime] = None
    mapping_config: Optional[MappingConfig] = None
    progress_percentage: int = 0

    class Config:
        from_attributes = True

    @field_validator('id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Convert UUID to string if needed."""
        if isinstance(v, UUID):
            return str(v)
        return v


class IngestJobListResponse(BaseModel):
    """Response schema for job list with pagination."""
    jobs: List[IngestJobResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class ModeSelectorRequest(BaseModel):
    """Request to select ingestion mode for a job."""
    mode: str = Field(..., description="quick_auto, guided_mapping, or advanced_batch")
    batch_size: Optional[int] = Field(None, ge=1, le=100)
    schedule_time: Optional[datetime] = None
    mapping_config: Optional[MappingConfig] = None


class MappingPreviewRequest(BaseModel):
    """Request to preview mapping for a sample document."""
    mapping_config: MappingConfig
    sample_content: Optional[str] = None  # Sample document content


class MappingPreviewResponse(BaseModel):
    """Response for mapping preview."""
    is_valid: bool
    extracted_fields: Dict[str, Any]
    warnings: Optional[List[str]] = None
    errors: Optional[List[str]] = None


class JobsFilterParams(BaseModel):
    """Filter parameters for job list."""
    status: Optional[str] = None
    created_after: Optional[datetime] = None
    source: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)
