"""
Duty Calculator Service.

Calculates customs duties, taxes, and fees for import entries:
- Base duty rates (ad valorem, specific, compound)
- Section 301 tariffs
- Section 232 tariffs
- ADD/CVD (Antidumping/Countervailing Duties)
- MPF (Merchandise Processing Fee)
- HMF (Harbor Maintenance Fee)
- FTA preferential rates

Task 2.1, 2.2, 2.3 from ROADMAP_FULL_WORKFLOW.md
"""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any, Tuple
from datetime import date
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reference_data import HTSCode

logger = logging.getLogger(__name__)


# ==================== Constants ====================

# MPF Constants (2024 rates)
MPF_RATE = Decimal("0.003464")  # 0.3464%
MPF_MIN = Decimal("29.66")
MPF_MAX = Decimal("575.35")
MPF_INFORMAL_PER_LINE = Decimal("2.18")

# HMF Constants
HMF_RATE = Decimal("0.00125")  # 0.125%

# Section 301 Tranches (China)
SECTION_301_LISTS = {
    "list_1": Decimal("25"),  # List 1: 25%
    "list_2": Decimal("25"),  # List 2: 25%
    "list_3": Decimal("25"),  # List 3: 25%
    "list_4a": Decimal("7.5"),  # List 4A: 7.5%
}

# Section 232 Rates
SECTION_232_RATES = {
    "steel": Decimal("25"),  # 25% on steel
    "aluminum": Decimal("10"),  # 10% on aluminum
}

# Countries exempt from Section 232 (as of current date - check for updates)
SECTION_232_EXEMPT_COUNTRIES = {"AU", "CA", "MX", "KR", "AR", "BR"}


# ==================== Data Classes ====================

@dataclass
class DutyBreakdown:
    """Breakdown of all duty components for a single line item."""
    # Input data
    hts_code: str
    entered_value: Decimal
    quantity: Decimal
    country_of_origin: str
    
    # Base duty
    base_duty_rate: Optional[Decimal] = None
    base_duty_rate_type: str = "ad_valorem"  # ad_valorem, specific, compound
    base_duty_amount: Decimal = Decimal("0")
    
    # Section 301 (China tariffs)
    section_301_rate: Optional[Decimal] = None
    section_301_amount: Decimal = Decimal("0")
    section_301_list: Optional[str] = None
    
    # Section 232 (Steel/Aluminum)
    section_232_rate: Optional[Decimal] = None
    section_232_amount: Decimal = Decimal("0")
    section_232_product: Optional[str] = None
    
    # ADD/CVD
    add_rate: Optional[Decimal] = None
    add_amount: Decimal = Decimal("0")
    add_case_number: Optional[str] = None
    
    cvd_rate: Optional[Decimal] = None
    cvd_amount: Decimal = Decimal("0")
    cvd_case_number: Optional[str] = None
    
    # FTA savings
    fta_code: Optional[str] = None
    fta_rate: Optional[Decimal] = None
    fta_eligible: bool = False
    fta_savings: Decimal = Decimal("0")
    
    # Totals
    total_duty: Decimal = Decimal("0")
    
    # Reference data
    hts_description: Optional[str] = None
    duty_rate_string: Optional[str] = None  # Original rate string from HTS schedule
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "hts_code": self.hts_code,
            "entered_value": float(self.entered_value),
            "quantity": float(self.quantity),
            "country_of_origin": self.country_of_origin,
            "base_duty": {
                "rate": float(self.base_duty_rate) if self.base_duty_rate else None,
                "rate_type": self.base_duty_rate_type,
                "amount": float(self.base_duty_amount),
            },
            "section_301": {
                "rate": float(self.section_301_rate) if self.section_301_rate else None,
                "amount": float(self.section_301_amount),
                "list": self.section_301_list,
            },
            "section_232": {
                "rate": float(self.section_232_rate) if self.section_232_rate else None,
                "amount": float(self.section_232_amount),
                "product": self.section_232_product,
            },
            "add_cvd": {
                "add_rate": float(self.add_rate) if self.add_rate else None,
                "add_amount": float(self.add_amount),
                "add_case_number": self.add_case_number,
                "cvd_rate": float(self.cvd_rate) if self.cvd_rate else None,
                "cvd_amount": float(self.cvd_amount),
                "cvd_case_number": self.cvd_case_number,
            },
            "fta": {
                "code": self.fta_code,
                "rate": float(self.fta_rate) if self.fta_rate else None,
                "eligible": self.fta_eligible,
                "savings": float(self.fta_savings),
            },
            "total_duty": float(self.total_duty),
            "hts_description": self.hts_description,
        }


