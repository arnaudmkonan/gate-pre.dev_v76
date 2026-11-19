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


class ResendVerificationRequest(BaseModel):
    email: str


class VerifyEmailRequest(BaseModel):
    token: str


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


BROKERAGE_ONLY_ROLES = {"admin", "broker_admin", "broker_staff"}
ALLOWED_PORTAL_ROLES = {"admin", "broker_staff", "client_admin", "user", "readonly"}


def _assert_caller_can_manage_client_users(caller, target_client_id: Optional[UUID] = None, requested_role: Optional[str] = None) -> None:
    """Enforce RBAC + tenant boundaries on portal user & invitation management."""
    if not caller.can_manage_users():
        raise HTTPException(status_code=403, detail="Insufficient permissions to manage portal users")

    is_platform_admin = caller.role in ("admin", "broker_admin")

    if requested_role is not None:
        if requested_role not in ALLOWED_PORTAL_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role '{requested_role}'")
        if requested_role in BROKERAGE_ONLY_ROLES and not is_platform_admin:
            raise HTTPException(
                status_code=403,
                detail="Only brokerage administrators can assign brokerage staff roles",
            )

    if not is_platform_admin and target_client_id is not None and str(caller.client_id) != str(target_client_id):
        raise HTTPException(
            status_code=403,
            detail="You may only manage users within your own organization",
        )


# ==================== Invitation Endpoints ====================

