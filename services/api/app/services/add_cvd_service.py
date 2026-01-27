"""
ADD/CVD Lookup Service.

Service to check and apply antidumping and countervailing duty rates.

Task 2.3 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.add_cvd_orders import AddCvdOrder


@dataclass
class AddCvdResult:
    """Result of ADD/CVD lookup for a product."""
    has_add_cvd: bool
    add_rate: Optional[float] = None
    add_amount: Optional[float] = None
    add_case_number: Optional[str] = None
    cvd_rate: Optional[float] = None
    cvd_amount: Optional[float] = None
    cvd_case_number: Optional[str] = None
    combined_rate: Optional[float] = None
    combined_amount: Optional[float] = None
    product_description: Optional[str] = None
    country_code: Optional[str] = None
    requires_liquidation_review: bool = False
    message: Optional[str] = None
    orders: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.orders is None:
            self.orders = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_add_cvd": self.has_add_cvd,
            "add_rate": self.add_rate,
            "add_amount": self.add_amount,
            "add_case_number": self.add_case_number,
            "cvd_rate": self.cvd_rate,
            "cvd_amount": self.cvd_amount,
            "cvd_case_number": self.cvd_case_number,
            "combined_rate": self.combined_rate,
            "combined_amount": self.combined_amount,
            "product_description": self.product_description,
            "country_code": self.country_code,
            "requires_liquidation_review": self.requires_liquidation_review,
            "message": self.message,
            "orders": self.orders,
        }


class AddCvdLookupService:
    """
    Service to lookup and apply ADD/CVD rates.
    
    ADD (Antidumping Duties): Applied when foreign goods are sold in the US
    at less than fair value.
    
    CVD (Countervailing Duties): Applied to offset subsidies provided by
    foreign governments.
    """
    
    # In-memory cache for common lookups (in production, use Redis)
    _cache: Dict[str, AddCvdResult] = {}
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def check_add_cvd(
        self,
        hts_code: str,
        country_of_origin: str,
        entered_value: float = 0,
    ) -> AddCvdResult:
        """
        Check if ADD/CVD orders apply to an HTS + country combination.
        
        Args:
            hts_code: Full or partial HTS code
            country_of_origin: 2-letter ISO country code
            entered_value: Value to calculate duty amounts
            
        Returns:
            AddCvdResult with applicable rates and amounts
        """
        if not hts_code or not country_of_origin:
            return AddCvdResult(has_add_cvd=False, message="Missing HTS or country")
        
        # Normalize inputs
        hts_clean = hts_code.replace(".", "").strip()
        country = country_of_origin.upper().strip()
        
        # Extract HTS components
        chapter = hts_clean[:2] if len(hts_clean) >= 2 else None
        heading = hts_clean[:4] if len(hts_clean) >= 4 else None
        subheading = hts_clean[:6] if len(hts_clean) >= 6 else None
        
        if not chapter:
            return AddCvdResult(has_add_cvd=False, message="Invalid HTS code")
        
        # Check cache
        cache_key = f"{hts_code}:{country}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            # Recalculate amounts for new value
            if entered_value > 0:
                return self._apply_rates(cached, entered_value)
            return cached
        
        # Query for applicable orders
        # Match by HTS chapter + country, then filter by heading/subheading
        orders = []
        try:
            result = await self.db.execute(
                select(AddCvdOrder).where(
                    and_(
                        AddCvdOrder.is_active == True,
                        AddCvdOrder.country_code == country,
                        or_(
                            AddCvdOrder.hts_chapter == chapter,
                            AddCvdOrder.hts_heading == heading,
                            AddCvdOrder.hts_subheading == subheading,
                        )
                    )
                )
            )
            orders = result.scalars().all()
        except Exception:
            # Table doesn't exist or other DB error - use fallback data
            pass

        
        if not orders:
            # No orders found - check if we should use fallback data
            fallback = self._check_fallback_data(hts_code, country)
            if fallback.has_add_cvd:
                self._cache[cache_key] = fallback
                if entered_value > 0:
                    return self._apply_rates(fallback, entered_value)
                return fallback
            
            return AddCvdResult(
                has_add_cvd=False,
                message=f"No active ADD/CVD orders for HTS {hts_code} from {country}"
            )
        
        # Find the most specific matching order(s)
        add_order = None
        cvd_order = None
        
        for order in orders:
            # Score by specificity
            if self._order_matches(order, hts_clean):
                if order.case_type == "ADD" or order.add_rate:
                    if not add_order or self._is_more_specific(order, add_order, hts_clean):
                        add_order = order
                if order.case_type == "CVD" or order.cvd_rate:
                    if not cvd_order or self._is_more_specific(order, cvd_order, hts_clean):
                        cvd_order = order
        
        if not add_order and not cvd_order:
            return AddCvdResult(
                has_add_cvd=False,
                message=f"No specific match for HTS {hts_code} from {country}"
            )
        
        # Build result
        add_rate = float(add_order.add_rate) if add_order and add_order.add_rate else None
        cvd_rate = float(cvd_order.cvd_rate) if cvd_order and cvd_order.cvd_rate else None
        
        combined_rate = 0
        if add_rate:
            combined_rate += add_rate
        if cvd_rate:
            combined_rate += cvd_rate
        
        result = AddCvdResult(
            has_add_cvd=True,
            add_rate=add_rate,
            add_case_number=add_order.case_number if add_order else None,
            cvd_rate=cvd_rate,
            cvd_case_number=cvd_order.case_number if cvd_order else None,
            combined_rate=combined_rate if combined_rate > 0 else None,
            product_description=add_order.product_description if add_order else (cvd_order.product_description if cvd_order else None),
            country_code=country,
            requires_liquidation_review=True,
            message=f"ADD/CVD orders apply: {add_order.case_number if add_order else ''} {cvd_order.case_number if cvd_order else ''}".strip(),
            orders=[
                {"case_number": o.case_number, "case_type": o.case_type, "rate": float(o.add_rate or o.cvd_rate or 0)}
                for o in [add_order, cvd_order] if o
            ],
        )
        
        # Cache result
        self._cache[cache_key] = result
        
        # Calculate amounts if value provided
        if entered_value > 0:
            return self._apply_rates(result, entered_value)
        
        return result
    
    def _apply_rates(self, result: AddCvdResult, entered_value: float) -> AddCvdResult:
        """Apply rates to value to calculate duty amounts."""
        add_amount = entered_value * result.add_rate if result.add_rate else None
        cvd_amount = entered_value * result.cvd_rate if result.cvd_rate else None
        combined_amount = entered_value * result.combined_rate if result.combined_rate else None
        
        return AddCvdResult(
            has_add_cvd=result.has_add_cvd,
            add_rate=result.add_rate,
            add_amount=add_amount,
            add_case_number=result.add_case_number,
            cvd_rate=result.cvd_rate,
            cvd_amount=cvd_amount,
            cvd_case_number=result.cvd_case_number,
            combined_rate=result.combined_rate,
            combined_amount=combined_amount,
            product_description=result.product_description,
            country_code=result.country_code,
            requires_liquidation_review=result.requires_liquidation_review,
            message=result.message,
            orders=result.orders,
        )
    
    def _order_matches(self, order: AddCvdOrder, hts_clean: str) -> bool:
        """Check if an order matches the HTS code."""
        if order.hts_full and hts_clean.startswith(order.hts_full.replace(".", "")):
            return True
        if order.hts_subheading and hts_clean.startswith(order.hts_subheading):
            return True
        if order.hts_heading and hts_clean.startswith(order.hts_heading):
            return True
        if order.hts_chapter and hts_clean.startswith(order.hts_chapter):
            return True
        return False
    
    def _is_more_specific(self, new: AddCvdOrder, current: AddCvdOrder, hts_clean: str) -> bool:
        """Check if new order is more specific than current."""
        new_len = 0
        curr_len = 0
        
        if new.hts_full:
            new_len = len(new.hts_full.replace(".", ""))
        elif new.hts_subheading:
            new_len = len(new.hts_subheading)
        elif new.hts_heading:
            new_len = len(new.hts_heading)
        elif new.hts_chapter:
            new_len = len(new.hts_chapter)
        
        if current.hts_full:
            curr_len = len(current.hts_full.replace(".", ""))
        elif current.hts_subheading:
            curr_len = len(current.hts_subheading)
        elif current.hts_heading:
            curr_len = len(current.hts_heading)
        elif current.hts_chapter:
            curr_len = len(current.hts_chapter)
        
        return new_len > curr_len
    
    def _check_fallback_data(self, hts_code: str, country: str) -> AddCvdResult:
        """
        Check against known ADD/CVD data when database is empty.
        
        This uses the SAMPLE_ADD_CVD_ORDERS data as a fallback.
        In production, this would not be needed if the database is populated.
        """
        from app.models.add_cvd_orders import SAMPLE_ADD_CVD_ORDERS
        
        hts_clean = hts_code.replace(".", "").strip()
        chapter = hts_clean[:2] if len(hts_clean) >= 2 else None
        heading = hts_clean[:4] if len(hts_clean) >= 4 else None
        
        add_order = None
        cvd_order = None
        
        for order in SAMPLE_ADD_CVD_ORDERS:
            if order["country_code"] != country:
                continue
            if order.get("is_active") is False:
                continue
            
            # Check HTS match
            order_chapter = order.get("hts_chapter")
            order_heading = order.get("hts_heading")
            
            matches = False
            if order_heading and heading and heading.startswith(order_heading):
                matches = True
            elif order_chapter and chapter == order_chapter:
                matches = True
            
            if matches:
                if order.get("case_type") == "ADD" or order.get("add_rate"):
                    add_order = order
                if order.get("case_type") == "CVD" or order.get("cvd_rate"):
                    cvd_order = order
        
        if not add_order and not cvd_order:
            return AddCvdResult(has_add_cvd=False)
        
        add_rate = add_order.get("add_rate") if add_order else None
        cvd_rate = cvd_order.get("cvd_rate") if cvd_order else None
        
        combined = 0
        if add_rate:
            combined += add_rate
        if cvd_rate:
            combined += cvd_rate
        
        return AddCvdResult(
            has_add_cvd=True,
            add_rate=add_rate,
            add_case_number=add_order.get("case_number") if add_order else None,
            cvd_rate=cvd_rate,
            cvd_case_number=cvd_order.get("case_number") if cvd_order else None,
            combined_rate=combined if combined > 0 else None,
            product_description=add_order.get("product_description") if add_order else (cvd_order.get("product_description") if cvd_order else None),
            country_code=country,
            requires_liquidation_review=True,
            message="ADD/CVD order found (fallback data)",
            orders=[
                {"case_number": o.get("case_number"), "case_type": o.get("case_type"), "rate": o.get("add_rate") or o.get("cvd_rate")}
                for o in [add_order, cvd_order] if o
            ],
        )


async def check_add_cvd(
    db: AsyncSession,
    hts_code: str,
    country_of_origin: str,
    entered_value: float = 0,
) -> AddCvdResult:
    """
    Convenience function to check ADD/CVD applicability.
    
    Args:
        db: Database session
        hts_code: HTS code to check
        country_of_origin: Country code
        entered_value: Value to calculate duty amounts
        
    Returns:
        AddCvdResult with applicable rates
    """
    service = AddCvdLookupService(db)
    return await service.check_add_cvd(hts_code, country_of_origin, entered_value)
