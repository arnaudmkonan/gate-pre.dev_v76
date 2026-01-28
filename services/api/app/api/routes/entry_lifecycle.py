"""
Entry Lifecycle API Routes.

Endpoints for entry lifecycle management:
- Liquidation tracking
- Protests
- Reconciliation
- Drawback claims
- Prior disclosures

Phase 6 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List
from uuid import UUID
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db


router = APIRouter(prefix="/api/lifecycle", tags=["Entry Lifecycle"])


# ==================== Request Models ====================

class CreateLiquidationRequest(BaseModel):
    entry_id: str
    entry_date: str  # YYYY-MM-DD
    estimated_duty: Optional[float] = None


class ExtendDeadlineRequest(BaseModel):
    extension_days: int
    reason: str


class RecordLiquidationRequest(BaseModel):
    liquidation_date: str  # YYYY-MM-DD
    liquidated_duty: float
    cbp_code: Optional[str] = None


class CreateProtestRequest(BaseModel):
    entry_id: str
    client_id: str
    liquidation_date: str  # YYYY-MM-DD
    protest_category: str
    protest_reason: str
    duty_contested: Optional[float] = None
    refund_requested: Optional[float] = None


class FileProtestRequest(BaseModel):
    protest_number: str


class ProtestDecisionRequest(BaseModel):
    decision: str  # approved, denied, partial
    refund_granted: Optional[float] = None
    decision_reason: Optional[str] = None


class EscalateProtestRequest(BaseModel):
    cit_case_number: str


class CreateReconciliationRequest(BaseModel):
    client_id: str
    flag_types: List[str]
    flagged_entry_ids: List[str]
    first_entry_date: str  # YYYY-MM-DD
    original_duty: Optional[float] = None


class FileReconciliationRequest(BaseModel):
    recon_entry_number: str
    final_value: Optional[float] = None
    final_duty: Optional[float] = None


class CreateDrawbackRequest(BaseModel):
    client_id: str
    drawback_type: str
    import_entry_ids: List[str]
    total_duty_paid: float


class RecordExportRequest(BaseModel):
    export_date: str  # YYYY-MM-DD
    export_reference: str


class FileDrawbackRequest(BaseModel):
    claim_number: str


class DrawbackDecisionRequest(BaseModel):
    decision: str  # approved, denied
    approved_amount: Optional[float] = None
    denial_reason: Optional[str] = None


class CreateDisclosureRequest(BaseModel):
    client_id: str
    violation_type: str
    description: str
    affected_entry_ids: List[str]
    discovery_date: str  # YYYY-MM-DD
    duty_loss: Optional[float] = None


class FileDisclosureRequest(BaseModel):
    disclosure_number: str


class ResolveDisclosureRequest(BaseModel):
    final_duty: float
    final_penalty: float
    total_payment: float


# ==================== Liquidation Endpoints (Task 6.1) ====================

@router.post("/liquidation")
async def create_liquidation_tracking(
    request: CreateLiquidationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create liquidation tracking for an entry."""
    from app.services.entry_lifecycle_service import LiquidationService
    from datetime import datetime
    
    service = LiquidationService(db)
    
    liquidation = await service.create_liquidation_tracking(
        entry_id=UUID(request.entry_id),
        entry_date=datetime.strptime(request.entry_date, "%Y-%m-%d").date(),
        estimated_duty=Decimal(str(request.estimated_duty)) if request.estimated_duty else None,
    )
    
    return {
        "liquidation": liquidation.to_dict(),
        "message": "Liquidation tracking created",
    }


