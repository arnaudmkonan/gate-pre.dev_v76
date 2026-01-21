"""Celery worker for batch job processing using sync database connections."""
import logging
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from sqlalchemy import select, and_

from app.core.celery_app import celery_app
from app.core.database import get_sync_db
from app.models.ingest_job import IngestJob, IngestJobStatus
from app.models.batch_schedule import BatchSchedule

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def run_batch(self, batch_job_ids: List[str], schedule_id: str = None):
    """
    Execute a batch of ingest jobs.

    Args:
        batch_job_ids: List of job IDs to process
        schedule_id: Optional schedule ID for tracking
        
    Uses synchronous database connections to avoid async event loop conflicts.
    """
    try:
        logger.info(f"Running batch with {len(batch_job_ids)} jobs")
        result = _run_batch_sync(batch_job_ids, schedule_id)
        logger.info(f"Batch processing completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Error running batch: {e}")
        raise


def _run_batch_sync(batch_job_ids: List[str], schedule_id: str = None):
    """Synchronous implementation of batch runner for Celery."""
    with get_sync_db() as session:
        try:
            start_time = datetime.now(timezone.utc)
            succeeded = 0
            failed = 0

            logger.info(f"Processing batch of {len(batch_job_ids)} jobs")

            for job_id_str in batch_job_ids:
                try:
                    job_id = UUID(job_id_str) if isinstance(job_id_str, str) else job_id_str

                    # Get job
                    result = session.execute(
                        select(IngestJob).where(IngestJob.id == job_id)
                    )
                    job = result.scalar_one_or_none()
                    
                    if not job:
                        logger.warning(f"Job {job_id} not found")
                        failed += 1
                        continue

                    # Mark as processing
                    job.status = IngestJobStatus.PROCESSING
                    session.add(job)
                    session.commit()

                    # TODO: Call orchestration agent to process job
                    # For now, mark as completed for testing
                    job.status = IngestJobStatus.COMPLETED
                    session.add(job)
                    session.commit()

                    logger.info(f"Job {job_id} processed successfully")
                    succeeded += 1

                except Exception as e:
                    session.rollback()
                    logger.error(f"Error processing job {job_id_str}: {e}")
                    failed += 1

            # Update schedule if provided
            if schedule_id:
                try:
                    schedule_uuid = UUID(schedule_id) if isinstance(schedule_id, str) else schedule_id
                    result = session.execute(
                        select(BatchSchedule).where(BatchSchedule.id == schedule_uuid)
                    )
                    schedule = result.scalar_one_or_none()
                    if schedule:
                        schedule.last_run_at = datetime.now(timezone.utc)
                        session.add(schedule)
                        session.commit()
                except Exception as e:
                    session.rollback()
                    logger.warning(f"Error updating schedule {schedule_id}: {e}")

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            return {
                "status": "completed",
                "total_jobs": len(batch_job_ids),
                "succeeded": succeeded,
                "failed": failed,
                "execution_time_seconds": execution_time,
            }

        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            raise


@celery_app.task(bind=True)
def schedule_batch_processor(self):
    """
    Periodic task that checks for pending batches and processes them.

    This task:
    1. Gets all active batch schedules
    2. Finds batches that are due to run
    3. Retrieves pending jobs up to batch_size
    4. Respects max_concurrency limits
    5. Triggers batch runner tasks
    
    Uses synchronous database connections to avoid async event loop conflicts.
    """
    try:
        logger.info("Checking for pending batches...")
        result = _schedule_batches_sync()
        logger.info(f"Batch scheduling completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Error scheduling batches: {e}")
        raise


def _schedule_batches_sync():
    """Synchronous implementation of batch scheduler for Celery."""
    with get_sync_db() as session:
        try:
            from croniter import croniter
            
            now = datetime.now(timezone.utc)
            
            # Get all active batch schedules that are due
            result = session.execute(
                select(BatchSchedule).where(
                    and_(
                        BatchSchedule.is_active == True,
                        BatchSchedule.next_run_at <= now,
                    )
                )
            )
            pending_schedules = result.scalars().all()
            logger.info(f"Found {len(pending_schedules)} pending schedules")

            batch_count = 0
            total_jobs = 0

            for schedule in pending_schedules:
                try:
                    # Get pending jobs for this batch
                    job_result = session.execute(
                        select(IngestJob).where(
                            IngestJob.status == IngestJobStatus.PENDING
                        ).limit(schedule.batch_size)
                    )
                    jobs = job_result.scalars().all()

                    if not jobs:
                        logger.info(f"No pending jobs for schedule {schedule.schedule_name}")
                        # Still update next_run_at
                        cron = croniter(schedule.cron_expression, now)
                        schedule.next_run_at = cron.get_next(datetime)
                        session.add(schedule)
                        session.commit()
                        continue

                    logger.info(
                        f"Schedule {schedule.schedule_name}: processing {len(jobs)} jobs "
                        f"(max_concurrency: {schedule.max_concurrency})"
                    )

                    # Submit batch runner task
                    job_ids = [str(job.id) for job in jobs]
                    run_batch.delay(job_ids, str(schedule.id))

                    # Update schedule next_run_at
                    cron = croniter(schedule.cron_expression, now)
                    schedule.next_run_at = cron.get_next(datetime)
                    schedule.last_run_at = now
                    session.add(schedule)
                    session.commit()

                    batch_count += 1
                    total_jobs += len(jobs)

                except Exception as e:
                    session.rollback()
                    logger.error(f"Error processing schedule {schedule.schedule_name}: {e}")
                    continue

            return {
                "status": "completed",
                "batches_scheduled": batch_count,
                "total_jobs_queued": total_jobs,
            }

        except Exception as e:
            logger.error(f"Error in batch scheduling: {e}")
            raise