@router.post("/invitations")
async def create_invitation(
    request: InviteUserRequest,
    caller = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Invite a user to the client portal (requires brokerage admin or matching client_admin).
    """
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    try:
        client_uuid = UUID(request.client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")

    _assert_caller_can_manage_client_users(caller, target_client_id=client_uuid, requested_role=request.role)
    
    service = ClientPortalAuthService(db)
    
    try:
        invitation = await service.create_invitation(
            email=request.email,
            client_id=client_uuid,
            role=request.role,
            invited_by_id=caller.id,
            invited_by_name=caller.full_name,
            message=request.message,
        )
        
        return {
            "invitation": invitation.to_dict(),
            "invitation_link": f"/register?token={invitation.token}",
            "message": f"Invitation sent to {request.email}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/invitations")
async def list_invitations(
    client_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    caller = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """List portal invitations (scoped for client_admin)."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    _assert_caller_can_manage_client_users(caller)
    is_platform_admin = caller.role in ("admin", "broker_admin")

    scoped_uuid: Optional[UUID] = None
    if client_id:
        try:
            scoped_uuid = UUID(client_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid client ID")
        _assert_caller_can_manage_client_users(caller, target_client_id=scoped_uuid)
    elif not is_platform_admin:
        scoped_uuid = caller.client_id

    service = ClientPortalAuthService(db)
    
    invitations = await service.list_invitations(
        client_id=scoped_uuid,
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
    caller = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a pending invitation."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    try:
        invitation_uuid = UUID(invitation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invitation ID")
    
    service = ClientPortalAuthService(db)
    inv = await service._get_invitation(invitation_uuid)
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")
    _assert_caller_can_manage_client_users(caller, target_client_id=inv.client_id)
    
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
        from app.core.config import settings

        user = await service.accept_invitation(
            token=request.token,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            phone=request.phone,
            job_title=request.job_title,
        )

        if settings.require_email_verification and not user.is_email_verified:
            return {
                "user": user.to_dict(),
                "session_token": None,
                "message": "Account created. Check your email to verify before signing in.",
                "requires_email_verification": True,
            }

        user, session = await service.login(
            email=user.email,
            password=request.password,
        )

        return {
            "user": user.to_dict(),
            "session_token": session.token,
            "message": "Account created successfully",
            "requires_email_verification": False,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify-email")
async def verify_email(
    request: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.services.client_portal_auth_service import ClientPortalAuthService

    service = ClientPortalAuthService(db)
    try:
        user = await service.verify_email(request.token)
        return {"message": "Email verified", "user": user.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resend-verification")
async def resend_verification(
    request: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.services.client_portal_auth_service import ClientPortalAuthService

    service = ClientPortalAuthService(db)
    await service.resend_verification_email(request.email)
    return {"message": "If an unverified account exists, a verification email was sent"}


# ==================== Authentication Endpoints ====================

_FAILED_LOGIN_WINDOW_SECONDS = 900  # 15 minutes
_MAX_FAILED_LOGIN_ATTEMPTS = 10
_failed_login_tracker: dict[str, list[float]] = {}


def _login_throttle_key(ip: Optional[str], email: str) -> str:
    return f"{ip or 'unknown'}:{email.lower().strip()}"


def _assert_not_login_throttled(ip: Optional[str], email: str) -> None:
    import time

    key = _login_throttle_key(ip, email)
    now = time.monotonic()
    recent = [ts for ts in _failed_login_tracker.get(key, []) if now - ts < _FAILED_LOGIN_WINDOW_SECONDS]
    _failed_login_tracker[key] = recent
    if len(recent) >= _MAX_FAILED_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many failed sign-in attempts. Please wait 15 minutes or reset your password.",
        )


def _record_failed_login(ip: Optional[str], email: str) -> None:
    import time

    key = _login_throttle_key(ip, email)
    _failed_login_tracker.setdefault(key, []).append(time.monotonic())


def _clear_failed_login(ip: Optional[str], email: str) -> None:
    _failed_login_tracker.pop(_login_throttle_key(ip, email), None)


@router.post("/login")
async def login(
    request: LoginRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
):
    """Log in to client portal (protected by brute-force lockout)."""
    from app.services.client_portal_auth_service import ClientPortalAuthService

    client_ip = req.client.host if req.client else None
    _assert_not_login_throttled(client_ip, request.email)
    
    service = ClientPortalAuthService(db)
    
    try:
        user, session = await service.login(
            email=request.email,
            password=request.password,
            ip_address=client_ip,
            user_agent=req.headers.get("user-agent"),
        )
        _clear_failed_login(client_ip, request.email)
        
        return {
            "user": user.to_dict(),
            "session_token": session.token,
            "expires_at": session.expires_at.isoformat(),
        }
    except ValueError as e:
        _record_failed_login(client_ip, request.email)
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
    from app.core.config import settings
    from app.services.client_portal_auth_service import ClientPortalAuthService
    from app.services.email_service import EmailService

    service = ClientPortalAuthService(db)
    token = await service.request_password_reset(request.email)

    reset_url = None
    if token:
        reset_url = f"{settings.public_app_url}/reset-password?token={token}"
        await EmailService().send_password_reset(
            to_email=request.email.lower().strip(),
            reset_token=token,
            reset_url=reset_url,
        )

    # Always return success to not reveal if user exists
    payload: dict = {
        "message": "If an account exists with that email, a reset link has been sent",
    }
    if settings.environment == "development" and reset_url:
        payload["_dev_reset_link"] = reset_url
    return payload


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
    caller = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """List client portal users (scoped for client_admin)."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    _assert_caller_can_manage_client_users(caller)
    is_platform_admin = caller.role in ("admin", "broker_admin")

    scoped_uuid: Optional[UUID] = None
    if client_id:
        try:
            scoped_uuid = UUID(client_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid client ID")
        _assert_caller_can_manage_client_users(caller, target_client_id=scoped_uuid)
    elif not is_platform_admin:
        scoped_uuid = caller.client_id

    service = ClientPortalAuthService(db)
    
    users = await service.list_users(
        client_id=scoped_uuid,
        status=status,
    )
    
    return {
        "users": [u.to_dict() for u in users],
        "count": len(users),
    }


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    caller = Depends(get_current_portal_user),
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

    if str(caller.id) != str(user.id):
        _assert_caller_can_manage_client_users(caller, target_client_id=user.client_id)
    
    return user.to_dict()


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    request: UpdateUserRoleRequest,
    caller = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user role (prevents privilege escalation to brokerage admin)."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    service = ClientPortalAuthService(db)
    target = await service.get_user(user_uuid)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    _assert_caller_can_manage_client_users(
        caller,
        target_client_id=target.client_id,
        requested_role=request.role,
    )
    if target.role in BROKERAGE_ONLY_ROLES and caller.role not in ("admin", "broker_admin"):
        raise HTTPException(status_code=403, detail="Cannot modify brokerage staff accounts")
    
    try:
        user = await service.update_user(
            user_uuid,
            {"role": request.role},
            allow_privileged_fields=True,
        )
        return {
            "user": user.to_dict(),
            "message": f"Role updated to {request.role}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    caller = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a user."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    service = ClientPortalAuthService(db)
    target = await service.get_user(user_uuid)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    _assert_caller_can_manage_client_users(caller, target_client_id=target.client_id)
    if target.role in BROKERAGE_ONLY_ROLES and caller.role not in ("admin", "broker_admin"):
        raise HTTPException(status_code=403, detail="Cannot deactivate brokerage staff accounts")
    
    try:
        await service.deactivate_user(user_uuid)
        return {"message": "User deactivated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/users/{user_id}/reactivate")
async def reactivate_user(
    user_id: str,
    caller = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Reactivate a deactivated user."""
    from app.services.client_portal_auth_service import ClientPortalAuthService
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    service = ClientPortalAuthService(db)
    target = await service.get_user(user_uuid)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    _assert_caller_can_manage_client_users(caller, target_client_id=target.client_id)
    if target.role in BROKERAGE_ONLY_ROLES and caller.role not in ("admin", "broker_admin"):
        raise HTTPException(status_code=403, detail="Cannot reactivate brokerage staff accounts")
    
    try:
        await service.reactivate_user(user_uuid)
        return {"message": "User reactivated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Reference Data ====================

@router.get("/reference/roles")
async def get_roles():
    """Get available importer portal user roles."""
    return {
        "roles": [
            {"value": "client_admin", "name": "Client Admin", "description": "Can manage portal users within this importer account"},
            {"value": "user", "name": "Client User", "description": "Can upload documents, view, and approve entries"},
            {"value": "readonly", "name": "Read Only", "description": "View-only access to assigned importer records"},
        ],
    }
