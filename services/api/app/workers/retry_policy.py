import logging
import random
from typing import Type

logger = logging.getLogger(__name__)


class RetryPolicy:
    """Retry policy for task execution."""

    # Transient exceptions that should be retried
    TRANSIENT_EXCEPTIONS = (
        ConnectionError,
        TimeoutError,
        OSError,
    )

    @staticmethod
    def calculate_backoff(retry_count: int, max_backoff: int = 3600) -> int:
        """Calculate exponential backoff with jitter."""
        # Exponential backoff: 2^retry_count with jitter
        base_delay = min(2**retry_count, max_backoff)
        jitter = random.uniform(0, base_delay * 0.1)
        return int(base_delay + jitter)

    @staticmethod
    def should_retry(exception: Exception, attempt_count: int, max_retries: int = 3) -> bool:
        """Determine if exception is transient and should be retried."""
        if attempt_count >= max_retries:
            logger.info(f"Max retries ({max_retries}) reached for {exception}")
            return False

        # Check if exception is transient
        is_transient = isinstance(exception, RetryPolicy.TRANSIENT_EXCEPTIONS)

        if is_transient:
            logger.info(f"Transient exception detected, will retry: {exception}")
        else:
            logger.warning(f"Permanent exception, no retry: {exception}")

        return is_transient

    @staticmethod
    def dead_letter_queue(job_log_id: str, error_message: str, traceback: str):
        """Move job to dead letter queue for manual review."""
        logger.error(f"Moving job {job_log_id} to DLQ: {error_message}")
        # DLQ creation is handled in the route handlers
        return {"job_log_id": job_log_id, "queued_for_review": True}
