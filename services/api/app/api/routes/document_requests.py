"""
Document Request and Notification API Routes.

Endpoints for document requests and client notifications.

Tasks 5.3 and 5.5 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.routes.client_portal import get_current_portal_user


router = APIRouter(prefix="/api/portal", tags=["Document Requests & Notifications"])


# ==================== Request Models ====================

class CreateDocumentRequest(BaseModel):
    """Create document request."""
    client_id: str
    document_type: str
    description: str
    entry_id: Optional[str] = None
    instructions: Optional[str] = None
    priority: str = "normal"
    due_date: Optional[str] = None  # YYYY-MM-DD


class FulfillDocumentRequest(BaseModel):
    """Fulfill document request."""
    document_id: str
    document_filename: str


class RejectDocumentRequest(BaseModel):
    """Reject document request."""
    reason: str


# ==================== Document Request Endpoints (Broker) ====================

@router.post("/document-requests")
async def create_document_request(
    request: CreateDocumentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a document request (broker action)."""
    from app.services.document_request_service import DocumentRequestService
    
    try:
        client_uuid = UUID(request.client_id)
        entry_uuid = UUID(request.entry_id) if request.entry_id else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    service = DocumentRequestService(db)
    
    doc_request = await service.create_request(
        client_id=client_uuid,
        document_type=request.document_type,
        description=request.description,
        entry_id=entry_uuid,
        instructions=request.instructions,
        priority=request.priority,
        due_date=datetime.strptime(request.due_date, "%Y-%m-%d").date() if request.due_date else None,
    )
    
    return {
        "document_request": doc_request.to_dict(),
        "message": "Document request created",
    }


@router.get("/document-requests")
async def list_document_requests(
    client_id: Optional[str] = Query(None),
    entry_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    include_completed: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """List document requests."""
    from app.services.document_request_service import DocumentRequestService
    
    service = DocumentRequestService(db)
    
    requests = await service.list_requests(
        client_id=UUID(client_id) if client_id else None,
        entry_id=UUID(entry_id) if entry_id else None,
        status=status,
        include_completed=include_completed,
    )
    
    return {
        "document_requests": [r.to_dict() for r in requests],
        "count": len(requests),
    }


@router.get("/document-requests/{request_id}")
async def get_document_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get document request details."""
    from app.services.document_request_service import DocumentRequestService
    
    try:
        request_uuid = UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request ID")
    
    service = DocumentRequestService(db)
    doc_request = await service.get_request(request_uuid)
    
    if not doc_request:
        raise HTTPException(status_code=404, detail="Document request not found")
    
    return doc_request.to_dict()


@router.post("/document-requests/{request_id}/approve")
async def approve_document(
    request_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Approve an uploaded document (broker action)."""
    from app.services.document_request_service import DocumentRequestService
    
    try:
        request_uuid = UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request ID")
    
    service = DocumentRequestService(db)
    
    try:
        doc_request = await service.approve_document(request_uuid)
        return {
            "document_request": doc_request.to_dict(),
            "message": "Document approved",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/document-requests/{request_id}/reject")
async def reject_document(
    request_id: str,
    request: RejectDocumentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reject an uploaded document (broker action)."""
    from app.services.document_request_service import DocumentRequestService
    
    try:
        request_uuid = UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request ID")
    
    service = DocumentRequestService(db)
    
    try:
        doc_request = await service.reject_document(request_uuid, request.reason)
        return {
            "document_request": doc_request.to_dict(),
            "message": "Document rejected",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/document-requests/{request_id}")
async def cancel_document_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a document request."""
    from app.services.document_request_service import DocumentRequestService
    
    try:
        request_uuid = UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request ID")
    
    service = DocumentRequestService(db)
    
    try:
        await service.cancel_request(request_uuid)
        return {"message": "Document request cancelled"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Client Portal Endpoints ====================

@router.get("/my-document-requests")
async def list_my_document_requests(
    status: Optional[str] = Query(None),
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """List document requests for logged-in client."""
    from app.services.document_request_service import DocumentRequestService
    
    service = DocumentRequestService(db)
    
    requests = await service.list_requests(
        client_id=user.client_id,
        status=status,
    )
    
    return {
        "document_requests": [r.to_dict() for r in requests],
        "count": len(requests),
    }


@router.post("/document-requests/{request_id}/fulfill")
async def fulfill_document_request(
    request_id: str,
    request: FulfillDocumentRequest,
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Fulfill a document request by uploading document."""
    from app.services.document_request_service import DocumentRequestService
    
    try:
        request_uuid = UUID(request_id)
        document_uuid = UUID(request.document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    service = DocumentRequestService(db)
    
    try:
        doc_request = await service.fulfill_request(
            request_uuid,
            document_uuid,
            request.document_filename,
            user,
        )
        return {
            "document_request": doc_request.to_dict(),
            "message": "Document uploaded successfully",
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Notification Endpoints ====================

@router.get("/notifications")
async def get_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Get notifications for logged-in user."""
    from app.services.document_request_service import ClientNotificationService
    
    service = ClientNotificationService(db)
    notifications = await service.get_user_notifications(user.id, unread_only, limit)
    unread_count = await service.get_unread_count(user.id)
    
    return {
        "notifications": [n.to_dict() for n in notifications],
        "count": len(notifications),
        "unread_count": unread_count,
    }


@router.get("/notifications/count")
async def get_notification_count(
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Get unread notification count."""
    from app.services.document_request_service import ClientNotificationService
    
    service = ClientNotificationService(db)
    count = await service.get_unread_count(user.id)
    
    return {"unread_count": count}


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark notification as read."""
    from app.services.document_request_service import ClientNotificationService
    
    try:
        notification_uuid = UUID(notification_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid notification ID")
    
    service = ClientNotificationService(db)
    await service.mark_as_read(notification_uuid)
    
    return {"message": "Notification marked as read"}


@router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read."""
    from app.services.document_request_service import ClientNotificationService
    
    service = ClientNotificationService(db)
    await service.mark_all_read(user.id)
    
    return {"message": "All notifications marked as read"}


@router.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: str,
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a notification."""
    from app.services.document_request_service import ClientNotificationService
    
    try:
        notification_uuid = UUID(notification_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid notification ID")
    
    service = ClientNotificationService(db)
    await service.delete_notification(notification_uuid)
    
    return {"message": "Notification deleted"}
