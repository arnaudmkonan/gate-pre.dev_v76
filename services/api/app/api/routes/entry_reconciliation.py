"""
Entry Reconciliation API Routes
Provides endpoints for drawback eligibility and import/export matching.
"""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.services.entry_reconciliation_service import (
    EntryReconciliationService,
    calculate_drawback_eligibility,
    estimate_drawback_refund,
)

router = APIRouter(prefix="/api/entry-reconciliation", tags=["Entry Reconciliation"])


# ==================== Request/Response Models ====================

class ImportEntry(BaseModel):
    """Import entry for reconciliation."""
    id: str
    entry_number: Optional[str] = None
    entry_date: Optional[str] = None
    hts_code: str
    description: Optional[str] = None
    quantity: float = 0
    unit: Optional[str] = "PCS"
    value: float = 0
    duty_paid: float = 0
    country_of_origin: Optional[str] = None


class ExportRecord(BaseModel):
    """Export record for reconciliation."""
    id: str
    export_date: Optional[str] = None
    hts_code: Optional[str] = None
    description: Optional[str] = None
    quantity: float = 0
    destination: Optional[str] = None


class ReconciliationRequest(BaseModel):
    """Request for import/export reconciliation."""
    import_entries: List[ImportEntry]
    export_records: List[ExportRecord]


class DrawbackEligibilityRequest(BaseModel):
    """Request for drawback eligibility check."""
    import_date: str = Field(..., description="Import entry date (YYYY-MM-DD or ISO)")
    export_date: Optional[str] = Field(None, description="Export date (optional)")


class DrawbackEstimateRequest(BaseModel):
    """Request for drawback refund estimate."""
    duty_paid: float = Field(..., description="Total duty paid on import")
    quantity_imported: float = Field(..., description="Quantity imported")
    quantity_exported: float = Field(..., description="Quantity exported")
    match_type: str = Field("direct", description="Match type: 'direct' or 'substitution'")


# ==================== Endpoints ====================

@router.post("/reconcile")
async def reconcile_entries(
    request: ReconciliationRequest,
    db=Depends(get_db)
):
    """
    Match import entries to export records for drawback claims.
    
    This endpoint performs automated matching based on:
    - HTS code similarity (50% weight)
    - Description similarity (20% weight)
    - Quantity ratio (15% weight)
    - Date proximity within 5-year window (15% weight)
    
    Returns matched pairs with confidence scores and potential refund amounts.
    
    **Drawback Types:**
    - **Direct Identification (19 USC 1313(a))**: Same goods exported (exact HTS match)
    - **Substitution (19 USC 1313(b))**: Same kind/quality goods exported
    
    **Refund Rate:** 99% of duty paid
    """
    service = EntryReconciliationService(db)
    
    # Convert Pydantic models to dicts
    imports = [entry.model_dump() for entry in request.import_entries]
    exports = [record.model_dump() for record in request.export_records]
    
    result = await service.reconcile(imports, exports)
    
    return result


@router.post("/eligibility")
async def check_drawback_eligibility(request: DrawbackEligibilityRequest):
    """
    Check if an import entry is still eligible for drawback.
    
    Per 19 USC 1313, drawback must be claimed within 5 years of import entry.
    
    Returns:
    - eligible: Whether drawback can still be claimed
    - deadline: Date by which claim must be filed
    - days_remaining: Days until deadline (negative if expired)
    """
    result = calculate_drawback_eligibility(
        import_date=request.import_date,
        export_date=request.export_date
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/eligibility")
async def check_eligibility_get(
    import_date: str = Query(..., description="Import entry date (YYYY-MM-DD)"),
    export_date: Optional[str] = Query(None, description="Export date (optional)")
):
    """Check drawback eligibility (GET version for convenience)."""
    result = calculate_drawback_eligibility(import_date, export_date)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/estimate-refund")
async def estimate_refund(request: DrawbackEstimateRequest):
    """
    Estimate potential drawback refund amount.
    
    Calculates the refund based on:
    - Duty paid
    - Quantity ratio (exported / imported)
    - 99% refund rate
    
    Returns detailed breakdown of potential refund.
    """
    result = estimate_drawback_refund(
        duty_paid=request.duty_paid,
        quantity_imported=request.quantity_imported,
        quantity_exported=request.quantity_exported,
        match_type=request.match_type
    )
    return result


@router.get("/estimate-refund")
async def estimate_refund_get(
    duty_paid: float = Query(..., description="Total duty paid"),
    quantity_imported: float = Query(..., description="Quantity imported"),
    quantity_exported: float = Query(..., description="Quantity exported"),
    match_type: str = Query("direct", description="Match type: direct or substitution")
):
    """Estimate drawback refund (GET version for convenience)."""
    result = estimate_drawback_refund(
        duty_paid=duty_paid,
        quantity_imported=quantity_imported,
        quantity_exported=quantity_exported,
        match_type=match_type
    )
    return result


@router.get("/info")
async def get_drawback_info():
    """
    Get information about drawback rules and eligibility requirements.
    
    Returns reference information for implementing drawback claims.
    """
    return {
        "program": "Duty Drawback (19 USC 1313)",
        "refund_rate": 0.99,
        "refund_rate_percent": 99,
        "eligibility_window_years": 5,
        "eligibility_window_days": 1825,
        "types": [
            {
                "name": "Direct Identification",
                "code": "1313(a)",
                "description": "Same goods that were imported are exported",
                "requirements": [
                    "Exact HTS code match",
                    "Same quantity or less exported",
                    "Export within 5 years of import"
                ]
            },
            {
                "name": "Substitution",
                "code": "1313(b)", 
                "description": "Goods of same kind and quality exported",
                "requirements": [
                    "Same 8-digit HTS classification",
                    "Commercially interchangeable",
                    "Export within 5 years of import"
                ]
            },
            {
                "name": "Manufacturing",
                "code": "1313(a)",
                "description": "Imported goods used in manufacture of exported goods",
                "requirements": [
                    "Imported goods used in production",
                    "Finished product exported",
                    "Export within 5 years of import"
                ]
            }
        ],
        "filing_requirements": [
            "CBP Form 7551 (Drawback Entry)",
            "Proof of import (entry summary, 7501)",
            "Proof of export (bill of lading, export declaration)",
            "Evidence of manufacture (if applicable)"
        ],
        "excluded_programs": [
            "Section 301 tariffs (China)",
            "Section 232 tariffs (Steel/Aluminum)" 
        ],
        "cbp_1_percent_fee": "CBP retains 1% of eligible drawback amount"
    }