@dataclass
class FeeBreakdown:
    """Breakdown of entry-level fees (MPF, HMF)."""
    total_entered_value: Decimal
    line_count: int
    entry_type: str = "formal"  # formal or informal
    
    mpf_amount: Decimal = Decimal("0")
    hmf_amount: Decimal = Decimal("0")
    
    mpf_rate: Decimal = MPF_RATE
    hmf_rate: Decimal = HMF_RATE
    
    # Calculations
    mpf_calculated: Decimal = Decimal("0")  # Before min/max
    mpf_capped: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_entered_value": float(self.total_entered_value),
            "line_count": self.line_count,
            "entry_type": self.entry_type,
            "mpf": {
                "rate": float(self.mpf_rate * 100),
                "calculated": float(self.mpf_calculated),
                "amount": float(self.mpf_amount),
                "min": float(MPF_MIN),
                "max": float(MPF_MAX),
                "capped": self.mpf_capped,
            },
            "hmf": {
                "rate": float(self.hmf_rate * 100),
                "amount": float(self.hmf_amount),
            },
            "total_fees": float(self.mpf_amount + self.hmf_amount),
        }


@dataclass
class EntryDutySummary:
    """Complete duty summary for an entire entry."""
    entry_id: Optional[str] = None
    line_count: int = 0
    
    # Value totals
    total_entered_value: Decimal = Decimal("0")
    total_dutiable_value: Decimal = Decimal("0")
    
    # Duty totals
    total_base_duty: Decimal = Decimal("0")
    total_section_301: Decimal = Decimal("0")
    total_section_232: Decimal = Decimal("0")
    total_add: Decimal = Decimal("0")
    total_cvd: Decimal = Decimal("0")
    total_duty: Decimal = Decimal("0")
    
    # Fees
    mpf_amount: Decimal = Decimal("0")
    hmf_amount: Decimal = Decimal("0")
    total_fees: Decimal = Decimal("0")
    
    # Grand total
    total_amount_due: Decimal = Decimal("0")
    
    # Line breakdowns
    lines: List[DutyBreakdown] = field(default_factory=list)
    fee_breakdown: Optional[FeeBreakdown] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "line_count": self.line_count,
            "totals": {
                "entered_value": float(self.total_entered_value),
                "dutiable_value": float(self.total_dutiable_value),
                "base_duty": float(self.total_base_duty),
                "section_301": float(self.total_section_301),
                "section_232": float(self.total_section_232),
                "add": float(self.total_add),
                "cvd": float(self.total_cvd),
                "total_duty": float(self.total_duty),
                "mpf": float(self.mpf_amount),
                "hmf": float(self.hmf_amount),
                "total_fees": float(self.total_fees),
                "total_amount_due": float(self.total_amount_due),
            },
            "lines": [line.to_dict() for line in self.lines],
            "fees": self.fee_breakdown.to_dict() if self.fee_breakdown else None,
        }


# ==================== Duty Calculator Service ====================

