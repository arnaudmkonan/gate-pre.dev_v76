import logging
from datetime import datetime, timezone
from uuid import UUID
from celery import Task

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.services.metadata_service import MetadataService
from app.services.ingest_service import IngestService

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """Task class with callback support."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {task_id} failed: {exc}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        logger.warning(f"Task {task_id} retrying: {exc}")

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
def extract_metadata(self, job_id: str, file_bytes: bytes, filename: str, file_type: str):
    """
    Celery task to extract metadata from an uploaded file.

    Args:
        job_id: UUID of the ingest job
        file_bytes: Raw file bytes
        filename: Original filename
        file_type: File extension/type
    """
    try:
        import asyncio

        job_uuid = UUID(job_id) if isinstance(job_id, str) else job_id

        logger.info(f"Extracting metadata for job {job_id}")

        # Run async metadata extraction
        metadata = asyncio.run(
            MetadataService.extract_metadata(file_bytes, filename, file_type)
        )

        # Update job with metadata
        asyncio.run(
            _update_job_metadata(job_uuid, metadata)
        )

        logger.info(f"Metadata extraction completed for job {job_id}")
        return {"status": "success", "job_id": job_id, "metadata": metadata}

    except Exception as e:
        logger.error(f"Error extracting metadata: {e}")
        raise


async def _update_job_metadata(job_id: UUID, metadata: dict):
    """Update job record with extracted metadata."""
    async with AsyncSessionLocal() as session:
        try:
            await IngestService.update_job_status(
                session,
                job_id,
                status=None,  # Keep current status
                metadata=metadata,
            )
            logger.info(f"Updated job {job_id} with metadata")
        except Exception as e:
            logger.error(f"Error updating job metadata: {e}")
            raise
