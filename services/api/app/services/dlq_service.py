import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dead_letter_queue import DeadLetterQueue
from app.models.ingest_job import IngestJob, IngestJobStatus

logger = logging.getLogger(__name__)


class DLQService:
    """Service for managing dead letter queue operations."""

    @staticmethod
    async def move_to_dlq(
        session: AsyncSession,
        job_id: UUID,
        error_message: str,
        retry_history: Optional[list] = None,
        original_filename: Optional[str] = None,
    ) -> DeadLetterQueue:
        """
        Move a failed job to the dead letter queue.

        Args:
            session: Database session
            job_id: Job ID to move to DLQ
            error_message: Error message explaining the failure
            retry_history: List of retry attempts (optional)
            original_filename: Original filename (optional)

        Returns:
            Created DeadLetterQueue instance
        """
        try:
            # Get the job to extract information
            job = await session.execute(
                select(IngestJob).where(IngestJob.id == job_id)
            )
            job = job.scalar_one_or_none()

            dlq_item = DeadLetterQueue(
                job_id=job_id,
                original_filename=original_filename or (job.filename if job else None),
                error_message=error_message,
                retry_history=retry_history or [],
                failure_count=job.attempts if job else 1,
                status="pending_review",
            )

            session.add(dlq_item)

            # Update job status to failed
            if job:
                job.status = IngestJobStatus.FAILED
                job.error_message = error_message

            await session.commit()
            await session.refresh(dlq_item)

            logger.info(f"Job {job_id} moved to DLQ")
            return dlq_item

        except Exception as e:
            await session.rollback()
            logger.error(f"Error moving job to DLQ: {e}")
            raise

    @staticmethod
    async def get_dlq_item(
        session: AsyncSession,
        dlq_id: UUID,
    ) -> Optional[DeadLetterQueue]:
        """Get a specific DLQ item."""
        try:
            result = await session.execute(
                select(DeadLetterQueue).where(DeadLetterQueue.id == dlq_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error retrieving DLQ item: {e}")
            raise

    @staticmethod
    async def list_dlq(
        session: AsyncSession,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DeadLetterQueue], int]:
        """
        List DLQ items with optional filtering.

        Returns:
            Tuple of (items, total_count)
        """
        try:
            query = select(DeadLetterQueue)

            if status:
                query = query.where(DeadLetterQueue.status == status)

            # Get total count
            count_result = await session.execute(query)
            total = len(count_result.scalars().all())

            # Get paginated results
            query = query.order_by(desc(DeadLetterQueue.created_at)).offset(offset).limit(limit)

            result = await session.execute(query)
            items = result.scalars().all()

            return items, total

        except Exception as e:
            logger.error(f"Error listing DLQ: {e}")
            raise

    @staticmethod
    async def reprocess_dlq_item(
        session: AsyncSession,
        dlq_id: UUID,
    ) -> Optional[IngestJob]:
        """
        Reprocess a DLQ item by re-enqueueing its job.

        Args:
            session: Database session
            dlq_id: DLQ item ID to reprocess

        Returns:
            Updated IngestJob instance
        """
        try:
            # Get DLQ item
            dlq_item = await DLQService.get_dlq_item(session, dlq_id)
            if not dlq_item:
                raise ValueError(f"DLQ item {dlq_id} not found")

            # Get associated job
            job = await session.execute(
                select(IngestJob).where(IngestJob.id == dlq_item.job_id)
            )
            job = job.scalar_one_or_none()

            if not job:
                raise ValueError(f"Job {dlq_item.job_id} not found")

            # Reset job status to pending for retry
            job.status = IngestJobStatus.PENDING
            job.error_message = None
            job.attempts = 0

            # Mark DLQ item as archived
            dlq_item.status = "archived"

            await session.commit()
            await session.refresh(job)

            logger.info(f"DLQ item {dlq_id} reprocessed, job {job.id} set to pending")
            return job

        except Exception as e:
            await session.rollback()
            logger.error(f"Error reprocessing DLQ item: {e}")
            raise

    @staticmethod
    async def delete_dlq_item(
        session: AsyncSession,
        dlq_id: UUID,
    ) -> None:
        """Delete a DLQ item."""
        try:
            dlq_item = await DLQService.get_dlq_item(session, dlq_id)
            if dlq_item:
                await session.delete(dlq_item)
                await session.commit()
                logger.info(f"DLQ item {dlq_id} deleted")
            else:
                raise ValueError(f"DLQ item {dlq_id} not found")

        except Exception as e:
            await session.rollback()
            logger.error(f"Error deleting DLQ item: {e}")
            raise

    @staticmethod
    async def update_dlq_notes(
        session: AsyncSession,
        dlq_id: UUID,
        notes: str,
    ) -> DeadLetterQueue:
        """Update manual notes on a DLQ item."""
        try:
            dlq_item = await DLQService.get_dlq_item(session, dlq_id)
            if not dlq_item:
                raise ValueError(f"DLQ item {dlq_id} not found")

            dlq_item.manual_notes = notes

            await session.commit()
            await session.refresh(dlq_item)

            logger.info(f"DLQ item {dlq_id} notes updated")
            return dlq_item

        except Exception as e:
            await session.rollback()
            logger.error(f"Error updating DLQ notes: {e}")
            raise
