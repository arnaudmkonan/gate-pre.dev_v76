"""
Duty Calculator API Routes.

Provides endpoints for calculating customs duties and fees.

Task 2.6 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.duty_calculator_service import DutyCalculatorService

router = APIRouter(prefix="/api/tools/duty-calculator", tags=["Duty Calculator"])


# ==================== Request/Response Models ====================

class DutyCalculationRequest(BaseModel):
    """Request for duty calculation."""
    hts_code: str = Field(..., description="HTS code (10 digits)")
    value: float = Field(..., ge=0, description="Entered value in USD")
    quantity: float = Field(1, ge=0, description="Quantity for specific rates")
    country_of_origin: str = Field("", description="2-letter ISO country code")
    fta_code: Optional[str] = Field(None, description="FTA code (USMCA, KORUS, etc.)")


class EntryCalculationRequest(BaseModel):
    """Request for full entry calculation."""
    lines: List[dict] = Field(..., description="Line items with hts_code, value, quantity, country_of_origin")
    entry_type: str = Field("formal", description="Entry type: formal or informal")


class MPFCalculationRequest(BaseModel):
    """Request for MPF/HMF calculation."""
    total_value: float = Field(..., ge=0)
    line_count: int = Field(1, ge=1)
    entry_type: str = Field("formal")


# ==================== Endpoints ====================

@router.post("/calculate")
async def calculate_duty(
    request: DutyCalculationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate duty for a single line item.

    Returns breakdown of all duty components including:
    - Base duty (ad valorem, specific, or compound)
    - Section 301 (if China origin)
    - Section 232 (if steel/aluminum)
    - ADD/CVD (if applicable)
    - FTA savings (if FTA code provided)
    """
    calc = DutyCalculatorService(db)

    result = await calc.calculate_line_duty(
        hts_code=request.hts_code,
        entered_value=request.value,
        quantity=request.quantity,
        country_of_origin=request.country_of_origin,
        fta_code=request.fta_code,
    )

    return result.to_dict()


