"""
Document Request Service.

Manages document requests from broker to client:
- Create document requests
- Client fulfillment
- Status tracking
- Notifications

Task 5.3 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, date, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document_request import (
    DocumentRequest, ClientNotification,
    DocumentRequestStatus, DocumentRequestPriority
)
from app.models.client_portal import ClientUser


class DocumentRequestService:
    """Service for managing document requests."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_request(
        self,
        client_id: UUID,
        document_type: str,
        description: str,
        entry_id: Optional[UUID] = None,
        instructions: Optional[str] = None,
        priority: str = DocumentRequestPriority.NORMAL.value,
        due_date: Optional[date] = None,
        requested_by_id: Optional[UUID] = None,
        requested_by_name: Optional[str] = None,
    ) -> DocumentRequest:
        """Create a document request."""
        request = DocumentRequest(
            client_id=client_id,
            entry_id=entry_id,
            document_type=document_type,
            description=description,
            instructions=instructions,
            priority=priority,
            due_date=due_date,
            status=DocumentRequestStatus.PENDING.value,
            requested_by_id=requested_by_id,
            requested_by_name=requested_by_name,
        )
        
        self.db.add(request)
        await self.db.commit()
        await self.db.refresh(request)
        
        # Create notifications for client users
        await self._notify_client_users(request)
        
        return request
    
    async def _notify_client_users(self, request: DocumentRequest):
        """Create notifications for all active client users."""
        # Get active users for the client
        query = select(ClientUser).where(
            and_(
                ClientUser.client_id == request.client_id,
                ClientUser.status == "active",
            )
        )
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        for user in users:
            # Check notification preferences
            prefs = user.notification_prefs or {}
            if not prefs.get("document_requested", True):
                continue
            
            notification = ClientNotification(
                user_id=user.id,
                client_id=request.client_id,
                title="Document Requested",
                message=f"A {request.document_type} has been requested: {request.description}",
                notification_type="document_requested",
                document_request_id=request.id,
                action_url=f"/portal/document-requests/{request.id}",
                action_label="View Request",
            )
            self.db.add(notification)
        
        await self.db.commit()
    
    async def get_request(self, request_id: UUID) -> Optional[DocumentRequest]:
        """Get document request by ID."""
        query = select(DocumentRequest).where(DocumentRequest.id == request_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_requests(
        self,
        client_id: Optional[UUID] = None,
        entry_id: Optional[UUID] = None,
        status: Optional[str] = None,
        include_completed: bool = False,
    ) -> List[DocumentRequest]:
        """List document requests with filters."""
        query = select(DocumentRequest)
        
        if client_id:
            query = query.where(DocumentRequest.client_id == client_id)
        
        if entry_id:
            query = query.where(DocumentRequest.entry_id == entry_id)
        
        if status:
            query = query.where(DocumentRequest.status == status)
        elif not include_completed:
            query = query.where(DocumentRequest.status.in_([
                DocumentRequestStatus.PENDING.value,
                DocumentRequestStatus.UPLOADED.value,
            ]))
        
        query = query.order_by(
            DocumentRequest.status.asc(),
            DocumentRequest.due_date.asc().nullslast(),
            DocumentRequest.created_at.desc(),
        )
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def fulfill_request(
        self,
        request_id: UUID,
        document_id: UUID,
        document_filename: str,
        fulfilled_by: ClientUser,
    ) -> DocumentRequest:
        """Mark request as fulfilled by uploading document."""
        request = await self.get_request(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        if request.status != DocumentRequestStatus.PENDING.value:
            raise ValueError(f"Request is not pending (status: {request.status})")
        
        # Verify user can fulfill
        if str(fulfilled_by.client_id) != str(request.client_id):
            raise PermissionError("User cannot fulfill requests for other clients")
        
        if not fulfilled_by.can_upload_documents():
            raise PermissionError("User does not have permission to upload documents")
        
        request.status = DocumentRequestStatus.UPLOADED.value
        request.document_id = document_id
        request.document_filename = document_filename
        request.fulfilled_by_id = fulfilled_by.id
        request.fulfilled_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(request)
        
        return request
    
    async def approve_document(
        self,
        request_id: UUID,
    ) -> DocumentRequest:
        """Approve an uploaded document (broker action)."""
        request = await self.get_request(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        if request.status != DocumentRequestStatus.UPLOADED.value:
            raise ValueError(f"Document not uploaded (status: {request.status})")
        
        request.status = DocumentRequestStatus.APPROVED.value
        
        await self.db.commit()
        await self.db.refresh(request)
        
        return request
    
    async def reject_document(
        self,
        request_id: UUID,
        reason: str,
    ) -> DocumentRequest:
        """Reject an uploaded document (broker action)."""
        request = await self.get_request(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        if request.status != DocumentRequestStatus.UPLOADED.value:
            raise ValueError(f"Document not uploaded (status: {request.status})")
        
        request.status = DocumentRequestStatus.REJECTED.value
        request.rejection_reason = reason
        request.rejected_at = datetime.now(timezone.utc)
        request.document_id = None  # Clear document for re-upload
        
        await self.db.commit()
        await self.db.refresh(request)
        
        # Notify client of rejection
        await self._notify_rejection(request)
        
        return request
    
    async def _notify_rejection(self, request: DocumentRequest):
        """Notify client user of document rejection."""
        if request.fulfilled_by_id:
            notification = ClientNotification(
                user_id=request.fulfilled_by_id,
                client_id=request.client_id,
                title="Document Rejected",
                message=f"Your {request.document_type} was rejected: {request.rejection_reason}",
                notification_type="document_rejected",
                document_request_id=request.id,
                action_url=f"/portal/document-requests/{request.id}",
                action_label="Re-upload",
            )
            self.db.add(notification)
            await self.db.commit()
    
    async def resubmit_document(
        self,
        request_id: UUID,
        document_id: UUID,
        document_filename: str,
        fulfilled_by: ClientUser,
    ) -> DocumentRequest:
        """Resubmit document after rejection."""
        request = await self.get_request(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        if request.status != DocumentRequestStatus.REJECTED.value:
            raise ValueError(f"Request is not rejected (status: {request.status})")
        
        request.status = DocumentRequestStatus.UPLOADED.value
        request.document_id = document_id
        request.document_filename = document_filename
        request.fulfilled_by_id = fulfilled_by.id
        request.fulfilled_at = datetime.now(timezone.utc)
        request.rejection_reason = None
        request.rejected_at = None
        
        await self.db.commit()
        await self.db.refresh(request)
        
        return request
    
    async def cancel_request(self, request_id: UUID) -> DocumentRequest:
        """Cancel a document request."""
        request = await self.get_request(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        request.status = DocumentRequestStatus.CANCELLED.value
        
        await self.db.commit()
        await self.db.refresh(request)
        
        return request
    
    async def get_overdue_requests(
        self,
        client_id: Optional[UUID] = None,
    ) -> List[DocumentRequest]:
        """Get overdue document requests."""
        today = date.today()
        
        query = select(DocumentRequest).where(
            and_(
                DocumentRequest.status == DocumentRequestStatus.PENDING.value,
                DocumentRequest.due_date < today,
            )
        )
        
        if client_id:
            query = query.where(DocumentRequest.client_id == client_id)
        
        result = await self.db.execute(query)
        return result.scalars().all()


class ClientNotificationService:
    """Service for managing client notifications."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_notification(
        self,
        user_id: UUID,
        client_id: UUID,
        title: str,
        message: str,
        notification_type: str,
        entry_id: Optional[UUID] = None,
        document_request_id: Optional[UUID] = None,
        action_url: Optional[str] = None,
        action_label: Optional[str] = None,
    ) -> ClientNotification:
        """Create a notification for a user."""
        notification = ClientNotification(
            user_id=user_id,
            client_id=client_id,
            title=title,
            message=message,
            notification_type=notification_type,
            entry_id=entry_id,
            document_request_id=document_request_id,
            action_url=action_url,
            action_label=action_label,
        )
        
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        
        return notification
    
    async def notify_client_users(
        self,
        client_id: UUID,
        title: str,
        message: str,
        notification_type: str,
        entry_id: Optional[UUID] = None,
        action_url: Optional[str] = None,
    ):
        """Send notification to all active client users."""
        # Get active users
        query = select(ClientUser).where(
            and_(
                ClientUser.client_id == client_id,
                ClientUser.status == "active",
            )
        )
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        for user in users:
            # Check preferences
            prefs = user.notification_prefs or {}
            if not prefs.get(notification_type, True):
                continue
            
            notification = ClientNotification(
                user_id=user.id,
                client_id=client_id,
                title=title,
                message=message,
                notification_type=notification_type,
                entry_id=entry_id,
                action_url=action_url,
            )
            self.db.add(notification)
        
        await self.db.commit()
    
    async def get_user_notifications(
        self,
        user_id: UUID,
        unread_only: bool = False,
        limit: int = 50,
    ) -> List[ClientNotification]:
        """Get notifications for a user."""
        query = select(ClientNotification).where(ClientNotification.user_id == user_id)
        
        if unread_only:
            query = query.where(ClientNotification.is_read == False)
        
        query = query.order_by(ClientNotification.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_unread_count(self, user_id: UUID) -> int:
        """Get unread notification count."""
        query = select(func.count(ClientNotification.id)).where(
            and_(
                ClientNotification.user_id == user_id,
                ClientNotification.is_read == False,
            )
        )
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def mark_as_read(self, notification_id: UUID):
        """Mark notification as read."""
        query = select(ClientNotification).where(ClientNotification.id == notification_id)
        result = await self.db.execute(query)
        notification = result.scalar_one_or_none()
        
        if notification:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            await self.db.commit()
    
    async def mark_all_read(self, user_id: UUID):
        """Mark all notifications as read for a user."""
        query = select(ClientNotification).where(
            and_(
                ClientNotification.user_id == user_id,
                ClientNotification.is_read == False,
            )
        )
        result = await self.db.execute(query)
        notifications = result.scalars().all()
        
        now = datetime.now(timezone.utc)
        for n in notifications:
            n.is_read = True
            n.read_at = now
        
        await self.db.commit()
    
    async def delete_notification(self, notification_id: UUID):
        """Delete a notification."""
        query = select(ClientNotification).where(ClientNotification.id == notification_id)
        result = await self.db.execute(query)
        notification = result.scalar_one_or_none()
        
        if notification:
            await self.db.delete(notification)
            await self.db.commit()
    
    async def send_entry_notification(
        self,
        entry_id: UUID,
        client_id: UUID,
        notification_type: str,
        entry_number: Optional[str] = None,
    ):
        """Send standard entry notification."""
        messages = {
            "entry_filed": {
                "title": "Entry Filed",
                "message": f"Entry {entry_number} has been filed with CBP",
            },
            "entry_released": {
                "title": "Entry Released",
                "message": f"Entry {entry_number} has been released by CBP",
            },
            "entry_accepted": {
                "title": "Entry Accepted",
                "message": f"Entry {entry_number} has been accepted by CBP",
            },
            "exam_required": {
                "title": "Exam Required",
                "message": f"Entry {entry_number} has been selected for CBP examination",
            },
            "entry_on_hold": {
                "title": "Entry On Hold",
                "message": f"Entry {entry_number} is on hold - action may be required",
            },
            "approval_needed": {
                "title": "Approval Needed",
                "message": f"Entry {entry_number} is ready for your review and approval",
            },
        }
        
        msg = messages.get(notification_type, {
            "title": "Entry Update",
            "message": f"Entry {entry_number} has been updated",
        })
        
        await self.notify_client_users(
            client_id=client_id,
            title=msg["title"],
            message=msg["message"],
            notification_type=notification_type,
            entry_id=entry_id,
            action_url=f"/portal/entries/{entry_id}",
        )
