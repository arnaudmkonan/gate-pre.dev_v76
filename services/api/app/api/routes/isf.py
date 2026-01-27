"""
ISF (Importer Security Filing) API Routes.

CRUD and filing operations for ISF/10+2.

Task 3.6 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db


router = APIRouter(prefix="/api/isf", tags=["ISF (10+2)"])


# ==================== Request/Response Models ====================

class ISFCreateRequest(BaseModel):
    """Create ISF request."""
    shipment_id: Optional[str] = None
    entry_id: Optional[str] = None
    
    # 10 Elements
    seller_name: Optional[str] = None
    seller_address: Optional[str] = None
    seller_country: Optional[str] = None
    
    buyer_name: Optional[str] = None
    buyer_address: Optional[str] = None
    buyer_country: Optional[str] = None
    
    importer_of_record_number: Optional[str] = None
    importer_of_record_name: Optional[str] = None
    
    consignee_number: Optional[str] = None
    consignee_name: Optional[str] = None
    
    manufacturer_name: Optional[str] = None
    manufacturer_address: Optional[str] = None
    manufacturer_country: Optional[str] = None
    manufacturer_id: Optional[str] = None  # MID
    
    ship_to_name: Optional[str] = None
    ship_to_address: Optional[str] = None
    ship_to_city: Optional[str] = None
    ship_to_country: Optional[str] = None
    
    country_of_origin: Optional[str] = None
    countries_of_origin: Optional[List[str]] = None
    
    hts_codes: Optional[List[str]] = None
    hts_primary: Optional[str] = None
    
    stuffing_location_name: Optional[str] = None
    stuffing_location_address: Optional[str] = None
    stuffing_location_country: Optional[str] = None
    
    consolidator_name: Optional[str] = None
    consolidator_address: Optional[str] = None
    consolidator_country: Optional[str] = None
    
    # Transport
    vessel_name: Optional[str] = None
    voyage_number: Optional[str] = None
    carrier_code: Optional[str] = None
    container_numbers: Optional[List[str]] = None
    master_bill_of_lading: Optional[str] = None
    house_bill_of_lading: Optional[str] = None
    port_of_loading: Optional[str] = None
    port_of_discharge: Optional[str] = None
    estimated_departure: Optional[datetime] = None
    estimated_arrival: Optional[datetime] = None
    
    # Options
    is_flexible: bool = True
    notes: Optional[str] = None


class ISFUpdateRequest(BaseModel):
    """Update ISF request."""
    seller_name: Optional[str] = None
    seller_address: Optional[str] = None
    seller_country: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_address: Optional[str] = None
    importer_of_record_number: Optional[str] = None
    importer_of_record_name: Optional[str] = None
    consignee_number: Optional[str] = None
    consignee_name: Optional[str] = None
    manufacturer_name: Optional[str] = None
    manufacturer_id: Optional[str] = None
    ship_to_name: Optional[str] = None
    ship_to_address: Optional[str] = None
    country_of_origin: Optional[str] = None
    hts_codes: Optional[List[str]] = None
    stuffing_location_name: Optional[str] = None
    consolidator_name: Optional[str] = None
    vessel_name: Optional[str] = None
    voyage_number: Optional[str] = None
    container_numbers: Optional[List[str]] = None
    master_bill_of_lading: Optional[str] = None
    port_of_loading: Optional[str] = None
    port_of_discharge: Optional[str] = None
    notes: Optional[str] = None


class ISFAmendRequest(BaseModel):
    """Amend ISF request."""
    changes: dict
    reason: str = ""


# ==================== Endpoints ====================

@router.post("")
async def create_isf(
    request: ISFCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new ISF filing.
    
    Can auto-populate from shipment or entry data.
    Supports flexible filing where not all data is known initially.
    """
    from app.services.isf_service import ISFService
    
    service = ISFService(db)
    
    try:
        # Parse UUIDs
        shipment_uuid = UUID(request.shipment_id) if request.shipment_id else None
        entry_uuid = UUID(request.entry_id) if request.entry_id else None
        
        # Get data dict
        data = request.model_dump(exclude={'shipment_id', 'entry_id'}, exclude_none=True)
        
        isf = await service.create_isf(
            shipment_id=shipment_uuid,
            entry_id=entry_uuid,
            data=data,
        )
        
        return {
            "isf": isf.to_dict(),
            "message": "ISF created successfully",
            "next_steps": [
                "Complete all 10 required elements",
                "Validate ISF before filing",
                "File at least 24 hours before vessel departure",
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_isf_filings(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all ISF filings with optional filtering."""
    from app.services.isf_service import ISFService
    
    service = ISFService(db)
    result = await service.list_isf_filings(status=status, limit=limit, offset=offset)
    
    return result


@router.get("/stats")
async def get_isf_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get ISF filing statistics by status."""
    from app.services.isf_service import ISFService
    
    service = ISFService(db)
    return await service.get_pending_isf_count()


@router.get("/{isf_id}")
async def get_isf(
    isf_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get ISF details by ID."""
    from app.services.isf_service import ISFService
    
    try:
        isf_uuid = UUID(isf_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ISF ID")
    
    service = ISFService(db)
    isf = await service.get_isf(isf_uuid)
    
    if not isf:
        raise HTTPException(status_code=404, detail="ISF not found")
    
    return isf.to_dict()


@router.put("/{isf_id}")
async def update_isf(
    isf_id: str,
    request: ISFUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update ISF with new data."""
    from app.services.isf_service import ISFService
    
    try:
        isf_uuid = UUID(isf_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ISF ID")
    
    service = ISFService(db)
    
    try:
        data = request.model_dump(exclude_none=True)
        isf = await service.update_isf(isf_uuid, data)
        
        return {
            "isf": isf.to_dict(),
            "message": "ISF updated successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{isf_id}/validate")
async def validate_isf(
    isf_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate ISF for filing.
    
    Checks all 10 required elements and returns:
    - Validation errors (blocking)
    - Warnings (non-blocking for flexible filing)
    - Completeness percentage
    """
    from app.services.isf_service import ISFService
    
    try:
        isf_uuid = UUID(isf_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ISF ID")
    
    service = ISFService(db)
    result = await service.validate_isf(isf_uuid)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.post("/{isf_id}/file")
async def file_isf(
    isf_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit ISF to CBP.
    
    ISF must be filed at least 24 hours before vessel departure.
    Supports flexible filing where not all data is known.
    """
    from app.services.isf_service import ISFService
    
    try:
        isf_uuid = UUID(isf_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ISF ID")
    
    service = ISFService(db)
    result = await service.file_isf(isf_uuid)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/{isf_id}/amend")
async def amend_isf(
    isf_id: str,
    request: ISFAmendRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    File an ISF amendment.
    
    Updates ISF data and tracks changes.
    """
    from app.services.isf_service import ISFService
    
    try:
        isf_uuid = UUID(isf_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ISF ID")
    
    service = ISFService(db)
    result = await service.amend_isf(isf_uuid, request.changes, request.reason)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/{isf_id}/match-entry/{entry_id}")
async def match_isf_to_entry(
    isf_id: str,
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Link ISF to a customs entry."""
    from app.services.isf_service import ISFService
    
    try:
        isf_uuid = UUID(isf_id)
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    service = ISFService(db)
    result = await service.match_isf_to_entry(isf_uuid, entry_uuid)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/{isf_id}/abi-message")
async def get_isf_abi_message(
    isf_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate ABI message for ISF filing.
    
    Returns ISF-10 message format for CBP submission.
    """
    from app.services.isf_service import ISFService
    
    try:
        isf_uuid = UUID(isf_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ISF ID")
    
    service = ISFService(db)
    result = await service.generate_isf_abi_message(isf_uuid)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


# ==================== Convenience Endpoints ====================

@router.post("/from-shipment/{shipment_id}")
async def create_isf_from_shipment(
    shipment_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Create ISF from shipment data.
    
    Auto-populates available fields from shipment.
    """
    from app.services.isf_service import ISFService
    
    try:
        shipment_uuid = UUID(shipment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid shipment ID")
    
    service = ISFService(db)
    
    # Check if ISF already exists for this shipment
    existing = await service.get_isf_by_shipment(shipment_uuid)
    if existing:
        return {
            "isf": existing.to_dict(),
            "message": "ISF already exists for this shipment",
            "already_exists": True,
        }
    
    try:
        isf = await service.create_isf(shipment_id=shipment_uuid)
        
        return {
            "isf": isf.to_dict(),
            "message": "ISF created from shipment",
            "already_exists": False,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/from-entry/{entry_id}")
async def create_isf_from_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Create ISF from entry data.
    
    Auto-populates available fields from entry.
    """
    from app.services.isf_service import ISFService
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    service = ISFService(db)
    
    # Check if ISF already exists for this entry
    existing = await service.get_isf_by_entry(entry_uuid)
    if existing:
        return {
            "isf": existing.to_dict(),
            "message": "ISF already exists for this entry",
            "already_exists": True,
        }
    
    try:
        isf = await service.create_isf(entry_id=entry_uuid)
        
        return {
            "isf": isf.to_dict(),
            "message": "ISF created from entry",
            "already_exists": False,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/by-entry/{entry_id}")
async def get_isf_by_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get ISF linked to an entry."""
    from app.services.isf_service import ISFService
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    service = ISFService(db)
    isf = await service.get_isf_by_entry(entry_uuid)
    
    if not isf:
        return {"isf": None, "message": "No ISF found for this entry"}
    
    return {"isf": isf.to_dict()}
