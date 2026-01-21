import logging
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import DLQEntry

logger = logging.getLogger(__name__)


class RetryManager:
    """Manages retry logic with exponential backoff and jitter."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.base_delay = 2  # seconds
        self.max_attempts = 3

    def calculate_backoff(self, retry_count: int) -> float:
        """
        Calculate exponential backoff with jitter.

        Args:
            retry_count: Current retry attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: 2^retry_count
        delay = self.base_delay ** retry_count
        # Add jitter: ±25% randomness
        jitter = delay * 0.25
        actual_delay = delay + random.uniform(-jitter, jitter)
        return max(actual_delay, 1)  # Minimum 1 second

    async def schedule_retry(
        self,
        dlq_entry_id: str,
        retry_count: int,
    ) -> bool:
        """
        Schedule retry for a DLQ entry.

        Args:
            dlq_entry_id: DLQ entry ID
            retry_count: Current retry count

        Returns:
            True if scheduled, False if max retries exceeded
        """
        if retry_count >= self.max_attempts:
            logger.warning(f"DLQ entry {dlq_entry_id} exceeded max retries ({self.max_attempts})")
            return False

        delay = self.calculate_backoff(retry_count)
        logger.info(f"Scheduled retry for DLQ entry {dlq_entry_id} in {delay:.2f}s (attempt {retry_count + 1}/{self.max_attempts})")

        # In production, would schedule Celery task with countdown
        # For now, just return success
        return True

    async def process_retries(self) -> dict:
        """
        Process dead-letter queue items and schedule retries.

        Returns:
            Results dict with retry counts
        """
        try:
            # Get all DLQ entries with retry_count < max_retries
            stmt = select(DLQEntry).where(
                DLQEntry.retry_count < DLQEntry.max_retries
            ).limit(100)

            result = await self.session.execute(stmt)
            dlq_entries = result.scalars().all()

            retried = 0
            permanent_failures = 0

            for entry in dlq_entries:
                if entry.retry_count < self.max_attempts:
                    scheduled = await self.schedule_retry(str(entry.id), entry.retry_count)
                    if scheduled:
                        entry.retry_count += 1
                        await self.session.commit()
                        retried += 1
                        logger.info(f"Retry scheduled for DLQ entry {entry.id}")
                else:
                    permanent_failures += 1
                    logger.error(f"DLQ entry {entry.id} marked as permanent failure")

            logger.info(f"DLQ processing: {retried} retried, {permanent_failures} permanent failures")

            return {
                "retried_count": retried,
                "permanent_failure_count": permanent_failures,
                "total_processed": retried + permanent_failures,
            }

        except Exception as e:
            logger.error(f"Failed to process DLQ retries: {e}")
            return {
                "error": str(e),
                "retried_count": 0,
                "permanent_failure_count": 0,
            }
