from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VectorStoreConfigCreate(BaseModel):
    """Create vector store config request."""

    backend: str = Field(..., description="Backend: 'supabase', 'pinecone', etc.")
    url: str = Field(..., description="Vector store URL")
    api_key: str = Field(..., description="API key for vector store")
    embedding_model: str = Field(default="text-embedding-3-small")
    embedding_dimension: int = Field(default=1536)
    namespace_collection_name: Optional[str] = None


class VectorStoreConfigUpdate(BaseModel):
    """Update vector store config request."""

    backend: Optional[str] = None
    url: Optional[str] = None
    api_key: Optional[str] = None
    embedding_model: Optional[str] = None
    namespace_collection_name: Optional[str] = None
    is_active: Optional[bool] = None


class VectorStoreConfigResponse(BaseModel):
    """Vector store config response."""

    id: UUID
    backend: str
    url: str
    embedding_model: str
    embedding_dimension: int
    namespace_collection_name: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmbeddingResponse(BaseModel):
    """Embedding response."""

    id: UUID
    content_chunk: str
    metadata_source_file_id: str
    metadata_timestamp: str
    metadata_embedding_model: str
    similarity_score: Optional[float] = None


class SearchResponse(BaseModel):
    """Search response."""

    results: list[EmbeddingResponse]
    query_time_ms: float


class RawVectorCreate(BaseModel):
    """Create raw vector request."""

    file_id: UUID = Field(..., description="File ID")
    vector: list[float] = Field(..., description="Embedding vector (1536-dim for OpenAI)")
    metadata: Optional[dict] = Field(default=None, description="File metadata: source_path, mime_type, timestamp")
    provenance: dict = Field(..., description="Provenance: processor_agent_id, extraction_version")

    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "550e8400-e29b-41d4-a716-446655440000",
                "vector": [0.1, 0.2, 0.3],  # 1536-dim in production
                "metadata": {
                    "source_path": "s3://bucket/file.pdf",
                    "mime_type": "application/pdf",
                    "timestamp": "2024-01-13T12:00:00Z"
                },
                "provenance": {
                    "processor_agent_id": "pdf-extractor-v1",
                    "extraction_version": "1.0.0"
                }
            }
        }


class RawVectorResponse(BaseModel):
    """Raw vector response."""

    id: UUID
    file_id: UUID
    doc_metadata: Optional[dict] = None
    provenance: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VectorSearchQuery(BaseModel):
    """Vector search query."""

    query: Optional[str] = Field(default=None, description="Text query for server-side embedding")
    embedding: Optional[list[float]] = Field(default=None, description="Pre-computed embedding vector")
    filters: Optional[dict] = Field(default=None, description="Metadata filters: date_range, document_type, etc.")
    limit: int = Field(default=10, ge=1, le=100, description="Max results to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "contract terms",
                "filters": {
                    "document_type": "legal",
                    "date_range": {
                        "start": "2024-01-01",
                        "end": "2024-12-31"
                    }
                },
                "limit": 10,
                "offset": 0
            }
        }


class SearchResultItem(BaseModel):
    """Individual search result item."""

    file_id: UUID
    similarity_score: float
    snippet: Optional[str] = None
    metadata: dict
    explainability: dict  # similarity_score, index_shard, retriever_version

    class Config:
        from_attributes = True


class VectorSearchResult(BaseModel):
    """Vector search result."""

    results: list[SearchResultItem]
    total_count: int
    processing_time_ms: float
