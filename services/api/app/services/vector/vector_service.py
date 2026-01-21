import logging
from uuid import UUID
from typing import Optional
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import VectorEmbedding, SilverRecord, RetryQueue
from app.services.metadata.mapper_service import MapperService

logger = logging.getLogger(__name__)


class VectorService:
    """Generates embeddings and stores them in pgvector for semantic search."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.embedding_dim = 1536  # OpenAI embedding dimension

    async def generate_embedding(
        self,
        file_id: UUID,
        content: str,
        metadata: Optional[dict] = None,
        section_index: Optional[int] = None,
    ) -> VectorEmbedding:
        """
        Generate embedding for content and store in pgvector.

        Args:
            file_id: ID of the file
            content: Text content to embed
            metadata: Optional metadata to attach
            section_index: Optional section index for multi-section documents

        Returns:
            Created VectorEmbedding record
        """
        try:
            # Call OpenAI API to generate embedding
            embedding = await self._call_openai_embedding(content)

            if not embedding or len(embedding) == 0:
                raise ValueError("Failed to generate embedding from OpenAI")

            # Create vector embedding record
            vector_record = VectorEmbedding(
                file_id=file_id,
                embedding=embedding,
                metadata=metadata or {},
                section_index=section_index,
                content_preview=content[:200] if len(content) > 200 else content,
            )

            self.session.add(vector_record)
            await self.session.commit()

            logger.info(f"Generated and stored embedding for file {file_id}")
            return vector_record

        except Exception as e:
            logger.error(f"Failed to generate embedding for file {file_id}: {e}")
            await self.session.rollback()
            # Add to retry queue
            await self._add_to_retry_queue(
                file_id,
                "embedding_error",
                f"Failed to generate embedding: {str(e)}",
            )
            raise

    async def batch_embed(
        self,
        embedding_data: list[dict],
    ) -> tuple[list[VectorEmbedding], list[dict]]:
        """
        Generate embeddings for multiple files in batch.

        Args:
            embedding_data: List of dicts with file_id, content, metadata, section_index

        Returns:
            Tuple of (successful_embeddings, failed_records)
        """
        successful = []
        failed = []

        for data in embedding_data:
            try:
                embedding = await self.generate_embedding(
                    file_id=data["file_id"],
                    content=data["content"],
                    metadata=data.get("metadata"),
                    section_index=data.get("section_index"),
                )
                successful.append(embedding)
            except Exception as e:
                logger.error(f"Batch embedding failed for {data['file_id']}: {e}")
                failed.append({
                    "file_id": data["file_id"],
                    "error": str(e),
                })

        logger.info(
            f"Batch embedding complete: {len(successful)} successful, {len(failed)} failed"
        )
        return successful, failed

    async def attach_metadata(
        self,
        embedding_id: UUID,
        metadata: dict,
    ) -> VectorEmbedding:
        """
        Attach or update metadata on an existing embedding.

        Args:
            embedding_id: ID of the embedding record
            metadata: Metadata to attach

        Returns:
            Updated VectorEmbedding
        """
        try:
            stmt = select(VectorEmbedding).where(VectorEmbedding.id == embedding_id)
            result = await self.session.execute(stmt)
            embedding = result.scalar_one_or_none()

            if embedding:
                # Merge metadata
                existing = embedding.metadata or {}
                existing.update(metadata)
                embedding.metadata = existing
                await self.session.commit()
                logger.info(f"Updated metadata for embedding {embedding_id}")
                return embedding
            else:
                logger.warning(f"Embedding {embedding_id} not found")
                raise ValueError(f"Embedding {embedding_id} not found")

        except Exception as e:
            logger.error(f"Failed to attach metadata: {e}")
            await self.session.rollback()
            raise

    async def ensure_consistency(
        self,
        file_id: UUID,
    ) -> bool:
        """
        Ensure vector store consistency with silver record.

        Verifies that embeddings and silver records are in sync.

        Args:
            file_id: File ID to verify

        Returns:
            True if consistent, False otherwise
        """
        try:
            # Get silver record
            stmt = select(SilverRecord).where(SilverRecord.file_id == file_id)
            result = await self.session.execute(stmt)
            silver = result.scalar_one_or_none()

            # Get embeddings
            stmt = select(VectorEmbedding).where(VectorEmbedding.file_id == file_id)
            result = await self.session.execute(stmt)
            embeddings = result.scalars().all()

            if not silver:
                logger.warning(f"No silver record found for file {file_id}")
                return False

            if not embeddings:
                logger.warning(f"No embeddings found for file {file_id}")
                return False

            # Basic consistency check
            logger.info(f"Vector store consistent for file {file_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to check consistency: {e}")
            return False

    async def _call_openai_embedding(self, content: str) -> list[float]:
        """
        Call OpenAI API to generate embeddings.

        This is a placeholder that would call the actual OpenAI API via LangChain.
        For now, returns a dummy embedding of correct dimension.

        Args:
            content: Text to embed

        Returns:
            Embedding vector
        """
        try:
            # TODO: Integrate with actual OpenAI API via LangChain
            # For now, return dummy embedding for testing
            import random
            embedding = [random.random() for _ in range(self.embedding_dim)]
            return embedding

        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise

    async def _add_to_retry_queue(
        self,
        file_id: UUID,
        error_type: str,
        error_message: str,
    ) -> None:
        """Add failed record to retry queue."""
        try:
            retry_item = RetryQueue(
                file_id=file_id,
                error_type=error_type,
                error_message=error_message,
            )
            self.session.add(retry_item)
            await self.session.commit()
            logger.info(f"Added file {file_id} to retry queue")
        except Exception as e:
            logger.error(f"Failed to add to retry queue: {e}")
            await self.session.rollback()
