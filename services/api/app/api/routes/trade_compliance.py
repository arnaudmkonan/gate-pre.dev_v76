"""
Trade Compliance API Routes

Provides endpoints for:
- AD/CVD screening
- Section 301/232 tariff screening
- FTA eligibility
- Comprehensive duty screening
- Liquidation tracking
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.services.trade_compliance_service import trade_compliance_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trade-compliance", tags=["trade-compliance"])


# --- Request/Response Models ---

class ScreeningRequest(BaseModel):
    hts_code: str
    country_of_origin: str
    entered_value: float = 0.0


class ADCVDMatch(BaseModel):
    order_id: str
    country: str
    product: str
    ad_rate: float
    cvd_rate: float
    combined_rate: float
    severity: str


class ScreeningResponse(BaseModel):
    hts_code: str
    country_of_origin: str
    entered_value: float
    adcvd: List[dict]
    section_301: dict
    section_232: dict
    fta_eligibility: dict
    alerts: List[dict]
    estimated_additional_duties: float


# --- Endpoints ---

@router.post("/screen", response_model=ScreeningResponse)
async def comprehensive_screening(request: ScreeningRequest):
    """
    Perform comprehensive duty screening for an item.
    
    Checks:
    - AD/CVD (Antidumping/Countervailing Duty) orders
    - Section 301 tariffs (China)
    - Section 232 tariffs (Steel/Aluminum)
    - FTA eligibility (USMCA, CAFTA-DR, Korea, Australia)
    
    Returns alerts and estimated additional duties.
    """
    result = trade_compliance_service.comprehensive_duty_screening(
        hts_code=request.hts_code,
        country_of_origin=request.country_of_origin,
        entered_value=request.entered_value
    )
    return result


@router.get("/adcvd")
async def screen_adcvd(
    hts_code: str = Query(..., description="HTS code"),
    country: str = Query(..., description="Country of origin")
):
    """Screen for AD/CVD duties."""
    matches = trade_compliance_service.screen_adcvd(hts_code, country)
    return {
        "hts_code": hts_code,
        "country": country,
        "matches": matches,
        "has_adcvd": len(matches) > 0
    }


@router.get("/section-301")
async def screen_section_301(
    hts_code: str = Query(..., description="HTS code"),
    country: str = Query(..., description="Country of origin")
):
    """Screen for Section 301 tariffs (China)."""
    result = trade_compliance_service.screen_section_301(hts_code, country)
    return result


@router.get("/section-232")
async def screen_section_232(
    hts_code: str = Query(..., description="HTS code"),
    country: str = Query(..., description="Country of origin")
):
    """Screen for Section 232 tariffs (Steel/Aluminum)."""
    result = trade_compliance_service.screen_section_232(hts_code, country)
    return result


@router.get("/fta-eligibility")
async def check_fta_eligibility(
    country: str = Query(..., description="Country of origin"),
    hts_code: Optional[str] = Query(None, description="HTS code (optional)")
):
    """Check FTA eligibility for a country."""
    result = trade_compliance_service.check_fta_eligibility(country, hts_code)
    return result


@router.get("/liquidation-dates")
async def calculate_liquidation_dates(
    entry_date: str = Query(..., description="Entry date (YYYY-MM-DD)")
):
    """Calculate liquidation deadlines and protest windows."""
    result = trade_compliance_service.calculate_liquidation_dates(entry_date)
    return result


@router.get("/adcvd-orders")
async def list_adcvd_orders(
    country: Optional[str] = Query(None, description="Filter by country")
):
    """List all AD/CVD orders in the database."""
    from app.services.trade_compliance_service import ADCVD_ORDERS
    
    orders = ADCVD_ORDERS
    if country:
        orders = [o for o in orders if country.lower() in o["country"].lower()]
    
    return {
        "total": len(orders),
        "orders": orders
    }


@router.get("/fta-agreements")
async def list_fta_agreements():
    """List all FTA agreements."""
    from app.services.trade_compliance_service import FTA_AGREEMENTS
    
    return {
        "total": len(FTA_AGREEMENTS),
        "agreements": FTA_AGREEMENTS
    }


# --- Penalty Calculator Endpoints ---

class PenaltyRequest(BaseModel):
    duty_loss: float
    violation_type: str  # 'negligence', 'gross_negligence', 'fraud'
    entry_value: float = 0.0
    entry_date: Optional[str] = None
    is_first_offense: bool = True
    full_cooperation: bool = True


@router.post("/penalty/calculate")
async def calculate_penalty(request: PenaltyRequest):
    """
    Calculate CBP penalties under 19 USC 1592.
    
    Violation types:
    - negligence: 2x duty loss (max domestic value)
    - gross_negligence: 4x duty loss (max domestic value)
    - fraud: Domestic value of merchandise
    
    Returns penalty with and without voluntary prior disclosure.
    """
    from app.services.penalty_calculator_service import penalty_calculator_service
    
    result = penalty_calculator_service.calculate(
        duty_loss=request.duty_loss,
        violation_type=request.violation_type,
        entry_value=request.entry_value,
        entry_date=request.entry_date,
        is_first_offense=request.is_first_offense,
        full_cooperation=request.full_cooperation
    )
    return result


@router.get("/penalty/statute-of-limitations")
async def calculate_statute_of_limitations(
    entry_date: str = Query(..., description="Entry date (YYYY-MM-DD)")
):
    """Calculate statute of limitations (5 years per 19 USC 1621)."""
    from app.services.penalty_calculator_service import penalty_calculator_service
    
    result = penalty_calculator_service.statute_of_limitations(entry_date)
    return result
