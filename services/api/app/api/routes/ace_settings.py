"""
ACE Settings API Routes.

CRUD operations for ACE Portal account configuration.
Supports organization-level settings and multiple filer codes.

Task 3.3 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.ace_settings import (
    ACESettings, FilerCode,
    validate_filer_code, validate_port_code, validate_surety_code
)
from app.models.organization import Organization

router = APIRouter(prefix="/api/settings/ace", tags=["ACE Settings"])


# ==================== Request/Response Models ====================

class FilerCodeCreate(BaseModel):
    """Create a filer code."""
    filer_code: str = Field(..., min_length=3, max_length=3)
    name: Optional[str] = None
    client_id: Optional[str] = None
    port_code: Optional[str] = Field(None, min_length=4, max_length=4)
    bond_type: Optional[str] = None
    bond_number: Optional[str] = None
    surety_code: Optional[str] = Field(None, min_length=3, max_length=3)
    is_primary: bool = False
    notes: Optional[str] = None

    @validator('filer_code')
    def validate_filer_code_format(cls, v):
        if not validate_filer_code(v.upper()):
            raise ValueError('Filer code must be 3 uppercase letters')
        return v.upper()

    @validator('port_code')
    def validate_port_code_format(cls, v):
        if v and not validate_port_code(v):
            raise ValueError('Port code must be 4 digits')
        return v

    @validator('surety_code')
    def validate_surety_code_format(cls, v):
        if v and not validate_surety_code(v):
            raise ValueError('Surety code must be 3 digits')
        return v


class FilerCodeUpdate(BaseModel):
    """Update a filer code."""
    name: Optional[str] = None
    client_id: Optional[str] = None
    port_code: Optional[str] = None
    bond_type: Optional[str] = None
    bond_number: Optional[str] = None
    surety_code: Optional[str] = None
    is_active: Optional[bool] = None
    is_primary: Optional[bool] = None
    notes: Optional[str] = None


class FilerCodeResponse(BaseModel):
    """Filer code response."""
    id: str
    filer_code: str
    name: Optional[str]
    client_id: Optional[str]
    port_code: Optional[str]
    bond_type: Optional[str]
    bond_number: Optional[str]
    surety_code: Optional[str]
    is_active: bool
    is_primary: bool
    notes: Optional[str]
    created_at: str
    updated_at: str


class ACESettingsCreate(BaseModel):
    """Create ACE settings."""
    organization_id: str
    primary_filer_code: Optional[str] = Field(None, min_length=3, max_length=3)
    primary_port_code: Optional[str] = Field(None, min_length=4, max_length=4)
    default_bond_type: Optional[str] = "continuous"
    default_bond_surety_code: Optional[str] = None
    ace_portal_username: Optional[str] = None
    ace_portal_client_id: Optional[str] = None
    ace_environment: str = "test"
    auto_file_when_ready: bool = False
    require_dual_approval: bool = True
    notify_on_filing: bool = True
    notify_on_acceptance: bool = True
    notify_on_rejection: bool = True
    notify_on_liquidation: bool = True
    notification_email: Optional[str] = None


class ACESettingsUpdate(BaseModel):
    """Update ACE settings."""
    primary_filer_code: Optional[str] = None
    primary_port_code: Optional[str] = None
    default_bond_type: Optional[str] = None
    default_bond_surety_code: Optional[str] = None
    ace_portal_username: Optional[str] = None
    ace_portal_client_id: Optional[str] = None
    ace_environment: Optional[str] = None
    auto_file_when_ready: Optional[bool] = None
    require_dual_approval: Optional[bool] = None
    notify_on_filing: Optional[bool] = None
    notify_on_acceptance: Optional[bool] = None
    notify_on_rejection: Optional[bool] = None
    notify_on_liquidation: Optional[bool] = None
    notification_email: Optional[str] = None


class ACESettingsResponse(BaseModel):
    """ACE settings response."""
    id: str
    organization_id: str
    primary_filer_code: Optional[str]
    primary_port_code: Optional[str]
    default_bond_type: Optional[str]
    default_bond_surety_code: Optional[str]
    ace_portal_username: Optional[str]
    ace_environment: str
    auto_file_when_ready: bool
    require_dual_approval: bool
    notify_on_filing: bool
    notify_on_acceptance: bool
    notify_on_rejection: bool
    notify_on_liquidation: bool
    notification_email: Optional[str]
    filer_codes: List[FilerCodeResponse]
    created_at: str
    updated_at: str


# ==================== Helper Functions ====================

def format_ace_settings(settings: ACESettings) -> dict:
    """Format ACE settings for response."""
    return {
        "id": str(settings.id),
        "organization_id": str(settings.organization_id),
        "primary_filer_code": settings.primary_filer_code,
        "primary_port_code": settings.primary_port_code,
        "default_bond_type": settings.default_bond_type,
        "default_bond_surety_code": settings.default_bond_surety_code,
        "ace_portal_username": settings.ace_portal_username,
        "ace_environment": settings.ace_environment,
        "auto_file_when_ready": settings.auto_file_when_ready,
        "require_dual_approval": settings.require_dual_approval,
        "notify_on_filing": settings.notify_on_filing,
        "notify_on_acceptance": settings.notify_on_acceptance,
        "notify_on_rejection": settings.notify_on_rejection,
        "notify_on_liquidation": settings.notify_on_liquidation,
        "notification_email": settings.notification_email,
        "filer_codes": [
            {
                "id": str(fc.id),
                "filer_code": fc.filer_code,
                "name": fc.name,
                "client_id": str(fc.client_id) if fc.client_id else None,
                "port_code": fc.port_code,
                "bond_type": fc.bond_type,
                "bond_number": fc.bond_number,
                "surety_code": fc.surety_code,
                "is_active": fc.is_active,
                "is_primary": fc.is_primary,
                "notes": fc.notes,
                "created_at": fc.created_at.isoformat(),
                "updated_at": fc.updated_at.isoformat(),
            }
            for fc in sorted(settings.filer_codes, key=lambda x: (not x.is_primary, x.filer_code))
        ],
        "created_at": settings.created_at.isoformat(),
        "updated_at": settings.updated_at.isoformat(),
    }


# ==================== ACE Settings Endpoints ====================

@router.get("")
async def get_ace_settings(
    organization_id: str = Query(..., description="Organization ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get ACE settings for an organization."""
    try:
        org_uuid = UUID(organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")

    query = (
        select(ACESettings)
        .options(selectinload(ACESettings.filer_codes))
        .where(ACESettings.organization_id == org_uuid)
    )
    result = await db.execute(query)
    settings = result.scalar_one_or_none()

    if not settings:
        # Return empty settings structure
        return {
            "id": None,
            "organization_id": organization_id,
            "primary_filer_code": None,
            "primary_port_code": None,
            "default_bond_type": "continuous",
            "default_bond_surety_code": None,
            "ace_portal_username": None,
            "ace_environment": "test",
            "auto_file_when_ready": False,
            "require_dual_approval": True,
            "notify_on_filing": True,
            "notify_on_acceptance": True,
            "notify_on_rejection": True,
            "notify_on_liquidation": True,
            "notification_email": None,
            "filer_codes": [],
            "created_at": None,
            "updated_at": None,
        }

    return format_ace_settings(settings)


@router.post("")
async def create_ace_settings(
    request: ACESettingsCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create ACE settings for an organization."""
    try:
        org_uuid = UUID(request.organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")

    # Check if settings already exist
    existing = await db.execute(
        select(ACESettings).where(ACESettings.organization_id == org_uuid)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="ACE settings already exist for this organization. Use PUT to update.")

    # Validate filer code format
    if request.primary_filer_code:
        if not validate_filer_code(request.primary_filer_code.upper()):
            raise HTTPException(status_code=400, detail="Invalid filer code format. Must be 3 uppercase letters.")

    # Validate port code format
    if request.primary_port_code:
        if not validate_port_code(request.primary_port_code):
            raise HTTPException(status_code=400, detail="Invalid port code format. Must be 4 digits.")

    settings = ACESettings(
        organization_id=org_uuid,
        primary_filer_code=request.primary_filer_code.upper() if request.primary_filer_code else None,
        primary_port_code=request.primary_port_code,
        default_bond_type=request.default_bond_type,
        default_bond_surety_code=request.default_bond_surety_code,
        ace_portal_username=request.ace_portal_username,
        ace_portal_client_id=request.ace_portal_client_id,
        ace_environment=request.ace_environment,
        auto_file_when_ready=request.auto_file_when_ready,
        require_dual_approval=request.require_dual_approval,
        notify_on_filing=request.notify_on_filing,
        notify_on_acceptance=request.notify_on_acceptance,
        notify_on_rejection=request.notify_on_rejection,
        notify_on_liquidation=request.notify_on_liquidation,
        notification_email=request.notification_email,
    )

    db.add(settings)
    await db.commit()
    await db.refresh(settings)

    # Reload with relationships
    query = (
        select(ACESettings)
        .options(selectinload(ACESettings.filer_codes))
        .where(ACESettings.id == settings.id)
    )
    result = await db.execute(query)
    settings = result.scalar_one()

    return format_ace_settings(settings)


@router.put("")
async def update_ace_settings(
    organization_id: str,
    request: ACESettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update ACE settings for an organization."""
    try:
        org_uuid = UUID(organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")

    query = (
        select(ACESettings)
        .options(selectinload(ACESettings.filer_codes))
        .where(ACESettings.organization_id == org_uuid)
    )
    result = await db.execute(query)
    settings = result.scalar_one_or_none()

    if not settings:
        raise HTTPException(status_code=404, detail="ACE settings not found for this organization")

    # Update fields
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            # Validate filer code
            if field == "primary_filer_code" and value:
                if not validate_filer_code(value.upper()):
                    raise HTTPException(status_code=400, detail="Invalid filer code format")
                value = value.upper()
            # Validate port code
            if field == "primary_port_code" and value:
                if not validate_port_code(value):
                    raise HTTPException(status_code=400, detail="Invalid port code format")
            setattr(settings, field, value)

    await db.commit()
    await db.refresh(settings)

    return format_ace_settings(settings)


# ==================== Filer Codes Endpoints ====================

@router.post("/filer-codes")
async def add_filer_code(
    organization_id: str,
    request: FilerCodeCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a filer code to organization's ACE settings."""
    try:
        org_uuid = UUID(organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID")

    # Get or create ACE settings
    query = select(ACESettings).where(ACESettings.organization_id == org_uuid)
    result = await db.execute(query)
    settings = result.scalar_one_or_none()

    if not settings:
        # Create settings first
        settings = ACESettings(organization_id=org_uuid)
        db.add(settings)
        await db.flush()

    # Check for duplicate filer code
    existing = await db.execute(
        select(FilerCode).where(
            FilerCode.ace_settings_id == settings.id,
            FilerCode.filer_code == request.filer_code.upper()
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Filer code {request.filer_code} already exists")

    # If this is primary, unset other primary codes
    if request.is_primary:
        await db.execute(
            select(FilerCode)
            .where(FilerCode.ace_settings_id == settings.id, FilerCode.is_primary == True)
        )
        for fc in (await db.execute(
            select(FilerCode).where(FilerCode.ace_settings_id == settings.id, FilerCode.is_primary == True)
        )).scalars():
            fc.is_primary = False

    filer_code = FilerCode(
        ace_settings_id=settings.id,
        filer_code=request.filer_code.upper(),
        name=request.name,
        client_id=UUID(request.client_id) if request.client_id else None,
        port_code=request.port_code,
        bond_type=request.bond_type,
        bond_number=request.bond_number,
        surety_code=request.surety_code,
        is_primary=request.is_primary,
        notes=request.notes,
    )

    db.add(filer_code)
    await db.commit()
    await db.refresh(filer_code)

    return {
        "id": str(filer_code.id),
        "filer_code": filer_code.filer_code,
        "name": filer_code.name,
        "client_id": str(filer_code.client_id) if filer_code.client_id else None,
        "port_code": filer_code.port_code,
        "bond_type": filer_code.bond_type,
        "bond_number": filer_code.bond_number,
        "surety_code": filer_code.surety_code,
        "is_active": filer_code.is_active,
        "is_primary": filer_code.is_primary,
        "notes": filer_code.notes,
        "created_at": filer_code.created_at.isoformat(),
        "updated_at": filer_code.updated_at.isoformat(),
    }


@router.put("/filer-codes/{filer_code_id}")
async def update_filer_code(
    filer_code_id: str,
    request: FilerCodeUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a filer code."""
    try:
        fc_uuid = UUID(filer_code_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filer code ID")

    query = select(FilerCode).where(FilerCode.id == fc_uuid)
    result = await db.execute(query)
    filer_code = result.scalar_one_or_none()

    if not filer_code:
        raise HTTPException(status_code=404, detail="Filer code not found")

    # Update fields
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            if field == "client_id":
                value = UUID(value) if value else None
            if field == "port_code" and value:
                if not validate_port_code(value):
                    raise HTTPException(status_code=400, detail="Invalid port code format")
            if field == "surety_code" and value:
                if not validate_surety_code(value):
                    raise HTTPException(status_code=400, detail="Invalid surety code format")
            setattr(filer_code, field, value)

    # If setting as primary, unset others
    if request.is_primary:
        for fc in (await db.execute(
            select(FilerCode).where(
                FilerCode.ace_settings_id == filer_code.ace_settings_id,
                FilerCode.id != filer_code.id,
                FilerCode.is_primary == True
            )
        )).scalars():
            fc.is_primary = False

    await db.commit()
    await db.refresh(filer_code)

    return {
        "id": str(filer_code.id),
        "filer_code": filer_code.filer_code,
        "name": filer_code.name,
        "client_id": str(filer_code.client_id) if filer_code.client_id else None,
        "port_code": filer_code.port_code,
        "bond_type": filer_code.bond_type,
        "bond_number": filer_code.bond_number,
        "surety_code": filer_code.surety_code,
        "is_active": filer_code.is_active,
        "is_primary": filer_code.is_primary,
        "notes": filer_code.notes,
        "created_at": filer_code.created_at.isoformat(),
        "updated_at": filer_code.updated_at.isoformat(),
    }


@router.delete("/filer-codes/{filer_code_id}")
async def delete_filer_code(
    filer_code_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a filer code."""
    try:
        fc_uuid = UUID(filer_code_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filer code ID")

    query = select(FilerCode).where(FilerCode.id == fc_uuid)
    result = await db.execute(query)
    filer_code = result.scalar_one_or_none()

    if not filer_code:
        raise HTTPException(status_code=404, detail="Filer code not found")

    await db.delete(filer_code)
    await db.commit()

    return {"message": "Filer code deleted", "id": filer_code_id}


# ==================== Validation Endpoints ====================

@router.post("/validate/filer-code")
async def validate_filer_code_endpoint(code: str):
    """Validate filer code format."""
    is_valid = validate_filer_code(code.upper())
    return {
        "code": code.upper(),
        "is_valid": is_valid,
        "format": "3 uppercase letters (A-Z)",
        "example": "ABC",
    }


@router.post("/validate/port-code")
async def validate_port_code_endpoint(code: str):
    """Validate port code format."""
    is_valid = validate_port_code(code)
    return {
        "code": code,
        "is_valid": is_valid,
        "format": "4 digits",
        "example": "2704",
    }


@router.post("/validate/surety-code")
async def validate_surety_code_endpoint(code: str):
    """Validate surety code format."""
    is_valid = validate_surety_code(code)
    return {
        "code": code,
        "is_valid": is_valid,
        "format": "3 digits",
        "example": "123",
    }
