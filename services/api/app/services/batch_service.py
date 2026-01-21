import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from croniter import croniter
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch_schedule import BatchSchedule
from app.models.ingest_job import IngestJob, IngestJobStatus

logger = logging.getLogger(__name__)


class BatchService:
    """Service for managing batch schedule operations."""

    @staticmethod
    def validate_cron_expression(cron_expression: str) -> bool:
        """
        Validate a cron expression.

        Args:
            cron_expression: Cron expression to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            croniter(cron_expression)
            return True
        except Exception:
            return False

    @staticmethod
    async def create_schedule(
        session: AsyncSession,
        schedule_name: str,
        cron_expression: str,
        max_concurrency: int = 5,
        batch_size: int = 10,
        description: Optional[str] = None,
    ) -> BatchSchedule:
        """
        Create a new batch schedule.

        Args:
            session: Database session
            schedule_name: Unique name for the schedule
            cron_expression: Cron expression for scheduling
            max_concurrency: Maximum concurrent jobs
            batch_size: Jobs per batch
            description: Optional description

        Returns:
            Created BatchSchedule instance
        """
        try:
            # Validate cron expression
            if not BatchService.validate_cron_expression(cron_expression):
                raise ValueError(f"Invalid cron expression: {cron_expression}")

            # Calculate next run time
            cron = croniter(cron_expression, datetime.now(timezone.utc))
            next_run_at = cron.get_next(datetime)

            schedule = BatchSchedule(
                schedule_name=schedule_name,
                cron_expression=cron_expression,
                max_concurrency=max_concurrency,
                batch_size=batch_size,
                is_active=True,
                next_run_at=next_run_at,
                description=description,
            )

            session.add(schedule)
            await session.commit()
            await session.refresh(schedule)

            logger.info(f"Batch schedule created: {schedule.id} ({schedule_name})")
            return schedule

        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating batch schedule: {e}")
            raise

    @staticmethod
    async def get_schedule(
        session: AsyncSession,
        schedule_id: UUID,
    ) -> Optional[BatchSchedule]:
        """Get a batch schedule by ID."""
        try:
            result = await session.execute(
                select(BatchSchedule).where(BatchSchedule.id == schedule_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error retrieving batch schedule: {e}")
            raise

    @staticmethod
    async def list_schedules(
        session: AsyncSession,
        is_active: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[BatchSchedule], int]:
        """
        List batch schedules.

        Returns:
            Tuple of (schedules, total_count)
        """
        try:
            query = select(BatchSchedule)

            if is_active is not None:
                query = query.where(BatchSchedule.is_active == is_active)

            # Get total count
            count_result = await session.execute(query)
            total = len(count_result.scalars().all())

            # Get paginated results
            query = query.order_by(desc(BatchSchedule.created_at)).offset(offset).limit(limit)

            result = await session.execute(query)
            schedules = result.scalars().all()

            return schedules, total

        except Exception as e:
            logger.error(f"Error listing schedules: {e}")
            raise

    @staticmethod
    async def update_schedule(
        session: AsyncSession,
        schedule_id: UUID,
        schedule_name: Optional[str] = None,
        cron_expression: Optional[str] = None,
        max_concurrency: Optional[int] = None,
        batch_size: Optional[int] = None,
        is_active: Optional[bool] = None,
        description: Optional[str] = None,
    ) -> BatchSchedule:
        """Update a batch schedule."""
        try:
            schedule = await BatchService.get_schedule(session, schedule_id)
            if not schedule:
                raise ValueError(f"Schedule {schedule_id} not found")

            if schedule_name:
                schedule.schedule_name = schedule_name
            if cron_expression:
                if not BatchService.validate_cron_expression(cron_expression):
                    raise ValueError(f"Invalid cron expression: {cron_expression}")
                schedule.cron_expression = cron_expression
                # Recalculate next run time
                cron = croniter(cron_expression, datetime.now(timezone.utc))
                schedule.next_run_at = cron.get_next(datetime)
            if max_concurrency is not None:
                schedule.max_concurrency = max_concurrency
            if batch_size is not None:
                schedule.batch_size = batch_size
            if is_active is not None:
                schedule.is_active = is_active
            if description is not None:
                schedule.description = description

            await session.commit()
            await session.refresh(schedule)

            logger.info(f"Batch schedule {schedule_id} updated")
            return schedule

        except Exception as e:
            await session.rollback()
            logger.error(f"Error updating batch schedule: {e}")
            raise

    @staticmethod
    async def delete_schedule(
        session: AsyncSession,
        schedule_id: UUID,
    ) -> None:
        """Delete a batch schedule."""
        try:
            schedule = await BatchService.get_schedule(session, schedule_id)
            if not schedule:
                raise ValueError(f"Schedule {schedule_id} not found")

            await session.delete(schedule)
            await session.commit()

            logger.info(f"Batch schedule {schedule_id} deleted")

        except Exception as e:
            await session.rollback()
            logger.error(f"Error deleting batch schedule: {e}")
            raise

    @staticmethod
    async def get_pending_schedules(session: AsyncSession) -> list[BatchSchedule]:
        """Get all schedules that are due to run."""
        try:
            now = datetime.now(timezone.utc)
            result = await session.execute(
                select(BatchSchedule).where(
                    and_(
                        BatchSchedule.is_active == True,
                        BatchSchedule.next_run_at <= now,
                    )
                )
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting pending schedules: {e}")
            raise

    @staticmethod
    async def update_last_run(
        session: AsyncSession,
        schedule_id: UUID,
    ) -> BatchSchedule:
        """Update the last run time and calculate next run time."""
        try:
            schedule = await BatchService.get_schedule(session, schedule_id)
            if not schedule:
                raise ValueError(f"Schedule {schedule_id} not found")

            schedule.last_run_at = datetime.now(timezone.utc)

            # Calculate next run time
            cron = croniter(schedule.cron_expression, schedule.last_run_at)
            schedule.next_run_at = cron.get_next(datetime)

            await session.commit()
            await session.refresh(schedule)

            logger.info(f"Batch schedule {schedule_id} updated - last_run_at: {schedule.last_run_at}")
            return schedule

        except Exception as e:
            await session.rollback()
            logger.error(f"Error updating last run: {e}")
            raise

    @staticmethod
    async def get_jobs_for_batch(
        session: AsyncSession,
        max_jobs: int,
        priority_order: bool = True,
    ) -> list[IngestJob]:
        """
        Get jobs ready for processing in the next batch.

        Args:
            session: Database session
            max_jobs: Maximum number of jobs to retrieve
            priority_order: If True, order by priority then created_at

        Returns:
            List of IngestJob instances
        """
        try:
            query = select(IngestJob).where(IngestJob.status == IngestJobStatus.PENDING)

            if priority_order:
                query = query.order_by(IngestJob.priority.desc(), IngestJob.created_at)
            else:
                query = query.order_by(IngestJob.created_at)

            query = query.limit(max_jobs)

            result = await session.execute(query)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting jobs for batch: {e}")
            raise
