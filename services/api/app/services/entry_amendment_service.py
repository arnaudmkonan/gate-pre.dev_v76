"""
Entry Amendment Service.

Handles post-filing amendments (Post Summary Corrections - PSC):
- Track field changes from original filing
- Generate amendment ABI message (RM record type)
- Calculate duty differences (owe more or refund)
- Prior disclosure support for penalty mitigation
- Amendment history tracking

Task 3.5 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID, uuid4
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.models.entry import Entry, EntryLine, EntryStatusHistory, EntryStatus


class AmendmentType(str, Enum):
    """Types of amendments."""
    VALUE_CORRECTION = "value_correction"  # Change in entered value
    CLASSIFICATION = "classification"  # HTS code change
    ORIGIN = "origin"  # Country of origin change
    QUANTITY = "quantity"  # Quantity correction
    PARTY = "party"  # Importer/consignee change
    RATE = "rate"  # Duty rate correction
    FTA = "fta"  # FTA claim addition/removal
    OTHER = "other"


class AmendmentReason(str, Enum):
    """Reasons for filing amendment."""
    CLERICAL_ERROR = "clerical_error"
    INCORRECT_VALUE = "incorrect_value"
    INCORRECT_CLASSIFICATION = "incorrect_classification"
    INCORRECT_QUANTITY = "incorrect_quantity"
    NEW_INFORMATION = "new_information"
    CBP_REQUEST = "cbp_request"
    AUDIT_FINDING = "audit_finding"
    VOLUNTARY_DISCLOSURE = "voluntary_disclosure"


@dataclass
class FieldChange:
    """Represents a single field change."""
    field_name: str
    old_value: Any
    new_value: Any
    change_type: AmendmentType = AmendmentType.OTHER
    line_number: Optional[int] = None  # If line-level change
    
    def duty_impact(self) -> Optional[float]:
        """Calculate approximate duty impact of this change."""
        if self.field_name in ["entered_value", "dutiable_value"]:
            old_val = float(self.old_value or 0)
            new_val = float(self.new_value or 0)
            # Approximate impact at 5% average rate
            return (new_val - old_val) * 0.05
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "old_value": str(self.old_value) if self.old_value is not None else None,
            "new_value": str(self.new_value) if self.new_value is not None else None,
            "change_type": self.change_type.value,
            "line_number": self.line_number,
            "duty_impact": self.duty_impact(),
        }


@dataclass
class Amendment:
    """Represents a complete amendment to an entry."""
    id: str = ""
    entry_id: str = ""
    amendment_number: int = 1
    filed_at: Optional[datetime] = None
    reason: AmendmentReason = AmendmentReason.CLERICAL_ERROR
    is_prior_disclosure: bool = False
    changes: List[FieldChange] = field(default_factory=list)
    
    # Duty impact
    original_duty: float = 0
    amended_duty: float = 0
    duty_difference: float = 0  # Positive = owe more, Negative = refund
    
    # Status
    status: str = "pending"  # pending, filed, accepted, rejected
    cbp_response: Optional[Dict[str, Any]] = None
    
    # Notes
    notes: str = ""
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def calculate_duty_difference(self):
        """Calculate total duty difference from all changes."""
        self.duty_difference = self.amended_duty - self.original_duty
    
    def is_increase(self) -> bool:
        """Check if amendment increases duty."""
        return self.duty_difference > 0
    
    def is_decrease(self) -> bool:
        """Check if amendment decreases duty (potential refund)."""
        return self.duty_difference < 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "entry_id": self.entry_id,
            "amendment_number": self.amendment_number,
            "filed_at": self.filed_at.isoformat() if self.filed_at else None,
            "reason": self.reason.value,
            "is_prior_disclosure": self.is_prior_disclosure,
            "changes": [c.to_dict() for c in self.changes],
            "original_duty": self.original_duty,
            "amended_duty": self.amended_duty,
            "duty_difference": self.duty_difference,
            "duty_direction": "increase" if self.is_increase() else "decrease" if self.is_decrease() else "no_change",
            "status": self.status,
            "cbp_response": self.cbp_response,
            "notes": self.notes,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
        }


# Fields that can be amended and their types
AMENDABLE_HEADER_FIELDS = {
    "total_entered_value": AmendmentType.VALUE_CORRECTION,
    "total_dutiable_value": AmendmentType.VALUE_CORRECTION,
    "importer_of_record_number": AmendmentType.PARTY,
    "importer_of_record_name": AmendmentType.PARTY,
    "ultimate_consignee_name": AmendmentType.PARTY,
    "port_of_entry": AmendmentType.OTHER,
    "entry_type": AmendmentType.OTHER,
}

AMENDABLE_LINE_FIELDS = {
    "hts_code": AmendmentType.CLASSIFICATION,
    "country_of_origin": AmendmentType.ORIGIN,
    "entered_value": AmendmentType.VALUE_CORRECTION,
    "dutiable_value": AmendmentType.VALUE_CORRECTION,
    "quantity_1": AmendmentType.QUANTITY,
    "quantity_2": AmendmentType.QUANTITY,
    "duty_rate": AmendmentType.RATE,
    "manufacturer_mid": AmendmentType.PARTY,
    "fta_code": AmendmentType.FTA,
    "fta_eligible": AmendmentType.FTA,
}


class EntryAmendmentService:
    """Service for managing entry amendments."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def compare_entries(
        self,
        entry_id: UUID,
        proposed_changes: Dict[str, Any],
    ) -> List[FieldChange]:
        """
        Compare current entry with proposed changes.
        
        Returns list of field changes that would result from the amendment.
        """
        # Fetch current entry
        query = (
            select(Entry)
            .options(selectinload(Entry.lines))
            .where(Entry.id == entry_id)
        )
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        
        if not entry:
            raise ValueError(f"Entry {entry_id} not found")
        
        changes = []
        
        # Check header-level changes
        for field_name, change_type in AMENDABLE_HEADER_FIELDS.items():
            if field_name in proposed_changes:
                old_value = getattr(entry, field_name, None)
                new_value = proposed_changes[field_name]
                
                if self._values_differ(old_value, new_value):
                    changes.append(FieldChange(
                        field_name=field_name,
                        old_value=old_value,
                        new_value=new_value,
                        change_type=change_type,
                    ))
        
        # Check line-level changes
        if "lines" in proposed_changes:
            for line_change in proposed_changes["lines"]:
                line_number = line_change.get("line_number")
                if not line_number:
                    continue
                
                # Find matching line
                current_line = next(
                    (l for l in entry.lines if l.line_number == line_number),
                    None
                )
                
                if not current_line:
                    # New line being added
                    for field_name in AMENDABLE_LINE_FIELDS:
                        if field_name in line_change:
                            changes.append(FieldChange(
                                field_name=field_name,
                                old_value=None,
                                new_value=line_change[field_name],
                                change_type=AMENDABLE_LINE_FIELDS[field_name],
                                line_number=line_number,
                            ))
                else:
                    # Existing line being modified
                    for field_name, change_type in AMENDABLE_LINE_FIELDS.items():
                        if field_name in line_change:
                            old_value = getattr(current_line, field_name, None)
                            new_value = line_change[field_name]
                            
                            if self._values_differ(old_value, new_value):
                                changes.append(FieldChange(
                                    field_name=field_name,
                                    old_value=old_value,
                                    new_value=new_value,
                                    change_type=change_type,
                                    line_number=line_number,
                                ))
        
        return changes
    
    def _values_differ(self, old_value: Any, new_value: Any) -> bool:
        """Check if two values are meaningfully different."""
        # Handle None cases
        if old_value is None and new_value is None:
            return False
        if old_value is None or new_value is None:
            return True
        
        # Normalize numeric values
        try:
            if isinstance(old_value, (int, float, Decimal)):
                old_float = float(old_value)
                new_float = float(new_value)
                return abs(old_float - new_float) > 0.001
        except (TypeError, ValueError):
            pass
        
        # String comparison
        return str(old_value).strip() != str(new_value).strip()
    
    async def create_amendment(
        self,
        entry_id: UUID,
        changes: List[Dict[str, Any]],
        reason: str = "clerical_error",
        is_prior_disclosure: bool = False,
        notes: str = "",
        created_by: str = "system",
    ) -> Amendment:
        """
        Create an amendment for an entry.
        
        Args:
            entry_id: Entry to amend
            changes: List of field changes (can be raw dict or FieldChange)
            reason: Amendment reason code
            is_prior_disclosure: True if prior disclosure for penalty mitigation
            notes: Free-text notes
            created_by: User who created amendment
            
        Returns:
            Amendment object with all changes and duty calculations
        """
        # Fetch current entry
        query = (
            select(Entry)
            .options(selectinload(Entry.lines))
            .where(Entry.id == entry_id)
        )
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        
        if not entry:
            raise ValueError(f"Entry {entry_id} not found")
        
        # Can only amend filed/accepted/released entries
        amendable_statuses = [
            EntryStatus.FILED.value,
            EntryStatus.ACCEPTED.value,
            EntryStatus.RELEASED.value,
        ]
        if entry.status not in amendable_statuses:
            raise ValueError(
                f"Cannot amend entry with status '{entry.status}'. "
                f"Entry must be filed, accepted, or released."
            )
        
        # Convert changes to FieldChange objects
        field_changes = []
        for change in changes:
            if isinstance(change, FieldChange):
                field_changes.append(change)
            elif isinstance(change, dict):
                field_changes.append(FieldChange(
                    field_name=change.get("field", change.get("field_name", "")),
                    old_value=change.get("old", change.get("old_value")),
                    new_value=change.get("new", change.get("new_value")),
                    change_type=AmendmentType(change.get("change_type", "other")),
                    line_number=change.get("line_number"),
                ))
        
        # Create amendment
        amendment = Amendment(
            id=str(uuid4()),
            entry_id=str(entry_id),
            amendment_number=self._get_next_amendment_number(entry),
            reason=AmendmentReason(reason),
            is_prior_disclosure=is_prior_disclosure,
            changes=field_changes,
            original_duty=float(entry.total_amount_due or 0),
            notes=notes,
            created_by=created_by,
        )
        
        # Calculate new duty (we'll simulate this)
        amended_duty = await self._calculate_amended_duty(entry, field_changes)
        amendment.amended_duty = amended_duty
        amendment.calculate_duty_difference()
        
        return amendment
    
    def _get_next_amendment_number(self, entry: Entry) -> int:
        """Get next amendment number for entry."""
        # In production, would query amendments table
        # For now, use a simple counter
        return 1
    
    async def _calculate_amended_duty(
        self,
        entry: Entry,
        changes: List[FieldChange],
    ) -> float:
        """
        Calculate new total duty after applying changes.
        
        This is a simplified calculation. In production, would need
        full recalculation through duty calculation service.
        """
        current_duty = float(entry.total_amount_due or 0)
        
        for change in changes:
            if change.field_name in ["entered_value", "dutiable_value"]:
                # Value change affects duty proportionally
                old_val = float(change.old_value or 0)
                new_val = float(change.new_value or 0)
                
                if old_val > 0:
                    # Estimate duty change based on ratio
                    ratio = new_val / old_val
                    current_duty = current_duty * ratio
            
            elif change.field_name == "duty_rate":
                # Rate change directly affects duty
                old_rate = float(change.old_value or 0)
                new_rate = float(change.new_value or 0)
                
                # Find the value for this line
                if change.line_number:
                    line = next(
                        (l for l in entry.lines if l.line_number == change.line_number),
                        None
                    )
                    if line:
                        line_value = float(line.dutiable_value or line.entered_value or 0)
                        old_duty = line_value * (old_rate / 100)
                        new_duty = line_value * (new_rate / 100)
                        current_duty = current_duty - old_duty + new_duty
        
        return round(current_duty, 2)
    
    async def apply_amendment(
        self,
        entry_id: UUID,
        amendment: Amendment,
    ) -> Dict[str, Any]:
        """
        Apply amendment changes to entry.
        
        Updates entry fields and recalculates duties.
        Creates status history record.
        """
        # Fetch entry
        query = (
            select(Entry)
            .options(selectinload(Entry.lines))
            .where(Entry.id == entry_id)
        )
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        
        if not entry:
            raise ValueError(f"Entry {entry_id} not found")
        
        # Apply header changes
        for change in amendment.changes:
            if change.line_number is None:
                # Header field
                if hasattr(entry, change.field_name):
                    setattr(entry, change.field_name, change.new_value)
            else:
                # Line field
                line = next(
                    (l for l in entry.lines if l.line_number == change.line_number),
                    None
                )
                if line and hasattr(line, change.field_name):
                    setattr(line, change.field_name, change.new_value)
        
        # Store amendment in ace_response
        if not entry.ace_response:
            entry.ace_response = {}
        
        if "amendments" not in entry.ace_response:
            entry.ace_response["amendments"] = []
        
        entry.ace_response["amendments"].append(amendment.to_dict())
        entry.ace_response["last_amendment"] = amendment.to_dict()
        
        # Create status history
        history = EntryStatusHistory(
            entry_id=entry_id,
            from_status=entry.status,
            to_status=entry.status,  # Status doesn't change on amendment
            changed_by=amendment.created_by,
            reason=f"Amendment #{amendment.amendment_number}: {amendment.reason.value}",
            ace_message={
                "amendment_id": amendment.id,
                "duty_difference": amendment.duty_difference,
                "is_prior_disclosure": amendment.is_prior_disclosure,
                "changes_count": len(amendment.changes),
            },
        )
        self.db.add(history)
        
        await self.db.commit()
        await self.db.refresh(entry)
        
        return {
            "entry_id": str(entry_id),
            "amendment": amendment.to_dict(),
            "entry_updated": True,
            "new_total_duty": amendment.amended_duty,
            "duty_difference": amendment.duty_difference,
            "message": (
                f"Amendment applied. Duty {'increased' if amendment.is_increase() else 'decreased'} "
                f"by ${abs(amendment.duty_difference):.2f}."
                if amendment.duty_difference != 0
                else "Amendment applied. No change in duty."
            ),
        }
    
    async def generate_amendment_abi(
        self,
        entry_id: UUID,
        amendment: Amendment,
    ) -> Dict[str, Any]:
        """
        Generate ABI RM (Replace/Modify) message for amendment.
        
        Uses the existing ABI generator with RM message type.
        """
        from app.services.abi_generator import generate_abi_message
        
        # Generate RM message
        abi_message = await generate_abi_message(
            self.db,
            str(entry_id),
            message_type="RM",  # Replace/Modify
        )
        
        return {
            "amendment_id": amendment.id,
            "entry_id": str(entry_id),
            "message_type": "RM",
            "abi_message": abi_message.to_dict(),
            "abi_content": abi_message.to_abi_string(),
            "validation": {
                "is_valid": len(abi_message.validation_errors) == 0,
                "errors": abi_message.validation_errors,
                "warnings": abi_message.validation_warnings,
            },
        }
    
    async def get_amendment_history(self, entry_id: UUID) -> List[Dict[str, Any]]:
        """Get all amendments for an entry."""
        query = (
            select(Entry)
            .options(selectinload(Entry.status_history))
            .where(Entry.id == entry_id)
        )
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        
        if not entry:
            return []
        
        # Get amendments from ace_response
        amendments = []
        if entry.ace_response and "amendments" in entry.ace_response:
            amendments = entry.ace_response["amendments"]
        
        return amendments


