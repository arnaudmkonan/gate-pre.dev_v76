"""
Entry Lifecycle Models.

Models for tracking entry lifecycle events:
- Liquidation tracking
- Protests and petitions
- Reconciliation entries
- Drawback claims
- Prior disclosures

Phase 6 from ROADMAP_FULL_WORKFLOW.md
"""
from enum import Enum
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import Column, String, DateTime, Date, ForeignKey, Integer, Text, Boolean, Index, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from app.models.base import BaseModel


# ==================== Liquidation Tracking (Task 6.1) ====================

class LiquidationStatus(str, Enum):
    """Entry liquidation status."""
    PENDING = "pending"  # Not yet liquidated
    EXTENDED = "extended"  # Extension granted
    SUSPENDED = "suspended"  # Suspended (e.g., legal hold)
    LIQUIDATED = "liquidated"  # Liquidated by CBP
    PROTESTED = "protested"  # Protest filed


class EntryLiquidation(BaseModel):
    """
    Liquidation tracking for an entry.
    
    CBP has 314 days from entry date to liquidate.
    """
    __tablename__ = "entry_liquidations"
    
    entry_id = Column(UUID(as_uuid=True), ForeignKey("entries.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Status
    status = Column(String(30), default=LiquidationStatus.PENDING.value, nullable=False)
    
    # Dates
    entry_date = Column(Date, nullable=False)  # Copy from entry for easy calculation
    original_deadline = Column(Date, nullable=False)  # 314 days from entry
    current_deadline = Column(Date, nullable=False)  # With extensions
    liquidation_date = Column(Date, nullable=True)  # Actual liquidation date
    
    # Extensions
    extension_days = Column(Integer, default=0, nullable=False)
    extension_reason = Column(Text, nullable=True)
    extension_granted_date = Column(Date, nullable=True)
    
    # Liquidated amounts
    estimated_duty = Column(Numeric(15, 2), nullable=True)  # Duty at entry
    liquidated_duty = Column(Numeric(15, 2), nullable=True)  # Final duty
    duty_difference = Column(Numeric(15, 2), nullable=True)  # + = owed, - = refund
    
    # Interest
    interest_owed = Column(Numeric(15, 2), nullable=True)
    
    # CBP reference
    cbp_liquidation_code = Column(String(20), nullable=True)
    cbp_notice_date = Column(Date, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Relationships
    entry = relationship("Entry", foreign_keys=[entry_id])
    
    __table_args__ = (
        Index("ix_entry_liquidations_entry", "entry_id"),
        Index("ix_entry_liquidations_status", "status"),
        Index("ix_entry_liquidations_deadline", "current_deadline"),
    )
    
    @property
    def days_until_deadline(self) -> Optional[int]:
        if not self.current_deadline:
            return None
        return (self.current_deadline - date.today()).days
    
    @property
    def is_overdue(self) -> bool:
        if self.status == LiquidationStatus.LIQUIDATED.value:
            return False
        return self.days_until_deadline is not None and self.days_until_deadline < 0
    
    @property
    def is_approaching(self) -> bool:
        """Within 30 days of deadline."""
        days = self.days_until_deadline
        return days is not None and 0 <= days <= 30
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "entry_id": str(self.entry_id),
            "status": self.status,
            "entry_date": self.entry_date.isoformat() if self.entry_date else None,
            "original_deadline": self.original_deadline.isoformat() if self.original_deadline else None,
            "current_deadline": self.current_deadline.isoformat() if self.current_deadline else None,
            "liquidation_date": self.liquidation_date.isoformat() if self.liquidation_date else None,
            "extension_days": self.extension_days,
            "extension_reason": self.extension_reason,
            "estimated_duty": float(self.estimated_duty) if self.estimated_duty else None,
            "liquidated_duty": float(self.liquidated_duty) if self.liquidated_duty else None,
            "duty_difference": float(self.duty_difference) if self.duty_difference else None,
            "interest_owed": float(self.interest_owed) if self.interest_owed else None,
            "days_until_deadline": self.days_until_deadline,
            "is_overdue": self.is_overdue,
            "is_approaching": self.is_approaching,
        }


# ==================== Protest Tracking (Task 6.2) ====================

class ProtestStatus(str, Enum):
    """Protest status."""
    DRAFT = "draft"
    FILED = "filed"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"  # Protest granted
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    ESCALATED = "escalated"  # To Court of Int'l Trade


class EntryProtest(BaseModel):
    """
    Protest against CBP liquidation decision.
    
    180 days from liquidation to file protest.
    """
    __tablename__ = "entry_protests"
    
    entry_id = Column(UUID(as_uuid=True), ForeignKey("entries.id", ondelete="CASCADE"), nullable=False)
    liquidation_id = Column(UUID(as_uuid=True), ForeignKey("entry_liquidations.id"), nullable=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    
    # Protest identification
    protest_number = Column(String(50), nullable=True, unique=True, index=True)
    
    # Status and dates
    status = Column(String(30), default=ProtestStatus.DRAFT.value, nullable=False)
    liquidation_date = Column(Date, nullable=False)
    filing_deadline = Column(Date, nullable=False)  # 180 days from liquidation
    filed_date = Column(Date, nullable=True)
    decision_date = Column(Date, nullable=True)
    
    # Protest details
    protest_category = Column(String(50), nullable=True)  # classification, value, origin, etc.
    protest_reason = Column(Text, nullable=False)
    legal_basis = Column(Text, nullable=True)
    
    # Amounts
    duty_contested = Column(Numeric(15, 2), nullable=True)
    refund_requested = Column(Numeric(15, 2), nullable=True)
    refund_granted = Column(Numeric(15, 2), nullable=True)
    
    # Decision
    decision = Column(String(30), nullable=True)  # approved, denied, partial
    decision_reason = Column(Text, nullable=True)
    
    # Escalation
    escalated_to_cit = Column(Boolean, default=False, nullable=False)
    cit_case_number = Column(String(50), nullable=True)
    cit_filing_date = Column(Date, nullable=True)
    
    # Documents
    supporting_documents = Column(ARRAY(String), nullable=True, default=[])
    
    notes = Column(Text, nullable=True)
    
    # Relationships
    entry = relationship("Entry", foreign_keys=[entry_id])
    liquidation = relationship("EntryLiquidation", foreign_keys=[liquidation_id])
    client = relationship("Client", foreign_keys=[client_id])
    
    __table_args__ = (
        Index("ix_entry_protests_entry", "entry_id"),
        Index("ix_entry_protests_client", "client_id"),
        Index("ix_entry_protests_status", "status"),
        Index("ix_entry_protests_deadline", "filing_deadline"),
    )
    
    @property
    def days_until_deadline(self) -> Optional[int]:
        if not self.filing_deadline or self.filed_date:
            return None
        return (self.filing_deadline - date.today()).days
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "entry_id": str(self.entry_id),
            "client_id": str(self.client_id),
            "protest_number": self.protest_number,
            "status": self.status,
            "liquidation_date": self.liquidation_date.isoformat() if self.liquidation_date else None,
            "filing_deadline": self.filing_deadline.isoformat() if self.filing_deadline else None,
            "filed_date": self.filed_date.isoformat() if self.filed_date else None,
            "protest_category": self.protest_category,
            "protest_reason": self.protest_reason,
            "duty_contested": float(self.duty_contested) if self.duty_contested else None,
            "refund_requested": float(self.refund_requested) if self.refund_requested else None,
            "decision": self.decision,
            "days_until_deadline": self.days_until_deadline,
        }


# ==================== Reconciliation Entries (Task 6.3) ====================

class ReconciliationStatus(str, Enum):
    """Reconciliation status."""
    FLAGGED = "flagged"  # Entry flagged for recon
    PENDING = "pending"  # Awaiting reconciliation entry
    FILED = "filed"  # Recon entry filed
    LIQUIDATED = "liquidated"


class ReconFlagType(str, Enum):
    """What is being reconciled."""
    VALUE = "value"  # Transaction value
    CLASSIFICATION = "classification"  # HTS classification
    RATE = "rate"  # Duty rate
    QUANTITY = "quantity"
    OTHER = "other"


class ReconciliationEntry(BaseModel):
    """
    Reconciliation program entry.
    
    Allows importers to file with estimated info and reconcile later.
    21-month deadline from date of first flagged entry.
    """
    __tablename__ = "reconciliation_entries"
    
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    
    # Reconciliation identification
    recon_entry_number = Column(String(30), nullable=True, unique=True, index=True)
    
    # Status
    status = Column(String(30), default=ReconciliationStatus.FLAGGED.value, nullable=False)
    
    # What's being reconciled
    flag_types = Column(ARRAY(String), nullable=False, default=[])  # value, classification, etc.
    
    # Linked entries
    flagged_entry_ids = Column(ARRAY(String), nullable=False, default=[])  # UUIDs of flagged entries
    entry_count = Column(Integer, default=0, nullable=False)
    
    # Dates
    first_entry_date = Column(Date, nullable=False)
    filing_deadline = Column(Date, nullable=False)  # 21 months from first entry
    filed_date = Column(Date, nullable=True)
    liquidation_date = Column(Date, nullable=True)
    
    # Original vs final values
    original_total_value = Column(Numeric(15, 2), nullable=True)
    final_total_value = Column(Numeric(15, 2), nullable=True)
    original_total_duty = Column(Numeric(15, 2), nullable=True)
    final_total_duty = Column(Numeric(15, 2), nullable=True)
    duty_difference = Column(Numeric(15, 2), nullable=True)
    
    # Interest
    interest_owed = Column(Numeric(15, 2), nullable=True)
    
    notes = Column(Text, nullable=True)
    
    # Relationships
    client = relationship("Client", foreign_keys=[client_id])
    
    __table_args__ = (
        Index("ix_reconciliation_entries_client", "client_id"),
        Index("ix_reconciliation_entries_status", "status"),
        Index("ix_reconciliation_entries_deadline", "filing_deadline"),
    )
    
    @property
    def days_until_deadline(self) -> Optional[int]:
        if not self.filing_deadline or self.filed_date:
            return None
        return (self.filing_deadline - date.today()).days
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "client_id": str(self.client_id),
            "recon_entry_number": self.recon_entry_number,
            "status": self.status,
            "flag_types": self.flag_types,
            "entry_count": self.entry_count,
            "first_entry_date": self.first_entry_date.isoformat() if self.first_entry_date else None,
            "filing_deadline": self.filing_deadline.isoformat() if self.filing_deadline else None,
            "filed_date": self.filed_date.isoformat() if self.filed_date else None,
            "original_total_duty": float(self.original_total_duty) if self.original_total_duty else None,
            "final_total_duty": float(self.final_total_duty) if self.final_total_duty else None,
            "duty_difference": float(self.duty_difference) if self.duty_difference else None,
            "days_until_deadline": self.days_until_deadline,
        }


# ==================== Drawback Claims (Task 6.4) ====================

class DrawbackStatus(str, Enum):
    """Drawback claim status."""
    ELIGIBLE = "eligible"  # Marked for potential drawback
    PENDING = "pending"  # Claim preparation
    FILED = "filed"  # Claim filed
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    DENIED = "denied"
    PAID = "paid"


class DrawbackType(str, Enum):
    """Type of drawback claim."""
    MANUFACTURING = "manufacturing"  # Manufactured goods exported
    UNUSED = "unused"  # Goods exported without use
    REJECTED = "rejected"  # Goods rejected and returned
    DESTROYED = "destroyed"  # Goods destroyed under supervision


class DrawbackClaim(BaseModel):
    """
    Duty drawback claim.
    
    Up to 99% of duties can be refunded when imported goods are
    exported or destroyed.
    """
    __tablename__ = "drawback_claims"
    
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    
    # Claim identification
    claim_number = Column(String(50), nullable=True, unique=True, index=True)
    drawback_type = Column(String(30), nullable=False)
    
    # Status
    status = Column(String(30), default=DrawbackStatus.ELIGIBLE.value, nullable=False)
    
    # Import entries linked to this claim
    import_entry_ids = Column(ARRAY(String), nullable=False, default=[])
    import_entry_count = Column(Integer, default=0, nullable=False)
    
    # Export/destruction info
    export_date = Column(Date, nullable=True)
    export_reference = Column(String(100), nullable=True)  # Export entry number
    destruction_date = Column(Date, nullable=True)
    destruction_location = Column(String(200), nullable=True)
    cbp_witnessed = Column(Boolean, default=False, nullable=False)  # CBP witnessed destruction
    
    # Filing
    filing_deadline = Column(Date, nullable=True)  # 5 years from import
    filed_date = Column(Date, nullable=True)
    decision_date = Column(Date, nullable=True)
    
    # Amounts
    total_duty_paid = Column(Numeric(15, 2), nullable=True)  # Original duty paid
    drawback_rate = Column(Numeric(5, 2), default=99.0, nullable=False)  # Usually 99%
    drawback_requested = Column(Numeric(15, 2), nullable=True)  # Amount claimed
    drawback_approved = Column(Numeric(15, 2), nullable=True)  # Amount approved
    drawback_paid = Column(Numeric(15, 2), nullable=True)  # Amount received
    
    # Decision
    decision = Column(String(30), nullable=True)
    denial_reason = Column(Text, nullable=True)
    
    notes = Column(Text, nullable=True)
    
    # Relationships
    client = relationship("Client", foreign_keys=[client_id])
    
    __table_args__ = (
        Index("ix_drawback_claims_client", "client_id"),
        Index("ix_drawback_claims_status", "status"),
        Index("ix_drawback_claims_type", "drawback_type"),
    )
    
    @property
    def potential_drawback(self) -> Optional[Decimal]:
        if self.total_duty_paid and self.drawback_rate:
            return self.total_duty_paid * (self.drawback_rate / 100)
        return None
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "client_id": str(self.client_id),
            "claim_number": self.claim_number,
            "drawback_type": self.drawback_type,
            "status": self.status,
            "import_entry_count": self.import_entry_count,
            "export_date": self.export_date.isoformat() if self.export_date else None,
            "total_duty_paid": float(self.total_duty_paid) if self.total_duty_paid else None,
            "drawback_rate": float(self.drawback_rate) if self.drawback_rate else None,
            "drawback_requested": float(self.drawback_requested) if self.drawback_requested else None,
            "potential_drawback": float(self.potential_drawback) if self.potential_drawback else None,
            "decision": self.decision,
        }


