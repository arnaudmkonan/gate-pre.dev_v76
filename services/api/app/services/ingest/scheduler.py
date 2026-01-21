import logging
import random
from uuid import UUID
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.models import IngestFile, IngestBatch, IngestFileStatus, IngestBatchStatus

logger = logging.getLogger(__name__)


class Scheduler:
    """Schedules ingestion jobs to Celery with retry configuration and batching."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def schedule_job(
        self,
        ingest_file_id: UUID,
        batch_id: UUID,
        agent_type: str,
        priority: str = "normal",
        max_retries: int = 3,
    ) -> str:
        """
        Schedule a single file for ingestion.

        Args:
            ingest_file_id: ID of the IngestFile record
            batch_id: ID of the batch this file belongs to
            agent_type: Type of agent to process this file
            priority: Task priority (low, normal, high)
            max_retries: Max retry attempts

        Returns:
            Celery task ID
        """
        try:
            # Enqueue to Celery with routing
            task = celery_app.send_task(
                "app.workers.ingest_file_processor.process_ingest_file",
                args=[str(ingest_file_id), agent_type],
                kwargs={
                    "batch_id": str(batch_id),
                    "max_retries": max_retries,
                },
                priority=self._priority_to_celery(priority),
                queue="ingest",
            )

            # Store the task ID in the ingest file record
            from sqlalchemy import select
            stmt = select(IngestFile).where(IngestFile.id == ingest_file_id)
            result = await self.session.execute(stmt)
            ingest_file = result.scalar_one_or_none()

            if ingest_file:
                ingest_file.celery_task_id = task.id
                ingest_file.status = IngestFileStatus.QUEUED
                await self.session.commit()
                logger.info(f"Scheduled file {ingest_file_id} with task {task.id}")
                return task.id
            else:
                logger.error(f"IngestFile {ingest_file_id} not found")
                raise ValueError(f"IngestFile {ingest_file_id} not found")

        except Exception as e:
            logger.error(f"Failed to schedule job: {e}")
            await self.session.rollback()
            raise

    async def batch_and_enqueue(
        self,
        ingest_file_ids: list[UUID],
        batch_id: UUID,
        agent_types: dict[UUID, str],
        max_concurrent: int = 5,
        immediate: bool = True,
    ) -> list[str]:
        """
        Enqueue multiple files in a batch with concurrency control.

        Args:
            ingest_file_ids: List of file IDs to enqueue
            batch_id: Batch ID
            agent_types: Mapping of file_id to agent_type
            max_concurrent: Max concurrent jobs
            immediate: Execute immediately or schedule for later

        Returns:
            List of Celery task IDs
        """
        task_ids = []

        try:
            for file_id in ingest_file_ids:
                agent_type = agent_types.get(file_id, "generic_agent")

                if immediate:
                    # Schedule with some jitter to avoid thundering herd
                    jitter_seconds = random.uniform(0, 5)
                    task_id = await self.schedule_job(
                        file_id,
                        batch_id,
                        agent_type,
                    )
                    task_ids.append(task_id)
                else:
                    # Schedule for later - add countdown with backoff
                    countdown = self._calculate_backoff(len(task_ids), max_concurrent)
                    task_id = await self.schedule_job(
                        file_id,
                        batch_id,
                        agent_type,
                    )
                    task_ids.append(task_id)

            logger.info(f"Enqueued {len(task_ids)} files for batch {batch_id}")
            return task_ids

        except Exception as e:
            logger.error(f"Failed to batch and enqueue: {e}")
            raise

    def _priority_to_celery(self, priority: str) -> int:
        """Convert priority string to Celery priority int."""
        priority_map = {
            "low": 0,
            "normal": 5,
            "high": 10,
        }
        return priority_map.get(priority.lower(), 5)

    def _calculate_backoff(self, attempt: int, max_concurrent: int) -> int:
        """Calculate exponential backoff with jitter for task scheduling."""
        base_backoff = (attempt // max_concurrent) * 10  # 10 seconds per "wave"
        jitter = random.uniform(0, 5)
        return int(base_backoff + jitter)