# ==================== Convenience Functions ====================

async def preview_amendment(
    db: AsyncSession,
    entry_id: str,
    proposed_changes: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Preview what an amendment would look like without applying it.
    
    Returns:
        Dictionary with changes, duty impact, and validation
    """
    service = EntryAmendmentService(db)
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        return {"error": "Invalid entry ID"}
    
    # Get changes
    changes = await service.compare_entries(entry_uuid, proposed_changes)
    
    if not changes:
        return {
            "entry_id": entry_id,
            "changes": [],
            "has_changes": False,
            "message": "No differences found between current entry and proposed changes",
        }
    
    # Calculate duty impact
    total_duty_impact = sum(c.duty_impact() or 0 for c in changes)
    
    # Group by type
    changes_by_type = {}
    for change in changes:
        type_name = change.change_type.value
        if type_name not in changes_by_type:
            changes_by_type[type_name] = []
        changes_by_type[type_name].append(change.to_dict())
    
    return {
        "entry_id": entry_id,
        "has_changes": True,
        "total_changes": len(changes),
        "changes": [c.to_dict() for c in changes],
        "changes_by_type": changes_by_type,
        "estimated_duty_impact": total_duty_impact,
        "requires_prior_disclosure": any(
            c.change_type == AmendmentType.VALUE_CORRECTION and 
            c.duty_impact() and c.duty_impact() > 1000
            for c in changes
        ),
    }
