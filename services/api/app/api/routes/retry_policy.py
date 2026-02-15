"""FastAPI routes for retry policy management endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.retry_policy_service import RetryPolicyService
from app.schemas.retry_policy import (
    RetryPolicyCreate,
    RetryPolicyResponse,
    RetryPolicyUpdate,
    RetryCalculation,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/retry-policy", tags=["retry-policy"])


@router.post("", response_model=RetryPolicyResponse)
async def create_retry_policy(
    policy: RetryPolicyCreate,
    session: AsyncSession = Depends(get_db),
):
    """Create a new retry policy."""
    try:
        return await RetryPolicyService.create_policy(session=session, policy=policy)

    except Exception as e:
        logger.error(f"Error creating retry policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating retry policy",
        )


@router.get("/pipeline/{pipeline_id}", response_model=RetryPolicyResponse)
async def get_retry_policy(
    pipeline_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get retry policy for a pipeline."""
    try:
        policy = await RetryPolicyService.get_policy(
            session=session,
            pipeline_id=pipeline_id,
        )

        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Retry policy not found for this pipeline",
            )

        return policy

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting retry policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving retry policy",
        )


@router.put("/pipeline/{pipeline_id}", response_model=RetryPolicyResponse)
async def update_retry_policy(
    pipeline_id: UUID,
    update: RetryPolicyUpdate,
    session: AsyncSession = Depends(get_db),
):
    """Update a retry policy for a pipeline."""
    try:
        return await RetryPolicyService.update_policy(
            session=session,
            pipeline_id=pipeline_id,
            update=update,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error updating retry policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating retry policy",
        )


@router.delete("/pipeline/{pipeline_id}")
async def delete_retry_policy(
    pipeline_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Delete a retry policy."""
    try:
        await RetryPolicyService.delete_policy(
            session=session,
            pipeline_id=pipeline_id,
        )

        return {"message": "Retry policy deleted successfully"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error deleting retry policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting retry policy",
        )


@router.post("/calculate", response_model=RetryCalculation)
async def calculate_retry_delay(
    pipeline_id: UUID,
    attempt_number: int,
    session: AsyncSession = Depends(get_db),
):
    """Calculate the next retry delay for an attempt."""
    try:
        policy = await RetryPolicyService.get_policy(
            session=session,
            pipeline_id=pipeline_id,
        )

        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Retry policy not found for this pipeline",
            )

        return RetryPolicyService.calculate_retry_delay(
            policy=policy,
            attempt_number=attempt_number,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating retry delay: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error calculating retry delay",
        )
