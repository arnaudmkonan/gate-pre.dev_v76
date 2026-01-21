import logging
from datetime import datetime, timezone
from typing import Optional

from openai import OpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embeddings import Embeddings
from app.models.upload_metadata import UploadMetadata
from app.models.vector_store_config import VectorStoreConfig

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Service for managing vector store operations."""

    def __init__(self, config: VectorStoreConfig, openai_api_key: str):
        """Initialize vector store service."""
        self.config = config
        self.client = OpenAI(api_key=openai_api_key)

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text using OpenAI."""
        try:
            response = self.client.embeddings.create(
                model=self.config.embedding_model,
                input=text,
            )

            embedding = response.data[0].embedding

            # Validate dimension
            if len(embedding) != self.config.embedding_dimension:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self.config.embedding_dimension}, "
                    f"got {len(embedding)}"
                )

            logger.info(f"Generated embedding for text chunk (dim: {len(embedding)})")
            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    async def store_embedding(
        self,
        session: AsyncSession,
        upload_metadata_id: str,
        text: str,
        source_file_id: str,
    ) -> Embeddings:
        """Generate and store embedding in database."""
        try:
            # Generate embedding
            embedding_vector = self.generate_embedding(text)

            # Create embedding record
            embedding_record = Embeddings(
                upload_metadata_id=upload_metadata_id,
                vector=embedding_vector,
                content_chunk=text[:2000],  # Store first 2000 chars
                metadata_source_file_id=source_file_id,
                metadata_timestamp=datetime.now(timezone.utc).isoformat(),
                metadata_embedding_model=self.config.embedding_model,
            )

            session.add(embedding_record)
            await session.flush()

            logger.info(f"Embedding stored for file: {source_file_id}")
            return embedding_record

        except Exception as e:
            logger.error(f"Error storing embedding: {e}")
            raise

    async def search_similar(
        self,
        session: AsyncSession,
        query_text: str,
        limit: int = 10,
        namespace: Optional[str] = None,
    ) -> list[dict]:
        """Search for similar embeddings using vector similarity."""
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query_text)

            # Fetch all embeddings and compute similarity in application layer
            # since we're using JSON instead of pgvector
            stmt = select(Embeddings)

            result = await session.execute(stmt)
            all_embeddings = result.scalars().all()

            # Compute cosine similarity for all embeddings
            import numpy as np
            query_vec = np.array(query_embedding)
            results = []

            for embedding in all_embeddings:
                embedding_vec = np.array(embedding.vector)
                # Cosine similarity
                dot_product = np.dot(query_vec, embedding_vec)
                norm_query = np.linalg.norm(query_vec)
                norm_embedding = np.linalg.norm(embedding_vec)
                similarity = dot_product / (norm_query * norm_embedding) if (norm_query * norm_embedding) > 0 else 0

                results.append({
                    "id": embedding.id,
                    "content_chunk": embedding.content_chunk,
                    "metadata_source_file_id": embedding.metadata_source_file_id,
                    "metadata_timestamp": embedding.metadata_timestamp,
                    "metadata_embedding_model": embedding.metadata_embedding_model,
                    "similarity_score": float(similarity),
                })

            # Sort by similarity and limit
            results = sorted(results, key=lambda x: x["similarity_score"], reverse=True)[:limit]

            logger.info(f"Search completed: found {len(results)} similar documents")
            return results

        except Exception as e:
            logger.error(f"Error searching embeddings: {e}")
            raise
