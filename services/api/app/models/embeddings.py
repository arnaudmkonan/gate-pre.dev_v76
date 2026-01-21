from sqlalchemy import Column, ForeignKey, Index, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class Embeddings(BaseModel):
    """Embeddings model for vector search."""

    __tablename__ = "embeddings"

    upload_metadata_id = Column(UUID(as_uuid=True), ForeignKey("upload_metadata.id"), nullable=False)
    vector = Column(JSON, nullable=False)  # Store as JSON array instead of pgvector
    content_chunk = Column(Text, nullable=False)
    metadata_source_file_id = Column(String(255), nullable=False)
    metadata_timestamp = Column(String(50), nullable=False)
    metadata_embedding_model = Column(String(100), nullable=False)

    __table_args__ = (
        Index("idx_embeddings_upload_metadata_id", "upload_metadata_id"),
    )