@router.get("/liquidation/{entry_id}")
async def get_liquidation(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get liquidation tracking for an entry."""
    from app.services.entry_lifecycle_service import LiquidationService
    
    service = LiquidationService(db)
    liquidation = await service.get_liquidation(UUID(entry_id))
    
    if not liquidation:
        raise HTTPException(status_code=404, detail="Liquidation tracking not found")
    
    return liquidation.to_dict()


@router.post("/liquidation/{entry_id}/extend")
async def extend_deadline(
    entry_id: str,
    request: ExtendDeadlineRequest,
    db: AsyncSession = Depends(get_db),
):
    """Extend liquidation deadline."""
    from app.services.entry_lifecycle_service import LiquidationService
    
    service = LiquidationService(db)
    
    try:
        liquidation = await service.extend_deadline(
            UUID(entry_id),
            request.extension_days,
            request.reason,
        )
        return {
            "liquidation": liquidation.to_dict(),
            "message": f"Deadline extended by {request.extension_days} days",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/liquidation/{entry_id}/liquidate")
async def record_liquidation(
    entry_id: str,
    request: RecordLiquidationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record that an entry has been liquidated."""
    from app.services.entry_lifecycle_service import LiquidationService
    from datetime import datetime
    
    service = LiquidationService(db)
    
    try:
        liquidation = await service.record_liquidation(
            UUID(entry_id),
            datetime.strptime(request.liquidation_date, "%Y-%m-%d").date(),
            Decimal(str(request.liquidated_duty)),
            request.cbp_code,
        )
        return {
            "liquidation": liquidation.to_dict(),
            "message": "Liquidation recorded",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/liquidation/alerts/approaching")
async def get_approaching_deadlines(
    days_ahead: int = Query(30, ge=1, le=90),
    client_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get entries approaching liquidation deadline."""
    from app.services.entry_lifecycle_service import LiquidationService
    
    service = LiquidationService(db)
    
    liquidations = await service.get_approaching_deadlines(
        days_ahead,
        UUID(client_id) if client_id else None,
    )
    
    return {
        "liquidations": [l.to_dict() for l in liquidations],
        "count": len(liquidations),
    }


@router.get("/liquidation/alerts/refunds")
async def get_refunds_owed(
    client_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get entries where refund is owed."""
    from app.services.entry_lifecycle_service import LiquidationService
    
    service = LiquidationService(db)
    
    liquidations = await service.get_refunds_owed(
        UUID(client_id) if client_id else None,
    )
    
    total_refund = sum(abs(l.duty_difference or 0) for l in liquidations)
    
    return {
        "liquidations": [l.to_dict() for l in liquidations],
        "count": len(liquidations),
        "total_refund_owed": float(total_refund),
    }


# ==================== Protest Endpoints (Task 6.2) ====================

@router.post("/protests")
async def create_protest(
    request: CreateProtestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a protest for an entry."""
    from app.services.entry_lifecycle_service import ProtestService
    from datetime import datetime
    
    service = ProtestService(db)
    
    protest = await service.create_protest(
        entry_id=UUID(request.entry_id),
        client_id=UUID(request.client_id),
        liquidation_date=datetime.strptime(request.liquidation_date, "%Y-%m-%d").date(),
        protest_category=request.protest_category,
        protest_reason=request.protest_reason,
        duty_contested=Decimal(str(request.duty_contested)) if request.duty_contested else None,
        refund_requested=Decimal(str(request.refund_requested)) if request.refund_requested else None,
    )
    
    return {
        "protest": protest.to_dict(),
        "message": "Protest created",
    }


@router.get("/protests")
async def list_protests(
    client_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List protests."""
    from app.services.entry_lifecycle_service import ProtestService
    
    service = ProtestService(db)
    
    protests = await service.list_protests(
        client_id=UUID(client_id) if client_id else None,
        status=status,
    )
    
    return {
        "protests": [p.to_dict() for p in protests],
        "count": len(protests),
    }


@router.get("/protests/{protest_id}")
async def get_protest(
    protest_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get protest details."""
    from app.services.entry_lifecycle_service import ProtestService
    
    service = ProtestService(db)
    protest = await service.get_protest(UUID(protest_id))
    
    if not protest:
        raise HTTPException(status_code=404, detail="Protest not found")
    
    return protest.to_dict()


@router.post("/protests/{protest_id}/file")
async def file_protest(
    protest_id: str,
    request: FileProtestRequest,
    db: AsyncSession = Depends(get_db),
):
    """File a protest with CBP."""
    from app.services.entry_lifecycle_service import ProtestService
    
    service = ProtestService(db)
    
    try:
        protest = await service.file_protest(UUID(protest_id), request.protest_number)
        return {
            "protest": protest.to_dict(),
            "message": "Protest filed",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/protests/{protest_id}/decision")
async def record_protest_decision(
    protest_id: str,
    request: ProtestDecisionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record protest decision."""
    from app.services.entry_lifecycle_service import ProtestService
    
    service = ProtestService(db)
    
    try:
        protest = await service.record_decision(
            UUID(protest_id),
            request.decision,
            Decimal(str(request.refund_granted)) if request.refund_granted else None,
            request.decision_reason,
        )
        return {
            "protest": protest.to_dict(),
            "message": f"Decision recorded: {request.decision}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/protests/{protest_id}/escalate")
async def escalate_protest(
    protest_id: str,
    request: EscalateProtestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Escalate protest to Court of International Trade."""
    from app.services.entry_lifecycle_service import ProtestService
    
    service = ProtestService(db)
    
    try:
        protest = await service.escalate_to_cit(UUID(protest_id), request.cit_case_number)
        return {
            "protest": protest.to_dict(),
            "message": "Protest escalated to CIT",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Reconciliation Endpoints (Task 6.3) ====================

@router.post("/reconciliations")
async def create_reconciliation(
    request: CreateReconciliationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a reconciliation entry group."""
    from app.services.entry_lifecycle_service import ReconciliationService
    from datetime import datetime
    
    service = ReconciliationService(db)
    
    recon = await service.create_reconciliation(
        client_id=UUID(request.client_id),
        flag_types=request.flag_types,
        flagged_entry_ids=request.flagged_entry_ids,
        first_entry_date=datetime.strptime(request.first_entry_date, "%Y-%m-%d").date(),
        original_duty=Decimal(str(request.original_duty)) if request.original_duty else None,
    )
    
    return {
        "reconciliation": recon.to_dict(),
        "message": "Reconciliation created",
    }


@router.get("/reconciliations")
async def list_reconciliations(
    client_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List reconciliation entries."""
    from app.services.entry_lifecycle_service import ReconciliationService
    
    service = ReconciliationService(db)
    
    recons = await service.list_reconciliations(
        client_id=UUID(client_id) if client_id else None,
        status=status,
    )
    
    return {
        "reconciliations": [r.to_dict() for r in recons],
        "count": len(recons),
    }


@router.post("/reconciliations/{recon_id}/file")
async def file_reconciliation(
    recon_id: str,
    request: FileReconciliationRequest,
    db: AsyncSession = Depends(get_db),
):
    """File a reconciliation entry."""
    from app.services.entry_lifecycle_service import ReconciliationService
    
    service = ReconciliationService(db)
    
    try:
        recon = await service.file_reconciliation(
            UUID(recon_id),
            request.recon_entry_number,
            Decimal(str(request.final_value)) if request.final_value else None,
            Decimal(str(request.final_duty)) if request.final_duty else None,
        )
        return {
            "reconciliation": recon.to_dict(),
            "message": "Reconciliation filed",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Drawback Endpoints (Task 6.4) ====================

@router.post("/drawback")
async def create_drawback_claim(
    request: CreateDrawbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a drawback claim."""
    from app.services.entry_lifecycle_service import DrawbackService
    
    service = DrawbackService(db)
    
    claim = await service.create_claim(
        client_id=UUID(request.client_id),
        drawback_type=request.drawback_type,
        import_entry_ids=request.import_entry_ids,
        total_duty_paid=Decimal(str(request.total_duty_paid)),
    )
    
    return {
        "claim": claim.to_dict(),
        "message": "Drawback claim created",
    }


@router.get("/drawback")
async def list_drawback_claims(
    client_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List drawback claims."""
    from app.services.entry_lifecycle_service import DrawbackService
    
    service = DrawbackService(db)
    
    claims = await service.list_claims(
        client_id=UUID(client_id) if client_id else None,
        status=status,
    )
    
    return {
        "claims": [c.to_dict() for c in claims],
        "count": len(claims),
    }


@router.post("/drawback/{claim_id}/export")
async def record_drawback_export(
    claim_id: str,
    request: RecordExportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record export for drawback claim."""
    from app.services.entry_lifecycle_service import DrawbackService
    from datetime import datetime
    
    service = DrawbackService(db)
    
    try:
        claim = await service.record_export(
            UUID(claim_id),
            datetime.strptime(request.export_date, "%Y-%m-%d").date(),
            request.export_reference,
        )
        return {
            "claim": claim.to_dict(),
            "message": "Export recorded",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/drawback/{claim_id}/file")
async def file_drawback_claim(
    claim_id: str,
    request: FileDrawbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """File a drawback claim."""
    from app.services.entry_lifecycle_service import DrawbackService
    
    service = DrawbackService(db)
    
    try:
        claim = await service.file_claim(UUID(claim_id), request.claim_number)
        return {
            "claim": claim.to_dict(),
            "message": "Claim filed",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/drawback/{claim_id}/decision")
async def record_drawback_decision(
    claim_id: str,
    request: DrawbackDecisionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record drawback claim decision."""
    from app.services.entry_lifecycle_service import DrawbackService
    
    service = DrawbackService(db)
    
    try:
        claim = await service.record_decision(
            UUID(claim_id),
            request.decision,
            Decimal(str(request.approved_amount)) if request.approved_amount else None,
            request.denial_reason,
        )
        return {
            "claim": claim.to_dict(),
            "message": f"Decision recorded: {request.decision}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Prior Disclosure Endpoints (Task 6.5) ====================

@router.post("/disclosures")
async def create_disclosure(
    request: CreateDisclosureRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a prior disclosure."""
    from app.services.entry_lifecycle_service import PriorDisclosureService
    from datetime import datetime
    
    service = PriorDisclosureService(db)
    
    disclosure = await service.create_disclosure(
        client_id=UUID(request.client_id),
        violation_type=request.violation_type,
        description=request.description,
        affected_entry_ids=request.affected_entry_ids,
        discovery_date=datetime.strptime(request.discovery_date, "%Y-%m-%d").date(),
        duty_loss=Decimal(str(request.duty_loss)) if request.duty_loss else None,
    )
    
    return {
        "disclosure": disclosure.to_dict(),
        "message": "Prior disclosure created",
        "penalty_savings": float(disclosure.penalty_savings) if disclosure.penalty_savings else None,
    }


@router.get("/disclosures")
async def list_disclosures(
    client_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List prior disclosures."""
    from app.services.entry_lifecycle_service import PriorDisclosureService
    
    service = PriorDisclosureService(db)
    
    disclosures = await service.list_disclosures(
        client_id=UUID(client_id) if client_id else None,
        status=status,
    )
    
    return {
        "disclosures": [d.to_dict() for d in disclosures],
        "count": len(disclosures),
    }


@router.post("/disclosures/{disclosure_id}/file")
async def file_disclosure(
    disclosure_id: str,
    request: FileDisclosureRequest,
    db: AsyncSession = Depends(get_db),
):
    """File a prior disclosure."""
    from app.services.entry_lifecycle_service import PriorDisclosureService
    
    service = PriorDisclosureService(db)
    
    try:
        disclosure = await service.file_disclosure(UUID(disclosure_id), request.disclosure_number)
        return {
            "disclosure": disclosure.to_dict(),
            "message": "Disclosure filed",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/disclosures/{disclosure_id}/resolve")
async def resolve_disclosure(
    disclosure_id: str,
    request: ResolveDisclosureRequest,
    db: AsyncSession = Depends(get_db),
):
    """Resolve a prior disclosure."""
    from app.services.entry_lifecycle_service import PriorDisclosureService
    
    service = PriorDisclosureService(db)
    
    try:
        disclosure = await service.resolve_disclosure(
            UUID(disclosure_id),
            Decimal(str(request.final_duty)),
            Decimal(str(request.final_penalty)),
            Decimal(str(request.total_payment)),
        )
        return {
            "disclosure": disclosure.to_dict(),
            "message": "Disclosure resolved",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Reference Data ====================

@router.get("/reference/liquidation-status")
async def get_liquidation_statuses():
    """Get liquidation status options."""
    from app.models.entry_lifecycle import LiquidationStatus
    return {
        "statuses": [{"value": s.value, "name": s.name} for s in LiquidationStatus],
    }


@router.get("/reference/protest-status")
async def get_protest_statuses():
    """Get protest status options."""
    from app.models.entry_lifecycle import ProtestStatus
    return {
        "statuses": [{"value": s.value, "name": s.name} for s in ProtestStatus],
    }


@router.get("/reference/drawback-types")
async def get_drawback_types():
    """Get drawback type options."""
    from app.models.entry_lifecycle import DrawbackType
    return {
        "types": [{"value": t.value, "name": t.name} for t in DrawbackType],
    }


@router.get("/reference/recon-flag-types")
async def get_recon_flag_types():
    """Get reconciliation flag type options."""
    from app.models.entry_lifecycle import ReconFlagType
    return {
        "types": [{"value": t.value, "name": t.name} for t in ReconFlagType],
    }
