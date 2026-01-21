import json
import logging
from datetime import datetime, timezone

from celery import Task
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.job_log import JobLog, JobStatus
from app.sentry_init import capture_exception, capture_message

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """Task class with callback support for logging and error tracking."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {task_id} failed: {exc}")
        capture_exception(exc, task_id=task_id, task_name=self.name)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        logger.warning(f"Task {task_id} retrying: {exc}")
        capture_message(f"Task {task_id} retrying: {str(exc)}", level="warning", task_id=task_id)

    def on_success(self, result, task_id, args, kwargs):
        """Handle task success."""
        logger.info(f"Task {task_id} completed successfully")


@celery_app.task(
    bind=True,
    base=CallbackTask,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=3600,
    retry_jitter=True,
)
def enqueue_for_processing(self, upload_metadata_id: str, metadata_dict: dict):
    """Enqueue file for extraction processing."""
    try:
        logger.info(f"Processing file: {upload_metadata_id}")

        # Import here to avoid circular imports
        import asyncio

        # Update job log with running status
        asyncio.run(
            update_job_log(
                self.request.id,
                upload_metadata_id,
                JobStatus.RUNNING,
            )
        )

        # Simulate processing - in real implementation, this would call extraction agents
        logger.info(f"Successfully processed: {upload_metadata_id}")

        # Update job log with completed status
        asyncio.run(
            update_job_log(
                self.request.id,
                upload_metadata_id,
                JobStatus.COMPLETED,
                output_data={"extracted": True},
            )
        )

        return {"status": "success", "file_id": upload_metadata_id}

    except Exception as e:
        logger.error(f"Error processing file: {e}")
        capture_exception(e, upload_id=upload_metadata_id, task_id=self.request.id)
        asyncio.run(
            update_job_log(
                self.request.id,
                upload_metadata_id,
                JobStatus.FAILED,
                error_message=str(e),
                retry_count=self.request.retries,
            )
        )
        raise


async def update_job_log(
    job_id: str,
    upload_metadata_id: str,
    status: str,
    error_message: str = None,
    output_data: dict = None,
    retry_count: int = 0,
):
    """Update job log in database."""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(JobLog).where(JobLog.job_id == job_id)
            )
            job_log = result.scalar_one_or_none()

            if job_log:
                job_log.status = status
                if status == JobStatus.RUNNING:
                    job_log.started_at = datetime.now(timezone.utc)
                    job_log.attempts += 1
                elif status == JobStatus.COMPLETED:
                    job_log.completed_at = datetime.now(timezone.utc)
                    job_log.output_data = output_data
                elif status == JobStatus.FAILED:
                    job_log.error_message = error_message
                    job_log.retry_count = retry_count
                elif status == JobStatus.RETRIED:
                    job_log.retry_count = retry_count

                await session.commit()
                logger.info(f"Job log updated: {job_id} -> {status}")
            else:
                logger.warning(f"Job log not found: {job_id}")

        except Exception as e:
            logger.error(f"Error updating job log: {e}")
            await session.rollback()
            raise
