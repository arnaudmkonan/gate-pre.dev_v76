"""DocumentEmbedding model for storing vector embeddings."""

from sqlalchemy import Column, Index, Integer, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSON, ARRAY
from sqlalchemy.types import TypeDecorator
import json

from app.models.base import BaseModel


class EmbeddingVector(TypeDecorator):
    """Custom type for storing embedding vectors as JSON arrays."""
    
    impl = Text
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return None
    
    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return None


class DocumentEmbedding(BaseModel):
    """
    Model for storing document embeddings.
    
    Each document can have multiple embeddings (one per chunk).
    Embeddings are stored as JSON arrays for portability.
    """
    
    __tablename__ = "document_embeddings"
    
    # Foreign key to document_metadata
    document_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Chunk information
    chunk_index = Column(Integer, nullable=False, default=0)
    content_preview = Column(Text, nullable=True)  # First 500 chars of chunk
    
    # The embedding vector (stored as JSON array)
    embedding = Column(EmbeddingVector, nullable=False)
    
    # Metadata about the embedding
    embedding_metadata = Column(JSON, nullable=True)
    embedding_model = Column(String(100), default="text-embedding-3-small", nullable=True)
    embedding_dimensions = Column(Integer, nullable=True)
    
    __table_args__ = (
        Index("idx_doc_embeddings_document_id", "document_id"),
        Index("idx_doc_embeddings_doc_chunk", "document_id", "chunk_index", unique=True),
    )
    
    def __repr__(self):
        return f"<DocumentEmbedding(id={self.id}, document_id={self.document_id}, chunk={self.chunk_index})>"
