"""Celery tasks for ingestion workflow."""
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import get_async_session
from app.models.raw_file import RawFile, RawFileStatus

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def queue_raw_file(self, file_id: str):
    """
    Queue a raw file for ingestion processing.

    Transitions status from 'uploaded' to 'queued' within 5 seconds.
    Handles chunked files by creating chunk records.
    """
    try:
        import asyncio
        from app.core.database import AsyncSessionLocal

        async def process():
            async with AsyncSessionLocal() as session:
                # Fetch the file record
                file_uuid = UUID(file_id)
                result = await session.execute(
                    select(RawFile).where(RawFile.id == file_uuid)
                )
                raw_file = result.scalar_one_or_none()

                if not raw_file:
                    logger.warning(f"Raw file {file_id} not found")
                    return

                # Transition to queued status
                raw_file.status = RawFileStatus.QUEUED
                raw_file.updated_at = datetime.now(timezone.utc)

                session.add(raw_file)
                await session.commit()

                logger.info(
                    f"Raw file queued: {raw_file.filename} "
                    f"(file_id={raw_file.id}, status={raw_file.status})"
                )

                # If file is chunked, create chunk records
                if raw_file.assembly_metadata and raw_file.total_chunks and raw_file.total_chunks > 1:
                    await _create_chunk_records(session, raw_file)

        # Run async function
        asyncio.run(process())

    except Exception as exc:
        logger.error(f"Error queuing raw file {file_id}: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


async def _create_chunk_records(session, master_file: RawFile):
    """
    Create raw file records for each chunk of a chunked file.

    Args:
        session: AsyncSession for database operations
        master_file: The master RawFile record with assembly metadata
    """
    try:
        chunk_size = master_file.assembly_metadata.get("chunk_size_bytes", 50 * 1024 * 1024)
        total_chunks = master_file.total_chunks

        for chunk_index in range(total_chunks):
            # Calculate chunk size (last chunk may be smaller)
            if chunk_index == total_chunks - 1:
                # Last chunk
                calculated_chunk_size = master_file.file_size - (chunk_index * chunk_size)
            else:
                calculated_chunk_size = chunk_size

            chunk_record = RawFile(
                filename=f"{master_file.filename}.chunk_{chunk_index}",
                file_type=master_file.file_type,
                file_size=calculated_chunk_size,
                storage_path=f"{master_file.storage_path}.chunk_{chunk_index}",
                mime_type=master_file.mime_type,
                status=RawFileStatus.QUEUED,
                uploader_id=master_file.uploader_id,
                source=master_file.source,
                customer_id=master_file.customer_id,
                tags=master_file.tags,
                checksum=master_file.checksum,  # Will be re-verified for chunks
                batch_id=master_file.batch_id,
                chunk_index=chunk_index,
                total_chunks=total_chunks,
                assembly_metadata={
                    "is_chunk": True,
                    "master_file_id": str(master_file.id),
                    "offset_bytes": chunk_index * chunk_size,
                }
            )
            session.add(chunk_record)

        await session.commit()
        logger.info(f"Created {total_chunks} chunk records for {master_file.filename}")

    except Exception as exc:
        logger.error(f"Error creating chunk records: {exc}")
        await session.rollback()
        raise
