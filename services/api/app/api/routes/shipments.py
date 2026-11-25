"""
Shipment Management API Routes

Provides endpoints for managing shipments and document linking.
Implements the Lakehouse architecture where documents are grouped
into virtual shipment folders via shared identifiers.
"""
from typing import List, Optional
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.services.auto_linker_service import AutoLinkerService
from app.services.key_extractor_service import KeyExtractorService
from app.models.gold_records import Shipment, ShipmentDocument, ShipmentStatus
from app.models.document_key import KeyType
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.core.auth import get_current_user

router = APIRouter(prefix="/api/shipments", tags=["Shipments"], dependencies=[Depends(get_current_user)])


# ==================== Request/Response Models ====================

class ShipmentCreate(BaseModel):
    """Manual shipment creation request."""
    name: Optional[str] = None
    reference_num: Optional[str] = None
    entry_number: Optional[str] = None
    bol_number: Optional[str] = None
    awb_number: Optional[str] = None
    importer_name: Optional[str] = None
    exporter_name: Optional[str] = None


class ShipmentUpdate(BaseModel):
    """Shipment update request."""
    name: Optional[str] = None
    reference_num: Optional[str] = None
    status: Optional[str] = None
    entry_number: Optional[str] = None
    bol_number: Optional[str] = None
    awb_number: Optional[str] = None
    importer_name: Optional[str] = None
    exporter_name: Optional[str] = None


class LinkDocumentRequest(BaseModel):
    """Request to manually link a document to a shipment."""
    document_id: str
    link_reason: Optional[str] = "Manual link"


class MergeShipmentsRequest(BaseModel):
    """Request to merge multiple shipments."""
    source_shipment_ids: List[str] = Field(..., min_length=1)


class AutoLinkRequest(BaseModel):
    """Request to run auto-linker."""
    document_ids: Optional[List[str]] = None
    only_unlinked: bool = True


class ShipmentSummary(BaseModel):
    """Summary of a shipment."""
    id: str
    name: Optional[str]
    reference_num: Optional[str]
    status: str
    document_count: int
    entry_number: Optional[str]
    bol_number: Optional[str]
    awb_number: Optional[str]
    importer_name: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ShipmentDetail(ShipmentSummary):
    """Detailed shipment information including linked documents."""
    primary_key_type: Optional[str]
    primary_key_value: Optional[str]
    exporter_name: Optional[str]
    manufacturer_name: Optional[str]
    container_numbers: Optional[List[str]]
    po_numbers: Optional[List[str]]
    total_declared_value: Optional[float]
    total_duty: Optional[float]
    document_types: Optional[List[str]]
    documents: Optional[List[str]] = None


class LinkedDocument(BaseModel):
    """Document linked to a shipment."""
    document_id: str
    filename: Optional[str] = None
    file_type: Optional[str] = None
    linked_by_key_type: Optional[str]
    linked_by_key_value: Optional[str]
    link_method: str
    link_confidence: float
    linked_at: datetime


class OrphanDocument(BaseModel):
    """Document with keys but not linked to a shipment."""
    document_id: str
    key_count: int
    key_types: List[str]


class LinkSuggestion(BaseModel):
    """Suggested shipment for an orphan document."""
    shipment_id: str
    shipment_name: str
    match_key_type: str
    match_key_value: str
    confidence: float
    document_count: int


# ==================== Endpoints ====================

