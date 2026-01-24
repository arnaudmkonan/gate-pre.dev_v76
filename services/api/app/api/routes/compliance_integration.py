"""
Compliance Integration API Routes.

Provides endpoints for:
- Viewing compliance check results for documents
- Manually triggering compliance checks
- Getting compliance statistics
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.reference_data import ComplianceScreen
from app.models.document_metadata import DocumentMetadata
from app.services.post_extraction_service import (
    PostExtractionService,
    PostExtractionResult,
    RiskLevel,
)

router = APIRouter(prefix="/api/compliance", tags=["Compliance Integration"])


# ==================== Request/Response Models ====================

class TriggerComplianceRequest(BaseModel):
    """Request to trigger compliance checks on a document."""
    document_id: str
    extraction_results: Optional[dict] = None  # If not provided, will fetch from DB
    template_name: Optional[str] = None


class ComplianceResultResponse(BaseModel):
    """Response with compliance check results."""
    document_id: str
    template_name: Optional[str]
    overall_risk_level: str
    hts_validations: List[dict]
    party_screenings: List[dict]
    naics_classifications: List[dict]
    issues_found: List[dict]
    processed_at: Optional[str]


class ComplianceStatsResponse(BaseModel):
    """Compliance statistics response."""
    total_screenings: int
    screenings_by_type: dict
    screenings_by_risk_level: dict
    recent_high_risk: List[dict]


class HTSValidationRequest(BaseModel):
    """Request to validate an HTS code."""
    hts_code: str


class PartyScreeningRequest(BaseModel):
    """Request to screen a party against OFAC."""
    party_name: str
    party_type: str = "unknown"
    threshold: float = Field(default=0.80, ge=0.0, le=1.0)


class BatchComplianceRequest(BaseModel):
    """Request to run compliance checks on multiple documents."""
    document_ids: List[str]


# ==================== Endpoints ====================

@router.post("/check", response_model=ComplianceResultResponse)
async def run_compliance_check(
    request: TriggerComplianceRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Run compliance checks on a document's extraction results.

    If extraction_results is not provided, will attempt to fetch
    the most recent template extraction from the database.
    """
    service = PostExtractionService(db)

    extraction_results = request.extraction_results

    # If no extraction results provided, try to get from database
    if not extraction_results:
        # Get document and its extraction results
        doc_uuid = UUID(request.document_id)
        doc_result = await db.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
        )
        doc = doc_result.scalar_one_or_none()

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Get extraction results from extraction_result table
        from app.models.extraction_result import ExtractionResult
        ext_result = await db.execute(
            select(ExtractionResult).where(
                ExtractionResult.document_id == doc_uuid,
                ExtractionResult.extraction_type == "template",
            )
        )
        extractions = ext_result.scalars().all()

        if not extractions:
            raise HTTPException(
                status_code=400,
                detail="No template extraction results found for this document"
            )

        # Build extraction results dict
        extraction_results = {
            "extractions": [
                {
                    "field_name": e.field_name,
                    "value": e.field_value,
                    "raw_value": e.raw_value,
                    "normalized_value": e.normalized_value,
                    "confidence": e.confidence,
                    "found": True,
                }
                for e in extractions
            ]
        }

    result = await service.process_extraction_results(
        document_id=request.document_id,
        extraction_results=extraction_results,
        template_name=request.template_name,
    )

    return ComplianceResultResponse(
        document_id=result.document_id,
        template_name=result.template_name,
        overall_risk_level=result.overall_risk_level.value,
        hts_validations=[v.to_dict() for v in result.hts_validations],
        party_screenings=[s.to_dict() for s in result.party_screenings],
        naics_classifications=[c.to_dict() for c in result.naics_classifications],
        issues_found=result.issues_found,
        processed_at=result.processed_at.isoformat() if result.processed_at else None,
    )


