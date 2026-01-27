"""
Shipment Management API Routes

Provides endpoints for managing shipments and document linking.
Implements the Lakehouse architecture where documents are grouped
into virtual shipment folders via shared identifiers.
"""
from typing import List, Optional
from datetime import datetime
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

router = APIRouter(prefix="/api/shipments", tags=["Shipments"])


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


class LinkedDocument(BaseModel):
    """Document linked to a shipment."""
    document_id: str
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
    
    query = query.order_by(Shipment.created_at.desc()).limit(limit).offset(offset)
    
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
        .where(Shipment.id == ship_uuid)
    )
    shipment = result.scalar_one_or_none()
    
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    return ShipmentDetail(
        id=str(shipment.id),
        name=shipment.name,
        reference_num=shipment.reference_num,
        status=shipment.status or ShipmentStatus.PARTIAL.value,
        document_count=shipment.document_count or 0,
        entry_number=shipment.entry_number,
        bol_number=shipment.bol_number,
        awb_number=shipment.awb_number,
        importer_name=shipment.importer_name,
        created_at=shipment.created_at,
        primary_key_type=shipment.primary_key_type,
        primary_key_value=shipment.primary_key_value,
        exporter_name=shipment.exporter_name,
        manufacturer_name=shipment.manufacturer_name,
        container_numbers=shipment.container_numbers,
        po_numbers=shipment.po_numbers,
        total_declared_value=float(shipment.total_declared_value) if shipment.total_declared_value else None,
        total_duty=float(shipment.total_duty) if shipment.total_duty else None,
        document_types=shipment.document_types
    )


@router.get("/{shipment_id}/documents", response_model=List[LinkedDocument])
async def get_shipment_documents(
    shipment_id: str = Path(..., description="Shipment ID"),
    db=Depends(get_db)
):
    """Get all documents linked to a shipment."""
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
    
    return [
        LinkedDocument(
            document_id=str(link.document_id),
            linked_by_key_type=link.linked_by_key_type,
            linked_by_key_value=link.linked_by_key_value,
            link_method=link.link_method,
            link_confidence=link.link_confidence,
            linked_at=link.created_at
        )
        for link in links
    ]


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
    request: CreateEntryFromShipmentRequest,
    shipment_id: str = Path(..., description="Shipment ID"),
    db=Depends(get_db)
):
    """
    Create a customs entry from a shipment.
    
    This endpoint:
    1. Creates a new Entry linked to the shipment
    2. Links all shipment documents to the entry
    3. Auto-populates entry fields from document extractions:
       - Importer from extraction data
       - BOL number from shipment
       - Entry number if already assigned
    4. Creates suggestions for fields that need review
    
    The entry is created in DRAFT status for review before filing.
    
    Task 1.7 from ROADMAP_FULL_WORKFLOW.md
    """
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
    from app.models.entry import Entry, EntryStatus, EntryStatusHistory, EntryDocument
    
    existing_entry = await db.execute(
        select(Entry).where(Entry.shipment_id == ship_uuid)
    )
    if existing_entry.scalar_one_or_none():
        raise HTTPException(
            status_code=400, 
            detail="Shipment already has an entry. Use the existing entry or unlink it first."
        )
    
    # Collect extraction data from all linked documents
    extraction_data = {}
    doc_types_seen = set()
    document_ids = []
    
    for doc_link in shipment.linked_documents:
        document_ids.append(doc_link.document_id)
        
        # Get document metadata
        from app.models.document import DocumentMetadata
        doc_result = await db.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == doc_link.document_id)
        )
        doc = doc_result.scalar_one_or_none()
        if doc and doc.document_type:
            doc_types_seen.add(doc.document_type)
        
        # Get extractions from this document
        from app.models.extraction_result import ExtractionResult
        ext_result = await db.execute(
            select(ExtractionResult).where(
                ExtractionResult.document_id == doc_link.document_id,
                ExtractionResult.extraction_type == "template"
            )
        )
        extractions = ext_result.scalars().all()
        
        for ext in extractions:
            field = ext.field_name.lower().replace(" ", "_")
            confidence = ext.confidence or 0.5
            
            # Keep highest confidence value for each field
            if field not in extraction_data or confidence > extraction_data[field]["confidence"]:
                extraction_data[field] = {
                    "value": ext.field_value,
                    "confidence": confidence,
                    "source_doc_id": str(doc_link.document_id),
                    "source_doc_type": doc.document_type if doc else None,
                }
    
    # Create the entry with populated data
    entry = Entry(
        entry_type=request.entry_type,
        port_of_entry=request.port_of_entry or shipment.entry_number[:4] if shipment.entry_number else None,
        entry_number=shipment.entry_number,
        bill_of_lading=shipment.bol_number,
        importer_of_record_name=shipment.importer_name,
        status=EntryStatus.DRAFT.value,
        shipment_id=ship_uuid,
        notes=f"Created from shipment: {shipment.name or shipment_id}",
    )
    
    # Map extracted fields to entry fields
    field_mappings = {
        "importer_name": "importer_of_record_name",
        "importer": "importer_of_record_name",
        "consignee": "consignee_name",
        "seller": "exporter_name",
        "exporter": "exporter_name",
        "manufacturer": "manufacturer_name",
        "carrier": "carrier_code",
        "vessel": "vessel_name",
        "voyage": "voyage_number",
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
    
    # Add entry to DB
    db.add(entry)
    await db.flush()  # Get entry ID
    
    # Create status history
    history = EntryStatusHistory(
        entry_id=entry.id,
        from_status=None,
        to_status=EntryStatus.DRAFT.value,
        changed_by="system",
        reason=f"Created from shipment {shipment_id}",
    )
    db.add(history)
    
    # Link documents to entry
    linked_count = 0
    for doc_id in document_ids:
        # Check if EntryDocument model exists
        try:
            entry_doc = EntryDocument(
                entry_id=entry.id,
                document_id=doc_id,
                is_primary=linked_count == 0,  # First doc is primary
                added_by="system",
            )
            db.add(entry_doc)
            linked_count += 1
        except Exception:
            # EntryDocument might not exist, skip
            pass
    
    await db.commit()
    await db.refresh(entry)
    
    # Optionally calculate duties
    duty_summary = None
    if request.auto_calculate and entry.lines:
        try:
            from app.services.duty_calculator_service import DutyCalculatorService
            calc = DutyCalculatorService(db)
            # Would calculate duties here if lines exist
        except Exception:
            pass
    
    # Build suggestions for fields that need review
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
        "entry_id": str(entry.id),
        "entry_number": entry.entry_number,
        "shipment_id": shipment_id,
        "status": entry.status,
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

