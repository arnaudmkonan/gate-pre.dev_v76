"""
POA API Routes  (Task B.1)

Provides CRUD + lifecycle management for CBP Powers of Attorney.

Endpoints:
  POST   /api/poa                             — Create (draft)
  GET    /api/poa                             — List for brokerage
  GET    /api/poa/{poa_id}                    — Get single
  PATCH  /api/poa/{poa_id}                    — Update (status, dates, etc.)
  POST   /api/poa/{poa_id}/activate           — Mark as active (signed)
  POST   /api/poa/{poa_id}/revoke             — Revoke
  GET    /api/poa/client/{client_id}          — Get all POAs for client
  GET    /api/poa/client/{client_id}/valid    — Check if client has valid POA
  GET    /api/poa/expiring                    — List POAs expiring within N days
"""
import logging
from datetime import date, datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.power_of_attorney import PowerOfAttorney, POAStatus, POAType
from app.services.poa_service import POAService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/poa",
    tags=["Power of Attorney"],
    dependencies=[Depends(get_current_user)],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class POACreateRequest(BaseModel):
    client_id: UUID
    poa_type: str = "general"
    grantor_name: str
    grantor_title: Optional[str] = None
    grantor_ein: Optional[str] = None
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    broker_license_id: Optional[UUID] = None
    notes: Optional[str] = None


class POAUpdateRequest(BaseModel):
    grantor_title: Optional[str] = None
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    notes: Optional[str] = None
    document_url: Optional[str] = None


class POAActivateRequest(BaseModel):
    signature_provider: Optional[str] = None
    signature_request_id: Optional[str] = None
    signature_ip: Optional[str] = None
    document_url: Optional[str] = None


class POARevokeRequest(BaseModel):
    reason: str


