from sqlalchemy import Column, Index, String, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class VectorRecord(BaseModel):
    """Store vector embeddings with metadata for semantic search."""

    __tablename__ = "vector_records"

    silver_record_id = Column(UUID(as_uuid=True), ForeignKey("silver_records.id"), nullable=False)
    embedding = Column(JSON, nullable=False)  # Store as JSON array (vector as list of floats)
    content_preview = Column(Text, nullable=True)  # Preview of chunked content
    section_index = Column(String(50), nullable=False)  # Index within document sections
    vector_metadata = Column(JSON, nullable=True)  # Chunk metadata, section info, etc.

    __table_args__ = (
        Index("idx_vector_records_silver_record_id", "silver_record_id"),
        Index("idx_vector_records_created_at", "created_at"),
    )
