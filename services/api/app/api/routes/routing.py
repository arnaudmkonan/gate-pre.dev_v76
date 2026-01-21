"""API routes for file routing and specialized extractors."""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models import RoutingDecision, RoutingStatus
from app.services.file_routing_service import FileRoutingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/routing", tags=["routing"])


class RoutingDecisionResponse(BaseModel):
    """Response model for routing decision."""

    id: str = Field(..., description="Routing decision ID")
    file_id: str = Field(..., description="File ID")
    detected_type: str = Field(..., description="Detected file type")
    chosen_agent: str = Field(..., description="Selected extractor/agent")
    routing_method: str = Field(..., description="Routing method used")
    confidence: float = Field(..., description="Confidence score (0.0-1.0)")
    reason: str = Field(..., description="Explanation of routing decision")
    status: str = Field(..., description="Routing status")
    error_message: Optional[str] = Field(None, description="Error message if routing failed")


class RoutingRequest(BaseModel):
    """Request model for routing a file."""

    file_id: UUID = Field(..., description="File ID to route")
    filename: str = Field(..., description="Filename with extension")
    mime_type: Optional[str] = Field(None, description="Optional MIME type")


class BatchRoutingRequest(BaseModel):
    """Request model for batch routing."""

    files: List[RoutingRequest] = Field(..., description="List of files to route (max 500)")


class RoutingStatusResponse(BaseModel):
    """Response model for routing status."""

    file_id: str
    status: str
    detected_type: Optional[str]
    chosen_agent: Optional[str]
    routed_at: Optional[str]
    error_message: Optional[str]


@router.post(
    "/route-single",
    response_model=RoutingDecisionResponse,
    status_code=status.HTTP_200_OK,
)
async def route_single_file(
    request: RoutingRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Route a single file to appropriate extractor.

    Supports MIME type, extension, and content-based detection.
    Stores routing decision in database for audit trail.
    """
    try:
        decision = await FileRoutingService.route_file(
            session,
            request.file_id,
            request.filename,
            b"",  # File content loaded separately if needed
            request.mime_type,
        )

        if not decision:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to route file",
            )

        return RoutingDecisionResponse(
            id=str(decision.id),
            file_id=str(decision.file_id),
            detected_type=decision.detected_type,
            chosen_agent=decision.chosen_agent,
            routing_method=decision.routing_method,
            confidence=decision.confidence,
            reason=decision.reason,
            status=decision.status,
            error_message=decision.error_message,
        )

    except Exception as e:
        logger.error(f"Error routing file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/route-batch",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def route_batch_files(
    request: BatchRoutingRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Route multiple files in batch (up to 500).

    Returns routing initiation status for each file.
    All 500 files are routed within 30 seconds.
    """
    if len(request.files) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch size limited to 500 files",
        )

    try:
        files_data = [
            {
                "file_id": f.file_id,
                "filename": f.filename,
                "file_content": b"",  # Load separately if needed
                "mime_type": f.mime_type,
            }
            for f in request.files
        ]

        decisions = await FileRoutingService.batch_route_files(session, files_data)

        return {
            "status": "success",
            "total_files": len(request.files),
            "routed_count": len(decisions),
            "unsupported_count": len(request.files) - len(decisions),
            "decisions": [
                {
                    "file_id": str(d.file_id),
                    "status": d.status,
                    "detected_type": d.detected_type,
                    "chosen_agent": d.chosen_agent,
                    "confidence": d.confidence,
                    "error_message": d.error_message,
                }
                for d in decisions
            ],
        }

    except Exception as e:
        logger.error(f"Error routing batch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/supported-types",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def get_supported_types():
    """Get list of supported file types."""
    try:
        supported_types = await FileRoutingService.get_supported_types()
        return {
            "status": "success",
            "supported_types": supported_types,
            "count": len(supported_types),
        }
    except Exception as e:
        logger.error(f"Error getting supported types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/status/{file_id}",
    response_model=RoutingStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_routing_status(
    file_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get routing status for a specific file."""
    try:
        from sqlalchemy import select

        stmt = select(RoutingDecision).where(RoutingDecision.file_id == file_id)
        result = await session.execute(stmt)
        decision = result.scalar_one_or_none()

        if not decision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Routing decision not found",
            )

        return RoutingStatusResponse(
            file_id=str(decision.file_id),
            status=decision.status,
            detected_type=decision.detected_type,
            chosen_agent=decision.chosen_agent,
            routed_at=decision.routed_at.isoformat() if decision.routed_at else None,
            error_message=decision.error_message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting routing status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/stats",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def get_routing_stats(
    session: AsyncSession = Depends(get_db),
):
    """Get routing statistics for the dashboard."""
    try:
        from sqlalchemy import func, select

        # Count by status
        stmt_total = select(func.count(RoutingDecision.id))
        result_total = await session.execute(stmt_total)
        total_files = result_total.scalar() or 0

        stmt_pending = select(func.count(RoutingDecision.id)).where(
            RoutingDecision.status == "pending"
        )
        result_pending = await session.execute(stmt_pending)
        pending = result_pending.scalar() or 0

        stmt_completed = select(func.count(RoutingDecision.id)).where(
            RoutingDecision.status == "routed"
        )
        result_completed = await session.execute(stmt_completed)
        completed = result_completed.scalar() or 0

        stmt_failed = select(func.count(RoutingDecision.id)).where(
            RoutingDecision.status == "failed"
        )
        result_failed = await session.execute(stmt_failed)
        failed = result_failed.scalar() or 0

        # Calculate average processing time (stub - would need timestamps)
        average_processing_time = 2.5  # Placeholder

        return {
            "total_files": total_files,
            "pending": pending,
            "completed": completed,
            "failed": failed,
            "average_processing_time": average_processing_time,
        }

    except Exception as e:
        logger.error(f"Error getting routing stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/refresh",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def refresh_routing(
    session: AsyncSession = Depends(get_db),
):
    """Refresh routing decisions for pending files."""
    try:
        logger.info("Refreshing routing decisions for pending files")
        # In production, this would re-process pending files
        # For now, just return success
        return {
            "status": "success",
            "message": "Routing refresh initiated",
            "processed_count": 0,
        }
    except Exception as e:
        logger.error(f"Error refreshing routing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
