"""
Document Request Model.

Models for broker-to-client document requests:
- Document request from broker
- Client upload fulfillment
- Status tracking

Task 5.3 from ROADMAP_FULL_WORKFLOW.md
"""
from enum import Enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Date, ForeignKey, Integer, Text, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from app.models.base import BaseModel


class DocumentRequestStatus(str, Enum):
    """Document request status."""
    PENDING = "pending"  # Awaiting document
    UPLOADED = "uploaded"  # Document uploaded by client
    APPROVED = "approved"  # Document approved by broker
    REJECTED = "rejected"  # Document rejected, need new upload
    CANCELLED = "cancelled"


class DocumentRequestPriority(str, Enum):
    """Document request priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class DocumentRequest(BaseModel):
    """
    Document request from broker to client.
    
    Used when broker needs additional documents from importer.
    """
    __tablename__ = "document_requests"
    
    # Link to entry and client
    entry_id = Column(UUID(as_uuid=True), ForeignKey("entries.id", ondelete="CASCADE"), nullable=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    
    # Request details
    document_type = Column(String(100), nullable=False)  # e.g., "Certificate of Origin"
    description = Column(Text, nullable=False)  # Detailed description
    instructions = Column(Text, nullable=True)  # How to get/upload the document
    
    # Priority and deadline
    priority = Column(String(20), default=DocumentRequestPriority.NORMAL.value)
    due_date = Column(Date, nullable=True)
    
    # Status
    status = Column(String(30), default=DocumentRequestStatus.PENDING.value)
    
    # Who requested
    requested_by_id = Column(UUID(as_uuid=True), nullable=True)
    requested_by_name = Column(String(200), nullable=True)
    
    # Fulfillment
    fulfilled_by_id = Column(UUID(as_uuid=True), ForeignKey("client_users.id"), nullable=True)
    fulfilled_at = Column(DateTime(timezone=True), nullable=True)
    document_id = Column(UUID(as_uuid=True), nullable=True)  # Uploaded document ID
    document_filename = Column(String(500), nullable=True)
    
    # Rejection (if applicable)
    rejection_reason = Column(Text, nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    client = relationship("Client", foreign_keys=[client_id])
    entry = relationship("Entry", foreign_keys=[entry_id])
    fulfilled_by = relationship("ClientUser", foreign_keys=[fulfilled_by_id])
    
    __table_args__ = (
        Index("ix_document_requests_client", "client_id"),
        Index("ix_document_requests_entry", "entry_id"),
        Index("ix_document_requests_status", "status"),
        Index("ix_document_requests_due", "due_date"),
    )
    
    @property
    def is_overdue(self) -> bool:
        if not self.due_date:
            return False
        return datetime.now(timezone.utc).date() > self.due_date
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "entry_id": str(self.entry_id) if self.entry_id else None,
            "client_id": str(self.client_id),
            "document_type": self.document_type,
            "description": self.description,
            "instructions": self.instructions,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status,
            "requested_by_name": self.requested_by_name,
            "fulfilled_at": self.fulfilled_at.isoformat() if self.fulfilled_at else None,
            "document_filename": self.document_filename,
            "is_overdue": self.is_overdue,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ClientNotification(BaseModel):
    """
    Notification for client portal user.
    
    Task 5.5: Client Notifications
    """
    __tablename__ = "client_notifications"
    
    # Target user
    user_id = Column(UUID(as_uuid=True), ForeignKey("client_users.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    
    # Notification content
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), nullable=False)  # entry_filed, entry_released, etc.
    
    # Related entities
    entry_id = Column(UUID(as_uuid=True), nullable=True)
    document_request_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Action link
    action_url = Column(String(500), nullable=True)
    action_label = Column(String(100), nullable=True)
    
    # Read status
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    # Email tracking
    email_sent = Column(Boolean, default=False, nullable=False)
    email_sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("ClientUser", foreign_keys=[user_id])
    client = relationship("Client", foreign_keys=[client_id])
    
    __table_args__ = (
        Index("ix_client_notifications_user", "user_id"),
        Index("ix_client_notifications_client", "client_id"),
        Index("ix_client_notifications_read", "is_read"),
        Index("ix_client_notifications_type", "notification_type"),
    )
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "title": self.title,
            "message": self.message,
            "notification_type": self.notification_type,
            "entry_id": str(self.entry_id) if self.entry_id else None,
            "document_request_id": str(self.document_request_id) if self.document_request_id else None,
            "action_url": self.action_url,
            "action_label": self.action_label,
            "is_read": self.is_read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