@router.get("", response_model=List[ShipmentSummary])
async def list_shipments(
    status: Optional[str] = Query(None, description="Filter by status"),
    entry_number: Optional[str] = Query(None, description="Filter by entry number"),
    bol_number: Optional[str] = Query(None, description="Filter by BOL number"),
    importer_name: Optional[str] = Query(None, description="Filter by importer name (partial match)"),
    search: Optional[str] = Query(None, description="Search across all key fields"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db=Depends(get_db)
):
    """
    List all shipments with optional filtering.
    
    Supports filtering by:
    - status: partial, complete, ready_for_audit, in_audit, archived
    - entry_number: Exact match
    - bol_number: Exact match
    - importer_name: Partial match (contains)
    - search: Searches entry_number, bol_number, importer_name
    """
    query = select(Shipment)
    
    if status:
        query = query.where(Shipment.status == status)
    if entry_number:
        query = query.where(Shipment.entry_number == entry_number)
    if bol_number:
        query = query.where(Shipment.bol_number == bol_number)
    if importer_name:
        query = query.where(Shipment.importer_name.ilike(f"%{importer_name}%"))
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (Shipment.entry_number.ilike(search_filter)) |
            (Shipment.bol_number.ilike(search_filter)) |
            (Shipment.importer_name.ilike(search_filter)) |
            (Shipment.reference_num.ilike(search_filter)) |
            (Shipment.name.ilike(search_filter))
        )
    
    query = query.order_by(Shipment.document_count.desc(), Shipment.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    shipments = result.scalars().all()
    
    return [
        ShipmentSummary(
            id=str(s.id),
            name=s.name,
            reference_num=s.reference_num,
            status=s.status or ShipmentStatus.PARTIAL.value,
            document_count=s.document_count or 0,
            entry_number=s.entry_number,
            bol_number=s.bol_number,
            awb_number=s.awb_number,
            importer_name=s.importer_name,
            created_at=s.created_at
        )
        for s in shipments
    ]


@router.get("/stats")
async def get_shipment_stats(db=Depends(get_db)):
    """Get summary statistics for shipments."""
    # Total counts by status
    status_query = select(
        Shipment.status,
        func.count(Shipment.id).label('count')
    ).group_by(Shipment.status)
    
    result = await db.execute(status_query)
    status_counts = {row[0] or 'unknown': row[1] for row in result.all()}
    
    # Total shipments
    total_result = await db.execute(select(func.count(Shipment.id)))
    total = total_result.scalar_one()
    
    # Total linked documents
    linked_docs_result = await db.execute(select(func.count(ShipmentDocument.id)))
    linked_docs = linked_docs_result.scalar_one()
    
    # Average documents per shipment
    avg_docs = linked_docs / total if total > 0 else 0
    
    return {
        "total_shipments": total,
        "total_linked_documents": linked_docs,
        "average_documents_per_shipment": round(avg_docs, 2),
        "status_breakdown": status_counts,
        "statuses": list(ShipmentStatus.__members__.keys())
    }


@router.get("/orphans", response_model=List[OrphanDocument])
async def get_orphan_documents(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db=Depends(get_db)
):
    """
    Get documents that have extracted keys but are not linked to any shipment.
    
    These are candidates for manual linking or auto-linker processing.
    """
    linker = AutoLinkerService(db)
    orphans = await linker.get_orphan_documents(limit=limit, offset=offset)
    
    return [
        OrphanDocument(
            document_id=o["document_id"],
            key_count=o["key_count"],
            key_types=o["key_types"]
        )
        for o in orphans
    ]


@router.get("/suggestions", response_model=List[dict])
async def list_all_suggestions(
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db)
):
    """
    List shipment assembly suggestions for all orphan documents.

    Returns suggested document groupings based on shared keys (entry numbers,
    BOL numbers, container numbers, etc.). Used by the Shipment Assembly UI.
    """
    linker = AutoLinkerService(db)

    # Get orphan documents (not yet linked to any shipment)
    orphans = await linker.get_orphan_documents(limit=limit)

    suggestions = []
    seen_shipments = set()

    for orphan in orphans:
        try:
            doc_uuid = UUID(orphan["document_id"])
        except (ValueError, KeyError):
            continue

        doc_suggestions = await linker.get_link_suggestions(doc_uuid, limit=5)

        for s in doc_suggestions:
            ship_id = s.get("shipment_id", "")
            if ship_id not in seen_shipments:
                seen_shipments.add(ship_id)
                suggestions.append({
                    "id": ship_id,
                    "master_bl": s.get("match_key_value") if s.get("match_key_type") == "BOL_NUM" else None,
                    "house_bl": None,
                    "container_numbers": [],
                    "booking_number": None,
                    "confidence_score": s.get("confidence", 0.0),
                    "match_reasons": [f"{s.get('match_key_type', 'unknown')}: {s.get('match_key_value', '')}"],
                    "status": "PENDING",
                    "document_ids": [orphan["document_id"]],
                    "document_count": s.get("document_count", 1),
                    "suggested_details": {
                        "shipment_name": s.get("shipment_name", ""),
                    },
                    "created_shipment_id": None,
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "reviewed_at": None,
                })

    return suggestions


@router.get("/assembly-mode")
async def get_assembly_mode():
    """
    Get the current shipment assembly mode configuration.

    Returns the assembly mode settings used by the Shipment Assembly UI.
    """
    return {
        "assembly_mode": "assisted",
        "auto_accept_threshold": 0.9,
        "notify_on_suggestion": True,
        "notify_on_auto_accept": True,
    }


@router.post("/auto-assemble")
async def auto_assemble_shipments(
    db=Depends(get_db)
):
    """
    Trigger automatic shipment assembly.

    Runs the auto-linker on all unlinked documents to create shipment groupings.
    """
    linker = AutoLinkerService(db)

    try:
        results = await linker.run_batch_linking(
            document_ids=None,
            only_unlinked=True
        )
        return {
            "status": "completed",
            "shipments_created": results.get("shipments_created", 0),
            "documents_analyzed": results.get("documents_processed", 0),
            "documents_linked": results.get("documents_linked", 0),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Auto-assembly failed: {str(e)}"
        )


@router.get("/suggestions/{document_id}", response_model=List[LinkSuggestion])
async def get_link_suggestions(
    document_id: str = Path(..., description="Document ID to get suggestions for"),
    limit: int = Query(10, ge=1, le=50),
    db=Depends(get_db)
):
    """
    Get suggested shipments for an orphan document to be linked to.
    
    Returns shipments that share at least one key (entry number, BOL, etc.)
    with the specified document.
    """
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    
    linker = AutoLinkerService(db)
    suggestions = await linker.get_link_suggestions(doc_uuid, limit=limit)
    
    return [
        LinkSuggestion(**s)
        for s in suggestions
    ]