class POAValidityResponse(BaseModel):
    client_id: str
    has_valid_poa: bool
    active_poa_count: int
    reason: Optional[str] = None
    expiring_soon: bool = False
    earliest_expiry: Optional[date] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_poa(
    req: POACreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new POA record in DRAFT status."""
    svc = POAService(db)
    try:
        record = svc.build_poa_record(req.dict(exclude_none=False))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    poa = PowerOfAttorney(
        client_id=req.client_id,
        poa_type=req.poa_type,
        grantor_name=req.grantor_name,
        grantor_title=req.grantor_title,
        grantor_ein=req.grantor_ein,
        effective_date=req.effective_date,
        expiry_date=req.expiry_date,
        broker_license_id=req.broker_license_id,
        notes=req.notes,
        status=POAStatus.DRAFT.value,
    )
    db.add(poa)
    await db.commit()
    await db.refresh(poa)
    logger.info("POA created: %s for client %s", poa.id, req.client_id)
    return poa.to_dict()


@router.get("")
async def list_poas(
    client_id: Optional[UUID] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all POAs, optionally filtered by client or status."""
    q = select(PowerOfAttorney)
    if client_id:
        q = q.where(PowerOfAttorney.client_id == client_id)
    if status_filter:
        q = q.where(PowerOfAttorney.status == status_filter)
    q = q.order_by(PowerOfAttorney.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(q)
    poas = result.scalars().all()
    return {"items": [p.to_dict() for p in poas], "total": len(poas)}


@router.get("/expiring")
async def list_expiring_poas(
    days: int = Query(30, description="Warn if expiry within N days"),
    db: AsyncSession = Depends(get_db),
):
    """List active POAs expiring within `days` days."""
    warn_date = date.today() + timedelta(days=days)
    result = await db.execute(
        select(PowerOfAttorney).where(
            PowerOfAttorney.status == POAStatus.ACTIVE.value,
            PowerOfAttorney.expiry_date is not None,
            PowerOfAttorney.expiry_date <= warn_date,
        ).order_by(PowerOfAttorney.expiry_date)
    )
    poas = result.scalars().all()
    return {
        "expiring_within_days": days,
        "count": len(poas),
        "items": [p.to_dict() for p in poas],
    }


@router.get("/client/{client_id}/valid", response_model=POAValidityResponse)
async def check_client_poa_validity(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Check whether a client has a currently valid POA on file."""
    result = await db.execute(
        select(PowerOfAttorney).where(PowerOfAttorney.client_id == client_id)
    )
    poas = result.scalars().all()
    svc = POAService(db)

    poa_dicts = [p.to_dict() for p in poas]
    can_file, reason = svc.can_file_entry(client_id, poa_dicts)

    # Check expiry warnings
    active_poas = [p for p in poas if p.is_active()]
    expiring_soon = any(
        p.days_until_expiry() is not None and p.days_until_expiry() <= 30
        for p in active_poas
    )
    earliest_expiry = None
    expiring_list = [
        p.expiry_date for p in active_poas if p.expiry_date
    ]
    if expiring_list:
        earliest_expiry = min(expiring_list)

    return POAValidityResponse(
        client_id=str(client_id),
        has_valid_poa=can_file,
        active_poa_count=len(active_poas),
        reason=reason if not can_file else None,
        expiring_soon=expiring_soon,
        earliest_expiry=earliest_expiry,
    )


@router.get("/client/{client_id}")
async def get_client_poas(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all POAs for a specific client."""
    result = await db.execute(
        select(PowerOfAttorney)
        .where(PowerOfAttorney.client_id == client_id)
        .order_by(PowerOfAttorney.created_at.desc())
    )
    poas = result.scalars().all()
    return {"client_id": str(client_id), "items": [p.to_dict() for p in poas]}


@router.get("/{poa_id}")
async def get_poa(
    poa_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single POA by ID."""
    poa = await _get_or_404(db, poa_id)
    return poa.to_dict()


@router.patch("/{poa_id}")
async def update_poa(
    poa_id: UUID,
    req: POAUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update non-status POA fields (effective/expiry dates, document URL, notes)."""
    poa = await _get_or_404(db, poa_id)
    if poa.status in (POAStatus.REVOKED.value, POAStatus.EXPIRED.value):
        raise HTTPException(
            status_code=422,
            detail=f"Cannot modify a {poa.status} POA",
        )
    for field, value in req.dict(exclude_none=True).items():
        setattr(poa, field, value)
    poa.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(poa)
    return poa.to_dict()


@router.post("/{poa_id}/activate")
async def activate_poa(
    poa_id: UUID,
    req: POAActivateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a POA as active (signing complete).

    Call this after the importer has signed (DocuSign callback, etc.).
    """
    poa = await _get_or_404(db, poa_id)
    if poa.status not in (POAStatus.DRAFT.value, POAStatus.PENDING_SIGNATURE.value):
        raise HTTPException(
            status_code=422,
            detail=f"Cannot activate a POA with status '{poa.status}'",
        )
    poa.status = POAStatus.ACTIVE.value
    poa.signed_at = datetime.now(timezone.utc)
    if req.signature_provider:
        poa.signature_provider = req.signature_provider
    if req.signature_request_id:
        poa.signature_request_id = req.signature_request_id
    if req.signature_ip:
        poa.signature_ip = req.signature_ip
    if req.document_url:
        poa.document_url = req.document_url
    if not poa.effective_date:
        poa.effective_date = date.today()
    poa.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(poa)
    logger.info("POA %s activated for client %s", poa_id, poa.client_id)
    return poa.to_dict()


@router.post("/{poa_id}/send-for-signature")
async def send_for_signature(
    poa_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark POA as pending_signature.

    In a future sprint this will trigger a DocuSign/HelloSign envelope.
    For now it transitions the status so brokers can track pending POAs.
    """
    poa = await _get_or_404(db, poa_id)
    if poa.status != POAStatus.DRAFT.value:
        raise HTTPException(
            status_code=422,
            detail=f"POA must be in DRAFT to send for signature (current: {poa.status})",
        )
    poa.status = POAStatus.PENDING_SIGNATURE.value
    poa.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(poa)
    return {
        "message": "POA marked pending_signature. E-signature integration pending.",
        "poa": poa.to_dict(),
    }


@router.post("/{poa_id}/revoke")
async def revoke_poa(
    poa_id: UUID,
    req: POARevokeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Revoke an active POA."""
    poa = await _get_or_404(db, poa_id)
    if poa.status == POAStatus.REVOKED.value:
        raise HTTPException(status_code=422, detail="POA is already revoked")
    poa.status = POAStatus.REVOKED.value
    poa.revoked_at = datetime.now(timezone.utc)
    poa.revocation_reason = req.reason
    poa.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(poa)
    logger.info("POA %s revoked: %s", poa_id, req.reason)
    return poa.to_dict()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _get_or_404(db: AsyncSession, poa_id: UUID) -> PowerOfAttorney:
    result = await db.execute(
        select(PowerOfAttorney).where(PowerOfAttorney.id == poa_id)
    )
    poa = result.scalar_one_or_none()
    if not poa:
        raise HTTPException(status_code=404, detail=f"POA {poa_id} not found")
    return poa
