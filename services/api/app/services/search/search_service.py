import logging
import time
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import RawVector, SilverMetadata
from app.lib.embeddings import TenantAwareEmbeddingClient

logger = logging.getLogger(__name__)


class SearchService:
    """Semantic vector search service."""

    def __init__(self, session: AsyncSession, tenant_id: str = "default"):
        self.session = session
        self.embedding_client = TenantAwareEmbeddingClient(tenant_id)

    async def search(
        self,
        query: str = None,
        embedding: list[float] = None,
        filters: dict = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict:
        """
        Perform semantic vector search with optional filtering.

        Args:
            query: Text query for server-side embedding
            embedding: Pre-computed embedding vector
            filters: Metadata filters (date_range, document_type, etc.)
            limit: Max results to return (1-100)
            offset: Pagination offset

        Returns:
            Search results dict with results list and metadata

        Raises:
            ValueError: If input is invalid
        """
        start_time = time.time()

        try:
            # Validate input
            if not query and not embedding:
                raise ValueError("Either query or embedding must be provided")

            if query and embedding:
                raise ValueError("Provide either query OR embedding, not both")

            # Generate embedding if needed
            if query:
                if not query.strip():
                    raise ValueError("Query cannot be empty")

                try:
                    embedding = await self._generate_embedding(query)
                except Exception as e:
                    logger.error(f"Failed to generate embedding: {e}")
                    raise

            # Validate embedding
            await self._validate_embedding(embedding)

            # Get all vectors (in production would use pgvector similarity search)
            stmt = select(RawVector).limit(1000)
            result = await self.session.execute(stmt)
            all_vectors = result.scalars().all()

            # Compute similarity scores
            results = []
            for vector_record in all_vectors:
                similarity = self._cosine_similarity(embedding, vector_record.vector)

                # Apply filters
                if filters and not self._apply_filters(vector_record, filters):
                    continue

                # Get associated silver metadata
                metadata = await self._get_silver_metadata(vector_record.file_id)

                results.append({
                    "file_id": vector_record.file_id,
                    "similarity_score": similarity,
                    "vector_id": vector_record.id,
                    "metadata": metadata or {},
                    "explainability": {
                        "similarity_score": similarity,
                        "index_shard": "primary",
                        "retriever_version": "1.0.0",
                    }
                })

            # Sort by similarity
            results.sort(key=lambda x: x["similarity_score"], reverse=True)

            # Apply pagination
            total_count = len(results)
            paginated = results[offset:offset + limit]

            processing_time_ms = (time.time() - start_time) * 1000

            logger.info(f"Search completed in {processing_time_ms:.2f}ms: {len(paginated)} results")

            return {
                "results": paginated,
                "total_count": total_count,
                "processing_time_ms": processing_time_ms,
                "limit": limit,
                "offset": offset,
            }

        except ValueError as e:
            logger.warning(f"Search validation error: {e}")
            raise
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    async def _generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        try:
            # Use embedding client to generate embedding
            embedding, error = await self.embedding_client.generate_embedding(text)
            if error:
                raise ValueError(f"Failed to generate embedding: {error}")
            logger.info(f"Generated embedding for text: {text[:50]}...")
            return embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    async def _validate_embedding(self, embedding: list[float]) -> bool:
        """
        Validate embedding vector.

        Args:
            embedding: Embedding vector

        Returns:
            True if valid

        Raises:
            ValueError: If invalid
        """
        if not isinstance(embedding, list):
            raise ValueError("Embedding must be a list")

        if len(embedding) != 1536:  # OpenAI embedding dimension
            raise ValueError(f"Embedding dimension mismatch: expected 1536, got {len(embedding)}")

        if not all(isinstance(x, (int, float)) for x in embedding):
            raise ValueError("Embedding values must be numeric")

        return True

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            a: First vector
            b: Second vector

        Returns:
            Similarity score (0-1)
        """
        import math

        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        magnitude_a = math.sqrt(sum(x * x for x in a))
        magnitude_b = math.sqrt(sum(x * x for x in b))

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0

        return dot_product / (magnitude_a * magnitude_b)

    def _apply_filters(self, vector_record: "RawVector", filters: dict) -> bool:
        """
        Apply metadata filters to a vector record.

        Args:
            vector_record: Vector record to filter
            filters: Filter criteria

        Returns:
            True if record passes filters, False otherwise
        """
        if not filters:
            return True

        # Check document_type filter
        if "document_type" in filters:
            # Would need to check associated silver metadata
            pass

        # Check date_range filter
        if "date_range" in filters:
            date_range = filters["date_range"]
            # Would parse and check dates
            pass

        return True

    async def _get_silver_metadata(self, file_id: UUID) -> dict | None:
        """
        Get silver metadata for a file.

        Args:
            file_id: File ID

        Returns:
            Metadata dict or None
        """
        try:
            stmt = select(SilverMetadata).where(SilverMetadata.file_id == file_id).limit(1)
            result = await self.session.execute(stmt)
            metadata = result.scalar_one_or_none()

            if metadata:
                return {
                    "title": metadata.title,
                    "author": metadata.author,
                    "date": metadata.date.isoformat() if metadata.date else None,
                    "document_type": metadata.document_type,
                    "custom": metadata.metadata_json or {},
                }

            return None

        except Exception as e:
            logger.error(f"Failed to get silver metadata: {e}")
            return None