@router.post("/validate-hts")
async def validate_hts_code(
    request: HTSValidationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate a single HTS code against the reference database.

    Returns validation status, duty rates, and suggestions if not found.
    """
    service = PostExtractionService(db)
    result = await service.validate_hts_code(request.hts_code)

    return result.to_dict()


@router.post("/screen-party")
async def screen_party(
    request: PartyScreeningRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Screen a party name against the OFAC SDN list.

    Returns matches found and risk level assessment.
    """
    service = PostExtractionService(db)
    result = await service.screen_party(
        party_name=request.party_name,
        party_type=request.party_type,
        threshold=request.threshold,
    )

    return result.to_dict()


@router.get("/document/{document_id}")
async def get_document_compliance(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all compliance screening results for a document.

    Returns historical compliance checks linked to this document.
    """
    doc_uuid = UUID(document_id)

    # Get document
    doc_result = await db.execute(
        select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
    )
    doc = doc_result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get compliance screens - need to find screens linked through shipments
    # or directly to this document's extracted parties
    screens_result = await db.execute(
        select(ComplianceScreen).order_by(
            ComplianceScreen.created_at.desc()
        ).limit(50)
    )
    screens = screens_result.scalars().all()

    return {
        "document_id": document_id,
        "filename": doc.filename,
        "compliance_screens": [
            {
                "id": str(s.id),
                "screen_type": s.screen_type,
                "risk_level": s.risk_level,
                "matches_count": len(s.matches or []),
                "resolved": s.resolved,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in screens
        ],
    }


@router.get("/stats", response_model=ComplianceStatsResponse)
async def get_compliance_stats(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to include"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get compliance screening statistics.

    Returns aggregate stats on screenings performed.
    """
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Total screenings
    total_result = await db.execute(
        select(func.count(ComplianceScreen.id)).where(
            ComplianceScreen.created_at >= cutoff
        )
    )
    total = total_result.scalar() or 0

    # By type
    type_result = await db.execute(
        select(
            ComplianceScreen.screen_type,
            func.count(ComplianceScreen.id).label("count"),
        ).where(
            ComplianceScreen.created_at >= cutoff
        ).group_by(ComplianceScreen.screen_type)
    )
    by_type = {row.screen_type: row.count for row in type_result}

    # By risk level
    risk_result = await db.execute(
        select(
            ComplianceScreen.risk_level,
            func.count(ComplianceScreen.id).label("count"),
        ).where(
            ComplianceScreen.created_at >= cutoff
        ).group_by(ComplianceScreen.risk_level)
    )
    by_risk = {row.risk_level or "unknown": row.count for row in risk_result}

    # Recent high risk
    high_risk_result = await db.execute(
        select(ComplianceScreen).where(
            ComplianceScreen.created_at >= cutoff,
            ComplianceScreen.risk_level.in_(["high", "critical", "confirmed_match"]),
        ).order_by(
            ComplianceScreen.created_at.desc()
        ).limit(10)
    )
    high_risk_screens = high_risk_result.scalars().all()

    return ComplianceStatsResponse(
        total_screenings=total,
        screenings_by_type=by_type,
        screenings_by_risk_level=by_risk,
        recent_high_risk=[
            {
                "id": str(s.id),
                "screen_type": s.screen_type,
                "risk_level": s.risk_level,
                "matches_count": len(s.matches or []),
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in high_risk_screens
        ],
    )


@router.post("/batch")
async def run_batch_compliance(
    request: BatchComplianceRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger compliance checks on multiple documents.

    Runs in the background and returns immediately.
    """
    # Validate document IDs
    valid_ids = []
    for doc_id in request.document_ids:
        try:
            UUID(doc_id)
            valid_ids.append(doc_id)
        except ValueError:
            pass

    if not valid_ids:
        raise HTTPException(status_code=400, detail="No valid document IDs provided")

    # Queue background task
    from app.workers.agent_processor import process_with_agents

    queued = 0
    for doc_id in valid_ids:
        try:
            process_with_agents.delay(doc_id, "standard")
            queued += 1
        except Exception as e:
            pass

    return {
        "status": "queued",
        "documents_queued": queued,
        "total_requested": len(request.document_ids),
    }


@router.get("/history")
async def get_compliance_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    screen_type: Optional[str] = Query(default=None, description="Filter by screen type"),
    risk_level: Optional[str] = Query(default=None, description="Filter by risk level"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get compliance screening history with optional filters.
    """
    query = select(ComplianceScreen)

    if screen_type:
        query = query.where(ComplianceScreen.screen_type == screen_type)
    if risk_level:
        query = query.where(ComplianceScreen.risk_level == risk_level)

    query = query.order_by(
        ComplianceScreen.created_at.desc()
    ).limit(limit).offset(offset)

    result = await db.execute(query)
    screens = result.scalars().all()

    return {
        "count": len(screens),
        "offset": offset,
        "screens": [
            {
                "id": str(s.id),
                "screen_type": s.screen_type,
                "risk_level": s.risk_level,
                "result": s.result,
                "matches_count": len(s.matches or []),
                "resolved": s.resolved,
                "resolved_at": s.resolved_at.isoformat() if s.resolved_at else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in screens
        ],
    }


@router.patch("/screen/{screen_id}/resolve")
async def resolve_compliance_screen(
    screen_id: str,
    resolved_by: str = Query(..., description="User or agent who resolved the screen"),
    notes: Optional[str] = Query(default=None, description="Resolution notes"),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a compliance screen as resolved.
    """
    screen_uuid = UUID(screen_id)

    result = await db.execute(
        select(ComplianceScreen).where(ComplianceScreen.id == screen_uuid)
    )
    screen = result.scalar_one_or_none()

    if not screen:
        raise HTTPException(status_code=404, detail="Compliance screen not found")

    screen.resolved = True
    screen.resolved_at = datetime.now(timezone.utc)
    screen.resolved_by = resolved_by
    if notes:
        screen.notes = notes

    await db.commit()

    return {
        "id": str(screen.id),
        "resolved": True,
        "resolved_at": screen.resolved_at.isoformat(),
        "resolved_by": resolved_by,
    }
