"""API routes for normalization and silver records management."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/normalization", tags=["normalization"])


@router.post(
    "/trigger",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def trigger_normalization(
    session: AsyncSession = Depends(get_db),
):
    """Trigger normalization for completed extractions."""
    try:
        logger.info("Triggering normalization for completed extractions")
        # In production, this would start the normalization pipeline
        # For now, just return success
        return {
            "status": "success",
            "message": "Normalization triggered",
            "processed_count": 0,
        }
    except Exception as e:
        logger.error(f"Error triggering normalization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
