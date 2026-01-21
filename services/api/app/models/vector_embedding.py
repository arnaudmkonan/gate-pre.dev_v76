from enum import Enum
from sqlalchemy import Column, Index, ForeignKey, JSON, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class VectorStatus(str, Enum):
    """Vector embedding status enum."""

    PENDING = "pending"
    GENERATED = "generated"
    FAILED = "failed"


class VectorEmbedding(BaseModel):
    """Vector embeddings for pgvector storage and semantic search."""

    __tablename__ = "raw_vectors"

    file_id = Column(UUID(as_uuid=True), ForeignKey("raw_files.id"), nullable=False)
    vector = Column(JSON, nullable=False)  # Actual DB column name (pgvector stored as JSON)
    doc_metadata = Column(JSON, nullable=True)  # Legacy field from original raw_vectors
    provenance = Column(JSON, nullable=True)  # Legacy field from original raw_vectors
    # New fields for metadata service
    embedding = Column(JSON, nullable=True)  # Alias for vector (used by VectorStoreService)
    metadata_tags = Column(JSON, nullable=True, default={})  # source, document_type, detected_entities
    vector_status = Column(String(50), default=VectorStatus.PENDING.value, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    error_reason = Column(String, nullable=True)

    __table_args__ = (
        Index("idx_vector_embeddings_file_id", "file_id"),
        Index("idx_vector_embeddings_created_at", "created_at"),
        Index("idx_vector_embeddings_vector_status", "vector_status"),
    )
