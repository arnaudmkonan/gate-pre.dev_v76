"""
Admin override routes for file routing management.
Allows admins to reassign or reroute queued/failed files.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.override_service import OverrideService
from app.services.ack_service import AckService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/override", tags=["admin-override"])


class OverrideRequest(BaseModel):
    """Admin override request."""

    file_id: UUID = Field(..., description="File ID to override")
    new_agent_id: str = Field(..., description="Target agent ID")
    reason: Optional[str] = Field(None, description="Reason for override")
    admin_id: str = Field(..., description="Admin user ID")


class OverrideResponse(BaseModel):
    """Admin override response."""

    status: str
    file_id: str
    agent_id: str
    ack_id: str
    task_id: str
    audit_id: str


@router.post("/", response_model=OverrideResponse, status_code=status.HTTP_200_OK)
async def override_file_routing(
    request: OverrideRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Admin endpoint to override file routing and requeue to different agent.

    Validates admin permissions, records audit entry, and requeues file.

    Returns confirmation within 3 seconds.

    Args:
        request: OverrideRequest with file_id, new_agent_id, reason, admin_id
        session: Database session

    Returns:
        OverrideResponse with confirmation details
    """
    try:
        # Get current ACK to find previous agent
        current_ack = await AckService.get_ack_by_file(session, request.file_id)
        prev_agent_id = current_ack.agent_id if current_ack else None

        # Perform override
        result = await OverrideService.override_and_requeue(
            session,
            admin_id=request.admin_id,
            file_id=request.file_id,
            new_agent_id=request.new_agent_id,
            storage_path=f"uploads/{request.file_id}",
            prev_agent_id=prev_agent_id,
            reason=request.reason,
            prev_routing_decision=current_ack.dispatched_at.isoformat() if current_ack else None,
        )

        logger.info(
            f"Admin {request.admin_id} overrode routing for file {request.file_id} "
            f"to agent {request.new_agent_id}"
        )

        return OverrideResponse(
            status="success",
            file_id=result["file_id"],
            agent_id=result["agent_id"],
            ack_id=result["ack_id"],
            task_id=result["task_id"],
            audit_id=result["audit_id"],
        )

    except PermissionError as e:
        logger.warning(f"Permission denied: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to override file routing",
        )
    except ValueError as e:
        logger.warning(f"Invalid request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except KeyError as e:
        logger.warning(f"Resource not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent or file not found: {e}",
        )
    except Exception as e:
        logger.error(f"Failed to override file routing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to override file routing",
        )
