"""
Reference Data API Routes
Provides endpoints for HTS, NAICS, and OFAC screening operations.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.database import get_db
from app.services.reference_data_service import ReferenceDataService, seed_reference_data
from app.core.auth import get_current_user

router = APIRouter(prefix="/api/reference-data", tags=["Reference Data"], dependencies=[Depends(get_current_user)])


# ==================== Request/Response Models ====================

class EntityScreenRequest(BaseModel):
    """Request model for entity screening."""
    name: str
    entity_type: Optional[str] = None  # Individual, Entity, Vessel
    id_number: Optional[str] = None
    threshold: float = 0.85


class HTSSearchRequest(BaseModel):
    """Request model for HTS search."""
    query: str
    chapter: Optional[int] = None
    limit: int = 20


class NAICSSearchRequest(BaseModel):
    """Request model for NAICS search."""
    query: str
    sector: Optional[str] = None
    limit: int = 20


# ==================== HTS Code Endpoints ====================

@router.get("/hts/search")
async def search_hts_codes(
    query: str = Query(..., description="HTS code or description to search"),
    chapter: Optional[int] = Query(None, description="Filter by chapter number"),
    limit: int = Query(20, le=100, description="Maximum results to return"),
    db=Depends(get_db)
):
    """
    Search HTS codes by code or description.
    
    Returns matching HTS codes with duty rates and special program rates.
    """
    service = ReferenceDataService(db)
    results = await service.search_hts_codes(query=query, chapter=chapter, limit=limit)
    return {
        "query": query,
        "count": len(results),
        "results": results,
    }


@router.get("/hts/code/{hts_code}")
async def get_hts_code(
    hts_code: str,
    db=Depends(get_db)
):
    """
    Get details for a specific HTS code.
    
    Returns full HTS code details including duty rates and notes.
    """
    service = ReferenceDataService(db)
    result = await service.get_hts_code(hts_code)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"HTS code {hts_code} not found")
        
    return result


@router.get("/hts/stats")
async def get_hts_stats(db=Depends(get_db)):
    """Get statistics about HTS codes in the database."""
    service = ReferenceDataService(db)
    return await service.get_hts_stats()


@router.get("/broker-profile")
async def get_broker_instance_profile(db=Depends(get_db)):
    """Return active single-tenant customs brokerage instance configuration & readiness summary."""
    from app.core.config import settings

    service = ReferenceDataService(db)
    hts_stats = await service.get_hts_stats()
    live_ace = bool(settings.ace_sftp_enabled and settings.ace_sftp_host.strip())

    return {
        "broker_name": settings.broker_name,
        "broker_filer_code": settings.broker_filer_code or None,
        "broker_default_port": settings.broker_default_port or None,
        "cargowise_company_code": settings.cargowise_company_code,
        "cargowise_enterprise_id": settings.cargowise_enterprise_id,
        "audit_log_retention_days": settings.audit_log_retention_days,
        "cbp_19_cfr_163_compliant": settings.audit_log_retention_days >= 1825,
        "ace_mode": "live_sftp" if live_ace else ("simulation" if settings.ace_allow_simulation else "export_only"),
        "email_imap_configured": bool(settings.email_imap_host and settings.email_imap_user),
        "smtp_configured": bool(settings.smtp_host and settings.smtp_username),
        "hts_code_count": hts_stats.get("total_codes", 0) if isinstance(hts_stats, dict) else 0,
    }


@router.get("/document-types")
async def list_document_types(
    active_only: bool = Query(True, description="Only return active catalog rows"),
    db=Depends(get_db),
):
    """
    List catalog document types for Request Missing Document dropdowns.

    Includes default importer instruction templates per type.
    """
    from sqlalchemy import select
    from app.models.document_type import DocumentType

    query = select(DocumentType).order_by(DocumentType.sort_order.asc(), DocumentType.label.asc())
    if active_only:
        query = query.where(DocumentType.is_active.is_(True))
    result = await db.execute(query)
    rows = result.scalars().all()
    return {
        "count": len(rows),
        "items": [row.to_dict() for row in rows],
    }


# ==================== OFAC Screening Endpoints ====================

@router.post("/ofac/screen")
async def screen_entity(
    request: EntityScreenRequest,
    db=Depends(get_db)
):
    """
    Screen an entity against the OFAC SDN list.
    
    Uses fuzzy matching with configurable threshold.
    Returns matches with confidence scores and risk level.
    
    Risk levels:
    - clear: No matches found
    - possible_match: Partial name matches found (score < 98%)
    - confirmed_match: High-confidence match (score >= 98%)
    """
    service = ReferenceDataService(db)
    result = await service.screen_entity(
        name=request.name,
        entity_type=request.entity_type,
        id_number=request.id_number,
        threshold=request.threshold,
    )
    return result


@router.get("/ofac/stats")
async def get_ofac_stats(db=Depends(get_db)):
    """Get statistics about OFAC SDN entries in the database."""
    service = ReferenceDataService(db)
    return await service.get_ofac_stats()


# ==================== NAICS Code Endpoints ====================

@router.get("/naics/search")
async def search_naics_codes(
    query: str = Query(..., description="NAICS code or title to search"),
    sector: Optional[str] = Query(None, description="Filter by sector"),
    limit: int = Query(20, le=100, description="Maximum results to return"),
    db=Depends(get_db)
):
    """
    Search NAICS codes by code or title.
    
    Returns matching NAICS codes with sector and level information.
    """
    service = ReferenceDataService(db)
    results = await service.search_naics_codes(query=query, sector=sector, limit=limit)
    return {
        "query": query,
        "count": len(results),
        "results": results,
    }


# ==================== Compliance Screening History ====================

@router.get("/screening-history")
async def get_screening_history(
    party_id: Optional[UUID] = Query(None, description="Filter by party ID"),
    shipment_id: Optional[UUID] = Query(None, description="Filter by shipment ID"),
    limit: int = Query(50, le=200, description="Maximum results"),
    db=Depends(get_db)
):
    """
    Get compliance screening history.
    
    Returns past screening results for a party or shipment.
    """
    service = ReferenceDataService(db)
    results = await service.get_screening_history(
        party_id=party_id,
        shipment_id=shipment_id,
        limit=limit,
    )
    return {
        "count": len(results),
        "results": results,
    }


# ==================== Data Management ====================

@router.post("/seed")
async def seed_data(db=Depends(get_db)):
    """
    Seed the database with embedded HTS and NAICS reference data.
    
    This endpoint populates the database with commonly-used codes
    for local development and testing.
    """
    result = await seed_reference_data(db)
    return {
        "message": "Reference data seeded successfully",
        "seeded": result,
    }
