"""
Notification API routes.

Endpoints for listing, reading, and managing user notifications.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.notification_service import NotificationService, NOTIFICATION_TYPES

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("/types")
async def list_notification_types():
    """List all notification types and their configuration."""
    return {
        "types": {
            key: {"title_template": val["title_template"], "has_email": val.get("email_method") is not None}
            for key, val in NOTIFICATION_TYPES.items()
        }
    }


@router.get("")
async def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user_id: str = Query(default=None, description="User ID (from auth context in production)"),
    db: AsyncSession = Depends(get_db),
):
    """
    List notifications for the current user.

    Returns paginated notifications with unread count.
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")

    service = NotificationService(db)
    notifications, total = await service.list_notifications(
        user_id=UUID(user_id),
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    unread_count = await service.get_unread_count(UUID(user_id))

    return {
        "total": total,
        "unread_count": unread_count,
        "offset": offset,
        "limit": limit,
        "notifications": [
            {
                "id": str(n.id),
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "data": n.data,
                "is_read": n.is_read,
                "channel": n.channel,
                "created_at": n.created_at.isoformat(),
                "read_at": n.read_at.isoformat() if n.read_at else None,
            }
            for n in notifications
        ],
    }


@router.get("/unread-count")
async def get_unread_count(
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get the number of unread notifications. Used by the notification bell."""
    service = NotificationService(db)
    count = await service.get_unread_count(UUID(user_id))
    return {"unread_count": count}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db),
):
    """Mark a single notification as read."""
    service = NotificationService(db)
    success = await service.mark_read(UUID(notification_id), UUID(user_id))
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"marked_read": True}


@router.post("/read-all")
async def mark_all_read(
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read."""
    service = NotificationService(db)
    count = await service.mark_all_read(UUID(user_id))
    return {"marked_read": count}
