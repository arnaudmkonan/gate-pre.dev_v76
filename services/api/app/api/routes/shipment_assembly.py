"""
Shipment Assembly API Routes

Endpoints for managing shipment suggestions and assembly.
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.database import get_db, AsyncSession
from app.services.shipment_assembly_service import (
    ShipmentAssemblyService,
    AssemblyMode
)
from app.models.shipment_suggestions import SuggestionStatus

router = APIRouter(prefix="/api/shipments", tags=["shipment-assembly"])


# Request/Response Models
class DocumentInfo(BaseModel):
    id: str
    filename: Optional[str]
    document_type: Optional[str]


class SuggestionResponse(BaseModel):
    id: str
    master_bl: Optional[str]
    house_bl: Optional[str]
    container_numbers: List[str]
    confidence_score: float
    match_reasons: List[str]
    status: str
    document_ids: List[str]
    document_count: int
    suggested_details: dict
    created_at: Optional[str]
    
    class Config:
        from_attributes = True


class SuggestionsListResponse(BaseModel):
    suggestions: List[SuggestionResponse]
    total: int
    pending_count: int


class AnalyzeRequest(BaseModel):
    document_ids: List[str] = Field(..., description="Document IDs to analyze for grouping")


class AnalyzeResponse(BaseModel):
    suggestions: List[dict]
    document_count: int
    groupings_found: int


class AcceptRequest(BaseModel):
    suggestion_ids: List[str] = Field(..., description="Suggestion IDs to accept")


class AcceptResponse(BaseModel):
    accepted_count: int
    shipments_created: List[str]
    errors: List[str]


class RejectRequest(BaseModel):
    suggestion_id: str
    reason: Optional[str] = None


class AssemblyModeRequest(BaseModel):
    mode: str = Field(..., description="Assembly mode: auto, manual, or assisted")


class AssemblyModeResponse(BaseModel):
    client_id: str
    mode: str
    updated: bool


# Routes

@router.get("/suggestions", response_model=SuggestionsListResponse)
async def get_suggestions(
    status: Optional[str] = Query("pending", description="Filter by status"),
    limit: int = Query(50, le=100),
    session: AsyncSession = Depends(get_db)
):
    """
    Get shipment suggestions for review.
    
    In manual mode, users review these suggestions before accepting.
    """
    suggestions = await ShipmentAssemblyService.get_pending_suggestions(
        session, limit=limit
    )
    
    return {
        "suggestions": [
            SuggestionResponse(
                id=str(s.id),
                master_bl=s.master_bl,
                house_bl=s.house_bl,
                container_numbers=s.container_numbers or [],
                confidence_score=s.confidence_score,
                match_reasons=s.match_reasons or [],
                status=s.status.value if s.status else "pending",
                document_ids=[str(d) for d in s.document_ids] if s.document_ids else [],
                document_count=len(s.document_ids) if s.document_ids else 0,
                suggested_details=s.suggested_details or {},
                created_at=s.created_at.isoformat() if s.created_at else None
            )
            for s in suggestions
        ],
        "total": len(suggestions),
        "pending_count": len([s for s in suggestions if s.status == SuggestionStatus.PENDING])
    }


@router.post("/suggestions/analyze", response_model=AnalyzeResponse)
async def analyze_documents(
    request: AnalyzeRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Analyze documents to find potential shipment groupings.
    
    Returns suggested groupings based on shared identifiers (BOL, container, etc.)
    Does not create suggestions - use /suggestions/create for that.
    """
    document_ids = [UUID(d) for d in request.document_ids]
    
    suggestions = await ShipmentAssemblyService.analyze_documents(
        session, document_ids
    )
    
    return {
        "suggestions": suggestions,
        "document_count": len(request.document_ids),
        "groupings_found": len(suggestions)
    }


@router.post("/suggestions/create")
async def create_suggestions(
    request: AnalyzeRequest,
    auto_accept: bool = Query(False, description="Auto-accept suggestions and create shipments"),
    session: AsyncSession = Depends(get_db)
):
    """
    Analyze documents and create shipment suggestions.
    
    If auto_accept=true, suggestions are immediately accepted and shipments created.
    Otherwise, suggestions are created with PENDING status for user review.
    """
    document_ids = [UUID(d) for d in request.document_ids]
    
    # Analyze first
    suggestions = await ShipmentAssemblyService.analyze_documents(
        session, document_ids
    )
    
    if not suggestions:
        return {
            "status": "no_suggestions",
            "message": "No groupings found - documents don't share common identifiers",
            "suggestions_created": 0
        }
    
    # Create suggestions
    created = await ShipmentAssemblyService.create_suggestions(
        session, suggestions, auto_mode=auto_accept
    )
    
    return {
        "status": "success",
        "suggestions_created": len(created),
        "auto_accepted": auto_accept,
        "suggestions": [s.to_dict() for s in created]
    }


