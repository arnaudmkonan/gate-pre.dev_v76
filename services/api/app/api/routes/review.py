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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/review", tags=["Review"])


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
async def get_review_queue(
    status: Optional[str] = Query(default=None, description="Filter by status"),
    assigned_to: Optional[str] = Query(default=None, description="Filter by assignee"),
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
            session, status, assigned_to, limit, offset
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


@router.post("/item/{item_id}/assign")
async def assign_review_item(
    item_id: str,
    request: AssignRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Assign a review item to a reviewer.
    """
    try:
        item = await ReviewService.assign_item(session, item_id, request.reviewer)
        return {
            "message": f"Assigned to {request.reviewer}",
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
    session: AsyncSession = Depends(get_db)
):
    """
    Approve a review item (extractions are correct).
    """
    try:
        item = await ReviewService.approve_item(
            session, item_id, request.reviewer, request.notes
        )
        return {
            "message": "Item approved",
            "item": item.to_dict(),
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
    session: AsyncSession = Depends(get_db)
):
    """
    Reject a review item (extractions are too poor to use).
    """
    try:
        item = await ReviewService.reject_item(
            session, item_id, request.reviewer, request.reason
        )
        return {
            "message": "Item rejected",
            "item": item.to_dict(),
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
    session: AsyncSession = Depends(get_db)
):
    """
    Correct a specific extraction field.
    """
    try:
        extraction = await ReviewService.correct_extraction(
            session,
            item_id,
            request.extraction_id,
            request.corrected_value,
            request.reviewer,
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
    reviewer: str = Query(...),
    session: AsyncSession = Depends(get_db)
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
        
        item.status = "skipped"
        item.assigned_to = None
        
        action = ReviewAction(
            review_item_id=item_uuid,
            action="skip",
            actor=reviewer,
        )
        session.add(action)
        
        await session.commit()
        
        return {"message": "Item skipped", "item": item.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error skipping item: {e}")
        raise HTTPException(status_code=500, detail=str(e))
