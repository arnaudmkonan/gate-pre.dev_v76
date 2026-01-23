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

router = APIRouter(prefix="/api/reference-data", tags=["Reference Data"])


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
