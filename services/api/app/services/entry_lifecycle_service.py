"""
Entry Lifecycle Service.

Manages entry lifecycle events:
- Liquidation tracking
- Protests and petitions
- Reconciliation entries
- Drawback claims
- Prior disclosures

Phase 6 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entry_lifecycle import (
    EntryLiquidation, LiquidationStatus,
    EntryProtest, ProtestStatus,
    ReconciliationEntry, ReconciliationStatus, ReconFlagType,
    DrawbackClaim, DrawbackStatus, DrawbackType,
    PriorDisclosure, DisclosureStatus
)
from app.models.entry import Entry


# Standard deadlines in days
LIQUIDATION_DEADLINE_DAYS = 314
PROTEST_DEADLINE_DAYS = 180
RECONCILIATION_DEADLINE_MONTHS = 21
DRAWBACK_DEADLINE_YEARS = 5


class LiquidationService:
    """Service for tracking entry liquidation."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_liquidation_tracking(
        self,
        entry_id: UUID,
        entry_date: date,
        estimated_duty: Optional[Decimal] = None,
    ) -> EntryLiquidation:
        """Create liquidation tracking for an entry."""
        # Calculate deadline (314 days)
        deadline = entry_date + timedelta(days=LIQUIDATION_DEADLINE_DAYS)
        
        liquidation = EntryLiquidation(
            entry_id=entry_id,
            status=LiquidationStatus.PENDING.value,
            entry_date=entry_date,
            original_deadline=deadline,
            current_deadline=deadline,
            estimated_duty=estimated_duty,
        )
        
        self.db.add(liquidation)
        await self.db.commit()
        await self.db.refresh(liquidation)
        
        return liquidation
    
    async def get_liquidation(self, entry_id: UUID) -> Optional[EntryLiquidation]:
        """Get liquidation tracking for entry."""
        query = select(EntryLiquidation).where(EntryLiquidation.entry_id == entry_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def extend_deadline(
        self,
        entry_id: UUID,
        extension_days: int,
        reason: str,
    ) -> EntryLiquidation:
        """Extend liquidation deadline."""
        liquidation = await self.get_liquidation(entry_id)
        if not liquidation:
            raise ValueError(f"No liquidation tracking for entry {entry_id}")
        
        liquidation.extension_days += extension_days
        liquidation.current_deadline = liquidation.original_deadline + timedelta(days=liquidation.extension_days)
        liquidation.extension_reason = reason
        liquidation.extension_granted_date = date.today()
        liquidation.status = LiquidationStatus.EXTENDED.value
        
        await self.db.commit()
        await self.db.refresh(liquidation)
        
        return liquidation
    
    async def record_liquidation(
        self,
        entry_id: UUID,
        liquidation_date: date,
        liquidated_duty: Decimal,
        cbp_code: Optional[str] = None,
    ) -> EntryLiquidation:
        """Record that an entry has been liquidated."""
        liquidation = await self.get_liquidation(entry_id)
        if not liquidation:
            raise ValueError(f"No liquidation tracking for entry {entry_id}")
        
        liquidation.status = LiquidationStatus.LIQUIDATED.value
        liquidation.liquidation_date = liquidation_date
        liquidation.liquidated_duty = liquidated_duty
        liquidation.cbp_liquidation_code = cbp_code
        liquidation.cbp_notice_date = date.today()
        
        # Calculate difference
        if liquidation.estimated_duty:
            liquidation.duty_difference = liquidated_duty - liquidation.estimated_duty
        
        await self.db.commit()
        await self.db.refresh(liquidation)
        
        return liquidation
    
    async def get_approaching_deadlines(
        self,
        days_ahead: int = 30,
        client_id: Optional[UUID] = None,
    ) -> List[EntryLiquidation]:
        """Get entries approaching liquidation deadline."""
        deadline = date.today() + timedelta(days=days_ahead)
        
        query = (
            select(EntryLiquidation)
            .options(selectinload(EntryLiquidation.entry))
            .where(
                and_(
                    EntryLiquidation.status.in_([
                        LiquidationStatus.PENDING.value,
                        LiquidationStatus.EXTENDED.value,
                    ]),
                    EntryLiquidation.current_deadline <= deadline,
                )
            )
            .order_by(EntryLiquidation.current_deadline)
        )
        
        if client_id:
            query = query.join(Entry).where(Entry.client_id == client_id)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_refunds_owed(
        self,
        client_id: Optional[UUID] = None,
    ) -> List[EntryLiquidation]:
        """Get entries where refund is owed (negative duty difference)."""
        query = (
            select(EntryLiquidation)
            .options(selectinload(EntryLiquidation.entry))
            .where(
                and_(
                    EntryLiquidation.status == LiquidationStatus.LIQUIDATED.value,
                    EntryLiquidation.duty_difference < 0,
                )
            )
        )
        
        if client_id:
            query = query.join(Entry).where(Entry.client_id == client_id)
        
        result = await self.db.execute(query)
        return result.scalars().all()


class ProtestService:
    """Service for managing protests."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_protest(
        self,
        entry_id: UUID,
        client_id: UUID,
        liquidation_date: date,
        protest_category: str,
        protest_reason: str,
        duty_contested: Optional[Decimal] = None,
        refund_requested: Optional[Decimal] = None,
    ) -> EntryProtest:
        """Create a protest for an entry."""
        # Calculate 180-day deadline
        deadline = liquidation_date + timedelta(days=PROTEST_DEADLINE_DAYS)
        
        # Get liquidation record if exists
        liq_query = select(EntryLiquidation).where(EntryLiquidation.entry_id == entry_id)
        liq_result = await self.db.execute(liq_query)
        liquidation = liq_result.scalar_one_or_none()
        
        protest = EntryProtest(
            entry_id=entry_id,
            client_id=client_id,
            liquidation_id=liquidation.id if liquidation else None,
            status=ProtestStatus.DRAFT.value,
            liquidation_date=liquidation_date,
            filing_deadline=deadline,
            protest_category=protest_category,
            protest_reason=protest_reason,
            duty_contested=duty_contested,
            refund_requested=refund_requested,
        )
        
        self.db.add(protest)
        
        # Mark liquidation as protested
        if liquidation:
            liquidation.status = LiquidationStatus.PROTESTED.value
        
        await self.db.commit()
        await self.db.refresh(protest)
        
        return protest
    
    async def get_protest(self, protest_id: UUID) -> Optional[EntryProtest]:
        """Get protest by ID."""
        query = select(EntryProtest).where(EntryProtest.id == protest_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def file_protest(
        self,
        protest_id: UUID,
        protest_number: str,
    ) -> EntryProtest:
        """Mark protest as filed."""
        protest = await self.get_protest(protest_id)
        if not protest:
            raise ValueError(f"Protest {protest_id} not found")
        
        protest.status = ProtestStatus.FILED.value
        protest.filed_date = date.today()
        protest.protest_number = protest_number
        
        await self.db.commit()
        await self.db.refresh(protest)
        
        return protest
    
    async def record_decision(
        self,
        protest_id: UUID,
        decision: str,  # approved, denied, partial
        refund_granted: Optional[Decimal] = None,
        decision_reason: Optional[str] = None,
    ) -> EntryProtest:
        """Record protest decision."""
        protest = await self.get_protest(protest_id)
        if not protest:
            raise ValueError(f"Protest {protest_id} not found")
        
        protest.status = ProtestStatus.APPROVED.value if decision == "approved" else ProtestStatus.DENIED.value
        protest.decision = decision
        protest.decision_date = date.today()
        protest.refund_granted = refund_granted
        protest.decision_reason = decision_reason
        
        await self.db.commit()
        await self.db.refresh(protest)
        
        return protest
    
    async def escalate_to_cit(
        self,
        protest_id: UUID,
        cit_case_number: str,
    ) -> EntryProtest:
        """Escalate protest to Court of International Trade."""
        protest = await self.get_protest(protest_id)
        if not protest:
            raise ValueError(f"Protest {protest_id} not found")
        
        protest.status = ProtestStatus.ESCALATED.value
        protest.escalated_to_cit = True
        protest.cit_case_number = cit_case_number
        protest.cit_filing_date = date.today()
        
        await self.db.commit()
        await self.db.refresh(protest)
        
        return protest
    
    async def list_protests(
        self,
        client_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> List[EntryProtest]:
        """List protests."""
        query = select(EntryProtest)
        
        if client_id:
            query = query.where(EntryProtest.client_id == client_id)
        
        if status:
            query = query.where(EntryProtest.status == status)
        
        query = query.order_by(EntryProtest.filing_deadline)
        
        result = await self.db.execute(query)
        return result.scalars().all()


class ReconciliationService:
    """Service for reconciliation entries."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_reconciliation(
        self,
        client_id: UUID,
        flag_types: List[str],
        flagged_entry_ids: List[str],
        first_entry_date: date,
        original_duty: Optional[Decimal] = None,
    ) -> ReconciliationEntry:
        """Create a reconciliation entry group."""
        # 21 months from first entry
        deadline = first_entry_date + timedelta(days=RECONCILIATION_DEADLINE_MONTHS * 30)
        
        recon = ReconciliationEntry(
            client_id=client_id,
            status=ReconciliationStatus.FLAGGED.value,
            flag_types=flag_types,
            flagged_entry_ids=flagged_entry_ids,
            entry_count=len(flagged_entry_ids),
            first_entry_date=first_entry_date,
            filing_deadline=deadline,
            original_total_duty=original_duty,
        )
        
        self.db.add(recon)
        await self.db.commit()
        await self.db.refresh(recon)
        
        return recon
    
    async def add_entry_to_recon(
        self,
        recon_id: UUID,
        entry_id: str,
    ) -> ReconciliationEntry:
        """Add an entry to reconciliation group."""
        query = select(ReconciliationEntry).where(ReconciliationEntry.id == recon_id)
        result = await self.db.execute(query)
        recon = result.scalar_one_or_none()
        
        if not recon:
            raise ValueError(f"Reconciliation {recon_id} not found")
        
        if entry_id not in recon.flagged_entry_ids:
            recon.flagged_entry_ids = recon.flagged_entry_ids + [entry_id]
            recon.entry_count = len(recon.flagged_entry_ids)
        
        await self.db.commit()
        await self.db.refresh(recon)
        
        return recon
    
    async def file_reconciliation(
        self,
        recon_id: UUID,
        recon_entry_number: str,
        final_value: Optional[Decimal] = None,
        final_duty: Optional[Decimal] = None,
    ) -> ReconciliationEntry:
        """File the reconciliation entry."""
        query = select(ReconciliationEntry).where(ReconciliationEntry.id == recon_id)
        result = await self.db.execute(query)
        recon = result.scalar_one_or_none()
        
        if not recon:
            raise ValueError(f"Reconciliation {recon_id} not found")
        
        recon.status = ReconciliationStatus.FILED.value
        recon.filed_date = date.today()
        recon.recon_entry_number = recon_entry_number
        recon.final_total_value = final_value
        recon.final_total_duty = final_duty
        
        if recon.original_total_duty and final_duty:
            recon.duty_difference = final_duty - recon.original_total_duty
        
        await self.db.commit()
        await self.db.refresh(recon)
        
        return recon
    
    async def list_reconciliations(
        self,
        client_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> List[ReconciliationEntry]:
        """List reconciliation entries."""
        query = select(ReconciliationEntry)
        
        if client_id:
            query = query.where(ReconciliationEntry.client_id == client_id)
        
        if status:
            query = query.where(ReconciliationEntry.status == status)
        
        query = query.order_by(ReconciliationEntry.filing_deadline)
        
        result = await self.db.execute(query)
        return result.scalars().all()


class DrawbackService:
    """Service for drawback claims."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_claim(
        self,
        client_id: UUID,
        drawback_type: str,
        import_entry_ids: List[str],
        total_duty_paid: Decimal,
    ) -> DrawbackClaim:
        """Create a drawback claim."""
        claim = DrawbackClaim(
            client_id=client_id,
            drawback_type=drawback_type,
            status=DrawbackStatus.ELIGIBLE.value,
            import_entry_ids=import_entry_ids,
            import_entry_count=len(import_entry_ids),
            total_duty_paid=total_duty_paid,
            drawback_rate=Decimal("99.0"),
            drawback_requested=total_duty_paid * Decimal("0.99"),
        )
        
        self.db.add(claim)
        await self.db.commit()
        await self.db.refresh(claim)
        
        return claim
    
    async def record_export(
        self,
        claim_id: UUID,
        export_date: date,
        export_reference: str,
    ) -> DrawbackClaim:
        """Record export for drawback claim."""
        query = select(DrawbackClaim).where(DrawbackClaim.id == claim_id)
        result = await self.db.execute(query)
        claim = result.scalar_one_or_none()
        
        if not claim:
            raise ValueError(f"Claim {claim_id} not found")
        
        claim.export_date = export_date
        claim.export_reference = export_reference
        claim.status = DrawbackStatus.PENDING.value
        
        await self.db.commit()
        await self.db.refresh(claim)
        
        return claim
    
    async def file_claim(
        self,
        claim_id: UUID,
        claim_number: str,
    ) -> DrawbackClaim:
        """File the drawback claim."""
        query = select(DrawbackClaim).where(DrawbackClaim.id == claim_id)
        result = await self.db.execute(query)
        claim = result.scalar_one_or_none()
        
        if not claim:
            raise ValueError(f"Claim {claim_id} not found")
        
        claim.status = DrawbackStatus.FILED.value
        claim.filed_date = date.today()
        claim.claim_number = claim_number
        
        await self.db.commit()
        await self.db.refresh(claim)
        
        return claim
    
    async def record_decision(
        self,
        claim_id: UUID,
        decision: str,
        approved_amount: Optional[Decimal] = None,
        denial_reason: Optional[str] = None,
    ) -> DrawbackClaim:
        """Record claim decision."""
        query = select(DrawbackClaim).where(DrawbackClaim.id == claim_id)
        result = await self.db.execute(query)
        claim = result.scalar_one_or_none()
        
        if not claim:
            raise ValueError(f"Claim {claim_id} not found")
        
        claim.decision = decision
        claim.decision_date = date.today()
        claim.drawback_approved = approved_amount
        claim.denial_reason = denial_reason
        
        if decision == "approved":
            claim.status = DrawbackStatus.APPROVED.value
        else:
            claim.status = DrawbackStatus.DENIED.value
        
        await self.db.commit()
        await self.db.refresh(claim)
        
        return claim
    
    async def list_claims(
        self,
        client_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> List[DrawbackClaim]:
        """List drawback claims."""
        query = select(DrawbackClaim)
        
        if client_id:
            query = query.where(DrawbackClaim.client_id == client_id)
        
        if status:
            query = query.where(DrawbackClaim.status == status)
        
        query = query.order_by(DrawbackClaim.created_at.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()


class PriorDisclosureService:
    """Service for prior disclosures."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_disclosure(
        self,
        client_id: UUID,
        violation_type: str,
        description: str,
        affected_entry_ids: List[str],
        discovery_date: date,
        duty_loss: Optional[Decimal] = None,
    ) -> PriorDisclosure:
        """Create a prior disclosure."""
        disclosure = PriorDisclosure(
            client_id=client_id,
            status=DisclosureStatus.DRAFT.value,
            violation_type=violation_type,
            description=description,
            discovery_date=discovery_date,
            affected_entry_ids=affected_entry_ids,
            entry_count=len(affected_entry_ids),
            duty_loss=duty_loss,
        )
        
        # Calculate penalty savings
        disclosure.calculate_penalty_savings()
        
        self.db.add(disclosure)
        await self.db.commit()
        await self.db.refresh(disclosure)
        
        return disclosure
    
    async def calculate_duty_loss(
        self,
        disclosure_id: UUID,
        original_declared: Decimal,
        correct_amount: Decimal,
    ) -> PriorDisclosure:
        """Calculate duty loss for disclosure."""
        query = select(PriorDisclosure).where(PriorDisclosure.id == disclosure_id)
        result = await self.db.execute(query)
        disclosure = result.scalar_one_or_none()
        
        if not disclosure:
            raise ValueError(f"Disclosure {disclosure_id} not found")
        
        disclosure.original_duty_declared = original_declared
        disclosure.correct_duty_amount = correct_amount
        disclosure.duty_loss = correct_amount - original_declared
        disclosure.calculate_penalty_savings()
        
        await self.db.commit()
        await self.db.refresh(disclosure)
        
        return disclosure
    
    async def file_disclosure(
        self,
        disclosure_id: UUID,
        disclosure_number: str,
    ) -> PriorDisclosure:
        """File the prior disclosure."""
        query = select(PriorDisclosure).where(PriorDisclosure.id == disclosure_id)
        result = await self.db.execute(query)
        disclosure = result.scalar_one_or_none()
        
        if not disclosure:
            raise ValueError(f"Disclosure {disclosure_id} not found")
        
        disclosure.status = DisclosureStatus.FILED.value
        disclosure.filed_date = date.today()
        disclosure.disclosure_number = disclosure_number
        
        await self.db.commit()
        await self.db.refresh(disclosure)
        
        return disclosure
    
    async def resolve_disclosure(
        self,
        disclosure_id: UUID,
        final_duty: Decimal,
        final_penalty: Decimal,
        total_payment: Decimal,
    ) -> PriorDisclosure:
        """Record resolution of disclosure."""
        query = select(PriorDisclosure).where(PriorDisclosure.id == disclosure_id)
        result = await self.db.execute(query)
        disclosure = result.scalar_one_or_none()
        
        if not disclosure:
            raise ValueError(f"Disclosure {disclosure_id} not found")
        
        disclosure.status = DisclosureStatus.RESOLVED.value
        disclosure.resolution_date = date.today()
        disclosure.final_duty_owed = final_duty
        disclosure.final_penalty = final_penalty
        disclosure.total_payment = total_payment
        
        await self.db.commit()
        await self.db.refresh(disclosure)
        
        return disclosure
    
    async def list_disclosures(
        self,
        client_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> List[PriorDisclosure]:
        """List prior disclosures."""
        query = select(PriorDisclosure)
        
        if client_id:
            query = query.where(PriorDisclosure.client_id == client_id)
        
        if status:
            query = query.where(PriorDisclosure.status == status)
        
        query = query.order_by(PriorDisclosure.created_at.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
