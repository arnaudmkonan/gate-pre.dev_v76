"""
Total Landed Cost Calculator Service.

Calculates complete landed cost including all duties, taxes, and fees.

Task 2.5 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
import logging

logger = logging.getLogger(__name__)


# Fee rates (2024)
MPF_RATE = Decimal("0.003464")  # 0.3464%
MPF_MIN = Decimal("29.66")
MPF_MAX = Decimal("575.35")
MPF_INFORMAL_PER_LINE = Decimal("2.18")
HMF_RATE = Decimal("0.00125")  # 0.125%


@dataclass
class LineItemCost:
    """Landed cost breakdown for a single line item."""
    line_number: int
    hts_code: str
    description: Optional[str] = None
    country_of_origin: str = ""
    
    # Values
    entered_value: Decimal = Decimal("0")
    quantity: Decimal = Decimal("1")
    unit_value: Decimal = Decimal("0")
    
    # Duty components
    base_duty_rate: Optional[Decimal] = None
    base_duty_amount: Decimal = Decimal("0")
    
    section_301_rate: Optional[Decimal] = None
    section_301_amount: Decimal = Decimal("0")
    
    section_232_rate: Optional[Decimal] = None
    section_232_amount: Decimal = Decimal("0")
    
    add_rate: Optional[Decimal] = None
    add_amount: Decimal = Decimal("0")
    
    cvd_rate: Optional[Decimal] = None
    cvd_amount: Decimal = Decimal("0")
    
    # FTA
    fta_code: Optional[str] = None
    fta_eligible: bool = False
    fta_savings: Decimal = Decimal("0")
    
    # Totals
    total_duty: Decimal = Decimal("0")
    total_additional: Decimal = Decimal("0")  # 301 + 232 + ADD/CVD
    
    # Landed cost
    landed_cost: Decimal = Decimal("0")
    landed_cost_per_unit: Decimal = Decimal("0")
    effective_duty_rate: Decimal = Decimal("0")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_number": self.line_number,
            "hts_code": self.hts_code,
            "description": self.description,
            "country_of_origin": self.country_of_origin,
            "values": {
                "entered_value": float(self.entered_value),
                "quantity": float(self.quantity),
                "unit_value": float(self.unit_value),
            },
            "duties": {
                "base": {
                    "rate": float(self.base_duty_rate) if self.base_duty_rate else None,
                    "amount": float(self.base_duty_amount),
                },
                "section_301": {
                    "rate": float(self.section_301_rate) if self.section_301_rate else None,
                    "amount": float(self.section_301_amount),
                },
                "section_232": {
                    "rate": float(self.section_232_rate) if self.section_232_rate else None,
                    "amount": float(self.section_232_amount),
                },
                "add": {
                    "rate": float(self.add_rate) if self.add_rate else None,
                    "amount": float(self.add_amount),
                },
                "cvd": {
                    "rate": float(self.cvd_rate) if self.cvd_rate else None,
                    "amount": float(self.cvd_amount),
                },
            },
            "fta": {
                "code": self.fta_code,
                "eligible": self.fta_eligible,
                "savings": float(self.fta_savings),
            },
            "totals": {
                "total_duty": float(self.total_duty),
                "total_additional": float(self.total_additional),
                "landed_cost": float(self.landed_cost),
                "landed_cost_per_unit": float(self.landed_cost_per_unit),
                "effective_duty_rate": float(self.effective_duty_rate),
            },
        }


@dataclass
class LandedCostSummary:
    """Complete landed cost summary for an entry."""
    entry_id: Optional[str] = None
    entry_type: str = "formal"
    
    # Counts
    line_count: int = 0
    line_items: List[LineItemCost] = field(default_factory=list)
    
    # Value totals
    total_entered_value: Decimal = Decimal("0")
    total_quantity: Decimal = Decimal("0")
    
    # Duty totals
    total_base_duty: Decimal = Decimal("0")
    total_section_301: Decimal = Decimal("0")
    total_section_232: Decimal = Decimal("0")
    total_add: Decimal = Decimal("0")
    total_cvd: Decimal = Decimal("0")
    total_duty: Decimal = Decimal("0")
    total_fta_savings: Decimal = Decimal("0")
    
    # Fees
    mpf_calculated: Decimal = Decimal("0")
    mpf_amount: Decimal = Decimal("0")
    mpf_capped: bool = False
    hmf_amount: Decimal = Decimal("0")
    total_fees: Decimal = Decimal("0")
    
    # Grand totals
    total_duties_and_fees: Decimal = Decimal("0")
    total_landed_cost: Decimal = Decimal("0")
    average_landed_cost_per_unit: Decimal = Decimal("0")
    effective_duty_rate: Decimal = Decimal("0")
    
    # Currency (for foreign invoice support)
    invoice_currency: str = "USD"
    exchange_rate: Decimal = Decimal("1")
    original_invoice_amount: Optional[Decimal] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "entry_type": self.entry_type,
            "line_count": self.line_count,
            "values": {
                "total_entered_value": float(self.total_entered_value),
                "total_quantity": float(self.total_quantity),
            },
            "duties": {
                "base_duty": float(self.total_base_duty),
                "section_301": float(self.total_section_301),
                "section_232": float(self.total_section_232),
                "add": float(self.total_add),
                "cvd": float(self.total_cvd),
                "total_duty": float(self.total_duty),
                "fta_savings": float(self.total_fta_savings),
            },
            "fees": {
                "mpf": {
                    "calculated": float(self.mpf_calculated),
                    "amount": float(self.mpf_amount),
                    "capped": self.mpf_capped,
                    "min": float(MPF_MIN),
                    "max": float(MPF_MAX),
                },
                "hmf": float(self.hmf_amount),
                "total_fees": float(self.total_fees),
            },
            "totals": {
                "duties_and_fees": float(self.total_duties_and_fees),
                "landed_cost": float(self.total_landed_cost),
                "average_landed_cost_per_unit": float(self.average_landed_cost_per_unit),
                "effective_duty_rate_percent": float(self.effective_duty_rate),
            },
            "currency": {
                "invoice_currency": self.invoice_currency,
                "exchange_rate": float(self.exchange_rate),
                "original_invoice_amount": float(self.original_invoice_amount) if self.original_invoice_amount else None,
            },
            "lines": [line.to_dict() for line in self.line_items],
        }


class LandedCostCalculator:
    """
    Service for calculating total landed cost.
    
    Combines:
    - Base duty (ad valorem, specific, compound)
    - Section 301 tariffs (China)
    - Section 232 tariffs (Steel/Aluminum)
    - ADD/CVD (Antidumping/Countervailing Duties)
    - MPF (Merchandise Processing Fee)
    - HMF (Harbor Maintenance Fee)
    - FTA savings analysis
    """
    
    def __init__(self, db=None):
        self.db = db
    
    async def calculate_landed_cost(
        self,
        lines: List[Dict[str, Any]],
        entry_type: str = "formal",
        entry_id: Optional[str] = None,
        invoice_currency: str = "USD",
        exchange_rate: float = 1.0,
    ) -> LandedCostSummary:
        """
        Calculate complete landed cost for an entry.
        
        Args:
            lines: List of line items with:
                - hts_code: str
                - value: float (entered value in USD)
                - quantity: float
                - country_of_origin: str
                - description: str (optional)
                - fta_code: str (optional)
            entry_type: "formal" or "informal"
            entry_id: Optional entry ID
            invoice_currency: Original invoice currency
            exchange_rate: Exchange rate to USD
            
        Returns:
            LandedCostSummary with complete breakdown
        """
        summary = LandedCostSummary(
            entry_id=entry_id,
            entry_type=entry_type,
            invoice_currency=invoice_currency,
            exchange_rate=Decimal(str(exchange_rate)),
        )
        
        # Calculate each line
        for idx, line_data in enumerate(lines):
            line_cost = await self._calculate_line_cost(
                line_number=idx + 1,
                hts_code=line_data.get("hts_code", ""),
                entered_value=float(line_data.get("value", 0)),
                quantity=float(line_data.get("quantity", 1)),
                country_of_origin=line_data.get("country_of_origin", ""),
                description=line_data.get("description"),
                fta_code=line_data.get("fta_code"),
            )
            
            summary.line_items.append(line_cost)
            
            # Accumulate totals
            summary.total_entered_value += line_cost.entered_value
            summary.total_quantity += line_cost.quantity
            summary.total_base_duty += line_cost.base_duty_amount
            summary.total_section_301 += line_cost.section_301_amount
            summary.total_section_232 += line_cost.section_232_amount
            summary.total_add += line_cost.add_amount
            summary.total_cvd += line_cost.cvd_amount
            summary.total_fta_savings += line_cost.fta_savings
        
        summary.line_count = len(lines)
        
        # Total duty
        summary.total_duty = (
            summary.total_base_duty +
            summary.total_section_301 +
            summary.total_section_232 +
            summary.total_add +
            summary.total_cvd
        )
        
        # Calculate fees
        self._calculate_fees(summary)
        
        # Grand totals
        summary.total_duties_and_fees = summary.total_duty + summary.total_fees
        summary.total_landed_cost = summary.total_entered_value + summary.total_duties_and_fees
        
        if summary.total_quantity > 0:
            summary.average_landed_cost_per_unit = (
                summary.total_landed_cost / summary.total_quantity
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        if summary.total_entered_value > 0:
            summary.effective_duty_rate = (
                (summary.total_duties_and_fees / summary.total_entered_value) * 100
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # Track original invoice if foreign currency
        if invoice_currency != "USD" and exchange_rate != 1.0:
            summary.original_invoice_amount = (
                summary.total_entered_value / Decimal(str(exchange_rate))
            ).quantize(Decimal("0.01"))
        
        return summary
    
    async def _calculate_line_cost(
        self,
        line_number: int,
        hts_code: str,
        entered_value: float,
        quantity: float,
        country_of_origin: str,
        description: Optional[str] = None,
        fta_code: Optional[str] = None,
    ) -> LineItemCost:
        """Calculate landed cost for a single line."""
        value = Decimal(str(entered_value))
        qty = Decimal(str(quantity))
        country = country_of_origin.upper()
        
        line = LineItemCost(
            line_number=line_number,
            hts_code=hts_code,
            description=description,
            country_of_origin=country,
            entered_value=value,
            quantity=qty,
            unit_value=(value / qty).quantize(Decimal("0.01")) if qty > 0 else Decimal("0"),
        )
        
        # Get base duty rate from HTS database
        hts_data = await self._get_hts_data(hts_code)
        if hts_data:
            line.description = line.description or hts_data.get("description")
            rate = hts_data.get("duty_rate_percent")
            if rate:
                line.base_duty_rate = Decimal(str(rate))
                line.base_duty_amount = (value * line.base_duty_rate / 100).quantize(Decimal("0.01"))
        
        # FTA check - may reduce base duty
        if fta_code:
            fta_result = await self._check_fta(hts_code, country, fta_code, value)
            if fta_result and fta_result.get("eligible"):
                line.fta_code = fta_code
                line.fta_eligible = True
                original_duty = line.base_duty_amount
                pref_rate = Decimal(str(fta_result.get("preferential_rate", 0)))
                line.base_duty_amount = (value * pref_rate / 100).quantize(Decimal("0.01"))
                line.fta_savings = original_duty - line.base_duty_amount
        
        # Section 301 (China)
        if country == "CN":
            s301_result = self._check_section_301(hts_code)
            if s301_result.get("covered"):
                line.section_301_rate = Decimal(str(s301_result.get("rate", 25)))
                line.section_301_amount = (value * line.section_301_rate / 100).quantize(Decimal("0.01"))
        
        # Section 232 (Steel/Aluminum)
        s232_result = self._check_section_232(hts_code, country)
        if s232_result.get("covered") and not s232_result.get("exempted"):
            line.section_232_rate = Decimal(str(s232_result.get("rate", 25)))
            line.section_232_amount = (value * line.section_232_rate / 100).quantize(Decimal("0.01"))
        
        # ADD/CVD
        addcvd_result = await self._check_add_cvd(hts_code, country)
        if addcvd_result:
            if addcvd_result.get("add_rate"):
                line.add_rate = Decimal(str(addcvd_result["add_rate"]))
                line.add_amount = (value * line.add_rate / 100).quantize(Decimal("0.01"))
            if addcvd_result.get("cvd_rate"):
                line.cvd_rate = Decimal(str(addcvd_result["cvd_rate"]))
                line.cvd_amount = (value * line.cvd_rate / 100).quantize(Decimal("0.01"))
        
        # Calculate line totals
        line.total_duty = line.base_duty_amount
        line.total_additional = (
            line.section_301_amount +
            line.section_232_amount +
            line.add_amount +
            line.cvd_amount
        )
        
        # Note: MPF/HMF calculated at entry level, not line level
        line.landed_cost = value + line.total_duty + line.total_additional
        
        if qty > 0:
            line.landed_cost_per_unit = (line.landed_cost / qty).quantize(Decimal("0.01"))
        
        if value > 0:
            line.effective_duty_rate = (
                (line.total_duty + line.total_additional) / value * 100
            ).quantize(Decimal("0.01"))
        
        return line
    
    def _calculate_fees(self, summary: LandedCostSummary):
        """Calculate MPF and HMF for the entry."""
        value = summary.total_entered_value
        
        if summary.entry_type == "informal":
            # Informal entry: Fixed per-line fee
            summary.mpf_amount = MPF_INFORMAL_PER_LINE * summary.line_count
            summary.mpf_calculated = summary.mpf_amount
        else:
            # Formal entry: Percentage with min/max
            summary.mpf_calculated = (value * MPF_RATE).quantize(Decimal("0.01"))
            
            if summary.mpf_calculated < MPF_MIN:
                summary.mpf_amount = MPF_MIN
                summary.mpf_capped = True
            elif summary.mpf_calculated > MPF_MAX:
                summary.mpf_amount = MPF_MAX
                summary.mpf_capped = True
            else:
                summary.mpf_amount = summary.mpf_calculated
        
        # HMF: Always calculated as percentage
        summary.hmf_amount = (value * HMF_RATE).quantize(Decimal("0.01"))
        
        summary.total_fees = summary.mpf_amount + summary.hmf_amount
    
    async def _get_hts_data(self, hts_code: str) -> Optional[Dict[str, Any]]:
        """Get HTS code data from database."""
        if not self.db:
            return None
        
        try:
            from app.models.reference_data import HTSCode
            from sqlalchemy import select
            
            hts_clean = hts_code.replace(".", "")
            result = await self.db.execute(
                select(HTSCode).where(
                    HTSCode.hts_code.ilike(f"%{hts_clean}%")
                ).limit(1)
            )
            hts = result.scalar_one_or_none()
            
            if hts:
                return {
                    "hts_code": hts.hts_code,
                    "description": hts.description,
                    "duty_rate": hts.duty_rate,
                    "duty_rate_percent": float(hts.duty_rate_percent) if hts.duty_rate_percent else None,
                }
        except Exception as e:
            logger.warning(f"HTS lookup failed for {hts_code}: {e}")
        
        return None
    
    async def _check_fta(
        self, hts_code: str, country: str, fta_code: str, value: Decimal
    ) -> Optional[Dict[str, Any]]:
        """Check FTA eligibility."""
        try:
            from app.services.fta_rate_service import fta_rate_service
            result = fta_rate_service.check_fta_eligibility(country, hts_code, float(value))
            return result.to_dict()
        except Exception as e:
            logger.warning(f"FTA check failed: {e}")
        return None
    
    def _check_section_301(self, hts_code: str) -> Dict[str, Any]:
        """Check Section 301 coverage."""
        try:
            from app.services.trade_compliance_service import trade_compliance_service
            result = trade_compliance_service.screen_section_301(hts_code, "CN")
            return {
                "covered": result.get("subject_to_301", False),
                "rate": result.get("total_rate", 25),
            }
        except Exception:
            pass
        return {"covered": False}
    
    def _check_section_232(self, hts_code: str, country: str) -> Dict[str, Any]:
        """Check Section 232 coverage."""
        try:
            from app.services.trade_compliance_service import trade_compliance_service
            result = trade_compliance_service.screen_section_232(hts_code, country)
            return {
                "covered": result.get("subject_to_232", False),
                "exempted": result.get("exempted", False),
                "rate": result.get("rate", 25),
                "product_type": result.get("product_type"),
            }
        except Exception:
            pass
        return {"covered": False}
    
    async def _check_add_cvd(self, hts_code: str, country: str) -> Optional[Dict[str, Any]]:
        """Check ADD/CVD orders."""
        try:
            from app.services.add_cvd_service import check_add_cvd
            if self.db:
                result = await check_add_cvd(self.db, hts_code, country)
                if result.has_add_cvd:
                    return {
                        "add_rate": result.add_rate * 100 if result.add_rate else None,  # Convert to %
                        "cvd_rate": result.cvd_rate * 100 if result.cvd_rate else None,
                        "add_case": result.add_case_number,
                        "cvd_case": result.cvd_case_number,
                    }
        except Exception as e:
            logger.warning(f"ADD/CVD check failed: {e}")
        return None


# Convenience function for API use
async def calculate_landed_cost(
    db,
    lines: List[Dict[str, Any]],
    entry_type: str = "formal",
    entry_id: Optional[str] = None,
) -> LandedCostSummary:
    """
    Calculate total landed cost for an entry.
    
    Args:
        db: Database session
        lines: Line items with hts_code, value, quantity, country_of_origin
        entry_type: "formal" or "informal"
        entry_id: Optional entry ID
        
    Returns:
        LandedCostSummary with complete breakdown
    """
    calculator = LandedCostCalculator(db)
    return await calculator.calculate_landed_cost(
        lines=lines,
        entry_type=entry_type,
        entry_id=entry_id,
    )
