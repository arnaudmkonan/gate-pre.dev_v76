"""
GATE Platform — Notification Service.

Unified notification dispatch: sends in-app notifications and emails
based on user preferences.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger = logging.getLogger(__name__)

# Notification type definitions
NOTIFICATION_TYPES = {
    "entry_status": {
        "title_template": "Entry {entry_number}: {new_status}",
        "email_method": "send_entry_status_update",
    },
    "document_request": {
        "title_template": "Document request for {entry_number}",
        "email_method": "send_document_request",
    },
    "compliance_alert": {
        "title_template": "Compliance alert: {alert_type}",
        "email_method": "send_compliance_alert",
    },
    "invitation": {
        "title_template": "You've been invited to {client_name}",
        "email_method": "send_invitation",
    },
    "password_reset": {
        "title_template": "Password reset requested",
        "email_method": "send_password_reset",
    },
    "isf_deadline": {
        "title_template": "ISF deadline approaching: {entry_number}",
        "email_method": None,  # In-app only
    },
    "system": {
        "title_template": "{message}",
        "email_method": None,
    },
}


class NotificationService:
    """
    Unified notification dispatch.

    Checks user preferences before sending. Creates in-app notification
    and optionally sends email.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def notify(
        self,
        user_id: UUID,
        notification_type: str,
        title: str,
        body: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        channel: str = "both",
        email_to: Optional[str] = None,
        client_id: Optional[UUID] = None,
    ) -> Notification:
        """
        Create a notification and optionally send an email.

        Args:
            user_id: Target user
            notification_type: Type key from NOTIFICATION_TYPES
            title: Notification title
            body: Optional body text
            data: Structured data (entry_id, etc.)
            channel: "email", "in_app", or "both"
            email_to: Email address (required if channel includes email)
            client_id: Associated client
        """
        # Create in-app notification
        notification = Notification(
            user_id=user_id,
            client_id=client_id,
            type=notification_type,
            title=title,
            body=body,
            data=data,
            channel=channel,
        )
        self.db.add(notification)

        # Send email if configured
        if channel in ("email", "both") and email_to:
            email_sent = await self._send_email(
                notification_type=notification_type,
                email_to=email_to,
                title=title,
                body=body,
                data=data or {},
            )
            notification.email_sent = email_sent
            if email_sent:
                notification.email_sent_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(notification)

        logger.info(f"Notification sent: type={notification_type}, user={user_id}, channel={channel}")
        return notification

    async def notify_entry_status_change(
        self,
        user_id: UUID,
        email: str,
        entry_number: str,
        old_status: str,
        new_status: str,
        entry_url: Optional[str] = None,
        notes: Optional[str] = None,
        client_id: Optional[UUID] = None,
    ) -> Notification:
        """Convenience: Send entry status change notification."""
        return await self.notify(
            user_id=user_id,
            notification_type="entry_status",
            title=f"Entry {entry_number}: {new_status.upper()}",
            body=f"Status changed from {old_status} to {new_status}" + (f". Notes: {notes}" if notes else ""),
            data={
                "entry_number": entry_number,
                "old_status": old_status,
                "new_status": new_status,
                "entry_url": entry_url,
            },
            email_to=email,
            client_id=client_id,
        )

    async def notify_compliance_alert(
        self,
        user_id: UUID,
        email: str,
        alert_type: str,
        entry_number: Optional[str] = None,
        details: Optional[str] = None,
        client_id: Optional[UUID] = None,
    ) -> Notification:
        """Convenience: Send compliance alert notification."""
        return await self.notify(
            user_id=user_id,
            notification_type="compliance_alert",
            title=f"Compliance Alert: {alert_type}",
            body=details,
            data={
                "alert_type": alert_type,
                "entry_number": entry_number,
            },
            email_to=email,
            client_id=client_id,
        )

    # =========================================================================
    # Read / List operations
    # =========================================================================

    async def get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread notifications for a user."""
        result = await self.db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read == False,
            )
        )
        return result.scalar() or 0

    async def list_notifications(
        self,
        user_id: UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Notification], int]:
        """
        List notifications for a user.

        Returns (notifications, total_count).
        """
        q = select(Notification).where(Notification.user_id == user_id)
        count_q = select(func.count(Notification.id)).where(Notification.user_id == user_id)

        if unread_only:
            q = q.where(Notification.is_read == False)
            count_q = count_q.where(Notification.is_read == False)

        # Get total
        total = (await self.db.execute(count_q)).scalar() or 0

        # Get page
        result = await self.db.execute(
            q.order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        notifications = list(result.scalars().all())

        return notifications, total

    async def mark_read(self, notification_id: UUID, user_id: UUID) -> bool:
        """Mark a single notification as read."""
        result = await self.db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
        notification = result.scalar_one_or_none()
        if not notification:
            return False

        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        await self.db.commit()
        return True

    async def mark_all_read(self, user_id: UUID) -> int:
        """Mark all notifications as read. Returns count updated."""
        result = await self.db.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read == False,
            )
            .values(
                is_read=True,
                read_at=datetime.now(timezone.utc),
            )
        )
        await self.db.commit()
        return result.rowcount

    # =========================================================================
    # Internal
    # =========================================================================

    async def _send_email(
        self,
        notification_type: str,
        email_to: str,
        title: str,
        body: Optional[str],
        data: Dict[str, Any],
    ) -> bool:
        """Send notification email using the email service."""
        try:
            from app.services.email_service import email_service

            type_config = NOTIFICATION_TYPES.get(notification_type, {})
            email_method_name = type_config.get("email_method")

            if not email_method_name:
                # No email method for this type
                return False

            method = getattr(email_service, email_method_name, None)
            if not method:
                logger.warning(f"Email method {email_method_name} not found on email_service")
                return False

            # Build kwargs based on notification type
            if notification_type == "entry_status":
                return await method(
                    to_email=email_to,
                    entry_number=data.get("entry_number", ""),
                    old_status=data.get("old_status", ""),
                    new_status=data.get("new_status", ""),
                    entry_url=data.get("entry_url"),
                    notes=body,
                )
            elif notification_type == "compliance_alert":
                return await method(
                    to_email=email_to,
                    alert_type=data.get("alert_type", ""),
                    entry_number=data.get("entry_number"),
                    details=body,
                )
            elif notification_type == "document_request":
                return await method(
                    to_email=email_to,
                    requester_name=data.get("requester_name", "GATE Platform"),
                    document_types=data.get("document_types", []),
                    entry_number=data.get("entry_number"),
                    message=body,
                )
            else:
                logger.debug(f"No specific email handler for type: {notification_type}")
                return False

        except Exception as e:
            logger.error(f"Failed to send notification email: {e}")
            return False
