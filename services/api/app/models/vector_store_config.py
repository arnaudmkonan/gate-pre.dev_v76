from sqlalchemy import Boolean, Column, Integer, String, Text

from app.models.base import BaseModel


class VectorStoreConfig(BaseModel):
    """Vector store configuration model."""

    __tablename__ = "vector_store_config"

    backend = Column(String(50), nullable=False)  # 'supabase', 'pinecone', etc.
    url = Column(String(500), nullable=False)
    api_key = Column(Text, nullable=False)  # Encrypted in application layer
    embedding_model = Column(String(100), default="text-embedding-3-small", nullable=False)
    embedding_dimension = Column(Integer, default=1536, nullable=False)
    namespace_collection_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
