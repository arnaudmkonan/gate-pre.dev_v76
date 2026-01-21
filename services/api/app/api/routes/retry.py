"""API routes for retry operations (Story 3)."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.retry import (
    RetryJobRequest,
    RetryBulkResponse,
    RetryResponse,
)
from app.services.retry_service import RetryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["retry"])


@router.post("/retry", response_model=RetryBulkResponse)
async def retry_jobs(
    request: RetryJobRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Retry one or multiple failed ingestion jobs (Story 3: Retry Failed Jobs).

    Args:
        request: RetryJobRequest with job_ids list and optional overrides
        session: Database session

    Returns:
        RetryBulkResponse with results for each retry attempt
    """
    try:
        if not request.job_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one job_id is required",
            )

        if len(request.job_ids) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot retry more than 100 jobs at once",
            )

        # Perform bulk retry
        result = await RetryService.retry_bulk_jobs(
            session=session,
            job_ids=request.job_ids,
            mode_override=request.mode_override,
            mapping_override=request.mapping_override,
        )

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
        logger.error(f"Error retrying jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry jobs",
        )


@router.get("/{job_id}/retry-history")
async def get_retry_history(
    job_id: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Get retry history for a specific job (Story 3).

    Args:
        job_id: The job ID to get retry history for

    Returns:
        List of retry attempts
    """
    try:
        # For now, return empty list as we don't have a direct retry_jobs table relation
        # In a full implementation, this would query RetryJob entries
        return {
            "job_id": job_id,
            "retry_count": 0,
            "retries": [],
        }

    except Exception as e:
        logger.error(f"Error getting retry history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get retry history",
        )