# ==================== Prior Disclosure (Task 6.5) ====================

class DisclosureStatus(str, Enum):
    """Prior disclosure status."""
    DRAFT = "draft"
    FILED = "filed"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    CLOSED = "closed"


class PriorDisclosure(BaseModel):
    """
    Voluntary prior disclosure to CBP.
    
    Reduces penalties when importer discovers compliance issues.
    """
    __tablename__ = "prior_disclosures"
    
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    
    # Disclosure identification
    disclosure_number = Column(String(50), nullable=True, unique=True, index=True)
    
    # Status
    status = Column(String(30), default=DisclosureStatus.DRAFT.value, nullable=False)
    
    # Issue description
    violation_type = Column(String(100), nullable=False)  # e.g., "Incorrect classification"
    description = Column(Text, nullable=False)
    discovery_date = Column(Date, nullable=False)  # When issue was discovered
    
    # Affected entries
    affected_entry_ids = Column(ARRAY(String), nullable=False, default=[])
    entry_count = Column(Integer, default=0, nullable=False)
    period_start = Column(Date, nullable=True)  # Earliest affected entry
    period_end = Column(Date, nullable=True)  # Latest affected entry
    
    # Duty calculation
    original_duty_declared = Column(Numeric(15, 2), nullable=True)
    correct_duty_amount = Column(Numeric(15, 2), nullable=True)
    duty_loss = Column(Numeric(15, 2), nullable=True)  # Underpaid amount
    
    # Interest
    interest_owed = Column(Numeric(15, 2), nullable=True)
    
    # Penalty calculation
    max_penalty = Column(Numeric(15, 2), nullable=True)  # Could be 4x duty loss
    mitigated_penalty = Column(Numeric(15, 2), nullable=True)  # With prior disclosure
    penalty_savings = Column(Numeric(15, 2), nullable=True)  # Savings from disclosure
    
    # Filing
    filed_date = Column(Date, nullable=True)
    cbp_receipt_date = Column(Date, nullable=True)
    
    # Resolution
    resolution_date = Column(Date, nullable=True)
    final_duty_owed = Column(Numeric(15, 2), nullable=True)
    final_penalty = Column(Numeric(15, 2), nullable=True)
    total_payment = Column(Numeric(15, 2), nullable=True)
    payment_date = Column(Date, nullable=True)
    
    notes = Column(Text, nullable=True)
    
    # Relationships
    client = relationship("Client", foreign_keys=[client_id])
    
    __table_args__ = (
        Index("ix_prior_disclosures_client", "client_id"),
        Index("ix_prior_disclosures_status", "status"),
    )
    
    def calculate_penalty_savings(self):
        """Calculate penalty savings from prior disclosure."""
        if self.duty_loss:
            # Max penalty is typically 2-4x duty loss for negligence/fraud
            self.max_penalty = self.duty_loss * Decimal("4.0")
            # Prior disclosure typically reduces to interest + duty only
            self.mitigated_penalty = Decimal("0")  # Often waived with prior disclosure
            self.penalty_savings = self.max_penalty - (self.mitigated_penalty or Decimal("0"))
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "client_id": str(self.client_id),
            "disclosure_number": self.disclosure_number,
            "status": self.status,
            "violation_type": self.violation_type,
            "description": self.description,
            "entry_count": self.entry_count,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "duty_loss": float(self.duty_loss) if self.duty_loss else None,
            "max_penalty": float(self.max_penalty) if self.max_penalty else None,
            "mitigated_penalty": float(self.mitigated_penalty) if self.mitigated_penalty else None,
            "penalty_savings": float(self.penalty_savings) if self.penalty_savings else None,
            "total_payment": float(self.total_payment) if self.total_payment else None,
            "filed_date": self.filed_date.isoformat() if self.filed_date else None,
        }
