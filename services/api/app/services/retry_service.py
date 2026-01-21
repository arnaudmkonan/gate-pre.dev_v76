import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion_retry import IngestionRetry, ErrorClassification
from app.models.ingest_job import IngestJob, IngestJobStatus

logger = logging.getLogger(__name__)


class RetryService:
    """Service for managing retry logic and backoff."""

    # Transient errors (can be retried)
    TRANSIENT_ERROR_KEYWORDS = [
        "timeout",
        "connection",
        "network",
        "503",
        "502",
        "429",
        "temporarily unavailable",
    ]

    # Permanent errors (move to DLQ)
    PERMANENT_ERROR_KEYWORDS = [
        "unsupported format",
        "invalid file",
        "corrupted",
        "403",
        "401",
        "not found",
        "invalid request",
    ]

    @staticmethod
    def classify_error(error_message: str) -> ErrorClassification:
        """
        Classify error as transient or permanent.

        Args:
            error_message: Error message to classify

        Returns:
            ErrorClassification enum
        """
        error_lower = error_message.lower()

        for keyword in RetryService.PERMANENT_ERROR_KEYWORDS:
            if keyword in error_lower:
                return ErrorClassification.PERMANENT

        for keyword in RetryService.TRANSIENT_ERROR_KEYWORDS:
            if keyword in error_lower:
                return ErrorClassification.TRANSIENT

        # Default to transient for unknown errors
        return ErrorClassification.TRANSIENT

    @staticmethod
    def calculate_backoff(attempt: int, base_delay: int = 60, max_delay: int = 3600) -> int:
        """
        Calculate exponential backoff with jitter.

        Args:
            attempt: Attempt number (1-indexed)
            base_delay: Base delay in seconds (default 60)
            max_delay: Maximum delay in seconds (default 3600)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: 60, 120, 240, 480, ... (capped at max_delay)
        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)

        # Add random jitter (±10%)
        jitter = int(delay * 0.1 * random.random())
        return delay + jitter

    @staticmethod
    async def create_retry(
        session: AsyncSession,
        job_id: UUID,
        error_message: str,
        attempt_number: int,
    ) -> IngestionRetry:
        """
        Create a retry record for a failed job.

        Args:
            session: Database session
            job_id: Job ID to retry
            error_message: Error message
            attempt_number: Current attempt number

        Returns:
            Created IngestionRetry instance
        """
        try:
            classification = RetryService.classify_error(error_message)
            backoff_delay = RetryService.calculate_backoff(attempt_number)
            jitter = backoff_delay - (attempt_number * 60)

            next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_delay)

            retry = IngestionRetry(
                job_id=job_id,
                attempt_number=attempt_number,
                error_message=error_message,
                error_classification=classification,
                retry_delay=backoff_delay,
                next_retry_at=next_retry_at,
                retry_jitter=jitter,
            )

            session.add(retry)
            await session.commit()
            await session.refresh(retry)

            logger.info(
                f"Retry created for job {job_id}: attempt {attempt_number}, "
                f"next_retry_at {next_retry_at}, classification {classification}"
            )
            return retry

        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating retry: {e}")
            raise

    @staticmethod
    async def should_retry(
        session: AsyncSession,
        job_id: UUID,
        max_attempts: int = 3,
    ) -> bool:
        """
        Check if a job should be retried based on attempt count.

        Args:
            session: Database session
            job_id: Job ID to check
            max_attempts: Maximum number of attempts allowed

        Returns:
            True if should retry, False otherwise
        """
        try:
            job = await session.execute(
                select(IngestJob).where(IngestJob.id == job_id)
            )
            job = job.scalar_one_or_none()

            if not job:
                return False

            return job.attempts < max_attempts

        except Exception as e:
            logger.error(f"Error checking retry eligibility: {e}")
            return False

    @staticmethod
    async def get_pending_retries(session: AsyncSession) -> list[IngestionRetry]:
        """Get all retries that are ready to execute."""
        try:
            now = datetime.now(timezone.utc)
            result = await session.execute(
                select(IngestionRetry).where(
                    and_(
                        IngestionRetry.next_retry_at <= now,
                        IngestionRetry.error_classification == ErrorClassification.TRANSIENT,
                    )
                )
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting pending retries: {e}")
            raise

    @staticmethod
    async def mark_retry_attempted(
        session: AsyncSession,
        retry_id: UUID,
    ) -> None:
        """Mark a retry as attempted (delete it after re-enqueueing)."""
        try:
            retry = await session.execute(
                select(IngestionRetry).where(IngestionRetry.id == retry_id)
            )
            retry = retry.scalar_one_or_none()

            if retry:
                await session.delete(retry)
                await session.commit()
                logger.info(f"Retry record {retry_id} marked as attempted")

        except Exception as e:
            await session.rollback()
            logger.error(f"Error marking retry as attempted: {e}")
            raise

    @staticmethod
    async def check_retry_prerequisites(
        session: AsyncSession, job_id: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a job can be retried for UI Story 3.

        Args:
            session: Database session
            job_id: Job ID to check

        Returns:
            Tuple of (can_retry: bool, reason_if_not: Optional[str])
        """
        try:
            logger.info(f"[PREREQUISITE CHECK] Starting validation for job_id={job_id}")

            # Prerequisite 1: Job exists
            logger.info(f"[PREREQUISITE 1] Checking if job exists with UUID: {job_id}")
            job = await session.execute(
                select(IngestJob).where(IngestJob.id == UUID(job_id))
            )
            job = job.scalar_one_or_none()

            if not job:
                logger.error(f"[PREREQUISITE 1 FAILED] Job {job_id} not found in database")
                return False, f"Job {job_id} not found"

            logger.info(f"[PREREQUISITE 1 PASSED] Job found: id={job.id}, filename={job.filename}, status={job.status}")

            # Prerequisite 2: Job has raw file (storage_path available)
            logger.info(f"[PREREQUISITE 2] Checking if job has storage_path. Current value: storage_path={job.storage_path}")
            if not job.storage_path:
                logger.error(f"[PREREQUISITE 2 FAILED] Job {job_id} has no storage_path available")
                return False, "Raw file not available for this job"

            logger.info(f"[PREREQUISITE 2 PASSED] Storage path exists: {job.storage_path}")

            # Prerequisite 3: Job can be retried regardless of status
            logger.info(f"[PREREQUISITE 3] Job status check: status={job.status}, attempts={job.attempts}")
            logger.info(f"[PREREQUISITE 3 PASSED] Job can be retried. All prerequisites met.")

            return True, None

        except ValueError as e:
            logger.error(f"[PREREQUISITE CHECK FAILED] Invalid UUID format: job_id={job_id}, error={e}")
            return False, f"Invalid job ID format: {e}"
        except Exception as e:
            logger.error(f"[PREREQUISITE CHECK FAILED] Unexpected error: job_id={job_id}, error={e}", exc_info=True)
            return False, str(e)

    @staticmethod
    async def retry_single_job(
        session: AsyncSession,
        job_id: str,
        mode_override: Optional[str] = None,
        mapping_override: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        Retry a single failed job for UI Story 3.

        Args:
            session: Database session
            job_id: Job ID to retry
            mode_override: Optional mode override
            mapping_override: Optional mapping override

        Returns:
            Dict with retry details or None if failed
        """
        try:
            # Check prerequisites
            can_retry, reason = await RetryService.check_retry_prerequisites(session, job_id)
            if not can_retry:
                logger.warning(f"Cannot retry job {job_id}: {reason}")
                return None

            # Get original job
            original_job = await session.execute(
                select(IngestJob).where(IngestJob.id == UUID(job_id))
            )
            original_job = original_job.scalar_one_or_none()
            if not original_job:
                return None

            # Create new ingest job from original
            new_job = IngestJob(
                filename=original_job.filename,
                file_type=original_job.file_type,
                size=original_job.size,
                storage_path=original_job.storage_path,
                status=IngestJobStatus.PENDING,
                uploader_id=original_job.uploader_id,
                mode=mode_override or original_job.mode,
                batch_size=original_job.batch_size,
                mapping_config=original_job.mapping_config,
            )

            session.add(new_job)
            await session.commit()
            await session.refresh(new_job)

            logger.info(f"Job {job_id} retried successfully, new job_id={new_job.id}")

            return {
                "job_id": job_id,
                "retry_id": str(new_job.id),  # The retry is represented as the new job ID
                "new_job_id": str(new_job.id),
                "status": "queued",
                "message": f"Job retried with new job ID {new_job.id}",
            }

        except Exception as e:
            await session.rollback()
            logger.error(f"Error retrying job {job_id}: {e}")
            raise

    @staticmethod
    async def retry_bulk_jobs(
        session: AsyncSession,
        job_ids: list[str],
        mode_override: Optional[str] = None,
        mapping_override: Optional[dict] = None,
    ) -> dict:
        """
        Retry multiple failed jobs (max 100) for UI Story 3.

        Args:
            session: Database session
            job_ids: List of job IDs to retry (max 100)
            mode_override: Optional mode override
            mapping_override: Optional mapping override

        Returns:
            Dict with results
        """
        if len(job_ids) > 100:
            raise ValueError("Cannot retry more than 100 jobs at once")

        results = []
        errors = []
        retried_count = 0
        failed_count = 0

        for job_id in job_ids:
            try:
                retry_result = await RetryService.retry_single_job(
                    session=session,
                    job_id=job_id,
                    mode_override=mode_override,
                    mapping_override=mapping_override,
                )

                if retry_result:
                    results.append(retry_result)
                    retried_count += 1
                else:
                    failed_count += 1
                    errors.append({
                        "job_id": job_id,
                        "error": "Could not retry job (prerequisites not met)",
                    })

            except Exception as e:
                failed_count += 1
                errors.append({
                    "job_id": job_id,
                    "error": str(e),
                })
                logger.warning(f"Error retrying job {job_id}: {e}")

        return {
            "retried_count": retried_count,
            "failed_count": failed_count,
            "results": results,
            "errors": errors if errors else None,
        }
