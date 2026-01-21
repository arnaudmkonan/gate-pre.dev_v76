"""Model for tracking normalization validation results."""

from sqlalchemy import Column, Index, String, JSON, UUID, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.base import BaseModel


class NormalizationValidation(BaseModel):
    """Track validation of normalization for records before silver upsert."""

    __tablename__ = "normalization_validation"

    batch_id = Column(PG_UUID(as_uuid=True), nullable=False)  # Batch being validated
    record_id = Column(String(500), nullable=False)  # Record being validated
    document_id = Column(String(500), nullable=False)  # Document reference
    validation_status = Column(String(20), nullable=False)  # pass, fail, warning
    field_errors = Column(JSON, nullable=True)  # {field: [error_messages]}
    validation_details = Column(JSON, nullable=True)  # Full validation report
    error_message = Column(String(2000), nullable=True)  # Summary error if status=fail

    __table_args__ = (
        Index("idx_normalization_validation_batch_id", "batch_id"),
        Index("idx_normalization_validation_status", "validation_status"),
        Index("idx_normalization_validation_batch_status", "batch_id", "validation_status"),
        Index("idx_normalization_validation_record_id", "record_id"),
        Index("idx_normalization_validation_document_id", "document_id"),
    )
