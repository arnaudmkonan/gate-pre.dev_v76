"""
ACE Status Tracking Service.

Handles tracking and updating entry status from ACE/CBP.
Supports status polling, webhook processing, and rejection handling.

Task 3.4 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID
from enum import Enum

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.models.entry import Entry, EntryStatus, EntryStatusHistory


class ACEStatus(str, Enum):
    """Status values from ACE/CBP."""
    PENDING = "pending"  # Transmission pending
    SUBMITTED = "submitted"  # Sent to ACE
    RECEIVED = "received"  # ACE received
    ACCEPTED = "accepted"  # CBP accepted entry
    REJECTED = "rejected"  # CBP rejected entry
    UNDER_REVIEW = "under_review"  # CBP reviewing
    HOLD = "hold"  # CBP hold for exam
    INTENSIVE_EXAM = "intensive_exam"  # Intensive examination
    RELEASED = "released"  # Cargo released
    PENDING_LIQUIDATION = "pending_liquidation"  # Awaiting liquidation
    LIQUIDATED = "liquidated"  # Final duty determination
    SUSPENDED = "suspended"  # Liquidation suspended


class ACEMessageType(str, Enum):
    """Types of ACE messages/responses."""
    ACCEPTANCE = "acceptance"
    REJECTION = "rejection"
    RELEASE = "release"
    HOLD = "hold"
    LIQUIDATION = "liquidation"
    STATUS_UPDATE = "status_update"
    ERROR = "error"


# CBP Error codes for common rejections
CBP_ERROR_CODES = {
    "CBP-001": "Invalid Entry Number format",
    "CBP-002": "Missing required field",
    "CBP-003": "Invalid HTS code",
    "CBP-004": "HTS code requires additional quantity",
    "CBP-005": "Invalid port code",
    "CBP-006": "Invalid importer number",
    "CBP-007": "Bond not on file",
    "CBP-008": "Duplicate entry number",
    "CBP-009": "Entry date out of acceptable range",
    "CBP-010": "Invalid country of origin",
    "CBP-011": "Manufacturer ID required",
    "CBP-012": "Special program indicator invalid",
    "CBP-013": "AD/CVD case not found",
    "CBP-014": "Value does not match invoice",
    "CBP-015": "License required for this commodity",
}


class ACEStatusMessage:
    """Represents a status message from ACE."""
    
    def __init__(
        self,
        message_type: ACEMessageType,
        ace_status: ACEStatus,
        message: str,
        timestamp: datetime = None,
        error_codes: List[str] = None,
        details: Dict[str, Any] = None,
    ):
        self.message_type = message_type
        self.ace_status = ace_status
        self.message = message
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.error_codes = error_codes or []
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_type": self.message_type.value,
            "ace_status": self.ace_status.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "error_codes": self.error_codes,
            "error_descriptions": [
                CBP_ERROR_CODES.get(code, f"Unknown error: {code}")
                for code in self.error_codes
            ],
            "details": self.details,
        }


class ACEStatusService:
    """Service for tracking and managing ACE entry status."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_entry_status(self, entry_id: UUID) -> Dict[str, Any]:
        """
        Get current ACE status for an entry.
        
        Returns comprehensive status information including:
        - Current status
        - History of status changes
        - Any CBP messages
        - Rejection details if applicable
        """
        query = select(Entry).where(Entry.id == entry_id)
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        
        if not entry:
            return {"error": "Entry not found"}
        
        # Get status history
        history_query = (
            select(EntryStatusHistory)
            .where(EntryStatusHistory.entry_id == entry_id)
            .order_by(EntryStatusHistory.changed_at.desc())
        )
        history_result = await self.db.execute(history_query)
        history = history_result.scalars().all()
        
        # Build response
        return {
            "entry_id": str(entry.id),
            "entry_number": entry.entry_number,
            "entry_status": entry.status,
            "ace_status": entry.ace_status,
            "ace_entry_id": entry.ace_entry_id,
            "filed_at": entry.filed_at.isoformat() if entry.filed_at else None,
            "release_date": entry.release_date.isoformat() if entry.release_date else None,
            "liquidation_date": entry.liquidation_date.isoformat() if entry.liquidation_date else None,
            "ace_response": entry.ace_response,
            "status_history": [
                {
                    "from_status": h.from_status,
                    "to_status": h.to_status,
                    "changed_by": h.changed_by,
                    "changed_at": h.changed_at.isoformat(),
                    "reason": h.reason,
                    "ace_message": h.ace_message,
                }
                for h in history
            ],
            "can_resubmit": entry.status == EntryStatus.REJECTED.value,
            "rejection_details": self._extract_rejection_details(entry) if entry.status == EntryStatus.REJECTED.value else None,
        }
    
    def _extract_rejection_details(self, entry: Entry) -> Dict[str, Any]:
        """Extract rejection details from ACE response."""
        if not entry.ace_response:
            return None
        
        response = entry.ace_response
        error_codes = response.get("error_codes", [])
        
        return {
            "error_codes": error_codes,
            "error_messages": [
                {
                    "code": code,
                    "description": CBP_ERROR_CODES.get(code, f"Unknown error: {code}"),
                }
                for code in error_codes
            ],
            "rejected_at": response.get("timestamp"),
            "cbp_message": response.get("message", "Entry rejected by CBP"),
            "can_resubmit": True,
            "correction_hints": self._get_correction_hints(error_codes),
        }
    
    def _get_correction_hints(self, error_codes: List[str]) -> List[str]:
        """Get hints for correcting rejections based on error codes."""
        hints = []
        
        for code in error_codes:
            if code == "CBP-003":
                hints.append("Verify HTS code is valid 10-digit classification")
            elif code == "CBP-004":
                hints.append("Add secondary quantity for this HTS code")
            elif code == "CBP-006":
                hints.append("Verify importer EIN/CBP number format")
            elif code == "CBP-007":
                hints.append("Bond must be on file with CBP before filing")
            elif code == "CBP-011":
                hints.append("Add manufacturer MID for this product")
            elif code == "CBP-013":
                hints.append("Verify AD/CVD case number is correct")
            elif code == "CBP-015":
                hints.append("Apply for and include required license")
        
        return hints
    
    async def update_status(
        self,
        entry_id: UUID,
        new_ace_status: ACEStatus,
        message: ACEStatusMessage,
        changed_by: str = "ACE Sync",
    ) -> Dict[str, Any]:
        """
        Update entry status based on ACE response.
        
        Maps ACE status to internal entry status and creates history record.
        """
        query = select(Entry).where(Entry.id == entry_id)
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        
        if not entry:
            return {"error": "Entry not found"}
        
        # Store previous status
        previous_status = entry.status
        previous_ace_status = entry.ace_status
        
        # Map ACE status to internal status
        status_mapping = {
            ACEStatus.PENDING: EntryStatus.FILING,
            ACEStatus.SUBMITTED: EntryStatus.FILING,
            ACEStatus.RECEIVED: EntryStatus.FILED,
            ACEStatus.ACCEPTED: EntryStatus.ACCEPTED,
            ACEStatus.REJECTED: EntryStatus.REJECTED,
            ACEStatus.UNDER_REVIEW: EntryStatus.FILED,
            ACEStatus.HOLD: EntryStatus.HOLD,
            ACEStatus.INTENSIVE_EXAM: EntryStatus.HOLD,
            ACEStatus.RELEASED: EntryStatus.RELEASED,
            ACEStatus.PENDING_LIQUIDATION: EntryStatus.RELEASED,
            ACEStatus.LIQUIDATED: EntryStatus.LIQUIDATED,
            ACEStatus.SUSPENDED: EntryStatus.RELEASED,
        }
        
        new_internal_status = status_mapping.get(new_ace_status, EntryStatus.FILED)
        
        # Update entry
        entry.ace_status = new_ace_status.value
        entry.status = new_internal_status.value
        entry.ace_response = message.to_dict()
        
        # Set dates based on status
        if new_ace_status == ACEStatus.RELEASED:
            entry.release_date = message.timestamp
        elif new_ace_status == ACEStatus.LIQUIDATED:
            entry.liquidation_date = message.timestamp
        
        # Create history record
        history = EntryStatusHistory(
            entry_id=entry_id,
            from_status=previous_status,
            to_status=new_internal_status.value,
            changed_by=changed_by,
            reason=message.message,
            ace_message=message.to_dict(),
        )
        self.db.add(history)
        
        await self.db.commit()
        await self.db.refresh(entry)
        
        return {
            "entry_id": str(entry.id),
            "previous_status": previous_status,
            "previous_ace_status": previous_ace_status,
            "new_status": entry.status,
            "new_ace_status": entry.ace_status,
            "message": message.message,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def simulate_ace_poll(self, entry_id: UUID) -> Dict[str, Any]:
        """
        Simulate polling ACE for status update.
        
        In production, this would call the actual ACE API.
        For demo, simulates status progression.
        """
        query = select(Entry).where(Entry.id == entry_id)
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        
        if not entry:
            return {"error": "Entry not found"}
        
        # Simulate status progression
        current_ace_status = entry.ace_status
        
        status_progression = {
            None: (ACEStatus.SUBMITTED, "Entry submitted to ACE"),
            "submitted": (ACEStatus.RECEIVED, "ACE has received the entry"),
            "received": (ACEStatus.ACCEPTED, "Entry accepted by CBP"),
            "accepted": (ACEStatus.RELEASED, "Cargo released by CBP"),
            "released": (ACEStatus.LIQUIDATED, "Entry has been liquidated"),
        }
        
        if current_ace_status in status_progression:
            new_status, msg = status_progression[current_ace_status]
            message = ACEStatusMessage(
                message_type=ACEMessageType.STATUS_UPDATE,
                ace_status=new_status,
                message=msg,
            )
            return await self.update_status(entry_id, new_status, message)
        
        return {
            "entry_id": str(entry_id),
            "ace_status": current_ace_status,
            "message": "No status change available",
        }
    
    async def mark_filed(self, entry_id: UUID, ace_entry_id: str = None) -> Dict[str, Any]:
        """Mark entry as filed to CBP."""
        query = select(Entry).where(Entry.id == entry_id)
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        
        if not entry:
            return {"error": "Entry not found"}
        
        previous_status = entry.status
        
        # Update entry
        entry.status = EntryStatus.FILED.value
        entry.ace_status = ACEStatus.SUBMITTED.value
        entry.filed_at = datetime.now(timezone.utc)
        
        if ace_entry_id:
            entry.ace_entry_id = ace_entry_id
        else:
            # Generate simulated ACE entry ID
            entry.ace_entry_id = f"ACE-{entry.entry_number or ''}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create history record
        history = EntryStatusHistory(
            entry_id=entry_id,
            from_status=previous_status,
            to_status=EntryStatus.FILED.value,
            changed_by="System",
            reason=f"Entry filed to CBP with ACE ID: {entry.ace_entry_id}",
        )
        self.db.add(history)
        
        await self.db.commit()
        await self.db.refresh(entry)
        
        return {
            "entry_id": str(entry.id),
            "entry_number": entry.entry_number,
            "ace_entry_id": entry.ace_entry_id,
            "status": entry.status,
            "ace_status": entry.ace_status,
            "filed_at": entry.filed_at.isoformat(),
        }
    
    async def resubmit_entry(self, entry_id: UUID, corrections: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Resubmit a rejected entry after corrections.
        
        Resets status to READY_TO_FILE so it can be filed again.
        """
        query = select(Entry).where(Entry.id == entry_id)
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        
        if not entry:
            return {"error": "Entry not found"}
        
        if entry.status != EntryStatus.REJECTED.value:
            return {"error": "Only rejected entries can be resubmitted"}
        
        previous_status = entry.status
        
        # Reset for resubmission
        entry.status = EntryStatus.READY_TO_FILE.value
        entry.ace_status = None
        
        # Create history record
        history = EntryStatusHistory(
            entry_id=entry_id,
            from_status=previous_status,
            to_status=EntryStatus.READY_TO_FILE.value,
            changed_by="User",
            reason="Entry reset for resubmission after corrections",
            ace_message={"corrections_applied": corrections} if corrections else None,
        )
        self.db.add(history)
        
        await self.db.commit()
        await self.db.refresh(entry)
        
        return {
            "entry_id": str(entry.id),
            "status": entry.status,
            "ace_status": entry.ace_status,
            "message": "Entry reset for resubmission",
            "can_file": True,
        }
    
    async def get_entries_pending_status(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get entries that are pending ACE status updates."""
        pending_statuses = [
            EntryStatus.FILING.value,
            EntryStatus.FILED.value,
            EntryStatus.ACCEPTED.value,
        ]
        
        pending_ace_statuses = [
            ACEStatus.PENDING.value,
            ACEStatus.SUBMITTED.value,
            ACEStatus.RECEIVED.value,
            ACEStatus.UNDER_REVIEW.value,
        ]
        
        query = (
            select(Entry)
            .where(
                and_(
                    Entry.status.in_(pending_statuses),
                    Entry.ace_status.in_(pending_ace_statuses) | Entry.ace_status.is_(None)
                )
            )
            .order_by(Entry.filed_at)
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        return [
            {
                "entry_id": str(e.id),
                "entry_number": e.entry_number,
                "ace_entry_id": e.ace_entry_id,
                "status": e.status,
                "ace_status": e.ace_status,
                "filed_at": e.filed_at.isoformat() if e.filed_at else None,
            }
            for e in entries
        ]
