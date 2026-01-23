"""
Entry Reconciliation Service
Matches import entries to export records for drawback claims.

Drawback Types:
- Direct Identification (19 USC 1313(a)): Same goods exported
- Substitution (19 USC 1313(b)): Same kind/quality goods exported  
- Manufacturing (19 USC 1313(a)): Imported goods used in manufacturing exports

99% refund rate for both direct identification and substitution drawback.
Claims must be filed within 5 years of import entry date.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class EntryReconciliationService:
    """
    Reconcile import entries with export records to identify drawback opportunities.
    """
    
    # Drawback eligibility window (5 years per 19 USC 1313)
    ELIGIBILITY_DAYS = 1825  # 5 years
    
    # Refund rate (99% for most drawback claims)
    REFUND_RATE = 0.99
    
    # Minimum match confidence threshold
    MIN_MATCH_THRESHOLD = 0.60

    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def reconcile(
        self,
        import_entries: List[Dict],
        export_records: List[Dict],
    ) -> Dict[str, Any]:
        """
        Main reconciliation function - matches imports to exports.
        
        Args:
            import_entries: List of import entry dicts with:
                - id, entry_number, entry_date, hts_code, description
                - quantity, unit, value, duty_paid, country_of_origin
            export_records: List of export record dicts with:
                - id, export_date, hts_code, description, quantity, destination
                
        Returns:
            {
                "matches": [{
                    "import_entry": {...},
                    "export_record": {...},
                    "match_type": "direct" | "substitution",
                    "match_confidence": 0.95,
                    "eligible_quantity": 100,
                    "potential_refund": 5000.00,
                    "reasoning": "..."
                }],
                "unmatched_imports": [...],
                "unmatched_exports": [...],
                "summary": {
                    "total_matches": 10,
                    "total_potential_refund": 50000.00,
                    "direct_matches": 5,
                    "substitution_matches": 5
                }
            }
        """
        result = {
            "matches": [],
            "unmatched_imports": [],
            "unmatched_exports": [],
            "summary": {
                "total_matches": 0,
                "total_potential_refund": 0,
                "direct_matches": 0,
                "substitution_matches": 0
            }
        }
        
        if not import_entries:
            logger.info("No import entries provided for reconciliation")
            return result
            
        if not export_records:
            logger.info("No export records provided for reconciliation")
            result["unmatched_imports"] = import_entries
            return result
        
        # Build export index for efficient matching
        export_index = self._build_export_index(export_records)
        
        # Track matched exports
        matched_export_ids = set()
        
        # Process each import entry
        for import_entry in import_entries:
            matches = self._find_matches(
                import_entry, 
                export_records, 
                export_index, 
                matched_export_ids
            )
            
            if matches:
                for match in matches:
                    result["matches"].append(match)
                    matched_export_ids.add(match["export_record"].get("id"))
                    
                    # Update summary
                    result["summary"]["total_matches"] += 1
                    result["summary"]["total_potential_refund"] += match["potential_refund"]
                    if match["match_type"] == "direct":
                        result["summary"]["direct_matches"] += 1
                    else:
                        result["summary"]["substitution_matches"] += 1
            else:
                result["unmatched_imports"].append(import_entry)
        
        # Collect unmatched exports
        result["unmatched_exports"] = [
            e for e in export_records 
            if e.get("id") not in matched_export_ids
        ]
        
        # Round total potential refund
        result["summary"]["total_potential_refund"] = round(
            result["summary"]["total_potential_refund"], 2
        )
        
        return result
    
    def _build_export_index(self, exports: List[Dict]) -> Dict:
        """Build index for efficient matching by HTS code."""
        index = {
            "by_hts": {},
            "by_hts_6": {},
        }
        
        for export in exports:
            hts = str(export.get("hts_code", "") or "")
            
            # Index by full HTS code
            if hts:
                if hts not in index["by_hts"]:
                    index["by_hts"][hts] = []
                index["by_hts"][hts].append(export)
            
            # Index by first 6 digits (heading level)
            hts_6 = hts.replace(".", "")[:6]
            if hts_6:
                if hts_6 not in index["by_hts_6"]:
                    index["by_hts_6"][hts_6] = []
                index["by_hts_6"][hts_6].append(export)
        
        return index
    
    def _find_matches(
        self, 
        import_entry: Dict, 
        all_exports: List[Dict],
        export_index: Dict,
        matched_ids: set
    ) -> List[Dict]:
        """Find matching export records for an import entry."""
        matches = []
        
        import_hts = str(import_entry.get("hts_code", "") or "")
        import_hts_6 = import_hts.replace(".", "")[:6]
        import_qty = float(import_entry.get("quantity") or 0)
        import_duty = float(import_entry.get("duty_paid") or 0)
        
        # Skip if no HTS or no duty paid
        if not import_hts or import_duty <= 0:
            return matches
        
        # Get candidate exports - prefer exact HTS match, then 6-digit match
        candidates = []
        
        if import_hts in export_index.get("by_hts", {}):
            candidates.extend(export_index["by_hts"][import_hts])
        
        if import_hts_6 in export_index.get("by_hts_6", {}):
            for exp in export_index["by_hts_6"][import_hts_6]:
                if exp not in candidates:
                    candidates.append(exp)
        
        # If no HTS-based candidates, consider all exports
        if not candidates:
            candidates = all_exports
        
        # Filter out already matched exports
        candidates = [c for c in candidates if c.get("id") not in matched_ids]
        
        # Score each candidate
        for export in candidates:
            score, match_type, reasoning = self._calculate_match_score(import_entry, export)
            
            if score >= self.MIN_MATCH_THRESHOLD:
                export_qty = float(export.get("quantity", import_qty) or import_qty)
                eligible_qty = min(import_qty, export_qty)
                
                # Calculate potential refund
                refund_qty_ratio = eligible_qty / import_qty if import_qty > 0 else 0
                potential_refund = import_duty * self.REFUND_RATE * refund_qty_ratio
                
                matches.append({
                    "import_entry": import_entry,
                    "export_record": export,
                    "match_type": match_type,
                    "match_confidence": round(score, 3),
                    "eligible_quantity": eligible_qty,
                    "refund_rate": self.REFUND_RATE,
                    "potential_refund": round(potential_refund, 2),
                    "reasoning": reasoning
                })
        
        # Sort by confidence and return best matches (top 3)
        matches.sort(key=lambda x: x["match_confidence"], reverse=True)
        return matches[:3]
    
    def _calculate_match_score(
        self, 
        import_entry: Dict, 
        export: Dict
    ) -> Tuple[float, str, str]:
        """
        Calculate match score between import and export.
        
        Scoring weights:
        - HTS match: 50% (exact=50%, 6-digit=35%, 4-digit=20%)
        - Description similarity: 20%
        - Quantity ratio: 15%
        - Date proximity: 15%
        
        Returns: (score, match_type, reasoning)
        """
        score = 0.0
        factors = []
        match_type = "substitution"
        
        # HTS code match (most important factor)
        import_hts = str(import_entry.get("hts_code", "") or "").replace(".", "")
        export_hts = str(export.get("hts_code", "") or "").replace(".", "")
        
        if import_hts and export_hts:
            if import_hts == export_hts:
                score += 0.50
                match_type = "direct"
                factors.append("Exact HTS match")
            elif import_hts[:6] == export_hts[:6]:
                score += 0.35
                factors.append("HTS heading match (6-digit)")
            elif import_hts[:4] == export_hts[:4]:
                score += 0.20
                factors.append("HTS chapter match (4-digit)")
        
        # Description similarity
        import_desc = str(import_entry.get("description", "") or "").lower()
        export_desc = str(export.get("description", "") or "").lower()
        
        if import_desc and export_desc:
            desc_similarity = SequenceMatcher(None, import_desc, export_desc).ratio()
            score += desc_similarity * 0.20
            if desc_similarity > 0.7:
                factors.append(f"Description similarity: {desc_similarity:.0%}")
        
        # Quantity ratio
        import_qty = float(import_entry.get("quantity") or 0)
        export_qty = float(export.get("quantity") or 0)
        
        if import_qty > 0 and export_qty > 0:
            qty_ratio = min(import_qty, export_qty) / max(import_qty, export_qty)
            score += qty_ratio * 0.15
            if qty_ratio > 0.5:
                factors.append(f"Quantity ratio: {qty_ratio:.0%}")
        
        # Date proximity (within 5 years)
        try:
            import_date = import_entry.get("entry_date")
            export_date = export.get("export_date")
            
            if import_date and export_date:
                import_dt = self._parse_date(import_date)
                export_dt = self._parse_date(export_date)
                
                if import_dt and export_dt:
                    days_diff = abs((export_dt - import_dt).days)
                    
                    if days_diff <= self.ELIGIBILITY_DAYS:
                        date_score = (self.ELIGIBILITY_DAYS - days_diff) / self.ELIGIBILITY_DAYS
                        score += date_score * 0.15
                        factors.append(f"Export within {days_diff} days of import")
        except Exception as e:
            logger.debug(f"Date parsing error: {e}")
        
        # Build reasoning
        reasoning = "; ".join(factors) if factors else "General match based on available data"
        
        return (score, match_type, reasoning)
    
    def _parse_date(self, date_value) -> Optional[datetime]:
        """Parse various date formats to datetime."""
        if isinstance(date_value, datetime):
            return date_value
        
        if isinstance(date_value, str):
            # Handle ISO format
            try:
                return datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            except:
                pass
            
            # Handle common date formats
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
                try:
                    return datetime.strptime(date_value, fmt)
                except:
                    pass
        
        return None


# ==================== Standalone Functions ====================

def calculate_drawback_eligibility(
    import_date: str,
    export_date: str = None
) -> Dict[str, Any]:
    """
    Calculate drawback eligibility based on dates.
    
    Per 19 USC 1313: Drawback must be claimed within 5 years of import.
    
    Returns:
        - eligible: bool
        - deadline: ISO date string
        - days_remaining: int (negative if expired)
    """
    try:
        import_dt = datetime.fromisoformat(import_date.replace('Z', '+00:00'))
    except:
        try:
            import_dt = datetime.strptime(import_date, "%Y-%m-%d")
        except:
            return {"eligible": False, "error": "Invalid import date format"}
    
    deadline = import_dt + timedelta(days=1825)  # 5 years
    now = datetime.now(timezone.utc) if import_dt.tzinfo else datetime.now()
    
    days_remaining = (deadline - now).days
    
    result = {
        "import_date": import_dt.isoformat(),
        "deadline": deadline.isoformat(),
        "days_remaining": days_remaining,
        "eligible": days_remaining > 0,
        "eligibility_expires": deadline.strftime("%Y-%m-%d"),
    }
    
    if export_date:
        try:
            export_dt = datetime.fromisoformat(export_date.replace('Z', '+00:00'))
            export_within_window = (export_dt - import_dt).days <= 1825
            result["export_within_window"] = export_within_window
        except:
            pass
    
    return result


def estimate_drawback_refund(
    duty_paid: float,
    quantity_imported: float,
    quantity_exported: float,
    match_type: str = "direct"
) -> Dict[str, Any]:
    """
    Estimate potential drawback refund.
    
    Args:
        duty_paid: Total duty paid on import
        quantity_imported: Quantity imported
        quantity_exported: Quantity exported
        match_type: "direct" or "substitution"
        
    Returns:
        Estimated refund details
    """
    # 99% refund rate for both direct and substitution
    refund_rate = 0.99
    
    # Cannot claim more than was exported/imported
    eligible_quantity = min(quantity_imported, quantity_exported)
    quantity_ratio = eligible_quantity / quantity_imported if quantity_imported > 0 else 0
    
    potential_refund = duty_paid * refund_rate * quantity_ratio
    
    return {
        "duty_paid": duty_paid,
        "quantity_imported": quantity_imported,
        "quantity_exported": quantity_exported,
        "eligible_quantity": eligible_quantity,
        "match_type": match_type,
        "refund_rate": refund_rate,
        "refund_rate_percent": refund_rate * 100,
        "quantity_ratio": round(quantity_ratio, 4),
        "potential_refund": round(potential_refund, 2),
        "retained_by_cbp": round(duty_paid * quantity_ratio * (1 - refund_rate), 2),
    }


# Create singleton-like access
class EntryReconciliationServiceFactory:
    """Factory for creating reconciliation service instances."""
    
    @staticmethod
    def create(db: AsyncSession) -> EntryReconciliationService:
        return EntryReconciliationService(db)