@router.post("/calculate-entry")
async def calculate_entry_duties(
    request: EntryCalculationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate complete duties for an entry with multiple lines.

    Returns line-by-line breakdown plus entry totals including MPF/HMF.
    """
    calc = DutyCalculatorService(db)

    result = await calc.calculate_entry(
        lines=request.lines,
        entry_type=request.entry_type,
    )

    return result.to_dict()


@router.post("/calculate-fees")
async def calculate_fees(
    request: MPFCalculationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate MPF and HMF for an entry.

    - MPF (Formal): 0.3464% of value (min $29.66, max $575.35)
    - MPF (Informal): $2.18 per line
    - HMF: 0.125% of value
    """
    calc = DutyCalculatorService(db)

    result = calc.calculate_mpf(
        total_entered_value=request.total_value,
        line_count=request.line_count,
        entry_type=request.entry_type,
    )

    return result.to_dict()


@router.get("/hts/{hts_code}")
async def get_hts_info(
    hts_code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get HTS code information including duty rate.
    """
    calc = DutyCalculatorService(db)
    hts_data = await calc._get_hts_data(hts_code)

    if not hts_data:
        raise HTTPException(status_code=404, detail="HTS code not found")

    return {
        "hts_code": hts_data.get("hts_code"),
        "description": hts_data.get("description"),
        "duty_rate": hts_data.get("duty_rate"),
        "duty_rate_percent": hts_data.get("duty_rate_percent"),
        "chapter": hts_data.get("chapter"),
    }


@router.get("/quick/{hts_code}")
async def quick_duty_lookup(
    hts_code: str,
    value: float = 1000,
    country: str = "CN",
    db: AsyncSession = Depends(get_db),
):
    """
    Quick duty lookup with sensible defaults.

    Convenient endpoint for quick estimates.
    """
    calc = DutyCalculatorService(db)

    result = await calc.calculate_line_duty(
        hts_code=hts_code,
        entered_value=value,
        quantity=1,
        country_of_origin=country,
    )

    return {
        "hts_code": result.hts_code,
        "value": float(result.entered_value),
        "country": result.country_of_origin,
        "base_duty": float(result.base_duty_amount),
        "section_301": float(result.section_301_amount),
        "section_232": float(result.section_232_amount),
        "add_cvd": float(result.add_amount + result.cvd_amount),
        "total_duty": float(result.total_duty),
        "effective_rate": float(result.total_duty / result.entered_value * 100) if result.entered_value else 0,
    }


@router.get("/add-cvd/{hts_code}/{country}")
async def check_add_cvd(
    hts_code: str,
    country: str,
    value: float = 0,
    db: AsyncSession = Depends(get_db),
):
    """
    Check if ADD/CVD orders apply to an HTS + country combination.
    
    Returns applicable rates and case numbers if any.
    
    Examples:
    - Steel from China (7208.xx.xx + CN): ADD/CVD applies
    - Laptops from Taiwan (8471.30.xx + TW): No ADD/CVD
    """
    from app.services.add_cvd_service import check_add_cvd as add_cvd_check
    
    result = await add_cvd_check(
        db=db,
        hts_code=hts_code,
        country_of_origin=country,
        entered_value=value,
    )
    
    return result.to_dict()


@router.get("/add-cvd-orders")
async def list_add_cvd_orders(
    country: str = None,
    chapter: str = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """
    List known ADD/CVD orders, optionally filtered.
    """
    from app.models.add_cvd_orders import SAMPLE_ADD_CVD_ORDERS
    
    results = []
    for order in SAMPLE_ADD_CVD_ORDERS:
        if active_only and order.get("is_active") is False:
            continue
        if country and order.get("country_code") != country.upper():
            continue
        if chapter and order.get("hts_chapter") != chapter:
            continue
        
        results.append({
            "case_number": order.get("case_number"),
            "case_type": order.get("case_type"),
            "country_code": order.get("country_code"),
            "country_name": order.get("country_name"),
            "hts_chapter": order.get("hts_chapter"),
            "hts_heading": order.get("hts_heading"),
            "product_description": order.get("product_description"),
            "add_rate": order.get("add_rate"),
            "cvd_rate": order.get("cvd_rate"),
            "is_active": order.get("is_active", True),
        })
    
    return {
        "count": len(results),
        "orders": results,
    }


# ==================== FTA Endpoints ====================

@router.get("/fta/{country}")
async def check_fta_eligibility(
    country: str,
    hts_code: str = "8471.30.00",
    value: float = 1000,
    db: AsyncSession = Depends(get_db),
):
    """
    Check FTA eligibility for a country + HTS combination.
    
    Returns:
    - Whether the product qualifies for preferential treatment
    - Applicable FTA (USMCA, KORUS, CAFTA-DR, etc.)
    - Preferential rate vs MFN rate
    - Estimated savings
    - Certificate of origin requirements
    """
    from app.services.fta_rate_service import fta_rate_service
    
    result = fta_rate_service.check_fta_eligibility(
        country_of_origin=country,
        hts_code=hts_code,
        entered_value=value,
    )
    
    return result.to_dict()


@router.get("/fta-countries")
async def list_fta_countries():
    """
    List all countries with FTA agreements with the US.
    """
    from app.services.fta_rate_service import fta_rate_service
    
    countries = fta_rate_service.get_all_fta_countries()
    
    return {
        "count": len(countries),
        "countries": [
            {"code": code, "fta": fta}
            for code, fta in countries.items()
        ],
    }


@router.post("/compare-fta")
async def compare_fta_options(
    hts_code: str,
    value: float,
    countries: List[str],
    db: AsyncSession = Depends(get_db),
):
    """
    Compare FTA options across multiple sourcing countries.
    
    Useful for supply chain optimization to find the best sourcing option.
    """
    from app.services.fta_rate_service import fta_rate_service
    
    results = fta_rate_service.compare_fta_options(
        hts_code=hts_code,
        entered_value=value,
        countries=countries,
    )
    
    return {
        "hts_code": hts_code,
        "value": value,
        "comparison": results,
        "best_option": results[0] if results else None,
    }


# ==================== Landed Cost Endpoints ====================

class LandedCostRequest(BaseModel):
    """Request for landed cost calculation."""
    lines: List[dict] = Field(..., description="Line items")
    entry_type: str = Field("formal", description="Entry type")
    invoice_currency: str = Field("USD", description="Invoice currency")
    exchange_rate: float = Field(1.0, description="Exchange rate to USD")


@router.post("/landed-cost")
async def calculate_landed_cost(
    request: LandedCostRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate complete landed cost for an entry.
    
    Returns comprehensive breakdown including:
    - Per-line duty components (base, Section 301, Section 232, ADD/CVD)
    - FTA savings if applicable
    - Entry-level fees (MPF, HMF)
    - Total landed cost and per-unit cost
    - Effective duty rate
    
    Example request:
    ```json
    {
        "lines": [
            {"hts_code": "8471.30.01", "value": 50000, "quantity": 100, "country_of_origin": "CN"},
            {"hts_code": "8523.51.00", "value": 5000, "quantity": 1000, "country_of_origin": "CN"}
        ],
        "entry_type": "formal"
    }
    ```
    """
    from app.services.landed_cost_service import LandedCostCalculator
    
    calculator = LandedCostCalculator(db)
    result = await calculator.calculate_landed_cost(
        lines=request.lines,
        entry_type=request.entry_type,
        invoice_currency=request.invoice_currency,
        exchange_rate=request.exchange_rate,
    )
    
    return result.to_dict()


@router.get("/landed-cost/quick")
async def quick_landed_cost(
    hts_code: str,
    value: float,
    quantity: float = 1,
    country: str = "CN",
    fta_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Quick landed cost lookup for a single item.
    
    Simpler interface for quick estimates.
    """
    from app.services.landed_cost_service import LandedCostCalculator
    
    calculator = LandedCostCalculator(db)
    result = await calculator.calculate_landed_cost(
        lines=[{
            "hts_code": hts_code,
            "value": value,
            "quantity": quantity,
            "country_of_origin": country,
            "fta_code": fta_code,
        }],
        entry_type="formal",
    )
    
    # Return simplified response
    line = result.line_items[0] if result.line_items else None
    
    return {
        "hts_code": hts_code,
        "entered_value": value,
        "quantity": quantity,
        "country_of_origin": country,
        "duties": {
            "base": float(line.base_duty_amount) if line else 0,
            "section_301": float(line.section_301_amount) if line else 0,
            "section_232": float(line.section_232_amount) if line else 0,
            "add_cvd": float(line.add_amount + line.cvd_amount) if line else 0,
            "total_duty": float(line.total_duty + line.total_additional) if line else 0,
        },
        "fees": {
            "mpf": float(result.mpf_amount),
            "hmf": float(result.hmf_amount),
            "total_fees": float(result.total_fees),
        },
        "totals": {
            "duties_and_fees": float(result.total_duties_and_fees),
            "landed_cost": float(result.total_landed_cost),
            "landed_cost_per_unit": float(result.average_landed_cost_per_unit),
            "effective_rate_percent": float(result.effective_duty_rate),
        },
        "fta": {
            "code": line.fta_code if line else None,
            "eligible": line.fta_eligible if line else False,
            "savings": float(line.fta_savings) if line else 0,
        },
    }
