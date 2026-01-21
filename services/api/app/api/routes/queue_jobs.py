"""Routes for queue job management."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.queue_jobs import QueueJobResponse, QueueListResponse, EnqueueRequest
from app.services.queue_service import QueueService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/queue", tags=["queue"])


@router.post("/enqueue", response_model=dict, status_code=status.HTTP_201_CREATED)
async def enqueue_file(
    request: EnqueueRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Enqueue a file for processing.

    Returns job_id and status within 5 seconds.
    """
    try:
        result = await QueueService.enqueue(
            session,
            file_id=request.file_id,
            file_type=request.file_type,
            file_size=request.file_size,
            uploader_id=request.uploader_id,
            priority=request.priority,
        )

        logger.info(f"File {request.file_id} enqueued successfully")
        return result

    except Exception as e:
        logger.error(f"Error enqueueing file {request.file_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to enqueue file")


@router.get("/{job_id}", response_model=QueueJobResponse)
async def get_job_status(
    job_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get status of a queue job."""
    try:
        result = await QueueService.get_job_status(session, job_id)

        if not result:
            raise HTTPException(status_code=404, detail="Job not found")

        return QueueJobResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving job status for {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve job status")


@router.get("", response_model=QueueListResponse)
async def list_queue_jobs(
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """
    List queued jobs with optional status filter.

    Status values: queued, processing, completed, failed
    """
    try:
        result = await QueueService.list_queued(
            session,
            status=status,
            limit=limit,
            offset=offset,
        )

        return QueueListResponse(**result)

    except Exception as e:
        logger.error(f"Error listing queue jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to list queue jobs")


@router.post("/{job_id}/retry", response_model=dict)
async def retry_queue_job(
    job_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Retry a failed queue job."""
    try:
        result = await QueueService.retry_job(session, job_id)

        if not result:
            raise HTTPException(status_code=404, detail="Job not found or max retries exceeded")

        logger.info(f"Job {job_id} retry queued")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retry job")


@router.get("/stats/overview")
async def get_queue_stats(
    session: AsyncSession = Depends(get_db),
):
    """Get queue statistics (pending, processing, completed, failed counts)."""
    try:
        queued_result = await QueueService.list_queued(session, status="queued", limit=1)
        processing_result = await QueueService.list_queued(session, status="processing", limit=1)
        completed_result = await QueueService.list_queued(session, status="completed", limit=1)
        failed_result = await QueueService.list_queued(session, status="failed", limit=1)

        return {
            "queued": queued_result["total_count"],
            "processing": processing_result["total_count"],
            "completed": completed_result["total_count"],
            "failed": failed_result["total_count"],
        }

    except Exception as e:
        logger.error(f"Error retrieving queue stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve queue stats")
