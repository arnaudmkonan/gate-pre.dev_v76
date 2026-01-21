"""Schemas for silver (normalized) record operations."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SilverRecordInput(BaseModel):
    """Input for a single silver record during upsert."""

    document_id: str = Field(..., description="Unique document identifier", min_length=1, max_length=500)
    record_id: str = Field(..., description="Unique record identifier within document", min_length=1, max_length=500)
    canonical_id: Optional[str] = Field(None, description="Canonical ID for deduplication", max_length=500)
    source_file_id: UUID = Field(..., description="Source file ID from raw_files")
    file_type: str = Field(..., description="File type (pdf, csv, json, etc.)", max_length=50)
    size_bytes: int = Field(..., description="File size in bytes", ge=0)
    normalized_payload: dict = Field(..., description="Normalized data payload")
    title: Optional[str] = Field(None, description="Document title", max_length=1000)
    author: Optional[str] = Field(None, description="Document author", max_length=500)
    language: Optional[str] = Field(None, description="Document language code", max_length=20)
    content: Optional[str] = Field(None, description="Normalized/cleaned text content")
    extraction_date: Optional[datetime] = Field(None, description="When document was extracted")
    document_date: Optional[datetime] = Field(None, description="Document's own date field")
    record_metadata: Optional[dict] = Field(None, description="Additional metadata (checksum, facets, etc.)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Record timestamp")

    @field_validator("document_id", "record_id")
    @classmethod
    def validate_ids_not_empty(cls, v: str) -> str:
        """Ensure IDs are not empty."""
        if not v or not v.strip():
            raise ValueError("ID cannot be empty")
        return v.strip()

    @field_validator("size_bytes")
    @classmethod
    def validate_size(cls, v: int) -> int:
        """Ensure size is reasonable (max 5GB)."""
        if v > 5_000_000_000:
            raise ValueError("File size exceeds maximum allowed (5GB)")
        return v


class SilverRecordBatch(BaseModel):
    """Batch of silver records for upsert operation."""

    batch_id: Optional[UUID] = Field(None, description="Optional batch ID for tracking")
    records: list[SilverRecordInput] = Field(..., description="List of records to upsert", min_items=1, max_items=10000)
    source_context: Optional[dict] = Field(None, description="Optional context about the batch source")

    @field_validator("records")
    @classmethod
    def validate_records_not_empty(cls, v: list) -> list:
        """Ensure records list is not empty."""
        if not v:
            raise ValueError("Records list cannot be empty")
        return v


class FailedRecord(BaseModel):
    """Failed record with error details."""

    record_index: int = Field(..., description="Index in the original batch")
    document_id: str = Field(..., description="Document ID that failed")
    record_id: str = Field(..., description="Record ID that failed")
    error_message: str = Field(..., description="Detailed error message")
    error_type: str = Field(..., description="Type of error (validation, database, etc.)")
    field_errors: Optional[dict] = Field(None, description="Field-specific validation errors")


class SilverUpsertResult(BaseModel):
    """Result of silver record upsert operation."""

    batch_id: Optional[UUID] = Field(None, description="Batch ID that was processed")
    total_records: int = Field(..., description="Total records in batch")
    inserted_count: int = Field(..., description="Number of newly inserted records")
    updated_count: int = Field(..., description="Number of updated records")
    failed_count: int = Field(default=0, description="Number of failed records")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    failed_records: list[FailedRecord] = Field(default_factory=list, description="Details of failed records")

    class Config:
        from_attributes = True


class SilverRecordResponse(BaseModel):
    """Response for a silver record."""

    id: UUID
    document_id: Optional[str] = None
    record_id: Optional[str] = None
    canonical_id: Optional[str] = None
    batch_id: Optional[UUID] = None
    source_file_id: UUID
    file_type: str
    size_bytes: int
    title: Optional[str] = None
    author: Optional[str] = None
    language: Optional[str] = None
    content: Optional[str] = None
    normalized_payload: Optional[dict] = None
    processing_status: str
    processing_error: Optional[str] = None
    vector_store_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
