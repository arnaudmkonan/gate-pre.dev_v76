import logging
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.celery_app import celery_app
from app.core.config import settings
from app.models import (
    IngestBatch,
    IngestFile,
    IngestBatchStatus,
    IngestFileStatus,
    RawFile,
)
from app.services.ingest import Dispatcher, Scheduler

logger = logging.getLogger(__name__)


# Create async engine for Celery worker
# Ensure we're using asyncpg, not psycopg2
db_url = settings.database_url or "postgresql+asyncpg://postgres:postgres@localhost:5432/doc_ingestion"
if "+asyncpg://" not in db_url:
    db_url = db_url.replace("+psycopg://", "+asyncpg://").replace("+psycopg2://", "+asyncpg://").replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(db_url, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
async def process_ingest_batch(self, batch_id: str):
    """
    Process a batch ingestion job.

    Args:
        batch_id: ID of the IngestBatch to process
    """
    batch_uuid = UUID(batch_id)
    session = None

    try:
        async with AsyncSessionLocal() as session:
            # Fetch batch
            stmt = select(IngestBatch).where(IngestBatch.id == batch_uuid)
            result = await session.execute(stmt)
            batch = result.scalar_one_or_none()

            if not batch:
                logger.error(f"IngestBatch {batch_id} not found")
                return {"status": "failed", "error": "Batch not found"}

            # Update batch status to processing
            batch.status = IngestBatchStatus.PROCESSING
            batch.processing_started_at = None  # Will be set by first file
            await session.commit()

            # Get all files in batch
            stmt = select(IngestFile).where(IngestFile.batch_id == batch_uuid)
            result = await session.execute(stmt)
            files = result.scalars().all()

            logger.info(f"Processing batch {batch_id} with {len(files)} files")

            # Initialize services
            dispatcher = Dispatcher(session)
            scheduler = Scheduler(session)

            # Track task IDs for this batch
            task_ids = []
            file_by_id = {}

            for ingest_file in files:
                try:
                    # Get raw file info
                    stmt = select(RawFile).where(RawFile.id == ingest_file.file_id)
                    result = await session.execute(stmt)
                    raw_file = result.scalar_one_or_none()

                    if not raw_file:
                        logger.error(f"RawFile {ingest_file.file_id} not found")
                        ingest_file.status = IngestFileStatus.FAILED
                        ingest_file.last_error = "Raw file not found"
                        batch.failure_count += 1
                        continue

                    # Route file to appropriate agent
                    agent_type = dispatcher.route_file(
                        ingest_file.file_type,
                        mime_type=None,  # Could fetch from raw_file if available
                    )

                    # Record routing decision
                    await dispatcher.record_routing_decision(
                        ingest_file.id,
                        agent_type,
                        ingest_file.file_type,
                    )

                    # Schedule file processing
                    task_id = await scheduler.schedule_job(
                        ingest_file.id,
                        batch_uuid,
                        agent_type,
                        priority="normal",
                        max_retries=ingest_file.max_attempts,
                    )

                    task_ids.append(task_id)
                    file_by_id[task_id] = ingest_file.id

                    logger.info(
                        f"Scheduled file {ingest_file.file_id} with agent {agent_type}"
                    )

                except Exception as e:
                    logger.error(f"Failed to schedule file {ingest_file.file_id}: {e}")
                    ingest_file.status = IngestFileStatus.FAILED
                    ingest_file.last_error = str(e)
                    batch.failure_count += 1

            await session.commit()

            logger.info(f"Batch {batch_id} processing initiated with {len(task_ids)} tasks")

            return {
                "status": "processing",
                "batch_id": batch_id,
                "files_queued": len(task_ids),
                "task_ids": task_ids,
            }

    except Exception as exc:
        logger.error(f"Failed to process batch {batch_id}: {exc}")
        if session:
            try:
                stmt = select(IngestBatch).where(IngestBatch.id == batch_uuid)
                result = await session.execute(stmt)
                batch = result.scalar_one_or_none()
                if batch:
                    batch.status = IngestBatchStatus.FAILED
                    batch.error_message = str(exc)
                    await session.commit()
            except Exception as e:
                logger.error(f"Failed to update batch status: {e}")
            finally:
                await session.close()

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True)
async def finalize_batch(self, batch_id: str):
    """
    Finalize a batch after all files are processed.

    Args:
        batch_id: ID of the IngestBatch
    """
    batch_uuid = UUID(batch_id)

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(IngestBatch).where(IngestBatch.id == batch_uuid)
            result = await session.execute(stmt)
            batch = result.scalar_one_or_none()

            if not batch:
                logger.error(f"IngestBatch {batch_id} not found")
                return

            # Determine final status
            if batch.failure_count == 0:
                batch.status = IngestBatchStatus.COMPLETED
            elif batch.success_count > 0:
                batch.status = IngestBatchStatus.PARTIAL
            else:
                batch.status = IngestBatchStatus.FAILED

            batch.processing_completed_at = None  # Set by individual files

            await session.commit()

            logger.info(
                f"Finalized batch {batch_id}: {batch.success_count} success, "
                f"{batch.failure_count} failed"
            )

    except Exception as e:
        logger.error(f"Failed to finalize batch {batch_id}: {e}")
