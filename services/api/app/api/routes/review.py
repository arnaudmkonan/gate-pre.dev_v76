"""
Review API Routes.

Endpoints for the human-in-the-loop review workflow.
"""

import logging
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.review_service import ReviewService
from app.core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/review", tags=["Review"], dependencies=[Depends(get_current_user)])


# Request/Response Models

class AssignRequest(BaseModel):
    """Request to assign a review item."""
    reviewer: str


class ApproveRequest(BaseModel):
    """Request to approve a review item."""
    reviewer: str
    notes: Optional[str] = None


class RejectRequest(BaseModel):
    """Request to reject a review item."""
    reviewer: str
    reason: str


class CorrectRequest(BaseModel):
    """Request to correct an extraction."""
    extraction_id: str
    corrected_value: Any
    reviewer: str
    notes: Optional[str] = None


class AddToQueueRequest(BaseModel):
    """Request to manually add document to review queue."""
    document_id: str
    reason: str
    reason_code: str = "manual"
    priority: int = 1


# API Endpoints

@router.get("/queue")
@router.get("/items")
async def get_review_queue(
    status: Optional[str] = Query(default=None, description="Filter by status"),
    assigned_to: Optional[str] = Query(default=None, description="Filter by assignee"),
    reason_code: Optional[str] = Query(default=None, description="Filter by reason_code"),
    file_type: Optional[str] = Query(default=None, description="Filter by document file_type"),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0),
    session: AsyncSession = Depends(get_db)
):
    """
    Get items in the review queue.
    
    Returns queue items with document details, sorted by priority.
    """
    try:
        items = await ReviewService.get_review_queue(
            session, status, assigned_to, reason_code, file_type, limit, offset
        )
        return {
            "items": items,
            "count": len(items),
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"Error getting review queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_review_stats(
    days: int = Query(default=7, le=90),
    session: AsyncSession = Depends(get_db)
):
    """
    Get review queue statistics.
    """
    try:
        stats = await ReviewService.get_review_stats(session, days)
        return stats
    except Exception as e:
        logger.error(f"Error getting review stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/item/{item_id}")
async def get_review_item_detail(
    item_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Get detailed view of a review item.
    
    Includes document content, all extractions, and review history.
    """
    try:
        detail = await ReviewService.get_review_item_detail(session, item_id)
        if not detail:
            raise HTTPException(status_code=404, detail="Review item not found")
        return detail
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting review item detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _resolve_reviewer(provided: Optional[str], current_user: dict) -> str:
    if provided and provided not in ("reviewer", "user"):
        return provided
    return current_user.get("email") or current_user.get("sub") or provided or "reviewer"


@router.post("/item/{item_id}/assign")
async def assign_review_item(
    item_id: str,
    request: AssignRequest,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Assign a review item to a reviewer.
    """
    try:
        actor = _resolve_reviewer(request.reviewer, current_user)
        item = await ReviewService.assign_item(session, item_id, actor)
        return {
            "message": f"Assigned to {actor}",
            "item": item.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error assigning review item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/item/{item_id}/approve")
async def approve_review_item(
    item_id: str,
    request: ApproveRequest,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Approve a review item (extractions are correct).
    """
    try:
        actor = _resolve_reviewer(request.reviewer, current_user)
        item = await ReviewService.approve_item(
            session, item_id, actor, request.notes
        )
        from app.services.review_service import _next_pending_item_id, _shipments_for_document

        next_id = await _next_pending_item_id(session, exclude_id=item.id)
        shipments = await _shipments_for_document(session, item.document_id)
        return {
            "message": "Item approved",
            "item": item.to_dict(),
            "next_pending_id": next_id,
            "shipments": shipments,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error approving review item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/item/{item_id}/reject")
async def reject_review_item(
    item_id: str,
    request: RejectRequest,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Reject a review item (extractions are too poor to use).
    """
    try:
        actor = _resolve_reviewer(request.reviewer, current_user)
        item = await ReviewService.reject_item(
            session, item_id, actor, request.reason
        )
        from app.services.review_service import _next_pending_item_id

        next_id = await _next_pending_item_id(session, exclude_id=item.id)
        return {
            "message": "Item rejected",
            "item": item.to_dict(),
            "next_pending_id": next_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error rejecting review item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/item/{item_id}/correct")
async def correct_extraction(
    item_id: str,
    request: CorrectRequest,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Correct a specific extraction field.
    """
    try:
        actor = _resolve_reviewer(request.reviewer, current_user)
        extraction = await ReviewService.correct_extraction(
            session,
            item_id,
            request.extraction_id,
            request.corrected_value,
            actor,
            request.notes
        )
        return {
            "message": "Extraction corrected",
            "extraction": extraction.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error correcting extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue/add")
async def add_to_review_queue(
    request: AddToQueueRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Manually add a document to the review queue.
    """
    try:
        item = await ReviewService.add_to_review_queue(
            session,
            request.document_id,
            request.reason,
            request.reason_code,
            priority=request.priority
        )
        return {
            "message": "Added to review queue",
            "item": item.to_dict(),
        }
    except Exception as e:
        logger.error(f"Error adding to review queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/item/{item_id}/skip")
async def skip_review_item(
    item_id: str,
    reviewer: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Skip a review item (process later).
    """
    from uuid import UUID
    from sqlalchemy import select
    from app.models.review_queue import ReviewQueueItem, ReviewAction
    
    try:
        item_uuid = UUID(item_id)
        result = await session.execute(
            select(ReviewQueueItem).where(ReviewQueueItem.id == item_uuid)
        )
        item = result.scalar_one_or_none()
        
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        actor = _resolve_reviewer(reviewer, current_user)
        item.status = "skipped"
        item.assigned_to = None
        
        action = ReviewAction(
            review_item_id=item_uuid,
            action="skip",
            actor=actor,
        )
        session.add(action)
        
        await session.commit()
        
        return {"message": "Item skipped", "item": item.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error skipping item: {e}")
        raise HTTPException(status_code=500, detail=str(e))
