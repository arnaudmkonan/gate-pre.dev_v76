"""Service for triggering vectorization of silver records."""

import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SilverRecord, VectorEmbedding, RetryQueue
from app.services.vector.vector_service import VectorService

logger = logging.getLogger(__name__)


class VectorizationTriggerService:
    """Service for triggering and managing vectorization of silver records."""

    @staticmethod
    async def trigger_vectorization(
        session: AsyncSession,
        silver_record_id: UUID,
    ) -> Dict[str, Any]:
        """
        Trigger vectorization for a single silver record.

        Queues the record for embedding generation if not already vectorized.

        Args:
            session: Async database session
            silver_record_id: ID of the silver record

        Returns:
            Dict with vectorization status:
            {
                "record_id": UUID,
                "status": "queued|already_embedded|failed",
                "embedding_id": UUID (if already embedded),
                "message": str,
            }
        """
        try:
            # Fetch silver record
            stmt = select(SilverRecord).where(SilverRecord.id == silver_record_id)
            result = await session.execute(stmt)
            silver_record = result.scalar_one_or_none()

            if not silver_record:
                return {
                    "record_id": silver_record_id,
                    "status": "failed",
                    "message": f"Silver record {silver_record_id} not found",
                }

            # Check if already vectorized
            stmt = select(VectorEmbedding).where(
                VectorEmbedding.file_id == silver_record.file_id
            )
            result = await session.execute(stmt)
            existing_embedding = result.scalar_one_or_none()

            if existing_embedding:
                return {
                    "record_id": silver_record_id,
                    "status": "already_embedded",
                    "embedding_id": existing_embedding.id,
                    "message": f"Record {silver_record_id} already has embedding",
                }

            # Queue for vectorization
            await VectorizationTriggerService._queue_for_vectorization(
                session, silver_record
            )

            return {
                "record_id": silver_record_id,
                "status": "queued",
                "message": f"Record {silver_record_id} queued for vectorization",
            }

        except Exception as e:
            logger.error(f"Failed to trigger vectorization for {silver_record_id}: {e}")
            return {
                "record_id": silver_record_id,
                "status": "failed",
                "message": str(e),
            }

    @staticmethod
    async def trigger_batch_vectorization(
        session: AsyncSession,
        batch_id: UUID,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Trigger vectorization for all records in a batch.

        Args:
            session: Async database session
            batch_id: ID of the batch
            limit: Optional limit on number of records to process

        Returns:
            Dict with batch vectorization summary:
            {
                "batch_id": UUID,
                "total_records": int,
                "queued_count": int,
                "already_embedded_count": int,
                "failed_count": int,
                "processing_time_ms": int,
            }
        """
        import time
        start_time = time.time()

        try:
            # Fetch all records in batch
            stmt = select(SilverRecord).where(SilverRecord.batch_id == batch_id)
            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            silver_records = result.scalars().all()

            if not silver_records:
                return {
                    "batch_id": batch_id,
                    "total_records": 0,
                    "queued_count": 0,
                    "already_embedded_count": 0,
                    "failed_count": 0,
                    "processing_time_ms": 0,
                }

            queued_count = 0
            already_embedded_count = 0
            failed_count = 0

            for record in silver_records:
                try:
                    # Check if already vectorized
                    stmt = select(VectorEmbedding).where(
                        VectorEmbedding.file_id == record.file_id
                    )
                    result = await session.execute(stmt)
                    existing_embedding = result.scalar_one_or_none()

                    if existing_embedding:
                        already_embedded_count += 1
                        continue

                    # Queue for vectorization
                    await VectorizationTriggerService._queue_for_vectorization(
                        session, record
                    )
                    queued_count += 1

                except Exception as e:
                    logger.error(
                        f"Failed to queue record {record.id} for vectorization: {e}"
                    )
                    failed_count += 1

            await session.commit()
            logger.info(
                f"Batch vectorization triggered: batch_id={batch_id}, "
                f"queued={queued_count}, already_embedded={already_embedded_count}, "
                f"failed={failed_count}"
            )

        except Exception as e:
            logger.error(f"Failed to trigger batch vectorization for {batch_id}: {e}")
            await session.rollback()
            return {
                "batch_id": batch_id,
                "total_records": 0,
                "queued_count": 0,
                "already_embedded_count": 0,
                "failed_count": 1,
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "error": str(e),
            }

        processing_time_ms = int((time.time() - start_time) * 1000)

        return {
            "batch_id": batch_id,
            "total_records": len(silver_records),
            "queued_count": queued_count,
            "already_embedded_count": already_embedded_count,
            "failed_count": failed_count,
            "processing_time_ms": processing_time_ms,
        }

    @staticmethod
    async def trigger_file_vectorization(
        session: AsyncSession,
        file_id: UUID,
    ) -> Dict[str, Any]:
        """
        Trigger vectorization for a specific file's silver record.

        Args:
            session: Async database session
            file_id: ID of the file

        Returns:
            Dict with vectorization status
        """
        try:
            # Fetch silver record for file
            stmt = select(SilverRecord).where(SilverRecord.file_id == file_id)
            result = await session.execute(stmt)
            silver_record = result.scalar_one_or_none()

            if not silver_record:
                return {
                    "file_id": file_id,
                    "status": "failed",
                    "message": f"No silver record found for file {file_id}",
                }

            # Check if already vectorized
            stmt = select(VectorEmbedding).where(VectorEmbedding.file_id == file_id)
            result = await session.execute(stmt)
            existing_embedding = result.scalar_one_or_none()

            if existing_embedding:
                return {
                    "file_id": file_id,
                    "status": "already_embedded",
                    "embedding_id": existing_embedding.id,
                }

            # Queue for vectorization
            await VectorizationTriggerService._queue_for_vectorization(
                session, silver_record
            )

            return {
                "file_id": file_id,
                "status": "queued",
                "message": f"File {file_id} queued for vectorization",
            }

        except Exception as e:
            logger.error(f"Failed to trigger vectorization for file {file_id}: {e}")
            return {
                "file_id": file_id,
                "status": "failed",
                "message": str(e),
            }

    @staticmethod
    async def get_vectorization_status(
        session: AsyncSession,
        silver_record_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get vectorization status for a silver record.

        Args:
            session: Async database session
            silver_record_id: ID of the silver record

        Returns:
            Dict with vectorization status
        """
        try:
            stmt = select(SilverRecord).where(SilverRecord.id == silver_record_id)
            result = await session.execute(stmt)
            silver_record = result.scalar_one_or_none()

            if not silver_record:
                return {
                    "record_id": silver_record_id,
                    "status": "not_found",
                }

            # Check for embeddings
            stmt = select(VectorEmbedding).where(
                VectorEmbedding.file_id == silver_record.file_id
            )
            result = await session.execute(stmt)
            embeddings = result.scalars().all()

            return {
                "record_id": silver_record_id,
                "file_id": silver_record.file_id,
                "status": "embedded" if embeddings else "pending",
                "embedding_count": len(embeddings),
                "embeddings": [
                    {
                        "id": e.id,
                        "created_at": e.created_at,
                        "section_index": e.section_index,
                    }
                    for e in embeddings
                ],
            }

        except Exception as e:
            logger.error(f"Failed to get vectorization status: {e}")
            return {
                "record_id": silver_record_id,
                "status": "error",
                "message": str(e),
            }

    @staticmethod
    async def _queue_for_vectorization(
        session: AsyncSession,
        silver_record: SilverRecord,
    ) -> None:
        """
        Internal method to queue a record for vectorization.

        In production, this would enqueue to a task queue (Celery, etc.).
        For now, we just update the record status.

        Args:
            session: Async database session
            silver_record: The silver record to queue
        """
        try:
            # Update record status to pending vectorization
            stmt = (
                update(SilverRecord)
                .where(SilverRecord.id == silver_record.id)
                .values(processing_status="vectorization_pending")
            )
            await session.execute(stmt)
            await session.commit()

            logger.info(
                f"Queued silver record {silver_record.id} "
                f"(file_id={silver_record.file_id}) for vectorization"
            )

        except Exception as e:
            logger.error(f"Failed to queue record for vectorization: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def get_pending_vectorization(
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[SilverRecord], int]:
        """
        Get pending records that need vectorization.

        Args:
            session: Async database session
            limit: Max records to return
            offset: Offset for pagination

        Returns:
            Tuple of (records, total_count)
        """
        # Get count
        stmt = select(SilverRecord).where(
            SilverRecord.processing_status == "vectorization_pending"
        )
        count_result = await session.execute(stmt)
        total = len(count_result.scalars().all())

        # Get paginated results
        stmt = (
            select(SilverRecord)
            .where(SilverRecord.processing_status == "vectorization_pending")
            .order_by(SilverRecord.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        records = result.scalars().all()

        return records, total
