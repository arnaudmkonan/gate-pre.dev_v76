import logging
from uuid import UUID
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.celery_app import celery_app
from app.core.config import settings
from app.models import (
    IngestFile,
    IngestFileStatus,
    IngestBatch,
    RawFile,
)

logger = logging.getLogger(__name__)

# Create async engine for Celery worker
# Ensure we're using asyncpg, not psycopg2
db_url = settings.database_url or "postgresql+asyncpg://postgres:postgres@localhost:5432/doc_ingestion"
if "+asyncpg://" not in db_url:
    db_url = db_url.replace("+psycopg://", "+asyncpg://").replace("+psycopg2://", "+asyncpg://").replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(db_url, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
async def process_ingest_file(self, file_id: str, agent_type: str, batch_id: str = None, max_retries: int = 3):
    """
    Process a single file ingestion.

    Args:
        file_id: ID of the IngestFile to process
        agent_type: Type of agent to use for processing
        batch_id: ID of the parent batch
        max_retries: Maximum retry attempts
    """
    ingest_file_uuid = UUID(file_id)
    batch_uuid = UUID(batch_id) if batch_id else None

    try:
        async with AsyncSessionLocal() as session:
            # Fetch ingest file
            stmt = select(IngestFile).where(IngestFile.id == ingest_file_uuid)
            result = await session.execute(stmt)
            ingest_file = result.scalar_one_or_none()

            if not ingest_file:
                logger.error(f"IngestFile {file_id} not found")
                return {"status": "failed", "error": "IngestFile not found"}

            # Update status to processing
            ingest_file.status = IngestFileStatus.PROCESSING
            ingest_file.processing_started_at = datetime.utcnow()
            await session.commit()

            # Fetch raw file
            stmt = select(RawFile).where(RawFile.id == ingest_file.file_id)
            result = await session.execute(stmt)
            raw_file = result.scalar_one_or_none()

            if not raw_file:
                raise ValueError(f"RawFile {ingest_file.file_id} not found")

            logger.info(f"Processing file {file_id} with agent {agent_type}")

            # TODO: Call appropriate ingestion agent based on agent_type
            # For now, simulate successful processing
            raw_content = {
                "content": f"Processed content from {raw_file.filename}",
                "metadata": {
                    "source_file": raw_file.filename,
                    "file_type": raw_file.file_type,
                },
            }

            # After successful extraction, map to silver schema
            # This would normally be done via a separate task or service
            ingest_file.status = IngestFileStatus.SUCCESS
            ingest_file.processing_completed_at = datetime.utcnow()
            ingest_file.attempts += 1

            await session.commit()

            # Update batch counts
            if batch_uuid:
                stmt = select(IngestBatch).where(IngestBatch.id == batch_uuid)
                result = await session.execute(stmt)
                batch = result.scalar_one_or_none()

                if batch:
                    batch.success_count += 1
                    await session.commit()

            logger.info(f"Successfully processed file {file_id}")

            return {
                "status": "success",
                "file_id": file_id,
                "agent_type": agent_type,
            }

    except Exception as exc:
        logger.error(f"Failed to process file {file_id}: {exc}")

        try:
            async with AsyncSessionLocal() as session:
                stmt = select(IngestFile).where(IngestFile.id == ingest_file_uuid)
                result = await session.execute(stmt)
                ingest_file = result.scalar_one_or_none()

                if ingest_file:
                    ingest_file.attempts += 1
                    ingest_file.last_error = str(exc)

                    if ingest_file.attempts >= max_retries:
                        ingest_file.status = IngestFileStatus.FAILED
                        ingest_file.processing_completed_at = datetime.utcnow()

                        # Update batch failure count
                        if batch_uuid:
                            stmt = select(IngestBatch).where(IngestBatch.id == batch_uuid)
                            result = await session.execute(stmt)
                            batch = result.scalar_one_or_none()

                            if batch:
                                batch.failure_count += 1
                                await session.commit()
                    else:
                        ingest_file.status = IngestFileStatus.RETRY

                    await session.commit()
        except Exception as e:
            logger.error(f"Failed to update file status: {e}")

        # Retry with exponential backoff
        if self.request.retries < max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        else:
            return {"status": "failed", "file_id": file_id, "error": str(exc)}