@router.post("/suggestions/{suggestion_id}/accept")
async def accept_suggestion(
    suggestion_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Accept a shipment suggestion and create the shipment.
    
    Links all documents in the suggestion to the new shipment.
    """
    shipment = await ShipmentAssemblyService.accept_suggestion(
        session, UUID(suggestion_id), reviewed_by="user"
    )
    
    if not shipment:
        raise HTTPException(status_code=404, detail="Suggestion not found or already processed")
    
    return {
        "status": "accepted",
        "shipment_id": str(shipment.id),
        "primary_key": f"{shipment.primary_key_type}: {shipment.primary_key_value}"
    }


@router.post("/suggestions/accept-bulk", response_model=AcceptResponse)
async def accept_bulk_suggestions(
    request: AcceptRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Accept multiple suggestions at once.
    
    Creates shipments for all accepted suggestions.
    """
    shipments = []
    errors = []
    
    for sugg_id in request.suggestion_ids:
        try:
            shipment = await ShipmentAssemblyService.accept_suggestion(
                session, UUID(sugg_id), reviewed_by="user"
            )
            if shipment:
                shipments.append(str(shipment.id))
            else:
                errors.append(f"{sugg_id}: Not found or already processed")
        except Exception as e:
            errors.append(f"{sugg_id}: {str(e)}")
    
    return AcceptResponse(
        accepted_count=len(shipments),
        shipments_created=shipments,
        errors=errors
    )


@router.post("/suggestions/{suggestion_id}/reject")
async def reject_suggestion(
    suggestion_id: str,
    reason: Optional[str] = None,
    session: AsyncSession = Depends(get_db)
):
    """
    Reject a shipment suggestion.
    
    The suggestion is marked as rejected and documents remain unlinked.
    """
    success = await ShipmentAssemblyService.reject_suggestion(
        session, UUID(suggestion_id), rejection_reason=reason, reviewed_by="user"
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Suggestion not found or already processed")
    
    return {"status": "rejected", "suggestion_id": suggestion_id}


@router.post("/auto-assemble")
async def auto_assemble_shipments(
    limit: int = Query(100, description="Maximum documents to process"),
    session: AsyncSession = Depends(get_db)
):
    """
    Automatically analyze all unlinked documents and create shipments.
    
    This runs the full assembly pipeline:
    1. Find documents not linked to any shipment
    2. Analyze for common identifiers
    3. Create suggestions with auto-accept
    4. Create shipments
    
    Use with caution - this will create shipments automatically.
    """
    from sqlalchemy import select, not_, exists
    from app.models.document_metadata import DocumentMetadata
    from app.models.gold_records import ShipmentDocument
    
    # Find documents not in any shipment
    subquery = select(ShipmentDocument.document_id)
    query = select(DocumentMetadata.id).where(
        not_(DocumentMetadata.id.in_(subquery))
    ).limit(limit)
    
    result = await session.execute(query)
    unlinked_doc_ids = [r[0] for r in result.all()]
    
    if not unlinked_doc_ids:
        return {
            "status": "no_documents",
            "message": "No unlinked documents found"
        }
    
    # Analyze and create with auto-accept
    suggestions = await ShipmentAssemblyService.analyze_documents(
        session, unlinked_doc_ids
    )
    
    if not suggestions:
        return {
            "status": "no_groupings",
            "documents_analyzed": len(unlinked_doc_ids),
            "message": "No common identifiers found between documents"
        }
    
    created = await ShipmentAssemblyService.create_suggestions(
        session, suggestions, auto_mode=True
    )
    
    return {
        "status": "success",
        "documents_analyzed": len(unlinked_doc_ids),
        "shipments_created": len(created),
        "shipments": [
            {
                "id": str(s.created_shipment_id) if s.created_shipment_id else None,
                "master_bl": s.master_bl,
                "document_count": len(s.document_ids) if s.document_ids else 0
            }
            for s in created
        ]
    }


@router.get("/assembly-mode")
async def get_assembly_mode(
    client_id: str = Query("default", description="Client ID"),
    session: AsyncSession = Depends(get_db)
):
    """Get the current assembly mode preference for a client."""
    mode = await ShipmentAssemblyService.get_client_assembly_mode(session, client_id)
    return {
        "client_id": client_id,
        "mode": mode.value
    }


@router.post("/assembly-mode", response_model=AssemblyModeResponse)
async def set_assembly_mode(
    request: AssemblyModeRequest,
    client_id: str = Query("default", description="Client ID"),
    session: AsyncSession = Depends(get_db)
):
    """
    Set the assembly mode preference for a client.
    
    Modes:
    - auto: Automatically create shipments when documents are processed
    - manual: Create suggestions for user review
    - assisted: Auto-create high-confidence, flag low-confidence for review
    """
    try:
        mode = AssemblyMode(request.mode)
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid mode. Must be one of: auto, manual, assisted"
        )
    
    pref = await ShipmentAssemblyService.set_client_assembly_mode(session, client_id, mode)
    
    return AssemblyModeResponse(
        client_id=client_id,
        mode=pref.assembly_mode.value,
        updated=True
    )
