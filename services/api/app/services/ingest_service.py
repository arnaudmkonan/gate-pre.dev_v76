import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import desc, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingest_job import IngestJob, IngestJobStatus, IngestMode
from app.schemas.ingest import IngestJobCreate

logger = logging.getLogger(__name__)


class IngestService:
    """Service for managing ingestion jobs."""

    @staticmethod
    async def create_job(
        session: AsyncSession,
        job_data: IngestJobCreate,
        storage_path: str,
    ) -> IngestJob:
        """
        Create a new ingest job.

        Args:
            session: Database session
            job_data: Job creation data
            storage_path: Path to file in storage

        Returns:
            Created IngestJob instance
        """
        try:
            job = IngestJob(
                filename=job_data.filename,
                file_type=job_data.file_type,
                size=job_data.size,
                uploader_id=job_data.uploader_id,
                storage_path=storage_path,
                status=IngestJobStatus.PENDING,
                attempts=0,
                max_attempts=3,
                priority="normal",
            )

            session.add(job)
            await session.commit()
            await session.refresh(job)

            logger.info(f"Ingest job created: {job.id} ({job.filename})")
            return job

        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating ingest job: {e}")
            raise

    @staticmethod
    async def get_job(
        session: AsyncSession,
        job_id: UUID,
    ) -> Optional[IngestJob]:
        """Get ingest job by ID."""
        try:
            result = await session.execute(
                select(IngestJob).where(IngestJob.id == job_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error retrieving ingest job: {e}")
            raise

    @staticmethod
    async def update_job_status(
        session: AsyncSession,
        job_id: UUID,
        status: str,
        error_message: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> IngestJob:
        """Update job status."""
        try:
            job = await IngestService.get_job(session, job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            job.status = status
            if error_message:
                job.error_message = error_message
            if metadata:
                job.extracted_metadata = metadata
            if status == IngestJobStatus.PROCESSING:
                job.attempts += 1
                job.last_attempted_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(job)

            logger.info(f"Job {job_id} status updated to {status}")
            return job

        except Exception as e:
            await session.rollback()
            logger.error(f"Error updating job status: {e}")
            raise

    @staticmethod
    async def list_jobs(
        session: AsyncSession,
        status: Optional[str] = None,
        uploader_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[IngestJob], int]:
        """
        List ingest jobs with pagination.

        Returns:
            Tuple of (jobs, total_count)
        """
        try:
            query = select(IngestJob)

            if status:
                query = query.where(IngestJob.status == status)
            if uploader_id:
                query = query.where(IngestJob.uploader_id == uploader_id)

            # Get total count
            count_result = await session.execute(query)
            total = len(count_result.scalars().all())

            # Get paginated results
            offset = (page - 1) * page_size
            query = query.order_by(desc(IngestJob.created_at)).offset(offset).limit(page_size)

            result = await session.execute(query)
            jobs = result.scalars().all()

            return jobs, total

        except Exception as e:
            logger.error(f"Error listing jobs: {e}")
            raise

    @staticmethod
    async def get_queue_status(session: AsyncSession) -> dict:
        """Get queue status summary."""
        try:
            statuses = {
                "pending": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0,
            }

            for status in statuses.keys():
                result = await session.execute(
                    select(IngestJob).where(IngestJob.status == status)
                )
                statuses[status] = len(result.scalars().all())

            return statuses

        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            raise

    @staticmethod
    async def get_jobs_by_status(
        session: AsyncSession,
        status: str,
        limit: Optional[int] = None,
    ) -> list[IngestJob]:
        """Get jobs by status (useful for processing batches)."""
        try:
            query = select(IngestJob).where(IngestJob.status == status).order_by(
                desc(IngestJob.priority), IngestJob.created_at
            )

            if limit:
                query = query.limit(limit)

            result = await session.execute(query)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting jobs by status: {e}")
            raise

    @staticmethod
    async def get_job_detail(
        session: AsyncSession, job_id: str
    ) -> Optional[IngestJob]:
        """
        Get detailed information about a specific job.

        Args:
            session: Database session
            job_id: Job ID

        Returns:
            IngestJob or None if not found
        """
        try:
            job = await session.get(IngestJob, job_id)
            return job
        except Exception as e:
            logger.error(f"Error getting job detail: {e}")
            raise

    @staticmethod
    async def update_job_mode(
        session: AsyncSession,
        job_id: str,
        mode: str,
        batch_size: Optional[int] = None,
        schedule_time: Optional[datetime] = None,
        mapping_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[IngestJob]:
        """
        Update ingestion mode and settings for a job.

        Args:
            session: Database session
            job_id: Job ID
            mode: Ingestion mode (quick_auto, guided_mapping, advanced_batch)
            batch_size: Batch size for advanced_batch mode
            schedule_time: Scheduled time for processing
            mapping_config: Mapping configuration for guided_mapping mode

        Returns:
            Updated IngestJob or None if not found
        """
        try:
            job = await session.get(IngestJob, job_id)
            if not job:
                return None

            # Validate mode
            valid_modes = [m.value for m in [IngestMode.QUICK_AUTO, IngestMode.GUIDED_MAPPING, IngestMode.ADVANCED_BATCH]]
            if mode not in valid_modes:
                raise ValueError(f"Invalid mode: {mode}")

            # Update job
            job.mode = mode
            if batch_size is not None:
                job.batch_size = batch_size
            if schedule_time is not None:
                job.schedule_time = schedule_time
            if mapping_config is not None:
                job.mapping_config = mapping_config

            job.updated_at = datetime.now(timezone.utc)
            session.add(job)
            await session.commit()
            await session.refresh(job)

            logger.info(f"Job {job_id} mode updated to {mode}")
            return job

        except Exception as e:
            await session.rollback()
            logger.error(f"Error updating job mode: {e}")
            raise

    @staticmethod
    async def emit_job_status_update(
        session: AsyncSession, job_id: str, status: str, progress: int = 0
    ) -> None:
        """
        Emit job status update for WebSocket integration.

        Args:
            session: Database session
            job_id: Job ID
            status: New status
            progress: Progress percentage (0-100)
        """
        try:
            job = await session.get(IngestJob, job_id)
            if not job:
                return

            job.status = status
            job.progress_percentage = progress
            job.updated_at = datetime.now(timezone.utc)

            session.add(job)
            await session.commit()

            logger.info(f"Job {job_id} status updated to {status} ({progress}%)")
        except Exception as e:
            await session.rollback()
            logger.error(f"Error emitting job status update: {e}")
            raise
