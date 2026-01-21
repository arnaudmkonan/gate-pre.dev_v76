"""Schemas for file type mapping."""

from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, validator


class FileTypeMappingCreate(BaseModel):
    """Schema for creating a file type mapping."""

    file_type: str = Field(..., min_length=1, max_length=50, description="File type/extension (e.g., pdf, docx)")
    agent_name: str = Field(..., min_length=1, max_length=255, description="Agent name to process this file type")
    is_default: Optional[bool] = Field(False, description="Whether this is the default mapping")
    config: Optional[Dict[str, Any]] = Field(None, description="Optional agent configuration")

    @validator("file_type")
    def file_type_format(cls, v):
        if not v or not v.strip():
            raise ValueError("File type cannot be empty")
        return v.strip().lower()

    @validator("agent_name")
    def agent_name_format(cls, v):
        if not v or not v.strip():
            raise ValueError("Agent name cannot be empty")
        return v.strip()


class FileTypeMappingUpdate(BaseModel):
    """Schema for updating a file type mapping."""

    agent_name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_default: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


class FileTypeMappingResponse(BaseModel):
    """Schema for file type mapping response."""

    id: UUID
    file_type: str
    agent_name: str
    is_default: bool
    version: int
    config: Optional[Dict[str, Any]]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class FileTypeMappingListResponse(BaseModel):
    """Schema for listing file type mappings."""

    mappings: List[FileTypeMappingResponse]
    total: int
    page: int
    page_size: int


class FileTypeMappingTestRequest(BaseModel):
    """Schema for testing a file type mapping."""

    file_type: Optional[str] = Field(None, description="File type to test (optional, inferred from mapping)")
    sample_data: Optional[Dict[str, Any]] = Field(None, description="Sample data for testing")


class RoutingDecision(BaseModel):
    """Schema for routing decision."""

    would_route: bool
    matched_agent_name: Optional[str] = None
    file_type_handled: str
    mapping_version: int


class ConfigurationInfo(BaseModel):
    """Schema for configuration information."""

    agent_config: Dict[str, Any]
    config_valid: bool
    fallback_agent: Optional[str] = None


class ValidationResults(BaseModel):
    """Schema for validation results."""

    errors: List[str]
    error_count: int


class SampleValidation(BaseModel):
    """Schema for sample data validation."""

    provided_fields: List[str]
    sample_data_accepted: bool


class FileTypeMappingTestResponse(BaseModel):
    """Schema for test result."""

    file_type: str
    agent_name: str
    status: str  # "success" or "failed"
    message: str
    routing_decision: Optional[RoutingDecision] = None
    configuration: Optional[ConfigurationInfo] = None
    validation_results: Optional[ValidationResults] = None
    sample_validation: Optional[SampleValidation] = None
    processed_items: Optional[int] = None


class FileTypeMappingExportResponse(BaseModel):
    """Schema for exporting mappings."""

    mappings: List[FileTypeMappingResponse]
    export_timestamp: str


class FileTypeMappingImportRequest(BaseModel):
    """Schema for importing mappings."""

    mappings: List[FileTypeMappingCreate]
    overwrite_existing: Optional[bool] = Field(False, description="Whether to overwrite existing mappings")
