from sqlalchemy import Column, Index, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class UploadIdempotencyKey(BaseModel):
    """Idempotency key tracker for uploads to prevent duplicates."""

    __tablename__ = "upload_idempotency_keys"

    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("raw_files.id"), nullable=False)
    job_id = Column(UUID(as_uuid=True), nullable=False)  # UUID of the ingest job
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_idempotency_key_expires_at", "idempotency_key", "expires_at"),
    )
