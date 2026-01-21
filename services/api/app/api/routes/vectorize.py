"""API endpoints for vectorization."""

import logging
from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.celery_app import celery_app
from app.models import SilverRecord
from app.services.silver_service import SilverService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vectorize", tags=["vectorization"])


class VectorizeRequest(BaseModel):
    """Request to vectorize silver records."""

    silver_record_ids: List[UUID]
    batch_size: int = 10


class VectorizeResponse(BaseModel):
    """Response from vectorization request."""

    job_ids: List[str]
    total_records: int
    queued_count: int
    status: str


class VectorizeStatusResponse(BaseModel):
    """Status of a vectorization job."""

    job_id: str
    status: str  # queued, processing, completed, failed
    record_id: UUID
    embedding_id: Optional[str] = None
    error_message: Optional[str] = None
    processing_started_at: Optional[str] = None
    processing_completed_at: Optional[str] = None


from typing import Optional


@router.post(
    "/vectorize",
    response_model=VectorizeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enqueue_vectorization(
    request: VectorizeRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Enqueue silver records for vectorization.

    Accepts a list of silver record IDs and enqueues them for embedding
    generation. Returns job IDs for polling status.

    Args:
        request: List of silver record IDs to vectorize
        session: Database session

    Returns:
        202 Accepted with job IDs and queued count

    Raises:
        400 Bad Request if records not found or IDs invalid
        500 Internal Server Error on queueing errors
    """
    try:
        if not request.silver_record_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="silver_record_ids cannot be empty",
            )

        if len(request.silver_record_ids) > 10000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 10000 records per request",
            )

        # Verify records exist and fetch their content
        records = []
        for record_id in request.silver_record_ids:
            record = await SilverService.get_record(session, record_id)
            if not record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Silver record {record_id} not found",
                )
            records.append(record)

        # Enqueue vectorization jobs
        job_ids = []
        for record in records:
            # Create task for each record
            task = celery_app.send_task(
                "vectorize_record",
                args=[str(record.id), record.content or "", record.record_metadata],
                retry=True,
                retry_policy={
                    "max_retries": 3,
                    "interval_start": 1,
                    "interval_step": 2,
                    "interval_max": 10,
                },
            )
            job_ids.append(task.id)
            logger.info(f"Queued vectorization for silver record {record.id}: job {task.id}")

        return VectorizeResponse(
            job_ids=job_ids,
            total_records=len(request.silver_record_ids),
            queued_count=len(job_ids),
            status="accepted",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enqueue vectorization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enqueue vectorization",
        )


@router.get(
    "/status/{job_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def get_vectorization_status(
    job_id: str,
):
    """
    Get status of a vectorization job.

    Args:
        job_id: Celery task ID

    Returns:
        200 OK with job status and results
    """
    try:
        task = celery_app.AsyncResult(job_id)

        response = {
            "job_id": job_id,
            "status": task.status,
            "result": None,
            "error": None,
        }

        if task.ready():
            if task.successful():
                response["result"] = task.result
            else:
                response["error"] = str(task.info)

        return response

    except Exception as e:
        logger.error(f"Failed to get vectorization status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get job status",
        )
