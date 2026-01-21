import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.ingest import DLQItemResponse, DLQReprocessRequest
from app.services.dlq_service import DLQService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingest/dlq", tags=["dlq"])


@router.get("", response_model=list[DLQItemResponse])
async def list_dlq(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """
    Get dead letter queue items.

    Parameters:
    - status: Filter by status (pending_review, archived)
    - limit: Number of items to return
    - offset: Offset for pagination
    """
    try:
        items, total = await DLQService.list_dlq(
            session,
            status=status,
            limit=limit,
            offset=offset,
        )

        return [DLQItemResponse.from_orm(item) for item in items]

    except Exception as e:
        logger.error(f"Error retrieving DLQ: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve DLQ",
        )


@router.get("/{dlq_id}", response_model=DLQItemResponse)
async def get_dlq_item(
    dlq_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get a specific DLQ item."""
    try:
        item = await DLQService.get_dlq_item(session, dlq_id)

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"DLQ item {dlq_id} not found",
            )

        return DLQItemResponse.from_orm(item)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving DLQ item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve DLQ item",
        )


@router.post("/{dlq_id}/reprocess", status_code=status.HTTP_200_OK)
async def reprocess_dlq_item(
    dlq_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Reprocess a DLQ item by re-enqueueing its job.

    The job will be reset to pending status and re-entered into the processing queue.
    """
    try:
        job = await DLQService.reprocess_dlq_item(session, dlq_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job for DLQ item {dlq_id} not found",
            )

        logger.info(f"DLQ item {dlq_id} reprocessed, job {job.id} re-queued")

        return {
            "status": "reprocessed",
            "job_id": str(job.id),
            "message": "Job has been re-queued for processing",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reprocessing DLQ item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reprocess DLQ item",
        )


@router.delete("/{dlq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dlq_item(
    dlq_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Delete a DLQ item."""
    try:
        await DLQService.delete_dlq_item(session, dlq_id)
        logger.info(f"DLQ item {dlq_id} deleted")

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error deleting DLQ item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete DLQ item",
        )


@router.put("/{dlq_id}/notes", response_model=DLQItemResponse)
async def update_dlq_notes(
    dlq_id: UUID,
    notes: str = Query(..., description="Notes to add to the DLQ item"),
    session: AsyncSession = Depends(get_db),
):
    """Update manual notes on a DLQ item."""
    try:
        item = await DLQService.update_dlq_notes(session, dlq_id, notes)

        return DLQItemResponse.from_orm(item)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error updating DLQ notes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update DLQ notes",
        )