@router.get("/{shipment_id}", response_model=ShipmentDetail)
async def get_shipment(
    shipment_id: str = Path(..., description="Shipment ID"),
    db=Depends(get_db)
):
    """Get detailed information about a specific shipment."""
    try:
        ship_uuid = UUID(shipment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid shipment ID format")
    
    result = await db.execute(
        select(Shipment)
        .options(selectinload(Shipment.linked_documents))
        .where(Shipment.id == ship_uuid)
    )
    shipment = result.scalar_one_or_none()
    
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    doc_ids = [str(link.document_id) for link in (shipment.linked_documents or [])]

    prep = None
    if doc_ids:
        try:
            from app.services.entry_prep_service import EntryPrepService
            prep = await EntryPrepService.prepare_from_shipment(db, ship_uuid)
        except Exception:
            prep = None

    decl_val = (
        float(shipment.total_declared_value)
        if shipment.total_declared_value
        else (float(prep.total_entered_value) if prep and prep.total_entered_value else None)
    )
    est_duty = (
        float(shipment.total_duty)
        if shipment.total_duty
        else (float(prep.grand_total) if prep and prep.grand_total else None)
    )

    return ShipmentDetail(
        id=str(shipment.id),
        name=shipment.name or (f"Shipment {prep.master_bill}" if prep and prep.master_bill else None),
        reference_num=shipment.reference_num,
        status=shipment.status or ShipmentStatus.PARTIAL.value,
        document_count=shipment.document_count or len(doc_ids),
        entry_number=shipment.entry_number or (prep.entry_number if prep else None),
        bol_number=shipment.bol_number or (prep.master_bill if prep else None),
        awb_number=shipment.awb_number,
        importer_name=shipment.importer_name or (prep.importer_name if prep else None),
        created_at=shipment.created_at,
        primary_key_type=shipment.primary_key_type,
        primary_key_value=shipment.primary_key_value,
        exporter_name=shipment.exporter_name,
        manufacturer_name=shipment.manufacturer_name,
        container_numbers=shipment.container_numbers,
        po_numbers=shipment.po_numbers,
        total_declared_value=decl_val,
        total_duty=est_duty,
        document_types=shipment.document_types,
        documents=doc_ids,
    )


@router.get("/{shipment_id}/documents", response_model=List[LinkedDocument])
async def get_shipment_documents(
    shipment_id: str = Path(..., description="Shipment ID"),
    db=Depends(get_db)
):
    """Get all documents linked to a shipment."""
    from app.models.document_metadata import DocumentMetadata
    from app.models.raw_file import RawFile

    try:
        ship_uuid = UUID(shipment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid shipment ID format")
    
    result = await db.execute(
        select(ShipmentDocument)
        .where(ShipmentDocument.shipment_id == ship_uuid)
        .order_by(ShipmentDocument.created_at.desc())
    )
    links = result.scalars().all()
    
    enriched_docs = []
    for link in links:
        doc_res = await db.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == link.document_id)
        )
        doc = doc_res.scalar_one_or_none()
        raw_file = None
        if not doc:
            raw_res = await db.execute(
                select(RawFile).where(RawFile.id == link.document_id)
            )
            raw_file = raw_res.scalar_one_or_none()

        filename = (
            (doc.filename if doc else None)
            or (raw_file.filename if raw_file else None)
            or f"Document {str(link.document_id)[:8]}"
        )
        file_type = (
            (doc.file_type if doc else None)
            or (raw_file.file_type if raw_file else None)
        )
        enriched_docs.append(
            LinkedDocument(
                document_id=str(link.document_id),
                filename=filename,
                file_type=file_type,
                linked_by_key_type=link.linked_by_key_type,
                linked_by_key_value=link.linked_by_key_value,
                link_method=link.link_method,
                link_confidence=link.link_confidence,
                linked_at=link.created_at,
            )
        )

    return enriched_docs


@router.post("", response_model=ShipmentDetail)
async def create_shipment(
    request: ShipmentCreate,
    db=Depends(get_db)
):
    """
    Manually create a new shipment.
    
    Use this when you want to create a shipment ahead of document uploads,
    or to manually group documents that couldn't be auto-linked.
    """
    shipment = Shipment(
        name=request.name or f"Shipment {datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
        reference_num=request.reference_num,
        entry_number=request.entry_number,
        bol_number=request.bol_number,
        awb_number=request.awb_number,
        importer_name=request.importer_name,
        exporter_name=request.exporter_name,
        status=ShipmentStatus.PARTIAL.value,
        document_count=0
    )
    
    # Set primary key based on strongest identifier provided
    if request.entry_number:
        shipment.primary_key_type = KeyType.ENTRY_NUM.value
        shipment.primary_key_value = request.entry_number
    elif request.bol_number:
        shipment.primary_key_type = KeyType.BOL_NUM.value
        shipment.primary_key_value = request.bol_number
    elif request.awb_number:
        shipment.primary_key_type = KeyType.AWB_NUM.value
        shipment.primary_key_value = request.awb_number
    
    db.add(shipment)
    await db.commit()
    await db.refresh(shipment)
    
    return ShipmentDetail(
        id=str(shipment.id),
        name=shipment.name,
        reference_num=shipment.reference_num,
        status=shipment.status,
        document_count=0,
        entry_number=shipment.entry_number,
        bol_number=shipment.bol_number,
        awb_number=shipment.awb_number,
        importer_name=shipment.importer_name,
        created_at=shipment.created_at,
        primary_key_type=shipment.primary_key_type,
        primary_key_value=shipment.primary_key_value,
        exporter_name=shipment.exporter_name,
        manufacturer_name=None,
        container_numbers=[],
        po_numbers=[],
        total_declared_value=None,
        total_duty=None,
        document_types=[]
    )


