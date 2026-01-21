"""Celery worker for processing pending retries using sync database connections."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select, and_, delete

from app.core.celery_app import celery_app
from app.core.database import get_sync_db
from app.models.ingestion_retry import IngestionRetry, ErrorClassification
from app.models.ingest_job import IngestJob, IngestJobStatus
from app.models.dead_letter_queue import DeadLetterQueue

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def process_pending_retries(self):
    """
    Periodic task to process jobs that are ready for retry.

    This task:
    1. Finds all retries scheduled for now or earlier
    2. Re-queues transient failures back to pending
    3. Moves permanent failures to DLQ
    
    Uses synchronous database connections to avoid async event loop conflicts.
    """
    try:
        logger.info("Processing pending retries...")
        result = _process_retries_sync()
        logger.info(f"Retry processing completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Error processing retries: {e}")
        raise


def _process_retries_sync():
    """Synchronous implementation of retry processing for Celery."""
    with get_sync_db() as session:
        try:
            # Get all pending retries that are due
            now = datetime.now(timezone.utc)
            result = session.execute(
                select(IngestionRetry).where(
                    and_(
                        IngestionRetry.next_retry_at <= now,
                        IngestionRetry.error_classification == ErrorClassification.TRANSIENT,
                    )
                )
            )
            pending_retries = result.scalars().all()
            logger.info(f"Found {len(pending_retries)} pending retries")

            retry_count = 0
            dlq_count = 0

            for retry in pending_retries:
                try:
                    # Get the job
                    job_result = session.execute(
                        select(IngestJob).where(IngestJob.id == retry.job_id)
                    )
                    job = job_result.scalar_one_or_none()
                    
                    if not job:
                        logger.warning(f"Job {retry.job_id} not found for retry {retry.id}")
                        continue

                    # Check if should retry based on attempt count (max 3)
                    should_retry = job.attempts < 3

                    if should_retry:
                        # Reset job to pending status
                        job.status = IngestJobStatus.PENDING
                        session.add(job)

                        # Delete retry record
                        session.execute(
                            delete(IngestionRetry).where(IngestionRetry.id == retry.id)
                        )

                        logger.info(f"Job {retry.job_id} re-queued for retry")
                        retry_count += 1

                    else:
                        # Move to DLQ if max attempts exceeded
                        dlq_item = DeadLetterQueue(
                            job_id=retry.job_id,
                            error_message=f"Max retry attempts exceeded: {retry.error_message}",
                            retry_history=[{"error": retry.error_message, "attempt": retry.attempt_number}],
                            original_filename=job.filename,
                        )
                        session.add(dlq_item)

                        # Delete retry record
                        session.execute(
                            delete(IngestionRetry).where(IngestionRetry.id == retry.id)
                        )

                        logger.info(f"Job {retry.job_id} moved to DLQ")
                        dlq_count += 1

                    # Commit after each job to avoid holding locks too long
                    session.commit()

                except Exception as e:
                    session.rollback()
                    logger.error(f"Error processing retry {retry.id}: {e}")
                    continue

            return {
                "status": "completed",
                "retried": retry_count,
                "moved_to_dlq": dlq_count,
                "total_processed": len(pending_retries),
            }

        except Exception as e:
            logger.error(f"Error in retry processing: {e}")
            raise
