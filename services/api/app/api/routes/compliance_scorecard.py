"""
Compliance Scorecard and Prior Disclosure API Routes
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.database import get_db
from app.services.compliance_scorecard_service import (
    ComplianceScorecardService,
    calculate_compliance_score,
    get_compliance_trends,
    get_country_risk_ranking,
)
from app.services.prior_disclosure_service import (
    PriorDisclosureService,
    generate_prior_disclosure,
    get_disclosure_preview,
    ViolationType,
    ViolationCategory,
)

router = APIRouter(prefix="/api/compliance", tags=["Compliance Scorecard"])


# ==================== Request Models ====================

class DisclosurePreviewRequest(BaseModel):
    """Request for disclosure penalty preview."""
    duty_loss: float
    entry_count: int = 1
    violation_type: str = "negligence"
    oldest_entry_date: Optional[str] = None


class GenerateDisclosureRequest(BaseModel):
    """Request to generate a full prior disclosure."""
    entries: List[dict]
    violation_type: str = "negligence"
    violation_category: str = "classification"
    importer_info: Optional[dict] = None
    additional_info: Optional[dict] = None


# ==================== Scorecard Endpoints ====================

@router.get("/scorecard")
async def get_compliance_scorecard(
    importer: Optional[str] = Query(None, description="Filter by importer name"),
    period_days: int = Query(365, description="Analysis period in days"),
    db=Depends(get_db)
):
    """
    Calculate compliance scorecard for an importer.
    
    Returns weighted score based on:
    - Classification accuracy (30%)
    - Valuation accuracy (25%)
    - Sanctions screening (20%)
    - Country of origin (15%)
    - Documentation (10%)
    
    Grades: A (90+), B (80-89), C (70-79), D (60-69), F (<60)
    """
    service = ComplianceScorecardService(db)
    result = await service.calculate_importer_score(
        importer_name=importer,
        period_days=period_days
    )
    return result


@router.get("/trends")
async def get_trends(
    months: int = Query(12, le=24, description="Number of months to analyze"),
    db=Depends(get_db)
):
    """
    Get compliance trends over time.
    
    Returns:
    - Monthly entry/duty totals
    - Risk type breakdown
    - Top importers by value
    """
    result = await get_compliance_trends(db, months=months)
    return result


@router.get("/country-risk")
async def get_country_rankings(
    limit: int = Query(20, le=50, description="Number of countries to return"),
    db=Depends(get_db)
):
    """
    Get country risk rankings.
    
    Ranks countries by risk score based on:
    - Trade restriction status (301/232/AD-CVD)
    - Average duty rates
    - Entry volume
    """
    result = await get_country_risk_ranking(db, limit=limit)
    return {"countries": result, "count": len(result)}


# ==================== Prior Disclosure Endpoints ====================

@router.post("/disclosure/preview")
async def preview_disclosure_penalties(
    request: DisclosurePreviewRequest,
    db=Depends(get_db)
):
    """
    Preview prior disclosure penalties.
    
    Returns estimated penalties with and without voluntary disclosure,
    plus statute of limitations information.
    """
    result = await get_disclosure_preview(
        db,
        duty_loss=request.duty_loss,
        entry_count=request.entry_count,
        violation_type=request.violation_type,
        oldest_entry_date=request.oldest_entry_date
    )
    return result


@router.post("/disclosure/generate")
async def generate_disclosure_document(
    request: GenerateDisclosureRequest,
    db=Depends(get_db)
):
    """
    Generate a prior disclosure document.
    
    Creates a formatted 19 U.S.C. § 1592(c)(4) disclosure document
    with all required sections:
    - Disclosing party information
    - Nature of violation
    - Affected entries
    - Financial summary
    - Certifications
    """
    if not request.entries:
        raise HTTPException(400, "At least one entry is required")
    
    result = await generate_prior_disclosure(
        db,
        entries=request.entries,
        violation_type=request.violation_type,
        violation_category=request.violation_category,
        importer_info=request.importer_info,
        additional_info=request.additional_info
    )
    return result


@router.get("/disclosure/types")
async def get_disclosure_types():
    """
    Get available violation types and categories.
    """
    return {
        "violation_types": [
            {
                "value": "negligence",
                "label": "Negligence",
                "description": "Failure to exercise reasonable care",
                "penalty_multiplier": 2
            },
            {
                "value": "gross_negligence",
                "label": "Gross Negligence",
                "description": "Reckless disregard of the truth",
                "penalty_multiplier": 4
            },
            {
                "value": "fraud",
                "label": "Fraud",
                "description": "Willful intent to defraud",
                "penalty_multiplier": 4,
                "note": "Plus domestic value cap"
            }
        ],
        "categories": [
            {"value": "classification", "label": "Classification (HTS)"},
            {"value": "valuation", "label": "Valuation"},
            {"value": "country_of_origin", "label": "Country of Origin"},
            {"value": "marking", "label": "Marking Requirements"},
            {"value": "antidumping", "label": "AD/CVD Duties"},
            {"value": "free_trade", "label": "FTA Preference"}
        ],
        "disclosure_benefits": {
            "penalty_reduction": "Up to 75% reduction with prior disclosure",
            "interest_waiver": "Possible interest reduction",
            "criminal_protection": "Generally protects against criminal prosecution"
        }
    }


@router.get("/statute-check")
async def check_statute_of_limitations(
    entry_date: str = Query(..., description="Entry date (YYYY-MM-DD)"),
    db=Depends(get_db)
):
    """
    Check statute of limitations for an entry.
    
    Returns expiration date and urgency level.
    """
    from app.services.prior_disclosure_service import calculate_statute_of_limitations
    
    result = calculate_statute_of_limitations(entry_date)
    
    # Add urgency level
    days = result.get("days_remaining", 0)
    if days <= 0:
        urgency = "expired"
    elif days <= 90:
        urgency = "critical"
    elif days <= 180:
        urgency = "high"
    elif days <= 365:
        urgency = "medium"
    else:
        urgency = "low"
    
    result["urgency"] = urgency
    return result
