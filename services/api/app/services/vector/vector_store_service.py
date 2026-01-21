"""Service for managing vector embeddings and vector-based operations."""
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.vector_embedding import VectorEmbedding, VectorStatus

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Service for storing, querying, and managing vector embeddings."""

    @staticmethod
    async def upsert_vectors(
        session: AsyncSession,
        file_id: UUID,
        embedding: List[float],
        metadata_tags: Optional[dict] = None,
    ) -> VectorEmbedding:
        """
        Upsert vector embedding for a file.

        Args:
            session: Database session
            file_id: ID of the file being vectorized
            embedding: Embedding vector (1536 dimensions for text-embedding-3-small)
            metadata_tags: Tags to associate with the vector (source, document_type, etc.)

        Returns:
            VectorEmbedding record
        """
        try:
            # Check for existing vector
            query = select(VectorEmbedding).where(VectorEmbedding.file_id == file_id)
            result = await session.execute(query)
            existing = result.scalars().first()

            if existing:
                # Update existing
                existing.embedding = embedding
                existing.metadata_tags = metadata_tags or {}
                existing.vector_status = VectorStatus.GENERATED
                existing.retry_count = 0
                logger.info(f"Updated vector for file {file_id}")
            else:
                # Create new
                existing = VectorEmbedding(
                    file_id=file_id,
                    embedding=embedding,
                    metadata_tags=metadata_tags or {},
                    vector_status=VectorStatus.GENERATED,
                    retry_count=0,
                )
                session.add(existing)
                logger.info(f"Created new vector for file {file_id}")

            await session.commit()
            return existing

        except Exception as e:
            await session.rollback()
            logger.error(f"Error upserting vector: {e}")
            raise

    @staticmethod
    async def mark_failed(
        session: AsyncSession,
        file_id: UUID,
        error_reason: str,
        retry_count: int = 0,
    ) -> None:
        """
        Mark vector embedding as failed.

        Args:
            session: Database session
            file_id: File ID
            error_reason: Reason for failure
            retry_count: Number of retries attempted
        """
        try:
            query = select(VectorEmbedding).where(VectorEmbedding.file_id == file_id)
            result = await session.execute(query)
            vector = result.scalars().first()

            if vector:
                vector.vector_status = VectorStatus.FAILED
                vector.error_reason = error_reason
                vector.retry_count = retry_count
                session.add(vector)
                await session.commit()
                logger.info(f"Marked vector as failed for {file_id}: {error_reason}")

        except Exception as e:
            logger.error(f"Error marking vector as failed: {e}")

    @staticmethod
    async def cascade_delete(session: AsyncSession, file_id: UUID) -> None:
        """
        Delete vectors when silver record is deleted.

        Args:
            session: Database session
            file_id: File ID
        """
        try:
            query = select(VectorEmbedding).where(VectorEmbedding.file_id == file_id)
            result = await session.execute(query)
            vectors = result.scalars().all()

            for vector in vectors:
                await session.delete(vector)

            await session.commit()
            logger.info(f"Cascade deleted {len(vectors)} vectors for file {file_id}")

        except Exception as e:
            logger.error(f"Error cascade deleting vectors: {e}")

    @staticmethod
    async def query_by_tags(
        session: AsyncSession,
        tags_filter: dict,
        limit: int = 100,
    ) -> List[VectorEmbedding]:
        """
        Query vectors by metadata tags.

        Args:
            session: Database session
            tags_filter: Tags to filter by
            limit: Maximum results

        Returns:
            List of matching VectorEmbedding records
        """
        try:
            # For now, return all generated vectors
            # In production, would use pgvector similarity search
            query = select(VectorEmbedding).where(
                VectorEmbedding.vector_status == VectorStatus.GENERATED
            ).limit(limit)
            result = await session.execute(query)
            vectors = result.scalars().all()

            logger.info(f"Found {len(vectors)} vectors matching filter")
            return vectors

        except Exception as e:
            logger.error(f"Error querying vectors: {e}")
            return []
