"""Admin API routes for retry and dead-letter queue management."""

import logging
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.rbac import admin_required
from app.schemas.ingest import DLQItemResponse
from app.schemas.retry import RetryBulkResponse
from app.services.dlq_service import DLQService
from app.services.retry_service import RetryService
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/dlq",
    tags=["Admin - Retry & DLQ Management"],
)


@router.get("/", response_model=list[DLQItemResponse])
async def list_dlq_items(
    item_status: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(admin_required()),
):
    """
    List dead letter queue items with admin access.

    Parameters:
    - status: Filter by status (pending_review, archived)
    - limit: Number of items to return (max 500)
    - offset: Offset for pagination
    """
    try:
        items, total = await DLQService.list_dlq(
            session,
            status=item_status,
            limit=limit,
            offset=offset,
        )

        return [DLQItemResponse.from_orm(item) for item in items]

    except Exception as e:
        logger.error(f"Error retrieving DLQ items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve DLQ items",
        )


@router.get("/{dlq_id}", response_model=DLQItemResponse)
async def get_dlq_item(
    dlq_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(admin_required()),
):
    """Get a specific DLQ item."""
    try:
        item = await DLQService.get_dlq_item(session, dlq_id)

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"DLQ item not found: {dlq_id}",
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


@router.post("/{dlq_id}/retry", status_code=status.HTTP_200_OK)
async def retry_dlq_item(
    dlq_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(admin_required()),
):
    """
    Retry a failed DLQ item by re-enqueueing its job.

    The job will be reset to pending status and re-entered into the processing queue.
    """
    try:
        job = await DLQService.reprocess_dlq_item(session, dlq_id)

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job for DLQ item not found: {dlq_id}",
            )

        # Log audit action
        await AuditService.log_action(
            session=session,
            resource_type="dlq",
            resource_id=str(dlq_id),
            action="retry",
            changes={"job_id": str(job.id)},
        )
        await session.commit()

        logger.info(f"DLQ item {dlq_id} retried, job {job.id} re-queued")

        return {
            "status": "success",
            "dlq_id": str(dlq_id),
            "job_id": str(job.id),
            "message": "Job has been re-queued for processing",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying DLQ item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry DLQ item",
        )


@router.delete("/{dlq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dlq_item(
    dlq_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(admin_required()),
):
    """Delete a DLQ item."""
    try:
        await DLQService.delete_dlq_item(session, dlq_id)

        # Log audit action
        await AuditService.log_action(
            session=session,
            resource_type="dlq",
            resource_id=str(dlq_id),
            action="delete",
            changes={"dlq_id": str(dlq_id)},
        )
        await session.commit()

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


@router.post("/batch-retry", response_model=RetryBulkResponse)
async def batch_retry_jobs(
    request: dict,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(admin_required()),
):
    """
    Batch retry multiple failed jobs from DLQ.

    Request body:
    {
        "job_ids": ["job-id-1", "job-id-2", ...],
        "mode_override": "optional_mode",
        "mapping_override": "optional_mapping"
    }
    """
    try:
        job_ids = request.get("job_ids", [])
        if not job_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one job_id is required",
            )

        if len(job_ids) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot retry more than 100 jobs at once",
            )

        # Perform bulk retry
        result = await RetryService.retry_bulk_jobs(
            session=session,
            job_ids=job_ids,
            mode_override=request.get("mode_override"),
            mapping_override=request.get("mapping_override"),
        )

        await session.commit()

        return RetryBulkResponse(
            retried_count=result["retried_count"],
            failed_count=result["failed_count"],
            results=result["results"],
            errors=result["errors"],
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error batch retrying jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to batch retry jobs",
        )


@router.get("/stats/summary")
async def get_dlq_stats(
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(admin_required()),
):
    """Get DLQ statistics and summary."""
    try:
        items, total = await DLQService.list_dlq(
            session,
            limit=1000,
            offset=0,
        )

        pending = sum(1 for item in items if item.status == "pending_review")
        archived = sum(1 for item in items if item.status == "archived")

        return {
            "total_items": total,
            "pending_items": pending,
            "archived_items": archived,
            "oldest_item": min([item.created_at for item in items]) if items else None,
        }

    except Exception as e:
        logger.error(f"Error getting DLQ stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get DLQ statistics",
        )
