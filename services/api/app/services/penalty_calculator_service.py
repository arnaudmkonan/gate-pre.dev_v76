"""
Penalty Calculator Service - CBP penalty estimation per 19 USC 1592

Migrated from G.A.T.E.S. reference project.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ViolationType(str, Enum):
    NEGLIGENCE = "negligence"
    GROSS_NEGLIGENCE = "gross_negligence"
    FRAUD = "fraud"


class ViolationCategory(str, Enum):
    CLASSIFICATION = "classification"
    VALUATION = "valuation"
    COUNTRY_OF_ORIGIN = "country_of_origin"
    MARKING = "marking"
    TRADE_AGREEMENT = "trade_agreement"
    OTHER = "other"


# CBP Interest Rates (updated periodically by Treasury)
CBP_INTEREST_RATE = 0.08  # 8% annual rate (approximate)

# Penalty multipliers per 19 USC 1592
PENALTY_MULTIPLIERS = {
    ViolationType.NEGLIGENCE: 2,        # 2x duty loss
    ViolationType.GROSS_NEGLIGENCE: 4,  # 4x duty loss
    ViolationType.FRAUD: None,          # Domestic value (no multiplier)
}

# Prior disclosure mitigation factors
DISCLOSURE_MITIGATION = {
    ViolationType.NEGLIGENCE: 0.25,       # Pay 25% of max penalty
    ViolationType.GROSS_NEGLIGENCE: 0.50,  # Pay 50% of max penalty
    ViolationType.FRAUD: 0.50,             # Pay 50% of max penalty (if accepted)
}

# Additional mitigation factors
FIRST_OFFENSE_REDUCTION = 0.75  # 25% reduction for first offense
COOPERATION_REDUCTION = 0.90    # 10% reduction for full cooperation


class PenaltyCalculation:
    """Result of penalty calculation."""
    
    def __init__(self):
        self.duty_loss: float = 0.0
        self.violation_type: ViolationType = ViolationType.NEGLIGENCE
        self.violation_category: ViolationCategory = ViolationCategory.OTHER
        self.entry_value: float = 0.0
        self.entry_date: Optional[str] = None
        self.interest_rate: float = CBP_INTEREST_RATE
        self.interest_days: int = 0
        self.interest_amount: float = 0.0
        self.max_penalty: float = 0.0
        self.mitigated_penalty: float = 0.0
        self.total_without_disclosure: float = 0.0
        self.total_with_disclosure: float = 0.0
        self.potential_savings: float = 0.0
        self.calculation_details: Dict[str, Any] = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "duty_loss": self.duty_loss,
            "violation_type": self.violation_type.value if isinstance(self.violation_type, Enum) else self.violation_type,
            "violation_category": self.violation_category.value if isinstance(self.violation_category, Enum) else self.violation_category,
            "entry_value": self.entry_value,
            "entry_date": self.entry_date,
            "interest_rate": self.interest_rate,
            "interest_days": self.interest_days,
            "interest_amount": self.interest_amount,
            "max_penalty": self.max_penalty,
            "mitigated_penalty": self.mitigated_penalty,
            "total_without_disclosure": self.total_without_disclosure,
            "total_with_disclosure": self.total_with_disclosure,
            "potential_savings": self.potential_savings,
            "calculation_details": self.calculation_details,
        }


def calculate_penalty(
    duty_loss: float,
    violation_type: ViolationType,
    entry_value: float = 0.0,
    entry_date: str = None,
    is_first_offense: bool = True,
    full_cooperation: bool = True,
    calculation_date: str = None
) -> PenaltyCalculation:
    """
    Calculate CBP penalties under 19 USC 1592.
    
    Args:
        duty_loss: Amount of unpaid/underpaid duties
        violation_type: negligence, gross_negligence, or fraud
        entry_value: Total entered value of goods (domestic value)
        entry_date: Date of entry for interest calculation
        is_first_offense: Whether this is importer's first violation
        full_cooperation: Whether importer is fully cooperating
        calculation_date: Date to calculate to (default: today)
    
    Returns:
        PenaltyCalculation with all computed values
    """
    duty_loss_dec = Decimal(str(duty_loss))
    entry_value_dec = Decimal(str(entry_value)) if entry_value else duty_loss_dec * 10
    
    calc = PenaltyCalculation()
    calc.duty_loss = float(duty_loss_dec)
    calc.violation_type = violation_type
    calc.entry_value = float(entry_value_dec)
    calc.entry_date = entry_date
    calc.interest_rate = CBP_INTEREST_RATE
    
    # Calculate maximum penalty based on violation type
    multiplier = PENALTY_MULTIPLIERS.get(violation_type)
    
    if violation_type == ViolationType.FRAUD:
        max_penalty = entry_value_dec
    else:
        calculated_penalty = duty_loss_dec * multiplier
        max_penalty = min(calculated_penalty, entry_value_dec)
    
    calc.max_penalty = float(max_penalty.quantize(Decimal("0.01"), ROUND_HALF_UP))
    
    # Calculate interest
    if entry_date:
        try:
            entry_dt = datetime.strptime(entry_date[:10], "%Y-%m-%d")
            calc_dt = datetime.strptime(calculation_date[:10], "%Y-%m-%d") if calculation_date else datetime.now()
            
            days = (calc_dt - entry_dt).days
            calc.interest_days = max(0, days)
            
            annual_interest = duty_loss_dec * Decimal(str(CBP_INTEREST_RATE))
            daily_interest = annual_interest / 365
            total_interest = daily_interest * days
            
            calc.interest_amount = float(max(Decimal("0"), total_interest).quantize(Decimal("0.01"), ROUND_HALF_UP))
        except Exception as e:
            logger.warning(f"Interest calculation error: {e}")
            calc.interest_amount = 0.0
            calc.interest_days = 0
    
    # Calculate mitigated penalty (with voluntary disclosure)
    disclosure_factor = Decimal(str(DISCLOSURE_MITIGATION.get(violation_type, 1.0)))
    mitigated = max_penalty * disclosure_factor
    
    # Apply additional mitigation factors
    if is_first_offense:
        mitigated = mitigated * Decimal(str(FIRST_OFFENSE_REDUCTION))
    if full_cooperation:
        mitigated = mitigated * Decimal(str(COOPERATION_REDUCTION))
    
    calc.mitigated_penalty = float(mitigated.quantize(Decimal("0.01"), ROUND_HALF_UP))
    
    # Calculate totals
    interest = Decimal(str(calc.interest_amount))
    
    calc.total_without_disclosure = float(
        (max_penalty + interest + duty_loss_dec).quantize(Decimal("0.01"), ROUND_HALF_UP)
    )
    
    calc.total_with_disclosure = float(
        (mitigated + interest + duty_loss_dec).quantize(Decimal("0.01"), ROUND_HALF_UP)
    )
    
    calc.potential_savings = float(calc.total_without_disclosure - calc.total_with_disclosure)
    
    # Detailed breakdown
    calc.calculation_details = {
        "duty_loss": float(duty_loss_dec),
        "violation_type": violation_type.value,
        "penalty_multiplier": multiplier if multiplier else "domestic_value",
        "max_penalty": calc.max_penalty,
        "disclosure_mitigation_factor": float(disclosure_factor),
        "first_offense_reduction": FIRST_OFFENSE_REDUCTION if is_first_offense else 1.0,
        "cooperation_reduction": COOPERATION_REDUCTION if full_cooperation else 1.0,
        "mitigated_penalty": calc.mitigated_penalty,
        "interest_rate": CBP_INTEREST_RATE,
        "interest_days": calc.interest_days,
        "interest_amount": calc.interest_amount,
        "total_duty_owed": float(duty_loss_dec),
        "total_without_disclosure": calc.total_without_disclosure,
        "total_with_disclosure": calc.total_with_disclosure,
        "savings_from_disclosure": calc.potential_savings,
        "savings_percentage": round((calc.potential_savings / calc.total_without_disclosure) * 100, 1) if calc.total_without_disclosure > 0 else 0
    }
    
    return calc


def calculate_statute_of_limitations(entry_date: str) -> Dict[str, Any]:
    """
    Calculate statute of limitations for customs violations.
    
    Per 19 USC 1621:
    - 5 years from date of violation for most penalties
    - 5 years from date of entry for duty collection
    """
    try:
        entry_dt = datetime.strptime(entry_date[:10], "%Y-%m-%d")
        expiration_dt = entry_dt + timedelta(days=5*365)
        
        now = datetime.now()
        days_remaining = (expiration_dt - now).days
        
        return {
            "entry_date": entry_date,
            "expiration_date": expiration_dt.strftime("%Y-%m-%d"),
            "days_remaining": max(0, days_remaining),
            "years_remaining": round(days_remaining / 365, 1) if days_remaining > 0 else 0,
            "is_expired": days_remaining <= 0,
            "urgency": "critical" if 0 < days_remaining <= 90 else 
                      "high" if days_remaining <= 180 else
                      "medium" if days_remaining <= 365 else "low"
        }
    except Exception as e:
        logger.error(f"Statute calculation error: {e}")
        return {"error": str(e)}


class PenaltyCalculatorService:
    """Service for calculating CBP penalties."""
    
    @staticmethod
    def calculate(
        duty_loss: float,
        violation_type: str,
        entry_value: float = 0.0,
        entry_date: str = None,
        is_first_offense: bool = True,
        full_cooperation: bool = True
    ) -> Dict[str, Any]:
        """Calculate penalty and return as dictionary."""
        vtype = ViolationType(violation_type)
        result = calculate_penalty(
            duty_loss=duty_loss,
            violation_type=vtype,
            entry_value=entry_value,
            entry_date=entry_date,
            is_first_offense=is_first_offense,
            full_cooperation=full_cooperation
        )
        return result.to_dict()
    
    @staticmethod
    def statute_of_limitations(entry_date: str) -> Dict[str, Any]:
        """Calculate statute of limitations."""
        return calculate_statute_of_limitations(entry_date)


# Singleton instance
penalty_calculator_service = PenaltyCalculatorService()
