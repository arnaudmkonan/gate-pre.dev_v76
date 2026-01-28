"""
Client User and Portal Authentication Models.

Models for client portal users:
- Client users (separate from broker users)
- Role-based access control
- Portal invitations
- Session management

Task 5.1 from ROADMAP_FULL_WORKFLOW.md
"""
from enum import Enum
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, String, DateTime, Date, ForeignKey, Integer, Text, Boolean, Index, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import secrets
import hashlib

from app.models.base import BaseModel


class ClientUserRole(str, Enum):
    """Client user roles."""
    ADMIN = "admin"  # Can manage other client users
    USER = "user"  # Can view and take actions
    READONLY = "readonly"  # View only


class ClientUserStatus(str, Enum):
    """Client user account status."""
    PENDING = "pending"  # Invited but not activated
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class InvitationStatus(str, Enum):
    """Portal invitation status."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ClientUser(BaseModel):
    """
    Client portal user.
    
    Separate from broker/admin users, specifically for importer clients.
    """
    __tablename__ = "client_users"
    
    # User info
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # Null until activated
    
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(50), nullable=True)
    job_title = Column(String(200), nullable=True)
    
    # Link to client company
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    
    # Role and status
    role = Column(String(30), default=ClientUserRole.READONLY.value, nullable=False)
    status = Column(String(30), default=ClientUserStatus.PENDING.value, nullable=False)
    
    # Activation
    activated_at = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    login_count = Column(Integer, default=0, nullable=False)
    
    # Password reset
    reset_token = Column(String(100), nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)
    
    # Notification preferences
    notification_prefs = Column(JSONB, default={
        "entry_filed": True,
        "entry_released": True,
        "exam_required": True,
        "document_requested": True,
        "approval_needed": True,
        "invoice_ready": True,
    })
    
    # Profile settings
    timezone = Column(String(50), default="America/New_York")
    language = Column(String(10), default="en")
    
    # Relationships
    client = relationship("Client", foreign_keys=[client_id])
    
    __table_args__ = (
        Index("ix_client_users_client", "client_id"),
        Index("ix_client_users_status", "status"),
        Index("ix_client_users_email", "email"),
    )
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def set_password(self, password: str):
        """Hash and set password."""
        # Using SHA-256 for simplicity, use bcrypt in production
        salt = secrets.token_hex(16)
        hash_input = f"{salt}:{password}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()
        self.password_hash = f"{salt}:{hash_value}"
    
    def verify_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        if not self.password_hash:
            return False
        try:
            salt, stored_hash = self.password_hash.split(":")
            hash_input = f"{salt}:{password}"
            computed_hash = hashlib.sha256(hash_input.encode()).hexdigest()
            return computed_hash == stored_hash
        except:
            return False
    
    def generate_reset_token(self) -> str:
        """Generate password reset token."""
        token = secrets.token_urlsafe(32)
        self.reset_token = token
        self.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=24)
        return token
    
    def can_view_entry(self, entry_client_id) -> bool:
        """Check if user can view an entry."""
        return str(self.client_id) == str(entry_client_id)
    
    def can_approve_entry(self) -> bool:
        """Check if user can approve entries."""
        return self.role in [ClientUserRole.ADMIN.value, ClientUserRole.USER.value]
    
    def can_upload_documents(self) -> bool:
        """Check if user can upload documents."""
        return self.role in [ClientUserRole.ADMIN.value, ClientUserRole.USER.value]
    
    def can_manage_users(self) -> bool:
        """Check if user can manage other client users."""
        return self.role == ClientUserRole.ADMIN.value
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "phone": self.phone,
            "job_title": self.job_title,
            "client_id": str(self.client_id),
            "role": self.role,
            "status": self.status,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "notification_prefs": self.notification_prefs,
            "timezone": self.timezone,
        }


class PortalInvitation(BaseModel):
    """
    Invitation to join the client portal.
    
    Broker sends invitation, client user sets up account.
    """
    __tablename__ = "portal_invitations"
    
    # Invitation target
    email = Column(String(255), nullable=False, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    
    # Invitation details
    role = Column(String(30), default=ClientUserRole.READONLY.value, nullable=False)
    message = Column(Text, nullable=True)  # Personal message from broker
    
    # Invitation token
    token = Column(String(100), unique=True, nullable=False, index=True)
    
    # Status tracking
    status = Column(String(30), default=InvitationStatus.PENDING.value, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Who sent it
    invited_by_id = Column(UUID(as_uuid=True), nullable=True)  # Broker user ID
    invited_by_name = Column(String(200), nullable=True)
    
    # Acceptance tracking
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("client_users.id"), nullable=True)
    
    # Relationships
    client = relationship("Client", foreign_keys=[client_id])
    user = relationship("ClientUser", foreign_keys=[user_id])
    
    __table_args__ = (
        Index("ix_portal_invitations_token", "token"),
        Index("ix_portal_invitations_email", "email"),
        Index("ix_portal_invitations_client", "client_id"),
        Index("ix_portal_invitations_status", "status"),
    )
    
    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        return (
            self.status == InvitationStatus.PENDING.value and
            not self.is_expired
        )
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "email": self.email,
            "client_id": str(self.client_id),
            "role": self.role,
            "status": self.status,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "invited_by_name": self.invited_by_name,
            "is_expired": self.is_expired,
            "is_valid": self.is_valid,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ClientUserSession(BaseModel):
    """
    Session for client portal user.
    
    Tracks active sessions for security.
    """
    __tablename__ = "client_user_sessions"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("client_users.id", ondelete="CASCADE"), nullable=False)
    
    # Session token
    token = Column(String(100), unique=True, nullable=False, index=True)
    
    # Session info
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    device_info = Column(JSONB, nullable=True)
    
    # Timing
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_activity = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    user = relationship("ClientUser", foreign_keys=[user_id])
    
    __table_args__ = (
        Index("ix_client_user_sessions_token", "token"),
        Index("ix_client_user_sessions_user", "user_id"),
        Index("ix_client_user_sessions_active", "is_active"),
    )
    
    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.is_expired
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "ip_address": self.ip_address,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "is_active": self.is_active,
            "is_valid": self.is_valid,
        }
