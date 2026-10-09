"""
CBP Form 5106 API Routes  (Task B.3)

Endpoints for registering first-time importers with CBP via Form 5106
(Importer ID Number Application).

Endpoints:
  POST /api/cbp5106/validate        — Validate fields, return errors
  POST /api/cbp5106/generate        — Validate + build the CBP data packet
  GET  /api/cbp5106/client/{id}     — Get 5106 packet on file for a client
  POST /api/cbp5106/submit/{id}     — Mark as submitted to CBP (manual)
"""
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.services.cbp5106_service import CBP5106Service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/cbp5106",
    tags=["CBP Form 5106"],
    dependencies=[Depends(get_current_user)],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CBP5106Data(BaseModel):
    """5106 form data payload."""
    entity_type: str = "corporation"   # individual | corporation | partnership | llc
    # Business fields
    legal_name: Optional[str] = None
    doing_business_as: Optional[str] = None
    ein: Optional[str] = None
    # Individual fields
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    ssn_or_tin: Optional[str] = None
    # Address
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country_code: str = "US"
    # Contact
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    # Importer profile
    business_type: Optional[str] = None
    import_purpose: Optional[str] = None
    is_broker: bool = False
    # Client linkage (optional)
    client_id: Optional[UUID] = None


class CBP5106ValidateResponse(BaseModel):
    is_valid: bool
    errors: list
    field_count: int


class CBP5106PacketResponse(BaseModel):
    is_valid: bool
    errors: list
    packet: Optional[Dict[str, Any]]
    ior_number: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/validate", response_model=CBP5106ValidateResponse)
async def validate_5106(data: CBP5106Data):
    """
    Validate CBP Form 5106 data without generating a packet.

    Returns a list of field validation errors.  Empty list = ready to submit.
    """
    svc = CBP5106Service()
    errors = svc.validate(data.dict())
    return CBP5106ValidateResponse(
        is_valid=len(errors) == 0,
        errors=errors,
        field_count=len([v for v in data.dict().values() if v is not None]),
    )


@router.post("/generate", response_model=CBP5106PacketResponse)
async def generate_5106_packet(data: CBP5106Data):
    """
    Validate CBP Form 5106 data and generate the ACE/ACS data packet.

    The packet is suitable for:
    - Storing in the client record (cbp_5106_packet JSON field)
    - Transmission to ACE via ABI when supported

    Also returns the derived IOR number (EIN-based for corporations).
    """
    svc = CBP5106Service()
    errors = svc.validate(data.dict())
    if errors:
        return CBP5106PacketResponse(is_valid=False, errors=errors, packet=None)

    try:
        packet = svc.build_5106_packet(data.dict())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    ior_number = None
    ein = data.ein or ""
    if ein:
        ior_number = svc.generate_ior_number(ein)

    logger.info("Generated CBP 5106 packet for: %s", data.legal_name or data.last_name)
    return CBP5106PacketResponse(
        is_valid=True,
        errors=[],
        packet=packet,
        ior_number=ior_number,
    )


@router.get("/ior-number")
async def derive_ior_number(ein: str):
    """
    Derive a provisional IOR number from an EIN.

    CBP uses the EIN (9-digit, no dash) as the IOR number for corporations.
    Returns the formatted IOR number.
    """
    svc = CBP5106Service()
    if not svc._validate_ein(ein):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid EIN format '{ein}'. Expected: XX-XXXXXXX",
        )
    return {"ein": ein, "ior_number": svc.generate_ior_number(ein)}


@router.get("/entity-types")
async def list_entity_types():
    """Return the valid CBP entity type codes with descriptions."""
    from app.services.cbp5106_service import ENTITY_TYPES
    return {
        "entity_types": [
            {"code": k, "cbp_code": v}
            for k, v in ENTITY_TYPES.items()
        ]
    }