class DutyCalculatorService:
    """
    Service for calculating customs duties and fees.
    
    Provides methods for:
    - Single line duty calculation
    - Full entry calculation with fees
    - FTA savings analysis
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def calculate_line_duty(
        self,
        hts_code: str,
        entered_value: float,
        quantity: float = 1,
        country_of_origin: str = "",
        fta_code: Optional[str] = None,
    ) -> DutyBreakdown:
        """
        Calculate duties for a single line item.
        
        Args:
            hts_code: 10-digit HTS code
            entered_value: Value in USD
            quantity: Quantity for specific rates
            country_of_origin: 2-letter ISO country code
            fta_code: Optional FTA code (USMCA, KORUS, etc.)
            
        Returns:
            DutyBreakdown with all duty components
        """
        value = Decimal(str(entered_value))
        qty = Decimal(str(quantity))
        country = country_of_origin.upper()
        
        breakdown = DutyBreakdown(
            hts_code=hts_code,
            entered_value=value,
            quantity=qty,
            country_of_origin=country,
        )
        
        # Get HTS data from database
        hts_data = await self._get_hts_data(hts_code)
        
        if hts_data:
            breakdown.hts_description = hts_data.get("description")
            breakdown.duty_rate_string = hts_data.get("duty_rate")
            
            # Parse and apply base duty rate
            base_rate, rate_type = self._parse_duty_rate(hts_data.get("duty_rate", "Free"))
            breakdown.base_duty_rate = base_rate
            breakdown.base_duty_rate_type = rate_type
            
            # Check for FTA rate
            if fta_code and await self._check_fta_eligibility(hts_code, country, fta_code):
                breakdown.fta_code = fta_code
                breakdown.fta_eligible = True
                fta_rate = await self._get_fta_rate(hts_code, fta_code)
                if fta_rate is not None:
                    breakdown.fta_rate = fta_rate
                    mfn_duty = self._calculate_duty_amount(value, qty, base_rate, rate_type)
                    fta_duty = self._calculate_duty_amount(value, qty, fta_rate, "ad_valorem")
                    breakdown.fta_savings = mfn_duty - fta_duty
                    breakdown.base_duty_amount = fta_duty
                else:
                    breakdown.base_duty_amount = self._calculate_duty_amount(value, qty, base_rate, rate_type)
            else:
                breakdown.base_duty_amount = self._calculate_duty_amount(value, qty, base_rate, rate_type)
        
        # Section 301 (China only)
        if country == "CN":
            s301_rate, s301_list = await self._check_section_301(hts_code)
            if s301_rate:
                breakdown.section_301_rate = s301_rate
                breakdown.section_301_list = s301_list
                breakdown.section_301_amount = value * (s301_rate / 100)
        
        # Section 232 (Steel/Aluminum)
        if country not in SECTION_232_EXEMPT_COUNTRIES:
            s232_rate, s232_product = await self._check_section_232(hts_code)
            if s232_rate:
                breakdown.section_232_rate = s232_rate
                breakdown.section_232_product = s232_product
                breakdown.section_232_amount = value * (s232_rate / 100)
        
        # ADD/CVD
        add_cvd = await self._check_add_cvd(hts_code, country)
        if add_cvd:
            if add_cvd.get("add_rate"):
                breakdown.add_rate = Decimal(str(add_cvd["add_rate"]))
                breakdown.add_case_number = add_cvd.get("add_case_number")
                breakdown.add_amount = value * (breakdown.add_rate / 100)
            if add_cvd.get("cvd_rate"):
                breakdown.cvd_rate = Decimal(str(add_cvd["cvd_rate"]))
                breakdown.cvd_case_number = add_cvd.get("cvd_case_number")
                breakdown.cvd_amount = value * (breakdown.cvd_rate / 100)
        
        # Calculate total
        breakdown.total_duty = (
            breakdown.base_duty_amount +
            breakdown.section_301_amount +
            breakdown.section_232_amount +
            breakdown.add_amount +
            breakdown.cvd_amount
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        return breakdown
    
    def calculate_mpf(
        self,
        total_entered_value: float,
        line_count: int = 1,
        entry_type: str = "formal",
    ) -> FeeBreakdown:
        """
        Calculate Merchandise Processing Fee.
        
        Args:
            total_entered_value: Total entered value in USD
            line_count: Number of line items
            entry_type: "formal" or "informal"
            
        Returns:
            FeeBreakdown with MPF and HMF amounts
        """
        value = Decimal(str(total_entered_value))
        
        fee = FeeBreakdown(
            total_entered_value=value,
            line_count=line_count,
            entry_type=entry_type,
        )
        
        if entry_type == "informal":
            # Informal entry: $2.18 per line
            fee.mpf_calculated = MPF_INFORMAL_PER_LINE * line_count
            fee.mpf_amount = fee.mpf_calculated
        else:
            # Formal entry: 0.3464% with min/max
            fee.mpf_calculated = value * MPF_RATE
            
            if fee.mpf_calculated < MPF_MIN:
                fee.mpf_amount = MPF_MIN
                fee.mpf_capped = True
            elif fee.mpf_calculated > MPF_MAX:
                fee.mpf_amount = MPF_MAX
                fee.mpf_capped = True
            else:
                fee.mpf_amount = fee.mpf_calculated.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # HMF: 0.125% of value (imports only, not for FTZ or certain modes)
        fee.hmf_amount = (value * HMF_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        return fee
    
    async def calculate_entry(
        self,
        lines: List[Dict[str, Any]],
        entry_type: str = "formal",
        entry_id: Optional[str] = None,
    ) -> EntryDutySummary:
        """
        Calculate complete duties and fees for an entry.
        
        Args:
            lines: List of line items, each with:
                - hts_code: str
                - value: float
                - quantity: float (optional, default 1)
                - country_of_origin: str
                - fta_code: str (optional)
            entry_type: "formal" or "informal"
            entry_id: Optional entry ID for reference
            
        Returns:
            EntryDutySummary with all calculations
        """
        summary = EntryDutySummary(entry_id=entry_id)
        
        # Calculate each line
        for line_data in lines:
            breakdown = await self.calculate_line_duty(
                hts_code=line_data.get("hts_code", ""),
                entered_value=line_data.get("value", 0),
                quantity=line_data.get("quantity", 1),
                country_of_origin=line_data.get("country_of_origin", ""),
                fta_code=line_data.get("fta_code"),
            )
            summary.lines.append(breakdown)
            
            # Accumulate totals
            summary.total_entered_value += breakdown.entered_value
            summary.total_base_duty += breakdown.base_duty_amount
            summary.total_section_301 += breakdown.section_301_amount
            summary.total_section_232 += breakdown.section_232_amount
            summary.total_add += breakdown.add_amount
            summary.total_cvd += breakdown.cvd_amount
        
        summary.line_count = len(lines)
        summary.total_dutiable_value = summary.total_entered_value  # Simplified
        
        # Total duty
        summary.total_duty = (
            summary.total_base_duty +
            summary.total_section_301 +
            summary.total_section_232 +
            summary.total_add +
            summary.total_cvd
        )
        
        # Calculate fees
        fee_breakdown = self.calculate_mpf(
            total_entered_value=float(summary.total_entered_value),
            line_count=summary.line_count,
            entry_type=entry_type,
        )
        summary.fee_breakdown = fee_breakdown
        summary.mpf_amount = fee_breakdown.mpf_amount
        summary.hmf_amount = fee_breakdown.hmf_amount
        summary.total_fees = fee_breakdown.mpf_amount + fee_breakdown.hmf_amount
        
        # Grand total
        summary.total_amount_due = (
            summary.total_duty + summary.total_fees
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        return summary
    
    # ==================== Helper Methods ====================
    
    async def _get_hts_data(self, hts_code: str) -> Optional[Dict[str, Any]]:
        """Get HTS code data from database."""
        # Normalize code - remove dots
        normalized = hts_code.replace(".", "")
        
        # Try exact match
        result = await self.db.execute(
            select(HTSCode).where(
                HTSCode.hts_code.ilike(f"%{normalized}%")
            ).limit(1)
        )
        hts = result.scalar_one_or_none()
        
        if hts:
            return {
                "hts_code": hts.hts_code,
                "description": hts.description,
                "duty_rate": hts.duty_rate,
                "duty_rate_percent": float(hts.duty_rate_percent) if hts.duty_rate_percent else None,
                "chapter": hts.chapter,
            }
        return None
    
    def _parse_duty_rate(self, rate_string: str) -> Tuple[Optional[Decimal], str]:
        """Parse duty rate string into numeric rate and type."""
        if not rate_string:
            return None, "ad_valorem"
        
        rate_string = rate_string.strip().lower()
        
        # Free
        if rate_string == "free":
            return Decimal("0"), "ad_valorem"
        
        # Percentage (ad valorem)
        if "%" in rate_string:
            try:
                # Extract number before %
                num = rate_string.replace("%", "").strip()
                return Decimal(num), "ad_valorem"
            except:
                pass
        
        # Specific rate (e.g., "$1.50/kg")
        if "$" in rate_string or "¢" in rate_string:
            try:
                # Extract number
                import re
                match = re.search(r'[\$¢]?\s*([\d.]+)', rate_string)
                if match:
                    rate = Decimal(match.group(1))
                    if "¢" in rate_string:
                        rate = rate / 100  # Convert cents to dollars
                    return rate, "specific"
            except:
                pass
        
        # Try to parse as plain number (assume percentage)
        try:
            return Decimal(rate_string), "ad_valorem"
        except:
            return None, "ad_valorem"
    
    def _calculate_duty_amount(
        self,
        value: Decimal,
        quantity: Decimal,
        rate: Optional[Decimal],
        rate_type: str,
    ) -> Decimal:
        """Calculate duty amount based on rate type."""
        if rate is None:
            return Decimal("0")
        
        if rate_type == "ad_valorem":
            return (value * (rate / 100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        elif rate_type == "specific":
            return (quantity * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        elif rate_type == "compound":
            # For compound, assume rate is the ad valorem portion
            # Would need additional specific rate info
            return (value * (rate / 100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        return Decimal("0")
    
    async def _check_section_301(self, hts_code: str) -> Tuple[Optional[Decimal], Optional[str]]:
        """Check if HTS is subject to Section 301 tariffs."""
        # This would query a section_301_covered_products table
        # For now, use the trade_compliance_service pattern
        try:
            from app.services.trade_compliance_service import trade_compliance_service
            result = trade_compliance_service.screen_section_301(hts_code, "CN")
            if result.get("covered"):
                rate = result.get("additional_rate", 25)
                list_name = result.get("list", "list_3")
                return Decimal(str(rate)), list_name
        except Exception as e:
            logger.warning(f"Section 301 check failed for {hts_code}: {e}")
        
        return None, None
    
    async def _check_section_232(self, hts_code: str) -> Tuple[Optional[Decimal], Optional[str]]:
        """Check if HTS is subject to Section 232 tariffs (steel/aluminum)."""
        try:
            from app.services.trade_compliance_service import trade_compliance_service
            result = trade_compliance_service.screen_section_232(hts_code, "")
            if result.get("covered"):
                product = result.get("product_type", "steel")
                rate = SECTION_232_RATES.get(product, Decimal("25"))
                return rate, product
        except Exception as e:
            logger.warning(f"Section 232 check failed for {hts_code}: {e}")
        
        return None, None
    
    async def _check_add_cvd(self, hts_code: str, country: str) -> Optional[Dict[str, Any]]:
        """Check if HTS + country combination has ADD/CVD orders."""
        try:
            from app.services.trade_compliance_service import trade_compliance_service
            result = trade_compliance_service.screen_adcvd(hts_code, country)
            if result:
                return {
                    "add_rate": result.get("ad_rate"),
                    "add_case_number": result.get("ad_case_number"),
                    "cvd_rate": result.get("cvd_rate"),
                    "cvd_case_number": result.get("cvd_case_number"),
                }
        except Exception as e:
            logger.warning(f"ADD/CVD check failed for {hts_code}/{country}: {e}")
        
        return None
    
    async def _check_fta_eligibility(self, hts_code: str, country: str, fta_code: str) -> bool:
        """Check if product qualifies for FTA rate."""
        try:
            from app.services.trade_compliance_service import trade_compliance_service
            result = trade_compliance_service.check_fta_eligibility(country, hts_code)
            if result.get("eligible") and result.get("agreements"):
                for agreement in result["agreements"]:
                    if agreement.get("code", "").upper() == fta_code.upper():
                        return True
        except Exception as e:
            logger.warning(f"FTA eligibility check failed for {hts_code}/{country}/{fta_code}: {e}")
        
        return False
    
    async def _get_fta_rate(self, hts_code: str, fta_code: str) -> Optional[Decimal]:
        """Get preferential rate for FTA."""
        # Most FTAs have duty-free treatment
        # This would query an FTA rates table for specific rates
        # For now, assume duty-free for qualifying products
        return Decimal("0")


# ==================== Sync Version for Celery ====================

class DutyCalculatorServiceSync:
    """Synchronous version for Celery workers."""
    
    def __init__(self, db):
        self.db = db
    
    def calculate_line_duty(
        self,
        hts_code: str,
        entered_value: float,
        quantity: float = 1,
        country_of_origin: str = "",
        fta_code: Optional[str] = None,
    ) -> DutyBreakdown:
        """Calculate duties for a single line (sync version)."""
        value = Decimal(str(entered_value))
        qty = Decimal(str(quantity))
        country = country_of_origin.upper()
        
        breakdown = DutyBreakdown(
            hts_code=hts_code,
            entered_value=value,
            quantity=qty,
            country_of_origin=country,
        )
        
        # Get HTS from database
        from app.models.reference_data import HTSCode
        hts = self.db.query(HTSCode).filter(
            HTSCode.hts_code.ilike(f"%{hts_code.replace('.', '')}%")
        ).first()
        
        if hts:
            breakdown.hts_description = hts.description
            breakdown.duty_rate_string = hts.duty_rate
            
            # Parse rate
            rate = Decimal(str(hts.duty_rate_percent)) if hts.duty_rate_percent else Decimal("0")
            breakdown.base_duty_rate = rate
            breakdown.base_duty_amount = (value * (rate / 100)).quantize(Decimal("0.01"))
        
        # Section 301 (China)
        if country == "CN":
            # Simplified - check trade compliance
            from app.services.trade_compliance_service import trade_compliance_service
            try:
                result = trade_compliance_service.screen_section_301(hts_code, country)
                if result.get("covered"):
                    rate = Decimal(str(result.get("additional_rate", 25)))
                    breakdown.section_301_rate = rate
                    breakdown.section_301_amount = (value * (rate / 100)).quantize(Decimal("0.01"))
            except:
                pass
        
        # Calculate total
        breakdown.total_duty = (
            breakdown.base_duty_amount +
            breakdown.section_301_amount +
            breakdown.section_232_amount +
            breakdown.add_amount +
            breakdown.cvd_amount
        ).quantize(Decimal("0.01"))
        
        return breakdown
    
    def calculate_mpf(
        self,
        total_entered_value: float,
        line_count: int = 1,
        entry_type: str = "formal",
    ) -> FeeBreakdown:
        """Calculate MPF and HMF (sync version)."""
        value = Decimal(str(total_entered_value))
        
        fee = FeeBreakdown(
            total_entered_value=value,
            line_count=line_count,
            entry_type=entry_type,
        )
        
        if entry_type == "informal":
            fee.mpf_amount = MPF_INFORMAL_PER_LINE * line_count
        else:
            fee.mpf_calculated = value * MPF_RATE
            if fee.mpf_calculated < MPF_MIN:
                fee.mpf_amount = MPF_MIN
                fee.mpf_capped = True
            elif fee.mpf_calculated > MPF_MAX:
                fee.mpf_amount = MPF_MAX
                fee.mpf_capped = True
            else:
                fee.mpf_amount = fee.mpf_calculated.quantize(Decimal("0.01"))
        
        fee.hmf_amount = (value * HMF_RATE).quantize(Decimal("0.01"))
        
        return fee
