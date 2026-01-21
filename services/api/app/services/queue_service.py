"""Queue service for managing job queue with priority support."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.queue_job import QueueJob, QueueJobStatus, QueueJobPriority
from app.workers.ingest_worker import enqueue_for_processing

logger = logging.getLogger(__name__)


class QueueService:
    """Service for managing job queue with priority and retry logic."""

    @staticmethod
    async def enqueue(
        session: AsyncSession,
        file_id: str,
        file_type: str,
        file_size: int,
        uploader_id: Optional[str] = None,
        priority: str = QueueJobPriority.NORMAL,
        max_attempts: int = 3,
    ) -> Dict:
        """
        Enqueue a file for processing.

        Args:
            session: Database session
            file_id: ID of the uploaded file
            file_type: File extension (txt, docx, xlsx, etc.)
            file_size: File size in bytes
            uploader_id: User ID of uploader
            priority: Job priority (low, normal, high)
            max_attempts: Maximum retry attempts

        Returns:
            Dict with job_id, file_id, status
        """
        # Create queue job
        queue_job = QueueJob(
            file_id=file_id,
            uploader_id=uploader_id,
            file_type=file_type,
            file_size=file_size,
            priority=priority,
            status=QueueJobStatus.QUEUED,
            attempts=0,
            max_attempts=max_attempts,
        )

        session.add(queue_job)
        await session.flush()

        # Enqueue to Celery (dispatch to workers)
        try:
            # Map priority to Celery queue
            celery_queue = "high" if priority == QueueJobPriority.HIGH else "default"
            if priority == QueueJobPriority.LOW:
                celery_queue = "low"

            task = enqueue_for_processing.apply_async(
                            args=[str(file_id)],
                            kwargs={
                                "metadata_dict": {
                                    "filename": f"file.{file_type}",
                                    "size": file_size,
                                }
                            },
                            queue=celery_queue,
                            priority=3 if priority == QueueJobPriority.HIGH else (1 if priority == QueueJobPriority.LOW else 2),
                        )

            logger.info(f"File {file_id} enqueued with priority {priority}, Celery task: {task.id}")

            await session.commit()

            return {
                "job_id": str(queue_job.id),
                "file_id": str(file_id),
                "status": queue_job.status,
                "priority": queue_job.priority,
                "celery_task_id": task.id,
            }
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to enqueue file {file_id}: {e}")
            raise

    @staticmethod
    async def get_job_status(
        session: AsyncSession,
        job_id: str,
    ) -> Optional[Dict]:
        """
        Get status of a queued job.

        Args:
            session: Database session
            job_id: Job ID

        Returns:
            Dict with job details or None if not found
        """
        result = await session.execute(
            select(QueueJob).where(QueueJob.id == job_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            return None

        return {
            "job_id": str(job.id),
            "file_id": str(job.file_id),
            "status": job.status,
            "priority": job.priority,
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
            "last_error": job.last_error,
            "last_attempted_at": job.last_attempted_at,
            "created_at": job.created_at,
        }

    @staticmethod
    async def list_queued(
        session: AsyncSession,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict:
        """
        List queued jobs with optional status filter.

        Args:
            session: Database session
            status: Filter by status (queued, processing, completed, failed)
            limit: Number of records to return
            offset: Offset for pagination

        Returns:
            Dict with jobs and total count
        """
        # Build query
        query = select(QueueJob)

        if status:
            query = query.where(QueueJob.status == status)

        # Get total count
        count_result = await session.execute(
            select(QueueJob).where(QueueJob.status == status) if status else select(QueueJob)
        )
        total_count = len(count_result.scalars().all())

        # Get paginated results, ordered by priority then created_at
        from sqlalchemy import desc
        query = query.order_by(
            QueueJob.priority.desc(),
            QueueJob.created_at.asc()
        ).limit(limit).offset(offset)

        result = await session.execute(query)
        jobs = result.scalars().all()

        return {
            "jobs": [
                {
                    "job_id": str(job.id),
                    "file_id": str(job.file_id),
                    "status": job.status,
                    "priority": job.priority,
                    "attempts": job.attempts,
                    "max_attempts": job.max_attempts,
                    "last_error": job.last_error,
                    "last_attempted_at": job.last_attempted_at,
                    "created_at": job.created_at,
                }
                for job in jobs
            ],
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    async def update_job_status(
        session: AsyncSession,
        job_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Update job status.

        Args:
            session: Database session
            job_id: Job ID
            status: New status
            error_message: Error message if failed

        Returns:
            Updated job dict or None
        """
        result = await session.execute(
            select(QueueJob).where(QueueJob.id == job_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            return None

        job.status = status
        if error_message:
            job.last_error = error_message
        job.last_attempted_at = datetime.utcnow()

        if status == QueueJobStatus.PROCESSING:
            job.attempts += 1

        await session.commit()

        return {
            "job_id": str(job.id),
            "file_id": str(job.file_id),
            "status": job.status,
            "priority": job.priority,
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
            "last_error": job.last_error,
        }

    @staticmethod
    async def retry_job(
        session: AsyncSession,
        job_id: str,
    ) -> Optional[Dict]:
        """
        Retry a failed job.

        Args:
            session: Database session
            job_id: Job ID

        Returns:
            Updated job dict or None
        """
        result = await session.execute(
            select(QueueJob).where(QueueJob.id == job_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            return None

        if job.attempts >= job.max_attempts:
            return None  # Max retries exceeded

        job.status = QueueJobStatus.QUEUED
        job.last_error = None

        await session.commit()

        # Re-enqueue to Celery
        try:
            celery_queue = "high" if job.priority == QueueJobPriority.HIGH else "default"
            if job.priority == QueueJobPriority.LOW:
                celery_queue = "low"

            task = enqueue_for_processing.apply_async(
                args=[str(job.file_id)],
                queue=celery_queue,
                priority=3 if job.priority == QueueJobPriority.HIGH else (1 if job.priority == QueueJobPriority.LOW else 2),
            )

            logger.info(f"Job {job_id} retried, Celery task: {task.id}")
        except Exception as e:
            logger.error(f"Failed to retry job {job_id}: {e}")

        return {
            "job_id": str(job.id),
            "file_id": str(job.file_id),
            "status": job.status,
            "priority": job.priority,
            "attempts": job.attempts,
        }
