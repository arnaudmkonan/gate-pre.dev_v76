from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MetadataResponse(BaseModel):
    """Metadata response schema for a document."""

    id: UUID
    job_id: UUID
    filename: str
    file_type: str
    size: int
    uploader: Optional[str]
    ingestion_status: str
    extracted_text_snippet: Optional[str]
    detected_language: Optional[str]
    vector_store_id: Optional[str]
    raw_storage_path: Optional[str]
    extraction_timestamp: Optional[datetime]
    extractor_agent_version: Optional[str]
    page_count: Optional[int]
    mime_type: Optional[str]
    title: Optional[str]
    author: Optional[str]
    subject: Optional[str]
    keywords: Optional[list[str]]
    customer_id: Optional[str]
    source: Optional[str]
    tags: Optional[list[str]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MetadataListResponse(BaseModel):
    """Paginated metadata response."""

    total: int = Field(..., description="Total items")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")
    items: list[MetadataResponse] = Field(..., description="Metadata items")


class MetadataQueryParams(BaseModel):
    """Metadata query parameters for filtering."""

    job_id: Optional[UUID] = Field(None, description="Filter by job ID")
    document_id: Optional[UUID] = Field(None, description="Filter by document ID")
    customer_id: Optional[str] = Field(None, description="Filter by customer ID")
    file_type: Optional[str] = Field(None, description="Filter by file type")
    ingestion_status: Optional[str] = Field(None, description="Filter by ingestion status")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