@router.patch("/{shipment_id}", response_model=ShipmentDetail)
async def update_shipment(
    request: ShipmentUpdate,
    shipment_id: str = Path(..., description="Shipment ID"),
    db=Depends(get_db)
):
    """Update a shipment's details."""
    try:
        ship_uuid = UUID(shipment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid shipment ID format")
    
    result = await db.execute(
        select(Shipment).where(Shipment.id == ship_uuid)
    )
    shipment = result.scalar_one_or_none()
    
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(shipment, field, value)
    
    await db.commit()
    await db.refresh(shipment)
    
    return await get_shipment(shipment_id, db)


@router.post("/{shipment_id}/link/{document_id}")
async def link_document_to_shipment(
    shipment_id: str = Path(..., description="Shipment ID"),
    document_id: str = Path(..., description="Document ID to link"),
    reason: str = Query("Manual link", description="Reason for linking"),
    db=Depends(get_db)
):
    """
    Manually link a document to a shipment.
    
    Use this to manually associate a document with a shipment when
    auto-linking didn't work or wasn't run.
    """
    try:
        ship_uuid = UUID(shipment_id)
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    # Verify shipment exists
    result = await db.execute(
        select(Shipment).where(Shipment.id == ship_uuid)
    )
    shipment = result.scalar_one_or_none()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    # Check if already linked
    existing = await db.execute(
        select(ShipmentDocument).where(
            ShipmentDocument.shipment_id == ship_uuid,
            ShipmentDocument.document_id == doc_uuid
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Document already linked to this shipment")
    
    # Create link
    link = ShipmentDocument(
        shipment_id=ship_uuid,
        document_id=doc_uuid,
        linked_by_key_type="MANUAL",
        linked_by_key_value=reason,
        link_confidence=1.0,
        link_method="manual"
    )
    db.add(link)
    
    # Update document count
    shipment.document_count = (shipment.document_count or 0) + 1
    
    await db.commit()
    
    return {
        "message": "Document linked successfully",
        "shipment_id": shipment_id,
        "document_id": document_id
    }


@router.delete("/{shipment_id}/link/{document_id}")
async def unlink_document_from_shipment(
    shipment_id: str = Path(..., description="Shipment ID"),
    document_id: str = Path(..., description="Document ID to unlink"),
    db=Depends(get_db)
):
    """Remove a document from a shipment."""
    try:
        ship_uuid = UUID(shipment_id)
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    # Find and delete the link
    result = await db.execute(
        select(ShipmentDocument).where(
            ShipmentDocument.shipment_id == ship_uuid,
            ShipmentDocument.document_id == doc_uuid
        )
    )
    link = result.scalar_one_or_none()
    
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    
    await db.delete(link)
    
    # Update document count
    shipment_result = await db.execute(
        select(Shipment).where(Shipment.id == ship_uuid)
    )
    shipment = shipment_result.scalar_one_or_none()
    if shipment:
        shipment.document_count = max(0, (shipment.document_count or 0) - 1)
    
    await db.commit()
    
    return {"message": "Document unlinked successfully"}


@router.post("/linker/run")
async def run_auto_linker(
    request: AutoLinkRequest,
    db=Depends(get_db)
):
    """
    Run the auto-linker to group documents into shipments.
    
    The auto-linker finds documents with shared keys (entry number, BOL, etc.)
    and groups them into Shipment records.
    
    Options:
    - document_ids: Specific documents to process (null = all)
    - only_unlinked: Only process documents not yet in any shipment (default: true)
    """
    linker = AutoLinkerService(db)
    
    doc_uuids = None
    if request.document_ids:
        try:
            doc_uuids = [UUID(d) for d in request.document_ids]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid document ID format")
    
    results = await linker.run_batch_linking(
        document_ids=doc_uuids,
        only_unlinked=request.only_unlinked
    )
    
    return results


@router.post("/{target_shipment_id}/merge")
async def merge_shipments(
    request: MergeShipmentsRequest,
    target_shipment_id: str = Path(..., description="Target shipment to merge into"),
    db=Depends(get_db)
):
    """
    Merge multiple shipments into one.
    
    All documents from source shipments are moved to the target shipment.
    Source shipments are deleted after merge.
    """
    try:
        target_uuid = UUID(target_shipment_id)
        source_uuids = [UUID(s) for s in request.source_shipment_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid shipment ID format")
    
    linker = AutoLinkerService(db)
    
    try:
        shipment = await linker.merge_shipments(target_uuid, source_uuids)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    return {
        "message": f"Merged {len(source_uuids)} shipments into {target_shipment_id}",
        "shipment_id": str(shipment.id),
        "document_count": shipment.document_count
    }


@router.delete("/{shipment_id}")
async def delete_shipment(
    shipment_id: str = Path(..., description="Shipment ID to delete"),
    db=Depends(get_db)
):
    """
    Delete a shipment.
    
    Documents linked to the shipment are not deleted, only unlinked.
    """
    try:
        ship_uuid = UUID(shipment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid shipment ID format")
    
    result = await db.execute(
        select(Shipment).where(Shipment.id == ship_uuid)
    )
    shipment = result.scalar_one_or_none()
    
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    # ShipmentDocument records will be cascade deleted
    await db.delete(shipment)
    await db.commit()
    
    return {"message": "Shipment deleted successfully", "shipment_id": shipment_id}


@router.get("/{shipment_id}/keys")
async def get_shipment_keys(
    shipment_id: str = Path(..., description="Shipment ID"),
    db=Depends(get_db)
):
    """Get all unique keys from documents in a shipment."""
    try:
        ship_uuid = UUID(shipment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid shipment ID format")
    
    from app.models.document_key import DocumentKey
    
    # Get document IDs in this shipment
    doc_result = await db.execute(
        select(ShipmentDocument.document_id)
        .where(ShipmentDocument.shipment_id == ship_uuid)
    )
    doc_ids = [row[0] for row in doc_result.all()]
    
    if not doc_ids:
        return {"keys": [], "key_types": []}
    
    # Get all keys for these documents
    keys_result = await db.execute(
        select(DocumentKey)
        .where(DocumentKey.document_id.in_(doc_ids))
        .order_by(DocumentKey.key_type)
    )
    keys = keys_result.scalars().all()
    
    # Deduplicate and organize
    unique_keys = {}
    for key in keys:
        key_id = (key.key_type, key.key_value_normalized or key.key_value)
        if key_id not in unique_keys:
            unique_keys[key_id] = {
                "key_type": key.key_type,
                "key_value": key.key_value,
                "normalized": key.key_value_normalized,
                "confidence": key.confidence,
                "document_count": 1
            }
        else:
            unique_keys[key_id]["document_count"] += 1
    
    key_list = list(unique_keys.values())
    key_types = list(set(k["key_type"] for k in key_list))
    
    return {
        "keys": key_list,
        "key_types": key_types,
        "total_keys": len(key_list)
    }


# ==================== Key Extraction Endpoints ====================

class KeyExtractionRequest(BaseModel):
    """Request to extract keys from a document."""
    document_id: str
    use_llm: bool = False
    auto_link: bool = True


class BatchKeyExtractionRequest(BaseModel):
    """Request to extract keys from multiple documents."""
    document_ids: Optional[List[str]] = None
    only_without_keys: bool = True
    use_llm: bool = False
    auto_link: bool = True


@router.post("/keys/extract")
async def extract_document_keys(
    request: KeyExtractionRequest,
    db=Depends(get_db)
):
    """
    Extract linking keys from a document.
    
    Triggers the key extraction pipeline which:
    1. Extracts identifiers (Entry#, BOL#, Container#, PO#, etc.) from document text
    2. Saves extracted keys to the database
    3. Optionally runs auto-linking to group into shipments
    
    This runs asynchronously via Celery.
    """
    try:
        doc_uuid = UUID(request.document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    
    try:
        from app.workers.key_extraction_task import extract_document_keys as extract_task
        task = extract_task.delay(
            file_id=str(doc_uuid),
            use_llm=request.use_llm,
            auto_link=request.auto_link
        )
        return {
            "status": "queued",
            "task_id": task.id,
            "document_id": request.document_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(e)}")


@router.post("/keys/extract/batch")
async def batch_extract_keys(
    request: BatchKeyExtractionRequest,
    db=Depends(get_db)
):
    """
    Batch extract keys from multiple documents.
    
    This is useful for processing documents that were uploaded before
    key extraction was enabled in the pipeline.
    """
    try:
        from app.workers.key_extraction_task import batch_extract_keys as batch_task
        task = batch_task.delay(
            file_ids=request.document_ids,
            only_without_keys=request.only_without_keys,
            use_llm=request.use_llm,
            auto_link=request.auto_link
        )
        return {
            "status": "queued",
            "task_id": task.id,
            "message": "Batch key extraction started"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue batch task: {str(e)}")


@router.get("/keys/document/{document_id}")
async def get_document_keys(
    document_id: str = Path(..., description="Document ID"),
    db=Depends(get_db)
):
    """Get all extracted keys for a specific document."""
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    
    from app.models.document_key import DocumentKey
    
    result = await db.execute(
        select(DocumentKey)
        .where(DocumentKey.document_id == doc_uuid)
        .order_by(DocumentKey.key_type)
    )
    keys = result.scalars().all()
    
    return {
        "document_id": document_id,
        "key_count": len(keys),
        "keys": [
            {
                "id": str(key.id),
                "key_type": key.key_type,
                "key_value": key.key_value,
                "normalized": key.key_value_normalized,
                "confidence": key.confidence,
                "extraction_method": key.extraction_method,
                "source_text": key.source_text[:200] if key.source_text else None
            }
            for key in keys
        ]
    }


@router.get("/keys/types")
async def get_key_types():
    """Get available key types and their descriptions."""
    from app.models.document_key import KeyType, KEY_PRIORITY
    
    return {
        "key_types": [
            {
                "type": kt.value,
                "priority": KEY_PRIORITY.get(kt, 99),
                "description": _get_key_type_description(kt)
            }
            for kt in KeyType
        ]
    }


def _get_key_type_description(key_type: KeyType) -> str:
    """Get description for a key type."""
    from app.models.document_key import KeyType
    descriptions = {
        KeyType.ENTRY_NUM: "CBP Entry Number (11-digit customs filing identifier)",
        KeyType.ACE_BILL: "ACE Bill Number",
        KeyType.BOL_NUM: "Bill of Lading Number (ocean/sea shipments)",
        KeyType.AWB_NUM: "Air Waybill Number (air shipments)",
        KeyType.CONTAINER_NUM: "Container Number (4 letters + 7 digits)",
        KeyType.INVOICE_NUM: "Commercial Invoice Number",
        KeyType.PO_NUM: "Purchase Order Number",
        KeyType.IMPORTER_NAME: "Importer of Record name",
        KeyType.VENDOR_NAME: "Exporter/Seller name",
        KeyType.MANUFACTURER_NAME: "Manufacturer name",
        KeyType.HTS_CODE: "Harmonized Tariff Schedule code",
        KeyType.COUNTRY_ORIGIN: "Country of Origin code (2-letter ISO)",
    }
    return descriptions.get(key_type, "")


# ==================== Entry Creation from Shipment ====================

class CreateEntryFromShipmentRequest(BaseModel):
    """Request to create an entry from a shipment."""
    entry_type: str = Field("01", description="Entry type code (01=consumption, 02=FTZ)")
    port_of_entry: Optional[str] = Field(None, description="4-digit port code")
    auto_calculate: bool = Field(True, description="Auto-calculate duties after creation")


@router.post("/{shipment_id}/create-entry")
async def create_entry_from_shipment(
    request: Optional[CreateEntryFromShipmentRequest] = None,
    shipment_id: str = Path(..., description="Shipment ID"),
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a customs entry from a shipment (or return existing entry if already created).
    """
    if request is None:
        request = CreateEntryFromShipmentRequest()

    try:
        ship_uuid = UUID(shipment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid shipment ID format")
    
    # Get shipment with linked documents
    result = await db.execute(
        select(Shipment)
        .options(selectinload(Shipment.linked_documents))
        .where(Shipment.id == ship_uuid)
    )
    shipment = result.scalar_one_or_none()
    
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    # Check if shipment already has an entry
    from app.models.entry import Entry, EntryLine, EntryStatus, EntryStatusHistory, EntryDocument
    
    existing_res = await db.execute(
        select(Entry).where(Entry.shipment_id == ship_uuid).limit(1)
    )
    existing_entry = existing_res.scalar_one_or_none()
    if existing_entry:
        return {
            "message": "Entry already exists for this shipment",
            "already_exists": True,
            "entry_id": str(existing_entry.id),
            "entry_number": existing_entry.entry_number,
            "shipment_id": shipment_id,
            "status": existing_entry.status,
            "created_at": existing_entry.created_at.isoformat() if existing_entry.created_at else None,
        }
    
    # Collect extraction data from all linked documents + EntryPrepService
    extraction_data = {}
    doc_types_seen = set()
    document_ids = []
    
    from app.models.document_metadata import DocumentMetadata
    from app.models.extraction_result import ExtractionResult

    for doc_link in shipment.linked_documents:
        document_ids.append(doc_link.document_id)
        
        doc_result = await db.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == doc_link.document_id)
        )
        doc = doc_result.scalar_one_or_none()
        doc_type = getattr(doc, "document_type", None) or (doc.file_type if doc else None)
        if doc_type:
            doc_types_seen.add(doc_type)
        
        ext_result = await db.execute(
            select(ExtractionResult).where(
                ExtractionResult.document_id == doc_link.document_id,
            )
        )
        extractions = ext_result.scalars().all()
        
        for ext in extractions:
            field = ext.field_name.lower().replace(" ", "_")
            confidence = ext.confidence or 0.5
            
            if field not in extraction_data or confidence > extraction_data[field]["confidence"]:
                extraction_data[field] = {
                    "value": ext.field_value,
                    "confidence": confidence,
                    "source_doc_id": str(doc_link.document_id),
                    "source_doc_type": doc_type,
                }

    # Prepare rich 7501 data from EntryPrepService if available
    prep_data = None
    try:
        from app.services.entry_prep_service import EntryPrepService
        prep_data = await EntryPrepService.prepare_from_shipment(db, ship_uuid)
    except Exception:
        prep_data = None

    actor_email = current_user.get("email") or current_user.get("sub") or "system"

    # Match client_id: portal user's client, else IOR/EIN/name resolve
    from app.startup.client_access import portal_user_client_id
    from app.services.client_resolve_service import resolve_client_id

    resolved_client_id = portal_user_client_id(current_user)
    imp_lookup_name = shipment.importer_name or (prep_data.importer_name if prep_data else None)
    prep_ein = None
    if prep_data:
        prep_ein = getattr(prep_data, "importer_of_record_number", None) or getattr(
            prep_data, "importer_ein", None
        )
    if resolved_client_id is None:
        resolved_client_id = await resolve_client_id(
            db,
            importer_name=imp_lookup_name,
            ein=prep_ein,
            ior_number=prep_ein,
        )

    resolved_port = (
        request.port_of_entry
        or (prep_data.port_of_entry or prep_data.port_code if prep_data else None)
    )
    if resolved_port and len(resolved_port) > 4:
        resolved_port = resolved_port[:4] if resolved_port[:4].isdigit() else None

    unlading_port = prep_data.port_of_unlading if prep_data else None
    if unlading_port and (not unlading_port.isdigit() or len(unlading_port) != 4):
        unlading_port = resolved_port

    entry = Entry(
        entry_type=request.entry_type or (prep_data.entry_type if prep_data else "01"),
        filer_code=prep_data.filer_code[:3] if (prep_data and prep_data.filer_code) else None,
        entry_date=prep_data.entry_date if prep_data else datetime.now(timezone.utc),
        import_date=(prep_data.import_date if prep_data else None) or shipment.arrival_date or datetime.now(timezone.utc),
        port_of_entry=resolved_port,
        port_of_unlading=unlading_port,
        mode_of_transport="10",
        entry_number=shipment.entry_number or (prep_data.entry_number if prep_data else None),
        bill_of_lading=shipment.bol_number or (prep_data.master_bill if prep_data else None),
        master_bill=prep_data.master_bill if prep_data else shipment.bol_number,
        house_bill=prep_data.house_bill if prep_data else None,
        carrier_code=prep_data.carrier_code[:4] if (prep_data and prep_data.carrier_code) else None,
        vessel_name=prep_data.vessel_name if prep_data else None,
        voyage_flight_number=prep_data.voyage_number[:20] if (prep_data and prep_data.voyage_number) else None,
        container_numbers=shipment.container_numbers or [],
        importer_of_record_name=imp_lookup_name,
        importer_of_record_number=prep_data.importer_of_record_number[:15] if (prep_data and prep_data.importer_of_record_number) else None,
        ultimate_consignee_name=prep_data.consignee_name if prep_data else imp_lookup_name,
        bond_type=prep_data.bond_type if prep_data else "8",
        surety_code=prep_data.surety_code[:3] if (prep_data and prep_data.surety_code) else None,
        total_entered_value=float(prep_data.total_entered_value) if prep_data else float(shipment.total_declared_value or 0),
        total_dutiable_value=float(prep_data.total_entered_value) if prep_data else float(shipment.total_declared_value or 0),
        total_duty=float(prep_data.total_duty) if prep_data else float(shipment.total_duty or 0),
        mpf_amount=float(prep_data.total_mpf) if prep_data else 0.0,
        hmf_amount=float(prep_data.total_hmf) if prep_data else 0.0,
        total_fee=float((prep_data.total_mpf + prep_data.total_hmf)) if prep_data else 0.0,
        total_amount_due=float(prep_data.grand_total) if prep_data else float((shipment.total_duty or 0)),
        status=EntryStatus.DRAFT.value,
        client_id=resolved_client_id,
        shipment_id=ship_uuid,
        notes=f"Created from shipment: {shipment.name or shipment_id}",
    )
    
    field_mappings = {
        "importer_name": "importer_of_record_name",
        "importer": "importer_of_record_name",
        "consignee": "ultimate_consignee_name",
        "carrier": "carrier_code",
        "vessel": "vessel_name",
        "voyage": "voyage_flight_number",
        "port_of_entry": "port_of_entry",
        "port": "port_of_entry",
    }
    
    fields_populated = []
    for ext_field, entry_field in field_mappings.items():
        if ext_field in extraction_data:
            value = extraction_data[ext_field]["value"]
            if hasattr(entry, entry_field) and not getattr(entry, entry_field):
                setattr(entry, entry_field, value)
                fields_populated.append(entry_field)
    
    db.add(entry)
    await db.flush()

    # Add line items from EntryPrepService if available
    lines_created = 0
    if prep_data and prep_data.line_items:
        for idx, item in enumerate(prep_data.line_items, 1):
            raw_hts = item.get("hts_number")
            raw_origin = item.get("country_of_origin")
            line = EntryLine(
                entry_id=entry.id,
                line_number=item.get("line_number") or idx,
                hts_code=str(raw_hts)[:12] if raw_hts else None,
                product_description=item.get("description") or "Imported Merchandise",
                country_of_origin=str(raw_origin)[:2].upper() if raw_origin else None,
                quantity_1=float(item.get("quantity") or 0),
                uom_1=item.get("unit") or "PCS",
                gross_weight=float(item.get("gross_weight") or 0),
                entered_value=float(item.get("entered_value") or 0),
                dutiable_value=float(item.get("entered_value") or 0),
                duty_rate=float(item.get("duty_rate") or 0),
                duty_amount=float(item.get("duty_amount") or 0),
                total_line_duty=float(item.get("duty_amount") or 0),
            )
            db.add(line)
            lines_created += 1
        entry.line_count = lines_created
    
    # Create status history
    history = EntryStatusHistory(
        entry_id=entry.id,
        from_status=None,
        to_status=EntryStatus.DRAFT.value,
        changed_by=actor_email,
        reason=f"Created from shipment {shipment_id}",
    )
    db.add(history)
    
    # Link documents to entry (shipment_documents may reference raw_files.id;
    # entry_documents FK requires document_metadata.id — resolve when needed)
    linked_count = 0
    resolved_doc_ids = []
    for doc_id in document_ids:
        meta = await db.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == doc_id)
        )
        if meta.scalar_one_or_none():
            resolved_doc_ids.append(doc_id)
            continue
        # Try match metadata produced from this raw file / same storage basename
        from app.models.raw_file import RawFile
        raw = await db.execute(select(RawFile).where(RawFile.id == doc_id))
        raw_file = raw.scalar_one_or_none()
        if not raw_file:
            continue
        fname = getattr(raw_file, "filename", None) or getattr(raw_file, "original_filename", None)
        if not fname:
            continue
        meta_match = await db.execute(
            select(DocumentMetadata.id)
            .where(DocumentMetadata.filename == fname)
            .order_by(DocumentMetadata.created_at.desc())
            .limit(1)
        )
        meta_id = meta_match.scalar_one_or_none()
        if meta_id:
            resolved_doc_ids.append(meta_id)

    for doc_id in resolved_doc_ids:
        try:
            async with db.begin_nested():
                entry_doc = EntryDocument(
                    entry_id=entry.id,
                    document_id=doc_id,
                    is_primary=linked_count == 0,
                    added_by=actor_email,
                )
                db.add(entry_doc)
                await db.flush()
                linked_count += 1
        except Exception:
            pass
    
    await db.commit()
    await db.refresh(entry)
    
    suggestions = []
    for field, data in extraction_data.items():
        if data["confidence"] < 0.8 and field in field_mappings:
            suggestions.append({
                "field_name": field_mappings.get(field, field),
                "suggested_value": data["value"],
                "confidence": data["confidence"],
                "source_document_id": data["source_doc_id"],
                "source_document_type": data["source_doc_type"],
            })
    
    return {
        "message": "Entry created successfully from shipment",
        "already_exists": False,
        "entry_id": str(entry.id),
        "entry_number": entry.entry_number,
        "shipment_id": shipment_id,
        "status": entry.status,
        "lines_created": lines_created,
        "documents_linked": linked_count,
        "document_types": list(doc_types_seen),
        "fields_populated": fields_populated,
        "suggestions": suggestions,
        "created_at": entry.created_at.isoformat(),
    }


@router.get("/{shipment_id}/entry")
async def get_shipment_entry(
    shipment_id: str = Path(..., description="Shipment ID"),
    db=Depends(get_db)
):
    """
    Get the entry linked to a shipment, if any.
    """
    try:
        ship_uuid = UUID(shipment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid shipment ID format")
    
    from app.models.entry import Entry
    
    result = await db.execute(
        select(Entry).where(Entry.shipment_id == ship_uuid)
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        return {
            "has_entry": False,
            "shipment_id": shipment_id,
            "entry": None,
        }
    
    return {
        "has_entry": True,
        "shipment_id": shipment_id,
        "entry": {
            "id": str(entry.id),
            "entry_number": entry.entry_number,
            "entry_type": entry.entry_type,
            "status": entry.status,
            "port_of_entry": entry.port_of_entry,
            "importer_of_record_name": entry.importer_of_record_name,
            "created_at": entry.created_at.isoformat(),
        },
    }


@router.get("/{shipment_id}/pipeline")
async def get_shipment_pipeline(
    shipment_id: str = Path(..., description="Shipment ID"),
    db=Depends(get_db),
):
    """
    Job timeline for one shipment: Docs → Review → Assembled → ISF → Entry → ACE.
    """
    from app.services.shipment_pipeline_service import get_shipment_pipeline as build_pipeline

    try:
        ship_uuid = UUID(shipment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid shipment ID format")

    pipeline = await build_pipeline(db, ship_uuid)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return pipeline


class RequestMissingDocumentPayload(BaseModel):
    doc_type: str = Field(..., min_length=1, max_length=100)
    recipient_email: Optional[str] = Field(None, max_length=255)
    note: Optional[str] = Field(None, max_length=2000)


@router.post("/{shipment_id}/request-document")
async def request_missing_shipment_document(
    payload: RequestMissingDocumentPayload,
    shipment_id: str = Path(..., description="Shipment ID"),
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Dispatch a real missing-document request email via EmailService and write an audit log.

    When IMAP ingest is configured, Reply-To points at the monitored inbox and the
    subject includes ``[GATE-DOCREQ:{shipment_id}]`` so attachment replies auto-link.
    """
    from app.core.config import settings
    from app.models.client import Client
    from app.models.document_type import DocumentType
    from app.services.audit_service import audit
    from app.services.email_service import EmailService

    try:
        ship_uuid = UUID(shipment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid shipment ID format")

    result = await db.execute(select(Shipment).where(Shipment.id == ship_uuid))
    shipment = result.scalar_one_or_none()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    target_email = (payload.recipient_email or "").strip() or None
    importer_label = shipment.importer_name or "Importer"

    if not target_email and shipment.importer_name:
        client_res = await db.execute(
            select(Client)
            .options(selectinload(Client.contacts))
            .where(Client.name.ilike(shipment.importer_name.strip()))
            .limit(1)
        )
        matched_client = client_res.scalar_one_or_none()
        if matched_client:
            primary_contact = next(
                (c for c in (matched_client.contacts or []) if c.email and c.is_primary),
                next((c for c in (matched_client.contacts or []) if c.email), None),
            )
            target_email = (primary_contact.email if primary_contact else None) or matched_client.email

    doc_type_row = (
        await db.execute(
            select(DocumentType).where(DocumentType.code == payload.doc_type)
        )
    ).scalar_one_or_none()
    doc_label = doc_type_row.label if doc_type_row else payload.doc_type.replace("_", " ").title()
    bol_ref = shipment.bol_number or str(shipment.id)[:8].upper()
    requester = f"{current_user.get('first_name') or ''} {current_user.get('last_name') or ''}".strip() or (
        settings.broker_name or "Customs Brokerage"
    )
    imap_ready = bool(settings.email_imap_host and settings.email_imap_user)
    reply_to = settings.email_imap_user if imap_ready else None
    email_sent = False

    if target_email:
        email_sent = await EmailService().send_document_request(
            to_email=target_email,
            requester_name=requester,
            document_types=[doc_label],
            entry_number=shipment.entry_number or bol_ref,
            message=payload.note,
            upload_url=f"{settings.public_app_url}/ingest-ui",
            shipment_id=str(shipment.id),
            reply_to=reply_to,
        )

    await audit(
        db,
        action="request_document",
        resource_type="shipment",
        resource_id=str(shipment.id),
        actor_id=str(current_user.get("id") or current_user.get("email") or "broker"),
        after={
            "doc_type": payload.doc_type,
            "doc_label": doc_label,
            "recipient_email": target_email,
            "email_dispatched": email_sent,
            "note": payload.note,
            "reply_auto_ingest": imap_ready,
            "correlation_token": f"GATE-DOCREQ:{shipment.id}",
        },
    )
    await db.commit()

    if email_sent and target_email:
        message = (
            f"Requested {doc_label} from importer ({importer_label}) via {target_email}."
            + (
                " Replies with attachments to the monitored inbox will auto-ingest and link to this shipment."
                if imap_ready
                else " Configure EMAIL_IMAP_* to auto-process attachment replies."
            )
        )
    elif target_email and not email_sent:
        message = (
            f"Could not send request for {doc_label} to {target_email} "
            f"— SMTP is not configured or delivery failed. Request was audited."
        )
    else:
        message = (
            f"No email on file for importer ({importer_label}). "
            f"Add a client contact email or pass recipient_email to send via SMTP. Request was audited."
        )

    return {
        "shipment_id": str(shipment.id),
        "doc_type": payload.doc_type,
        "doc_label": doc_label,
        "importer_name": importer_label,
        "recipient_email": target_email,
        "email_dispatched": email_sent,
        "reply_auto_ingest": imap_ready,
        "correlation_token": f"GATE-DOCREQ:{shipment.id}",
        "message": message,
    }

