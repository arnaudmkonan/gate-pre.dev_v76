import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models import (
    IngestBatch,
    IngestFile,
    SilverRecord,
    RetryQueue,
    RawFile,
)
from app.schemas.orchestration import (
    IngestBatchCreate,
    IngestBatchResponse,
    IngestFileResponse,
    BatchStatusResponse,
    SilverRecordResponse,
    RetryQueueItemResponse,
    RetryQueueListResponse,
    RetryQueueUpdate,
    RetryQueueRetryRequest,
)
from app.services.ingest import Dispatcher, Scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingest", tags=["orchestration"])


@router.post(
    "/batch",
    response_model=IngestBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_batch_ingestion(
    request: IngestBatchCreate,
    session: AsyncSession = Depends(get_db),
):
    """
    Submit a batch of files for ingestion.

    Accepts multiple files with mixed types and creates a batch job
    that routes each file to the appropriate ingestion agent.

    Returns:
        201 Created with batch details including job ID
    """
    try:
        # Create batch record
        batch = IngestBatch(
            batch_name=request.batch_name,
            file_count=len(request.file_ids),
            created_by=request.created_by,
            scheduled_for=request.scheduled_for,
            max_concurrent_jobs=request.max_concurrent_jobs,
            batch_metadata=request.metadata,
        )

        session.add(batch)
        await session.commit()

        # Refresh batch to get server-generated fields
        await session.refresh(batch)

        # Create ingest file records for each file
        dispatcher = Dispatcher(session)
        agent_types = {}

        for file_id in request.file_ids:
            # Fetch raw file to get type info
            stmt = select(RawFile).where(RawFile.id == file_id)
            result = await session.execute(stmt)
            raw_file = result.scalar_one_or_none()

            if not raw_file:
                logger.warning(f"RawFile {file_id} not found, skipping")
                batch.failure_count += 1
                continue

            # Route file to agent
            agent_type = dispatcher.route_file(raw_file.file_type)
            agent_types[file_id] = agent_type

            # Create ingest file record
            ingest_file = IngestFile(
                batch_id=batch.id,
                file_id=file_id,
                file_type=raw_file.file_type,
                routing_decision=agent_type,
            )

            session.add(ingest_file)

        await session.commit()

        # Schedule processing if immediate
        if not request.scheduled_for:
            scheduler = Scheduler(session)
            try:
                stmt = select(IngestFile).where(IngestFile.batch_id == batch.id)
                result = await session.execute(stmt)
                files = result.scalars().all()

                for ingest_file in files:
                    agent_type = agent_types.get(ingest_file.file_id, "generic_agent")
                    await scheduler.schedule_job(
                        ingest_file.id,
                        batch.id,
                        agent_type,
                    )

                logger.info(f"Scheduled batch {batch.id} for immediate processing")
            except Exception as e:
                logger.error(f"Failed to schedule batch: {e}")
                batch.error_message = f"Scheduling failed: {str(e)}"
                await session.commit()

        # Refresh batch again to get all current values
        await session.refresh(batch)

        # Expunge from session before returning to avoid greenlet issues
        session.expunge(batch)

        return IngestBatchResponse.from_orm(batch)

    except Exception as e:
        logger.error(f"Failed to create batch ingestion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create batch: {str(e)}",
        )


@router.get(
    "/batch/{batch_id}",
    response_model=BatchStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_batch_status(
    batch_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get status of a batch ingestion job.

    Returns the batch details and status of all files within the batch.
    Status updates are available within 30 seconds of state changes.

    Returns:
        200 OK with batch and file statuses
        404 Not Found if batch doesn't exist
    """
    try:
        # Fetch batch
        stmt = select(IngestBatch).where(IngestBatch.id == batch_id)
        result = await session.execute(stmt)
        batch = result.scalar_one_or_none()

        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Batch {batch_id} not found",
            )

        # Fetch files in batch
        stmt = select(IngestFile).where(IngestFile.batch_id == batch_id)
        result = await session.execute(stmt)
        files = result.scalars().all()

        return BatchStatusResponse(
            batch=IngestBatchResponse.from_orm(batch),
            files=[IngestFileResponse.from_orm(f) for f in files],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get batch status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve batch status",
        )


@router.get(
    "/batch",
    response_model=list[IngestBatchResponse],
    status_code=status.HTTP_200_OK,
)
async def list_batches(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """
    List all batch ingestion jobs with optional filtering.

    Returns:
        200 OK with paginated list of batches
    """
    try:
        stmt = select(IngestBatch)

        if status_filter:
            stmt = stmt.where(IngestBatch.status == status_filter)

        # Get total count
        count_stmt = select(func.count(IngestBatch.id))
        if status_filter:
            count_stmt = count_stmt.where(IngestBatch.status == status_filter)
        count_result = await session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        stmt = stmt.order_by(IngestBatch.created_at.desc()).offset(offset).limit(page_size)

        result = await session.execute(stmt)
        batches = result.scalars().all()

        return [IngestBatchResponse.from_orm(b) for b in batches]

    except Exception as e:
        logger.error(f"Failed to list batches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve batches",
        )
