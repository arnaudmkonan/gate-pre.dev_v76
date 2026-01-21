import logging
from uuid import UUID
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models import Batch, DLQEntry, RawFile
from app.services.scheduler.retries import RetryManager

logger = logging.getLogger(__name__)


class BatchVectorizerScheduler:
    """Schedules and manages batch vectorization jobs."""

    def __init__(
        self,
        session: AsyncSession,
        batch_size: int = 100,
        worker_concurrency: int = 4,
    ):
        self.session = session
        self.batch_size = batch_size
        self.worker_concurrency = worker_concurrency
        self.retry_manager = RetryManager(session)

    async def dequeue_batch(self) -> Batch | None:
        """
        Dequeue next batch from pending queue.

        Returns:
            Next pending batch or None
        """
        try:
            stmt = select(Batch).where(
                Batch.status == "pending"
            ).limit(1)

            result = await self.session.execute(stmt)
            batch = result.scalar_one_or_none()

            if batch:
                # Mark as processing
                batch.status = "processing"
                await self.session.commit()
                logger.info(f"Dequeued batch {batch.id} for processing")

            return batch

        except Exception as e:
            logger.error(f"Failed to dequeue batch: {e}")
            return None

    async def mark_processed(
        self,
        batch_id: UUID,
        processed_count: int,
        failed_count: int,
    ) -> None:
        """
        Mark batch as processed with completion stats.

        Args:
            batch_id: Batch ID
            processed_count: Number of successfully processed items
            failed_count: Number of failed items
        """
        try:
            stmt = select(Batch).where(Batch.id == batch_id)
            result = await self.session.execute(stmt)
            batch = result.scalar_one_or_none()

            if batch:
                batch.processed_count = processed_count
                batch.failed_count = failed_count
                batch.status = "completed" if failed_count == 0 else "partial"
                await self.session.commit()
                logger.info(
                    f"Marked batch {batch_id} as {batch.status}: "
                    f"{processed_count} processed, {failed_count} failed"
                )

        except Exception as e:
            logger.error(f"Failed to mark batch as processed: {e}")

    async def mark_failed(
        self,
        batch_id: UUID,
        error_reason: str,
    ) -> None:
        """
        Mark batch as failed.

        Args:
            batch_id: Batch ID
            error_reason: Reason for failure
        """
        try:
            stmt = select(Batch).where(Batch.id == batch_id)
            result = await self.session.execute(stmt)
            batch = result.scalar_one_or_none()

            if batch:
                batch.status = "failed"
                await self.session.commit()
                logger.error(f"Marked batch {batch_id} as failed: {error_reason}")

        except Exception as e:
            logger.error(f"Failed to mark batch as failed: {e}")

    async def get_batch_progress(self, batch_id: UUID) -> dict:
        """
        Get progress metrics for a batch.

        Args:
            batch_id: Batch ID

        Returns:
            Progress dict with counts and ETA
        """
        try:
            stmt = select(Batch).where(Batch.id == batch_id)
            result = await self.session.execute(stmt)
            batch = result.scalar_one_or_none()

            if not batch:
                return {"error": "Batch not found"}

            # Calculate ETA if still processing
            eta = None
            if batch.status == "processing" and batch.total_count > 0:
                # Use timezone-aware datetime for consistency
                now = datetime.now(timezone.utc)
                created_at = batch.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                elapsed = (now - created_at).total_seconds()
                if batch.processed_count > 0 and elapsed > 0:
                    rate = batch.processed_count / elapsed
                    remaining = batch.total_count - batch.processed_count
                    eta_seconds = remaining / rate if rate > 0 else 0
                    eta = now + timedelta(seconds=eta_seconds)

            return {
                "batch_id": str(batch.id),
                "status": batch.status,
                "processed_count": batch.processed_count,
                "failed_count": batch.failed_count,
                "total_count": batch.total_count,
                "eta": eta.isoformat() if eta else None,
                "created_at": batch.created_at.isoformat(),
                "updated_at": batch.updated_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get batch progress: {e}")
            return {"error": str(e)}

    async def add_to_dlq(
        self,
        batch_id: UUID | None,
        file_id: UUID,
        error_reason: str,
        retry_count: int = 0,
    ) -> None:
        """
        Add failed item to dead-letter queue.

        Args:
            batch_id: Associated batch ID
            file_id: File ID that failed
            error_reason: Reason for failure
            retry_count: Current retry count
        """
        try:
            dlq_entry = DLQEntry(
                batch_id=batch_id,
                file_id=file_id,
                error_reason=error_reason,
                retry_count=retry_count,
                max_retries=3,
            )

            self.session.add(dlq_entry)
            await self.session.commit()
            logger.info(f"Added file {file_id} to DLQ: {error_reason}")

        except Exception as e:
            logger.error(f"Failed to add to DLQ: {e}")
            await self.session.rollback()

    async def process_dlq_retries(self) -> dict:
        """
        Process dead-letter queue items and retry failed items.

        Returns:
            Results dict with retry counts
        """
        return await self.retry_manager.process_retries()

    async def recover_from_crash(self) -> None:
        """
        Recover batch state after scheduler crash.

        Marks stale "processing" batches as failed if timeout exceeded.
        """
        try:
            timeout_minutes = 30
            timeout_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)

            # Find processing batches that haven't updated recently
            stmt = select(Batch).where(
                (Batch.status == "processing") &
                (Batch.updated_at < timeout_time)
            )

            result = await self.session.execute(stmt)
            stale_batches = result.scalars().all()

            for batch in stale_batches:
                batch.status = "failed"
                await self.session.commit()
                logger.warning(f"Recovered from crash: marked batch {batch.id} as failed (timeout)")

        except Exception as e:
            logger.error(f"Failed to recover from crash: {e}")
