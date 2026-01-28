"""
Client Portal Authentication Service.

Handles client user authentication:
- User registration via invitation
- Login/logout
- Session management
- Password reset
- Role-based access control

Task 5.1 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
import secrets

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.client_portal import (
    ClientUser, PortalInvitation, ClientUserSession,
    ClientUserRole, ClientUserStatus, InvitationStatus
)
from app.models.client import Client


class ClientPortalAuthService:
    """Service for client portal authentication."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ==================== Invitations ====================
    
    async def create_invitation(
        self,
        email: str,
        client_id: UUID,
        role: str = ClientUserRole.READONLY.value,
        invited_by_id: Optional[UUID] = None,
        invited_by_name: Optional[str] = None,
        message: Optional[str] = None,
        expires_in_days: int = 7,
    ) -> PortalInvitation:
        """
        Create an invitation for a client user.
        
        Returns invitation with token for email link.
        """
        # Check if user already exists
        existing_user = await self.get_user_by_email(email)
        if existing_user:
            raise ValueError(f"User with email {email} already exists")
        
        # Check if valid invitation already exists
        existing_invite = await self.get_pending_invitation_by_email(email, client_id)
        if existing_invite and existing_invite.is_valid:
            raise ValueError(f"Pending invitation already exists for {email}")
        
        # Verify client exists
        client = await self._get_client(client_id)
        if not client:
            raise ValueError(f"Client {client_id} not found")
        
        # Generate secure token
        token = secrets.token_urlsafe(32)
        
        invitation = PortalInvitation(
            email=email.lower().strip(),
            client_id=client_id,
            role=role,
            message=message,
            token=token,
            status=InvitationStatus.PENDING.value,
            expires_at=datetime.now(timezone.utc) + timedelta(days=expires_in_days),
            invited_by_id=invited_by_id,
            invited_by_name=invited_by_name,
        )
        
        self.db.add(invitation)
        await self.db.commit()
        await self.db.refresh(invitation)
        
        return invitation
    
    async def get_invitation_by_token(self, token: str) -> Optional[PortalInvitation]:
        """Get invitation by token."""
        query = select(PortalInvitation).where(PortalInvitation.token == token)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_pending_invitation_by_email(
        self,
        email: str,
        client_id: UUID,
    ) -> Optional[PortalInvitation]:
        """Get pending invitation for email at client."""
        query = select(PortalInvitation).where(
            and_(
                PortalInvitation.email == email.lower().strip(),
                PortalInvitation.client_id == client_id,
                PortalInvitation.status == InvitationStatus.PENDING.value,
            )
        ).order_by(PortalInvitation.created_at.desc())
        
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def list_invitations(
        self,
        client_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> List[PortalInvitation]:
        """List invitations with optional filters."""
        query = select(PortalInvitation)
        
        if client_id:
            query = query.where(PortalInvitation.client_id == client_id)
        
        if status:
            query = query.where(PortalInvitation.status == status)
        
        query = query.order_by(PortalInvitation.created_at.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def revoke_invitation(self, invitation_id: UUID):
        """Revoke a pending invitation."""
        invitation = await self._get_invitation(invitation_id)
        if not invitation:
            raise ValueError(f"Invitation {invitation_id} not found")
        
        invitation.status = InvitationStatus.REVOKED.value
        await self.db.commit()
    
    # ==================== User Registration ====================
    
    async def accept_invitation(
        self,
        token: str,
        password: str,
        first_name: str,
        last_name: str,
        phone: Optional[str] = None,
        job_title: Optional[str] = None,
    ) -> ClientUser:
        """
        Accept invitation and create user account.
        
        Called when user clicks invitation link and completes registration.
        """
        invitation = await self.get_invitation_by_token(token)
        
        if not invitation:
            raise ValueError("Invalid invitation token")
        
        if not invitation.is_valid:
            if invitation.is_expired:
                raise ValueError("Invitation has expired")
            else:
                raise ValueError("Invitation is no longer valid")
        
        # Create user
        user = ClientUser(
            email=invitation.email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            job_title=job_title,
            client_id=invitation.client_id,
            role=invitation.role,
            status=ClientUserStatus.ACTIVE.value,
            activated_at=datetime.now(timezone.utc),
        )
        user.set_password(password)
        
        self.db.add(user)
        
        # Update invitation
        invitation.status = InvitationStatus.ACCEPTED.value
        invitation.accepted_at = datetime.now(timezone.utc)
        invitation.user_id = user.id
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    # ==================== Authentication ====================
    
    async def login(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[ClientUser, ClientUserSession]:
        """
        Authenticate user and create session.
        
        Returns (user, session) on success.
        """
        user = await self.get_user_by_email(email)
        
        if not user:
            raise ValueError("Invalid email or password")
        
        if user.status != ClientUserStatus.ACTIVE.value:
            raise ValueError(f"Account is {user.status}")
        
        if not user.verify_password(password):
            raise ValueError("Invalid email or password")
        
        # Update login stats
        user.last_login_at = datetime.now(timezone.utc)
        user.login_count = (user.login_count or 0) + 1
        
        # Create session
        session = await self._create_session(user.id, ip_address, user_agent)
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return user, session
    
    async def logout(self, session_token: str):
        """Invalidate session."""
        query = select(ClientUserSession).where(ClientUserSession.token == session_token)
        result = await self.db.execute(query)
        session = result.scalar_one_or_none()
        
        if session:
            session.is_active = False
            await self.db.commit()
    
    async def logout_all(self, user_id: UUID):
        """Invalidate all sessions for user."""
        query = select(ClientUserSession).where(
            and_(
                ClientUserSession.user_id == user_id,
                ClientUserSession.is_active == True,
            )
        )
        result = await self.db.execute(query)
        sessions = result.scalars().all()
        
        for session in sessions:
            session.is_active = False
        
        await self.db.commit()
    
    async def validate_session(self, session_token: str) -> Optional[ClientUser]:
        """
        Validate session token and return user.
        
        Returns None if session is invalid.
        """
        query = (
            select(ClientUserSession)
            .options(selectinload(ClientUserSession.user))
            .where(ClientUserSession.token == session_token)
        )
        result = await self.db.execute(query)
        session = result.scalar_one_or_none()
        
        if not session or not session.is_valid:
            return None
        
        # Update last activity
        session.last_activity = datetime.now(timezone.utc)
        await self.db.commit()
        
        return session.user
    
    async def _create_session(
        self,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        expires_in_hours: int = 24,
    ) -> ClientUserSession:
        """Create a new session for user."""
        token = secrets.token_urlsafe(32)
        
        session = ClientUserSession(
            user_id=user_id,
            token=token,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_in_hours),
            is_active=True,
        )
        
        self.db.add(session)
        await self.db.flush()
        
        return session
    
    # ==================== Password Management ====================
    
    async def request_password_reset(self, email: str) -> Optional[str]:
        """
        Request password reset.
        
        Returns reset token if user exists, None otherwise.
        """
        user = await self.get_user_by_email(email)
        
        if not user:
            # Don't reveal if user exists
            return None
        
        token = user.generate_reset_token()
        await self.db.commit()
        
        return token
    
    async def reset_password(self, token: str, new_password: str) -> ClientUser:
        """Reset password using token."""
        query = select(ClientUser).where(
            and_(
                ClientUser.reset_token == token,
                ClientUser.reset_token_expires > datetime.now(timezone.utc),
            )
        )
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("Invalid or expired reset token")
        
        user.set_password(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        
        # Invalidate all sessions
        await self.logout_all(user.id)
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def change_password(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str,
    ) -> ClientUser:
        """Change password (requires current password)."""
        user = await self.get_user(user_id)
        
        if not user:
            raise ValueError("User not found")
        
        if not user.verify_password(current_password):
            raise ValueError("Current password is incorrect")
        
        user.set_password(new_password)
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    # ==================== User Management ====================
    
    async def get_user(self, user_id: UUID) -> Optional[ClientUser]:
        """Get user by ID."""
        query = select(ClientUser).where(ClientUser.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, email: str) -> Optional[ClientUser]:
        """Get user by email."""
        query = select(ClientUser).where(
            ClientUser.email == email.lower().strip()
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_users(
        self,
        client_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> List[ClientUser]:
        """List users with optional filters."""
        query = select(ClientUser)
        
        if client_id:
            query = query.where(ClientUser.client_id == client_id)
        
        if status:
            query = query.where(ClientUser.status == status)
        
        query = query.order_by(ClientUser.last_name)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update_user(
        self,
        user_id: UUID,
        data: Dict[str, Any],
    ) -> ClientUser:
        """Update user profile."""
        user = await self.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        updatable = [
            'first_name', 'last_name', 'phone', 'job_title',
            'role', 'status', 'notification_prefs', 'timezone', 'language'
        ]
        
        for field in updatable:
            if field in data:
                setattr(user, field, data[field])
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def deactivate_user(self, user_id: UUID):
        """Deactivate a user."""
        user = await self.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        user.status = ClientUserStatus.DEACTIVATED.value
        await self.logout_all(user_id)
        await self.db.commit()
    
    async def reactivate_user(self, user_id: UUID):
        """Reactivate a deactivated user."""
        user = await self.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        user.status = ClientUserStatus.ACTIVE.value
        await self.db.commit()
    
    # ==================== Helpers ====================
    
    async def _get_client(self, client_id: UUID) -> Optional[Client]:
        """Get client by ID."""
        query = select(Client).where(Client.id == client_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_invitation(self, invitation_id: UUID) -> Optional[PortalInvitation]:
        """Get invitation by ID."""
        query = select(PortalInvitation).where(PortalInvitation.id == invitation_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        query = select(ClientUserSession).where(
            and_(
                ClientUserSession.is_active == True,
                ClientUserSession.expires_at < datetime.now(timezone.utc),
            )
        )
        result = await self.db.execute(query)
        sessions = result.scalars().all()
        
        for session in sessions:
            session.is_active = False
        
        await self.db.commit()
        
        return len(sessions)
