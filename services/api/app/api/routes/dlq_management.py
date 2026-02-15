"""FastAPI routes for DLQ management endpoints."""

import logging
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.dlq_service import DLQService
from app.models.dlq_entry import DLQEntry
from app.schemas.dlq import (
    DLQEntryResponse,
    DLQFilterQuery,
    DLQListResponse,
    DLQRequeueRequest,
    DLQRequeueResponse,
    DLQArchiveRequest,
    DLQArchiveResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dlq", tags=["dlq"])


@router.get("/entries", response_model=DLQListResponse)
async def list_dlq_entries(
    file_id: str = None,
    error_type: str = None,
    pipeline: str = None,
    archived: bool = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """List DLQ entries with optional filtering."""
    try:
        from sqlalchemy import select, func

        # Get all DLQ entries
        query = select(DLQEntry)

        # Add filters
        if file_id:
            try:
                query = query.where(DLQEntry.file_id == UUID(file_id))
            except ValueError:
                pass

        # Get total count
        count_query = select(func.count(DLQEntry.id)).select_from(DLQEntry)
        if file_id:
            try:
                count_query = count_query.where(DLQEntry.file_id == UUID(file_id))
            except ValueError:
                pass
        count_result = await session.execute(count_query)
        total = count_result.scalar()

        # Get paginated results
        from sqlalchemy import desc

        query = query.order_by(desc(DLQEntry.created_at)).offset(offset).limit(limit)
        result = await session.execute(query)
        entries = result.scalars().all()

        responses = [_to_dlq_response(entry) for entry in entries]

        return DLQListResponse(
            entries=responses,
            total=total,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error(f"Error listing DLQ entries: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving DLQ entries",
        )


@router.post("/{dlq_entry_id}/requeue", response_model=DLQRequeueResponse)
async def requeue_dlq_entry(
    dlq_entry_id: UUID,
    request: DLQRequeueRequest,
    session: AsyncSession = Depends(get_db),
):
    """Requeue a DLQ entry."""
    try:
        # Get the DLQ entry
        dlq_item = await DLQService.get_dlq_item(session, dlq_entry_id)

        if not dlq_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DLQ entry not found",
            )

        # Mark as not archived to allow reprocessing
        dlq_item.archived = False
        dlq_item.updated_at = datetime.now(__import__("datetime").timezone.utc)

        # TODO: Enqueue the job to the appropriate queue

        await session.commit()

        return DLQRequeueResponse(
            success=True,
            dlq_entry_id=dlq_entry_id,
            job_id=None,  # Would be set if we enqueued a job
            message="DLQ entry requeued successfully",
            timestamp=datetime.now(__import__("datetime").timezone.utc),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requeuing DLQ entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error requeuing DLQ entry",
        )


@router.post("/{dlq_entry_id}/archive", response_model=DLQArchiveResponse)
async def archive_dlq_entry(
    dlq_entry_id: UUID,
    request: DLQArchiveRequest,
    session: AsyncSession = Depends(get_db),
):
    """Archive a DLQ entry."""
    try:
        # Get the DLQ entry
        dlq_item = await DLQService.get_dlq_item(session, dlq_entry_id)

        if not dlq_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DLQ entry not found",
            )

        dlq_item.archived = True
        dlq_item.archived_at = datetime.now(__import__("datetime").timezone.utc)

        await session.commit()

        return DLQArchiveResponse(
            success=True,
            dlq_entry_id=dlq_entry_id,
            message="DLQ entry archived successfully",
            timestamp=datetime.now(__import__("datetime").timezone.utc),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error archiving DLQ entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error archiving DLQ entry",
        )


def _to_dlq_response(entry: DLQEntry) -> DLQEntryResponse:
    """Convert DLQEntry to DLQEntryResponse."""
    return DLQEntryResponse(
        id=entry.id,
        file_id=entry.file_id,
        pipeline="system",
        error_type="processing_error",
        error_message=entry.error_reason,
        retry_count=entry.retry_count,
        last_retry_at=None,
        next_retry_at=None,
        metadata=None,
        archived=False,
        archived_at=None,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )
