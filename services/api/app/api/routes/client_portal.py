"""
Client Portal Authentication API Routes.

Endpoints for client portal authentication and user management.

Task 5.1 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db


router = APIRouter(prefix="/api/portal", tags=["Client Portal"])


# ==================== Request/Response Models ====================

class InviteUserRequest(BaseModel):
    """Invite user request."""
    email: str  # Email address
    client_id: str
    role: str = "readonly"
    message: Optional[str] = None


class AcceptInvitationRequest(BaseModel):
    """Accept invitation request."""
    token: str
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    job_title: Optional[str] = None


class LoginRequest(BaseModel):
    """Login request."""
    email: str  # Email address
    password: str


class PasswordResetRequest(BaseModel):
    """Password reset request."""
    email: str  # Email address


class PasswordResetConfirm(BaseModel):
    """Password reset confirm."""
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    """Change password request."""
    current_password: str
    new_password: str


class UpdateUserRequest(BaseModel):
    """Update user request."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    job_title: Optional[str] = None
    notification_prefs: Optional[dict] = None
    timezone: Optional[str] = None


class UpdateUserRoleRequest(BaseModel):
    """Update user role request."""
    role: str


# ==================== Helper Functions ====================

async def get_current_portal_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Get current portal user from session token."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Extract token from "Bearer <token>"
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    service = ClientPortalAuthService(db)
    user = await service.validate_session(token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    return user


# ==================== Invitation Endpoints ====================

@router.post("/invitations")
async def create_invitation(
    request: InviteUserRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Invite a user to the client portal.
    
    Called by broker to invite client users.
    """
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    try:
        client_uuid = UUID(request.client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientPortalAuthService(db)
    
    try:
        invitation = await service.create_invitation(
            email=request.email,
            client_id=client_uuid,
            role=request.role,
            message=request.message,
        )
        
        return {
            "invitation": invitation.to_dict(),
            "invitation_link": f"/portal/accept?token={invitation.token}",
            "message": f"Invitation sent to {request.email}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/invitations")
async def list_invitations(
    client_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List portal invitations."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    service = ClientPortalAuthService(db)
    
    invitations = await service.list_invitations(
        client_id=UUID(client_id) if client_id else None,
        status=status,
    )
    
    return {
        "invitations": [i.to_dict() for i in invitations],
        "count": len(invitations),
    }


@router.get("/invitations/{token}")
async def get_invitation(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Get invitation details by token."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    service = ClientPortalAuthService(db)
    invitation = await service.get_invitation_by_token(token)
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    # Get client name
    from sqlalchemy import select
    from app.models.client import Client
    
    query = select(Client).where(Client.id == invitation.client_id)
    result = await db.execute(query)
    client = result.scalar_one_or_none()
    
    return {
        "invitation": invitation.to_dict(),
        "client_name": client.name if client else "Unknown",
        "is_valid": invitation.is_valid,
    }


@router.delete("/invitations/{invitation_id}")
async def revoke_invitation(
    invitation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Revoke a pending invitation."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    try:
        invitation_uuid = UUID(invitation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invitation ID")
    
    service = ClientPortalAuthService(db)
    
    try:
        await service.revoke_invitation(invitation_uuid)
        return {"message": "Invitation revoked"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Registration Endpoints ====================

@router.post("/accept-invitation")
async def accept_invitation(
    request: AcceptInvitationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Accept invitation and create account.
    
    Called when user clicks invitation link and submits registration form.
    """
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    service = ClientPortalAuthService(db)
    
    try:
        user = await service.accept_invitation(
            token=request.token,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            phone=request.phone,
            job_title=request.job_title,
        )
        
        # Auto-login after registration
        user, session = await service.login(
            email=user.email,
            password=request.password,
        )
        
        return {
            "user": user.to_dict(),
            "session_token": session.token,
            "message": "Account created successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Authentication Endpoints ====================

@router.post("/login")
async def login(
    request: LoginRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
):
    """Log in to client portal."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    service = ClientPortalAuthService(db)
    
    try:
        user, session = await service.login(
            email=request.email,
            password=request.password,
            ip_address=req.client.host if req.client else None,
            user_agent=req.headers.get("user-agent"),
        )
        
        return {
            "user": user.to_dict(),
            "session_token": session.token,
            "expires_at": session.expires_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout")
async def logout(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Log out from client portal."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    if not authorization:
        return {"message": "Already logged out"}
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() == "bearer":
            service = ClientPortalAuthService(db)
            await service.logout(token)
    except:
        pass
    
    return {"message": "Logged out"}


@router.get("/me")
async def get_current_user(
    user = Depends(get_current_portal_user),
):
    """Get current logged-in user."""
    return {
        "user": user.to_dict(),
    }


# ==================== Password Endpoints ====================

@router.post("/password/forgot")
async def forgot_password(
    request: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request password reset."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    service = ClientPortalAuthService(db)
    token = await service.request_password_reset(request.email)
    
    # In production, send email with reset link
    # Always return success to not reveal if user exists
    return {
        "message": "If an account exists with that email, a reset link has been sent",
        # For testing only - remove in production:
        "_reset_link": f"/portal/reset-password?token={token}" if token else None,
    }


@router.post("/password/reset")
async def reset_password(
    request: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using token."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    service = ClientPortalAuthService(db)
    
    try:
        user = await service.reset_password(request.token, request.new_password)
        return {
            "message": "Password reset successfully",
            "email": user.email,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/password/change")
async def change_password(
    request: ChangePasswordRequest,
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Change password (when logged in)."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    service = ClientPortalAuthService(db)
    
    try:
        await service.change_password(
            user.id,
            request.current_password,
            request.new_password,
        )
        return {"message": "Password changed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== User Profile Endpoints ====================

@router.patch("/me")
async def update_profile(
    request: UpdateUserRequest,
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's profile."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    service = ClientPortalAuthService(db)
    
    updated_user = await service.update_user(
        user.id,
        request.model_dump(exclude_none=True),
    )
    
    return {
        "user": updated_user.to_dict(),
        "message": "Profile updated",
    }


# ==================== User Management (Admin) ====================

@router.get("/users")
async def list_users(
    client_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List client portal users."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    service = ClientPortalAuthService(db)
    
    users = await service.list_users(
        client_id=UUID(client_id) if client_id else None,
        status=status,
    )
    
    return {
        "users": [u.to_dict() for u in users],
        "count": len(users),
    }


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get user details."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    service = ClientPortalAuthService(db)
    user = await service.get_user(user_uuid)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user.to_dict()


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    request: UpdateUserRoleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update user role."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    service = ClientPortalAuthService(db)
    
    try:
        user = await service.update_user(user_uuid, {"role": request.role})
        return {
            "user": user.to_dict(),
            "message": f"Role updated to {request.role}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a user."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    service = ClientPortalAuthService(db)
    
    try:
        await service.deactivate_user(user_uuid)
        return {"message": "User deactivated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/users/{user_id}/reactivate")
async def reactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Reactivate a deactivated user."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    service = ClientPortalAuthService(db)
    
    try:
        await service.reactivate_user(user_uuid)
        return {"message": "User reactivated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Reference Data ====================

@router.get("/reference/roles")
async def get_roles():
    """Get available user roles."""
    from app.models.client_portal import ClientUserRole
    
    return {
        "roles": [
            {"value": "admin", "name": "Client Admin", "description": "Can manage other client users"},
            {"value": "user", "name": "Client User", "description": "Can view and take actions"},
            {"value": "readonly", "name": "Read Only", "description": "View only access"},
        ],
    }
