"""
Entry API Routes.

CRUD operations and workflow endpoints for customs entries.

Task 1.2 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.entry import (
    Entry, EntryLine, EntryDocument, EntryParty, EntryStatusHistory,
    EntryStatus, EntryType, PartyRole
)
from app.models.document_metadata import DocumentMetadata
from app.models.extraction_result import ExtractionResult

router = APIRouter(prefix="/api/entries", tags=["Entries"])


# ==================== Request/Response Models ====================

class EntryLineCreate(BaseModel):
    """Create/update entry line."""
    line_number: int = Field(ge=1)
    hts_code: Optional[str] = None
    product_description: Optional[str] = None
    country_of_origin: Optional[str] = None
    manufacturer_name: Optional[str] = None
    quantity_1: Optional[float] = None
    uom_1: Optional[str] = None
    entered_value: Optional[float] = None
    duty_rate: Optional[float] = None
    fta_code: Optional[str] = None


class EntryPartyCreate(BaseModel):
    """Create entry party."""
    role: str
    name: str
    address_line_1: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    cbp_number: Optional[str] = None


class EntryLineCreateInline(BaseModel):
    """Line item to create with entry (for wizard)."""
    line_number: int = Field(ge=1)
    hts_code: Optional[str] = None
    hts_description: Optional[str] = None
    product_description: Optional[str] = None
    country_of_origin: Optional[str] = None
    quantity: Optional[float] = None
    unit_of_measure: Optional[str] = None
    unit_value: Optional[float] = None
    entered_value: Optional[float] = None
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None


class EntryCreate(BaseModel):
    """Create new entry."""
    entry_type: str = EntryType.CONSUMPTION.value
    port_of_entry: Optional[str] = None
    entry_date: Optional[datetime] = None
    importer_of_record_number: Optional[str] = None
    importer_of_record_name: Optional[str] = None
    bill_of_lading: Optional[str] = None
    mode_of_transport: Optional[str] = None
    client_id: Optional[str] = None
    internal_reference: Optional[str] = None
    notes: Optional[str] = None
    # For wizard - include line items with entry creation
    line_items: Optional[List[EntryLineCreateInline]] = None


class EntryUpdate(BaseModel):
    """Update entry fields."""
    entry_type: Optional[str] = None
    port_of_entry: Optional[str] = None
    port_of_unlading: Optional[str] = None
    entry_date: Optional[datetime] = None
    import_date: Optional[datetime] = None
    importer_of_record_number: Optional[str] = None
    importer_of_record_name: Optional[str] = None
    ultimate_consignee_name: Optional[str] = None
    bill_of_lading: Optional[str] = None
    master_bill: Optional[str] = None
    house_bill: Optional[str] = None
    vessel_name: Optional[str] = None
    carrier_code: Optional[str] = None
    mode_of_transport: Optional[str] = None
    bond_type: Optional[str] = None
    bond_number: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    internal_reference: Optional[str] = None
    notes: Optional[str] = None


class EntryFromDocumentsRequest(BaseModel):
    """Create entry from extracted documents."""
    document_ids: List[str]
    client_id: Optional[str] = None


class EntryValidationResponse(BaseModel):
    """Entry validation result."""
    valid: bool
    filing_ready: bool = False
    errors: List[dict] = []
    warnings: List[dict] = []
    info: List[dict] = []
    error_count: int = 0
    warning_count: int = 0
    summary: str = ""


class EntryListResponse(BaseModel):
    """Paginated entry list."""
    count: int
    total: int
    offset: int
    limit: int
    entries: List[dict]


# ==================== CRUD Endpoints ====================

@router.post("", status_code=201)
async def create_entry(
    request: EntryCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new customs entry.
    
    Entry starts in DRAFT status.
    Optionally include line_items to create entry with lines in one call.
    """
    entry = Entry(
        entry_type=request.entry_type,
        port_of_entry=request.port_of_entry,
        entry_date=request.entry_date,
        importer_of_record_number=request.importer_of_record_number,
        importer_of_record_name=request.importer_of_record_name,
        bill_of_lading=request.bill_of_lading,
        mode_of_transport=request.mode_of_transport,
        internal_reference=request.internal_reference,
        notes=request.notes,
        status=EntryStatus.DRAFT.value,
    )
    
    if request.client_id:
        try:
            entry.client_id = UUID(request.client_id)
        except ValueError:
            pass
    
    db.add(entry)
    await db.flush()  # Get entry ID before creating history
    
    # Create line items if provided (wizard flow)
    total_entered_value = 0
    if request.line_items:
        for line_data in request.line_items:
            entered_value = line_data.entered_value
            if entered_value is None and line_data.quantity and line_data.unit_value:
                entered_value = line_data.quantity * line_data.unit_value
            
            line = EntryLine(
                entry_id=entry.id,
                line_number=line_data.line_number,
                hts_code=line_data.hts_code,
                hts_description=line_data.hts_description,
                product_description=line_data.product_description or line_data.hts_description,
                country_of_origin=line_data.country_of_origin,
                quantity_1=line_data.quantity,
                uom_1=line_data.unit_of_measure,
                gross_weight=line_data.gross_weight,
                net_weight=line_data.net_weight,
                entered_value=entered_value or 0,
            )
            db.add(line)
            total_entered_value += entered_value or 0
        
        # Update entry totals
        entry.line_count = len(request.line_items)
        entry.total_entered_value = total_entered_value
    
    # Create initial status history
    history = EntryStatusHistory(
        entry_id=entry.id,
        from_status=None,
        to_status=EntryStatus.DRAFT.value,
        changed_by="system",
        reason="Entry created" + (" with line items" if request.line_items else ""),
    )
    db.add(history)
    
    await db.commit()
    await db.refresh(entry)
    
    return {
        "id": str(entry.id),
        "entry_number": entry.entry_number,
        "status": entry.status,
        "line_count": entry.line_count,
        "total_entered_value": float(entry.total_entered_value) if entry.total_entered_value else 0,
        "created_at": entry.created_at.isoformat(),
    }


@router.get("")
async def list_entries(
    status: Optional[str] = Query(None, description="Filter by status"),
    client_id: Optional[str] = Query(None, description="Filter by client"),
    port: Optional[str] = Query(None, description="Filter by port of entry"),
    search: Optional[str] = Query(None, description="Search entry number, BOL, importer"),
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> EntryListResponse:
    """
    List entries with filtering and pagination.
    """
    query = select(Entry)
    count_query = select(func.count(Entry.id))
    
    # Apply filters
    if status:
        query = query.where(Entry.status == status)
        count_query = count_query.where(Entry.status == status)
    
    if client_id:
        try:
            client_uuid = UUID(client_id)
            query = query.where(Entry.client_id == client_uuid)
            count_query = count_query.where(Entry.client_id == client_uuid)
        except ValueError:
            pass
    
    if port:
        query = query.where(Entry.port_of_entry == port)
        count_query = count_query.where(Entry.port_of_entry == port)
    
    if search:
        search_filter = or_(
            Entry.entry_number.ilike(f"%{search}%"),
            Entry.bill_of_lading.ilike(f"%{search}%"),
            Entry.importer_of_record_name.ilike(f"%{search}%"),
            Entry.internal_reference.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    if date_from:
        query = query.where(Entry.entry_date >= date_from)
        count_query = count_query.where(Entry.entry_date >= date_from)
    
    if date_to:
        query = query.where(Entry.entry_date <= date_to)
        count_query = count_query.where(Entry.entry_date <= date_to)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Get entries
    query = query.order_by(Entry.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    entries = result.scalars().all()
    
    return EntryListResponse(
        count=len(entries),
        total=total,
        offset=offset,
        limit=limit,
        entries=[
            {
                "id": str(e.id),
                "entry_number": e.entry_number,
                "entry_type": e.entry_type,
                "status": e.status,
                "port_of_entry": e.port_of_entry,
                "importer_name": e.importer_of_record_name,
                "entry_date": e.entry_date.isoformat() if e.entry_date else None,
                "total_entered_value": float(e.total_entered_value) if e.total_entered_value else 0,
                "total_duty": float(e.total_duty) if e.total_duty else 0,
                "total_amount_due": float(e.total_amount_due) if e.total_amount_due else 0,
                "line_count": e.line_count,
                "bill_of_lading": e.bill_of_lading,
                "assigned_to": e.assigned_to,
                "created_at": e.created_at.isoformat(),
                "updated_at": e.updated_at.isoformat(),
            }
            for e in entries
        ],
    )


@router.get("/{entry_id}")
async def get_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get entry with all details including lines, parties, and documents.
    """
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    result = await db.execute(
        select(Entry)
        .options(
            selectinload(Entry.lines),
            selectinload(Entry.parties),
            selectinload(Entry.documents),
            selectinload(Entry.status_history),
        )
        .where(Entry.id == entry_uuid)
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    return {
        "id": str(entry.id),
        "entry_number": entry.entry_number,
        "entry_type": entry.entry_type,
        "filer_code": entry.filer_code,
        "status": entry.status,
        
        # Dates
        "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
        "import_date": entry.import_date.isoformat() if entry.import_date else None,
        "release_date": entry.release_date.isoformat() if entry.release_date else None,
        
        # Port info
        "port_of_entry": entry.port_of_entry,
        "port_of_unlading": entry.port_of_unlading,
        
        # Transport
        "mode_of_transport": entry.mode_of_transport,
        "carrier_code": entry.carrier_code,
        "vessel_name": entry.vessel_name,
        "voyage_flight_number": entry.voyage_flight_number,
        "bill_of_lading": entry.bill_of_lading,
        "master_bill": entry.master_bill,
        "house_bill": entry.house_bill,
        "container_numbers": entry.container_numbers,
        
        # Importer
        "importer_of_record_number": entry.importer_of_record_number,
        "importer_of_record_name": entry.importer_of_record_name,
        "ultimate_consignee_name": entry.ultimate_consignee_name,
        
        # Bond
        "bond_type": entry.bond_type,
        "bond_number": entry.bond_number,
        "surety_code": entry.surety_code,
        
        # Values
        "total_entered_value": float(entry.total_entered_value) if entry.total_entered_value else 0,
        "total_dutiable_value": float(entry.total_dutiable_value) if entry.total_dutiable_value else 0,
        "total_duty": float(entry.total_duty) if entry.total_duty else 0,
        "mpf_amount": float(entry.mpf_amount) if entry.mpf_amount else 0,
        "hmf_amount": float(entry.hmf_amount) if entry.hmf_amount else 0,
        "section_301_amount": float(entry.section_301_amount) if entry.section_301_amount else 0,
        "section_232_amount": float(entry.section_232_amount) if entry.section_232_amount else 0,
        "add_amount": float(entry.add_amount) if entry.add_amount else 0,
        "cvd_amount": float(entry.cvd_amount) if entry.cvd_amount else 0,
        "total_amount_due": float(entry.total_amount_due) if entry.total_amount_due else 0,
        "currency": entry.currency,
        
        # Lines
        "line_count": entry.line_count,
        "lines": [
            {
                "id": str(line.id),
                "line_number": line.line_number,
                "hts_code": line.hts_code,
                "hts_description": line.hts_description,
                "product_description": line.product_description,
                "country_of_origin": line.country_of_origin,
                "manufacturer_name": line.manufacturer_name,
                "quantity_1": float(line.quantity_1) if line.quantity_1 else None,
                "uom_1": line.uom_1,
                "entered_value": float(line.entered_value) if line.entered_value else 0,
                "duty_rate": float(line.duty_rate) if line.duty_rate else None,
                "duty_amount": float(line.duty_amount) if line.duty_amount else 0,
                "total_line_duty": float(line.total_line_duty) if line.total_line_duty else 0,
                "fta_code": line.fta_code,
                "fta_eligible": line.fta_eligible,
            }
            for line in sorted(entry.lines, key=lambda x: x.line_number)
        ],
        
        # Parties
        "parties": [
            {
                "id": str(p.id),
                "role": p.role,
                "name": p.name,
                "address_line_1": p.address_line_1,
                "city": p.city,
                "state_province": p.state_province,
                "postal_code": p.postal_code,
                "country": p.country,
                "cbp_number": p.cbp_number,
            }
            for p in entry.parties
        ],
        
        # Documents
        "documents": [
            {
                "id": str(d.id),
                "document_id": str(d.document_id),
                "document_type": d.document_type,
                "is_primary": d.is_primary,
                "added_by": d.added_by,
            }
            for d in entry.documents
        ],
        
        # Status history
        "status_history": [
            {
                "from_status": h.from_status,
                "to_status": h.to_status,
                "changed_by": h.changed_by,
                "changed_at": h.changed_at.isoformat(),
                "reason": h.reason,
            }
            for h in sorted(entry.status_history, key=lambda x: x.changed_at, reverse=True)
        ],
        
        # Workflow
        "assigned_to": entry.assigned_to,
        "internal_reference": entry.internal_reference,
        "notes": entry.notes,
        
        # Flags
        "is_ftz": entry.is_ftz,
        "has_add_cvd": entry.has_add_cvd,
        "is_reconciliation_flagged": entry.is_reconciliation_flagged,
        "requires_license": entry.requires_license,
        
        # Timestamps
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
    }


@router.put("/{entry_id}")
async def update_entry(
    entry_id: str,
    request: EntryUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update entry fields.
    """
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    result = await db.execute(
        select(Entry).where(Entry.id == entry_uuid)
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Update fields
    update_data = request.dict(exclude_unset=True)
    
    old_status = entry.status
    
    for key, value in update_data.items():
        if hasattr(entry, key) and value is not None:
            setattr(entry, key, value)
    
    # Track status change
    if "status" in update_data and update_data["status"] != old_status:
        history = EntryStatusHistory(
            entry_id=entry.id,
            from_status=old_status,
            to_status=update_data["status"],
            changed_by="user",  # TODO: Get from auth
            reason="Manual status update",
        )
        db.add(history)
    
    await db.commit()
    await db.refresh(entry)
    
    return {"id": str(entry.id), "status": entry.status, "updated_at": entry.updated_at.isoformat()}


@router.delete("/{entry_id}")
async def delete_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete (soft-delete via status) an entry.
    """
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    result = await db.execute(
        select(Entry).where(Entry.id == entry_uuid)
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Soft delete - change status to cancelled
    old_status = entry.status
    entry.status = EntryStatus.CANCELLED.value
    
    history = EntryStatusHistory(
        entry_id=entry.id,
        from_status=old_status,
        to_status=EntryStatus.CANCELLED.value,
        changed_by="user",
        reason="Entry deleted",
    )
    db.add(history)
    
    await db.commit()
    
    return {"id": str(entry.id), "status": "cancelled"}


# ==================== Line Items ====================

@router.post("/{entry_id}/lines")
async def add_entry_line(
    entry_id: str,
    request: EntryLineCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a line item to an entry.
    """
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    result = await db.execute(
        select(Entry).where(Entry.id == entry_uuid)
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Create line
    line = EntryLine(
        entry_id=entry.id,
        line_number=request.line_number,
        hts_code=request.hts_code,
        product_description=request.product_description,
        country_of_origin=request.country_of_origin,
        manufacturer_name=request.manufacturer_name,
        quantity_1=request.quantity_1,
        uom_1=request.uom_1,
        entered_value=request.entered_value,
        fta_code=request.fta_code,
    )
    
    # Calculate duties if we have HTS and value
    if request.hts_code and request.entered_value:
        from app.services.duty_calculator_service import DutyCalculatorService
        
        calc = DutyCalculatorService(db)
        duty_result = await calc.calculate_line_duty(
            hts_code=request.hts_code,
            entered_value=request.entered_value,
            quantity=request.quantity_1 or 1,
            country_of_origin=request.country_of_origin or "",
            fta_code=request.fta_code,
        )
        
        line.duty_rate = float(duty_result.base_duty_rate) if duty_result.base_duty_rate else None
        line.duty_amount = float(duty_result.base_duty_amount)
        line.section_301_rate = float(duty_result.section_301_rate) if duty_result.section_301_rate else None
        line.section_301_duty = float(duty_result.section_301_amount)
        line.total_line_duty = float(duty_result.total_duty)
        line.hts_description = duty_result.hts_description
        line.fta_eligible = duty_result.fta_eligible
    
    db.add(line)
    
    # Update entry totals
    from decimal import Decimal
    entry.line_count = (entry.line_count or 0) + 1
    current_value = entry.total_entered_value or Decimal("0")
    new_value = Decimal(str(request.entered_value)) if request.entered_value else Decimal("0")
    entry.total_entered_value = current_value + new_value
    
    await db.commit()
    await db.refresh(line)
    
    return {
        "id": str(line.id),
        "line_number": line.line_number,
        "hts_code": line.hts_code,
        "duty_amount": float(line.duty_amount) if line.duty_amount else 0,
        "total_line_duty": float(line.total_line_duty) if line.total_line_duty else 0,
    }


@router.get("/{entry_id}/lines")
async def get_entry_lines(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all line items for an entry.
    """
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    result = await db.execute(
        select(EntryLine)
        .where(EntryLine.entry_id == entry_uuid)
        .order_by(EntryLine.line_number)
    )
    lines = result.scalars().all()
    
    return {
        "entry_id": entry_id,
        "count": len(lines),
        "lines": [
            {
                "id": str(line.id),
                "line_number": line.line_number,
                "hts_code": line.hts_code,
                "hts_description": line.hts_description,
                "product_description": line.product_description,
                "country_of_origin": line.country_of_origin,
                "quantity_1": float(line.quantity_1) if line.quantity_1 else None,
                "uom_1": line.uom_1,
                "entered_value": float(line.entered_value) if line.entered_value else 0,
                "duty_rate": float(line.duty_rate) if line.duty_rate else None,
                "duty_amount": float(line.duty_amount) if line.duty_amount else 0,
                "section_301_duty": float(line.section_301_duty) if line.section_301_duty else 0,
                "total_line_duty": float(line.total_line_duty) if line.total_line_duty else 0,
                "fta_code": line.fta_code,
                "fta_eligible": line.fta_eligible,
            }
            for line in lines
        ],
    }


# ==================== Documents ====================

class LinkDocumentsRequest(BaseModel):
    """Link documents to entry request."""
    document_ids: List[str]
    auto_populate: bool = True  # Automatically populate entry fields from extraction data


class ExtractionSuggestion(BaseModel):
    """Field suggestion from extraction."""
    field_name: str
    current_value: Optional[str] = None
    suggested_value: str
    confidence: float
    source_document_id: str
    source_document_type: Optional[str] = None


@router.post("/{entry_id}/documents")
async def link_documents(
    entry_id: str,
    request: LinkDocumentsRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Link documents to an entry with optional auto-population.
    
    Returns extraction suggestions for fields that differ from current values.
    """
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    result = await db.execute(
        select(Entry).where(Entry.id == entry_uuid)
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    linked = []
    suggestions = []
    extraction_data = {}
    
    # Field mapping from extraction to entry
    field_mapping = {
        "importer_name": "importer_of_record_name",
        "importer_of_record_name": "importer_of_record_name",
        "importer": "importer_of_record_name",
        "consignee_name": "ultimate_consignee_name",
        "consignee": "ultimate_consignee_name",
        "bol_number": "bill_of_lading",
        "bill_of_lading": "bill_of_lading",
        "vessel_name": "vessel_name",
        "port_of_entry": "port_of_entry",
        "carrier_code": "carrier_code",
        "carrier": "carrier_code",
        "port_of_discharge": "port_of_unlading",
        "seller_name": None,  # Goes to party
        "manufacturer_name": None,  # Goes to party
    }
    
    for doc_id in request.document_ids:
        try:
            doc_uuid = UUID(doc_id)
            
            # Check document exists
            doc_result = await db.execute(
                select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
            )
            doc = doc_result.scalar_one_or_none()
            
            if not doc:
                continue
            
            # Check not already linked
            existing = await db.execute(
                select(EntryDocument).where(
                    EntryDocument.entry_id == entry.id,
                    EntryDocument.document_id == doc_uuid,
                )
            )
            if existing.scalar_one_or_none():
                continue
            
            # Get extraction data
            ext_result = await db.execute(
                select(ExtractionResult).where(
                    ExtractionResult.document_id == doc_uuid,
                    ExtractionResult.extraction_type == "template",
                )
            )
            extractions = ext_result.scalars().all()
            
            for ext in extractions:
                field = ext.field_name.lower().replace(" ", "_")
                entry_field = field_mapping.get(field, field)
                
                if entry_field and hasattr(entry, entry_field):
                    current = getattr(entry, entry_field)
                    suggested = ext.field_value
                    
                    # Clean JSON-encoded strings
                    if isinstance(suggested, str) and suggested.startswith('"'):
                        suggested = suggested.strip('"')
                    
                    # Track best extraction per field
                    if field not in extraction_data or (ext.confidence or 0) > extraction_data[field].get("confidence", 0):
                        extraction_data[field] = {
                            "entry_field": entry_field,
                            "value": suggested,
                            "confidence": ext.confidence or 0,
                            "source_doc": doc_id,
                            "source_type": doc.document_type,
                        }
                    
                    # Add suggestion if different from current
                    if suggested and str(suggested) != str(current):
                        suggestions.append({
                            "field_name": entry_field,
                            "current_value": str(current) if current else None,
                            "suggested_value": str(suggested),
                            "confidence": ext.confidence or 0,
                            "source_document_id": doc_id,
                            "source_document_type": doc.document_type,
                        })
            
            # Create link
            entry_doc = EntryDocument(
                entry_id=entry.id,
                document_id=doc_uuid,
                document_type=doc.document_type,
                added_by="user",
            )
            db.add(entry_doc)
            linked.append(doc_id)
            
        except ValueError:
            continue
    
    # Auto-populate if requested
    fields_updated = []
    if request.auto_populate and extraction_data:
        for field, data in extraction_data.items():
            entry_field = data["entry_field"]
            current = getattr(entry, entry_field, None)
            
            # Only populate empty fields or if confidence is very high
            if not current or data["confidence"] > 0.95:
                if hasattr(entry, entry_field):
                    setattr(entry, entry_field, data["value"])
                    fields_updated.append(entry_field)
    
    await db.commit()
    
    # Deduplicate suggestions
    unique_suggestions = {}
    for s in suggestions:
        key = s["field_name"]
        if key not in unique_suggestions or s["confidence"] > unique_suggestions[key]["confidence"]:
            unique_suggestions[key] = s
    
    return {
        "entry_id": entry_id,
        "linked_count": len(linked),
        "linked_documents": linked,
        "fields_updated": fields_updated,
        "suggestions": list(unique_suggestions.values()),
    }


@router.delete("/{entry_id}/documents/{document_id}")
async def unlink_document(
    entry_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Unlink a document from an entry.
    """
    try:
        entry_uuid = UUID(entry_id)
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    result = await db.execute(
        select(EntryDocument).where(
            EntryDocument.entry_id == entry_uuid,
            EntryDocument.document_id == doc_uuid,
        )
    )
    link = result.scalar_one_or_none()
    
    if not link:
        raise HTTPException(status_code=404, detail="Document link not found")
    
    await db.delete(link)
    await db.commit()
    
    return {
        "entry_id": entry_id,
        "document_id": document_id,
        "unlinked": True,
    }


@router.get("/{entry_id}/documents")
async def get_entry_documents(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all documents linked to an entry.
    """
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    result = await db.execute(
        select(EntryDocument)
        .where(EntryDocument.entry_id == entry_uuid)
    )
    links = result.scalars().all()
    
    documents = []
    for link in links:
        # Get document details
        doc_result = await db.execute(
            select(DocumentMetadata).where(DocumentMetadata.id == link.document_id)
        )
        doc = doc_result.scalar_one_or_none()
        
        documents.append({
            "id": str(link.document_id),
            "document_type": link.document_type,
            "is_primary": link.is_primary,
            "added_by": link.added_by,
            "added_at": link.created_at.isoformat() if link.created_at else None,
            "filename": doc.original_filename if doc else None,
            "storage_path": doc.storage_path if doc else None,
        })
    
    return {
        "entry_id": entry_id,
        "count": len(documents),
        "documents": documents,
    }


@router.get("/{entry_id}/extraction-suggestions")
async def get_extraction_suggestions(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all extraction suggestions from linked documents.
    
    Useful for reviewing what data could be populated from documents.
    """
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    result = await db.execute(
        select(Entry)
        .options(selectinload(Entry.documents))
        .where(Entry.id == entry_uuid)
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    suggestions = []
    conflicts = []
    
    field_mapping = {
        "importer_name": "importer_of_record_name",
        "importer_of_record_name": "importer_of_record_name",
        "consignee_name": "ultimate_consignee_name",
        "bol_number": "bill_of_lading",
        "bill_of_lading": "bill_of_lading",
        "vessel_name": "vessel_name",
        "port_of_entry": "port_of_entry",
        "carrier_code": "carrier_code",
    }
    
    # Collect all extractions from linked documents
    field_values = {}  # field -> list of (value, confidence, doc_id, doc_type)
    
    for entry_doc in entry.documents:
        ext_result = await db.execute(
            select(ExtractionResult).where(
                ExtractionResult.document_id == entry_doc.document_id,
                ExtractionResult.extraction_type == "template",
            )
        )
        extractions = ext_result.scalars().all()
        
        for ext in extractions:
            field = ext.field_name.lower().replace(" ", "_")
            entry_field = field_mapping.get(field, field)
            
            if entry_field and hasattr(entry, entry_field):
                if entry_field not in field_values:
                    field_values[entry_field] = []
                
                value = ext.field_value
                if isinstance(value, str) and value.startswith('"'):
                    value = value.strip('"')
                
                field_values[entry_field].append({
                    "value": value,
                    "confidence": ext.confidence or 0,
                    "document_id": str(entry_doc.document_id),
                    "document_type": entry_doc.document_type,
                })
    
    # Analyze each field
    for entry_field, values in field_values.items():
        current = getattr(entry, entry_field, None)
        
        # Get unique values
        unique_values = set(v["value"] for v in values if v["value"])
        
        if len(unique_values) > 1:
            # Conflict - same field has different values from different docs
            conflicts.append({
                "field_name": entry_field,
                "current_value": str(current) if current else None,
                "conflicting_values": [
                    {
                        "value": v["value"],
                        "confidence": v["confidence"],
                        "source_document_id": v["document_id"],
                        "source_document_type": v["document_type"],
                    }
                    for v in values
                ],
            })
        elif len(unique_values) == 1:
            best = max(values, key=lambda x: x["confidence"])
            if best["value"] != str(current) if current else None:
                suggestions.append({
                    "field_name": entry_field,
                    "current_value": str(current) if current else None,
                    "suggested_value": best["value"],
                    "confidence": best["confidence"],
                    "source_document_id": best["document_id"],
                    "source_document_type": best["document_type"],
                })
    
    return {
        "entry_id": entry_id,
        "suggestions": suggestions,
        "conflicts": conflicts,
        "total_linked_documents": len(entry.documents),
    }


@router.post("/{entry_id}/apply-suggestion")
async def apply_suggestion(
    entry_id: str,
    field_name: str,
    value: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Apply a suggested value to an entry field.
    """
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    result = await db.execute(
        select(Entry).where(Entry.id == entry_uuid)
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    if not hasattr(entry, field_name):
        raise HTTPException(status_code=400, detail=f"Invalid field name: {field_name}")
    
    old_value = getattr(entry, field_name)
    setattr(entry, field_name, value)
    
    await db.commit()
    
    return {
        "entry_id": entry_id,
        "field_name": field_name,
        "old_value": old_value,
        "new_value": value,
        "applied": True,
    }


# ==================== Create from Documents ====================

@router.post("/from-documents")
async def create_entry_from_documents(
    request: EntryFromDocumentsRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create an entry from extracted document data.
    
    Merges extraction results from multiple documents
    (e.g., commercial invoice + BOL) into a single entry.
    """
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="No document IDs provided")
    
    # Collect extraction data from all documents
    extraction_data = {}
    doc_links = []
    
    for doc_id in request.document_ids:
        try:
            doc_uuid = UUID(doc_id)
            
            # Get document
            doc_result = await db.execute(
                select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
            )
            doc = doc_result.scalar_one_or_none()
            
            if not doc:
                continue
            
            doc_links.append({
                "id": doc_uuid,
                "type": doc.document_type,
            })
            
            # Get extractions
            ext_result = await db.execute(
                select(ExtractionResult).where(
                    ExtractionResult.document_id == doc_uuid,
                    ExtractionResult.extraction_type == "template",
                )
            )
            extractions = ext_result.scalars().all()
            
            for ext in extractions:
                field = ext.field_name.lower()
                if field not in extraction_data or (ext.confidence or 0) > (extraction_data[field].get("confidence", 0)):
                    extraction_data[field] = {
                        "value": ext.field_value,
                        "confidence": ext.confidence,
                        "source_doc": doc_id,
                    }
                    
        except ValueError:
            continue
    
    if not doc_links:
        raise HTTPException(status_code=404, detail="No valid documents found")
    
    # Create entry from extracted data
    entry = Entry(
        status=EntryStatus.DRAFT.value,
        entry_type=EntryType.CONSUMPTION.value,
    )
    
    # Map extracted fields to entry fields
    field_mapping = {
        "importer_name": "importer_of_record_name",
        "importer_of_record_name": "importer_of_record_name",
        "importer": "importer_of_record_name",
        "consignee_name": "ultimate_consignee_name",
        "consignee": "ultimate_consignee_name",
        "bol_number": "bill_of_lading",
        "bill_of_lading": "bill_of_lading",
        "vessel_name": "vessel_name",
        "port_of_entry": "port_of_entry",
        "entry_date": "entry_date",
    }
    
    for extracted_field, entry_field in field_mapping.items():
        if extracted_field in extraction_data:
            value = extraction_data[extracted_field]["value"]
            if hasattr(entry, entry_field) and value:
                # Handle JSON-encoded strings
                if isinstance(value, str) and value.startswith('"'):
                    value = value.strip('"')
                setattr(entry, entry_field, value)
    
    if request.client_id:
        try:
            entry.client_id = UUID(request.client_id)
        except ValueError:
            pass
    
    db.add(entry)
    await db.flush()  # Get entry ID
    
    # Link documents
    for doc_link in doc_links:
        entry_doc = EntryDocument(
            entry_id=entry.id,
            document_id=doc_link["id"],
            document_type=doc_link["type"],
            is_primary=len(doc_links) == 1,
            added_by="system",
        )
        db.add(entry_doc)
    
    # Create status history
    history = EntryStatusHistory(
        entry_id=entry.id,
        from_status=None,
        to_status=EntryStatus.DRAFT.value,
        changed_by="system",
        reason=f"Entry created from {len(doc_links)} document(s)",
    )
    db.add(history)
    
    await db.commit()
    await db.refresh(entry)
    
    return {
        "id": str(entry.id),
        "status": entry.status,
        "documents_linked": len(doc_links),
        "fields_populated": list(extraction_data.keys()),
        "created_at": entry.created_at.isoformat(),
    }


# ==================== Validation & Calculation ====================

@router.post("/{entry_id}/validate")
async def validate_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
) -> EntryValidationResponse:
    """
    Validate entry for filing readiness.
    
    Runs comprehensive validation checks including:
    - Required CBP fields
    - HTS code format validation
    - Value reasonableness checks
    - Party information validation
    - ADD/CVD applicability warnings
    - Section 301 applicability checks
    """
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    result = await db.execute(
        select(Entry)
        .options(
            selectinload(Entry.lines),
            selectinload(Entry.parties),
        )
        .where(Entry.id == entry_uuid)
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Use comprehensive validation service
    from app.services.entry_validation_service import EntryValidationService
    
    validator = EntryValidationService(
        entry=entry,
        lines=entry.lines,
        parties=entry.parties,
    )
    validation_result = validator.validate()
    
    return EntryValidationResponse(
        valid=validation_result.valid,
        filing_ready=validation_result.filing_ready,
        errors=[e.to_dict() for e in validation_result.errors],
        warnings=[w.to_dict() for w in validation_result.warnings],
        info=[i.to_dict() for i in validation_result.info],
        error_count=len(validation_result.errors),
        warning_count=len(validation_result.warnings),
        summary=validation_result.summary,
    )


@router.post("/{entry_id}/calculate")
async def calculate_entry_duties(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate/recalculate all duties and fees for an entry.
    """
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    result = await db.execute(
        select(Entry)
        .options(selectinload(Entry.lines))
        .where(Entry.id == entry_uuid)
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    from app.services.duty_calculator_service import DutyCalculatorService
    
    calc = DutyCalculatorService(db)
    
    # Calculate each line
    for line in entry.lines:
        if line.hts_code and line.entered_value:
            duty_result = await calc.calculate_line_duty(
                hts_code=line.hts_code,
                entered_value=float(line.entered_value),
                quantity=float(line.quantity_1) if line.quantity_1 else 1,
                country_of_origin=line.country_of_origin or "",
                fta_code=line.fta_code,
            )
            
            line.duty_rate = float(duty_result.base_duty_rate) if duty_result.base_duty_rate else None
            line.duty_amount = float(duty_result.base_duty_amount)
            line.section_301_rate = float(duty_result.section_301_rate) if duty_result.section_301_rate else None
            line.section_301_duty = float(duty_result.section_301_amount)
            line.section_232_rate = float(duty_result.section_232_rate) if duty_result.section_232_rate else None
            line.section_232_duty = float(duty_result.section_232_amount)
            line.add_rate = float(duty_result.add_rate) if duty_result.add_rate else None
            line.add_duty = float(duty_result.add_amount)
            line.cvd_rate = float(duty_result.cvd_rate) if duty_result.cvd_rate else None
            line.cvd_duty = float(duty_result.cvd_amount)
            line.total_line_duty = float(duty_result.total_duty)
            line.hts_description = duty_result.hts_description
            line.fta_eligible = duty_result.fta_eligible
    
    # Recalculate entry totals
    entry.calculate_totals()
    
    # Calculate MPF/HMF
    fee_result = calc.calculate_mpf(
        total_entered_value=float(entry.total_entered_value) if entry.total_entered_value else 0,
        line_count=entry.line_count,
        entry_type="formal" if entry.entry_type in ["01", "03", "06"] else "informal",
    )
    
    entry.mpf_amount = float(fee_result.mpf_amount)
    entry.hmf_amount = float(fee_result.hmf_amount)
    entry.total_fee = float(fee_result.mpf_amount + fee_result.hmf_amount)
    
    # Grand total
    entry.total_amount_due = (
        (entry.total_duty or 0) +
        (entry.mpf_amount or 0) +
        (entry.hmf_amount or 0) +
        (entry.section_301_amount or 0) +
        (entry.section_232_amount or 0) +
        (entry.add_amount or 0) +
        (entry.cvd_amount or 0)
    )
    
    await db.commit()
    await db.refresh(entry)
    
    return {
        "id": str(entry.id),
        "total_entered_value": float(entry.total_entered_value) if entry.total_entered_value else 0,
        "total_duty": float(entry.total_duty) if entry.total_duty else 0,
        "mpf_amount": float(entry.mpf_amount) if entry.mpf_amount else 0,
        "hmf_amount": float(entry.hmf_amount) if entry.hmf_amount else 0,
        "section_301_amount": float(entry.section_301_amount) if entry.section_301_amount else 0,
        "section_232_amount": float(entry.section_232_amount) if entry.section_232_amount else 0,
        "add_amount": float(entry.add_amount) if entry.add_amount else 0,
        "cvd_amount": float(entry.cvd_amount) if entry.cvd_amount else 0,
        "total_amount_due": float(entry.total_amount_due) if entry.total_amount_due else 0,
        "line_count": entry.line_count,
    }


# ==================== Export Endpoints ====================

@router.get("/{entry_id}/export/cbp7501")
async def export_cbp_7501(
    entry_id: str,
    format: str = Query("pdf", description="Export format: pdf or json"),
    db: AsyncSession = Depends(get_db),
):
    """
    Export entry as CBP Form 7501 (Entry Summary).
    
    Generates an official-format CBP 7501 document from the entry data.
    
    Args:
        entry_id: Entry UUID
        format: "pdf" (default) or "json" for data preview
        
    Returns:
        PDF file or JSON data
    
    Task 3.1 from ROADMAP_FULL_WORKFLOW.md
    """
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID format")
    
    # Verify entry exists
    result = await db.execute(
        select(Entry)
        .options(selectinload(Entry.lines))
        .where(Entry.id == entry_uuid)
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    if format == "json":
        # Return data preview
        return {
            "entry_id": str(entry.id),
            "entry_number": entry.entry_number,
            "entry_type": entry.entry_type,
            "form": "CBP Form 7501",
            "preview": True,
            "data": {
                "header": {
                    "entry_number": entry.entry_number,
                    "entry_type": entry.entry_type,
                    "port_of_entry": entry.port_of_entry,
                    "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
                },
                "importer": {
                    "name": entry.importer_of_record_name,
                    "number": entry.importer_of_record_number,
                    "consignee": entry.ultimate_consignee_name,
                },
                "transport": {
                    "mode": entry.mode_of_transport,
                    "carrier": entry.carrier_code,
                    "vessel": entry.vessel_name,
                    "bill_of_lading": entry.bill_of_lading,
                },
                "lines": [
                    {
                        "line": line.line_number,
                        "hts": line.hts_code,
                        "description": line.product_description or line.hts_description,
                        "origin": line.country_of_origin,
                        "value": float(line.entered_value or 0),
                        "duty": float(line.total_line_duty or 0),
                    }
                    for line in entry.lines
                ],
                "totals": {
                    "entered_value": float(entry.total_entered_value or 0),
                    "duty": float(entry.total_duty or 0),
                    "mpf": float(entry.mpf_amount or 0),
                    "hmf": float(entry.hmf_amount or 0),
                    "total_due": float(entry.total_amount_due or 0),
                },
            },
        }
    
    # Generate PDF
    try:
        from app.services.cbp7501_generator import generate_cbp_7501
        pdf_bytes = await generate_cbp_7501(db, entry_id)
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="PDF generation not available. Install reportlab: pip install reportlab"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
    
    # Return PDF
    from fastapi.responses import Response
    
    filename = f"CBP7501_{entry.entry_number or entry_id[:8]}.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )


@router.get("/{entry_id}/export/summary")
async def export_entry_summary(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Export a comprehensive entry summary.
    
    Returns all entry data in a structured format suitable for
    review, auditing, or transformation to other formats.
    """
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID format")
    
    result = await db.execute(
        select(Entry)
        .options(
            selectinload(Entry.lines),
            selectinload(Entry.documents),
            selectinload(Entry.parties),
        )
        .where(Entry.id == entry_uuid)
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    return {
        "id": str(entry.id),
        "entry_number": entry.entry_number,
        "entry_type": entry.entry_type,
        "status": entry.status,
        "created_at": entry.created_at.isoformat(),
        "entry_date": entry.entry_date.isoformat() if entry.entry_date else None,
        "port": {
            "entry": entry.port_of_entry,
            "unlading": entry.port_of_unlading,
            "destination": entry.destination_port,
        },
        "transport": {
            "mode": entry.mode_of_transport,
            "carrier": entry.carrier_code,
            "vessel": entry.vessel_name,
            "voyage": entry.voyage_flight_number,
            "bill_of_lading": entry.bill_of_lading,
            "containers": entry.container_numbers,
        },
        "parties": {
            "importer": {
                "name": entry.importer_of_record_name,
                "number": entry.importer_of_record_number,
            },
            "consignee": entry.ultimate_consignee_name,
            "additional": [
                {
                    "role": p.role,
                    "name": p.name,
                    "country": p.country,
                }
                for p in entry.parties
            ],
        },
        "lines": [
            {
                "line_number": line.line_number,
                "hts_code": line.hts_code,
                "description": line.product_description or line.hts_description,
                "country_of_origin": line.country_of_origin,
                "quantity": float(line.quantity_1 or 0),
                "uom": line.uom_1,
                "value": float(line.entered_value or 0),
                "duty": {
                    "rate": float(line.duty_rate or 0),
                    "base": float(line.duty_amount or 0),
                    "section_301": float(line.section_301_duty or 0),
                    "section_232": float(line.section_232_duty or 0),
                    "add": float(line.add_duty or 0),
                    "cvd": float(line.cvd_duty or 0),
                    "total": float(line.total_line_duty or 0),
                },
                "fta": {
                    "code": line.fta_code,
                    "eligible": line.fta_eligible,
                },
            }
            for line in entry.lines
        ],
        "totals": {
            "line_count": entry.line_count,
            "entered_value": float(entry.total_entered_value or 0),
            "dutiable_value": float(entry.total_dutiable_value or 0),
            "base_duty": float(entry.total_duty or 0),
            "section_301": float(entry.section_301_amount or 0),
            "section_232": float(entry.section_232_amount or 0),
            "add": float(entry.add_amount or 0),
            "cvd": float(entry.cvd_amount or 0),
            "mpf": float(entry.mpf_amount or 0),
            "hmf": float(entry.hmf_amount or 0),
            "total_due": float(entry.total_amount_due or 0),
        },
        "documents": [
            {
                "id": str(doc.document_id),
                "type": doc.document_type,
                "is_primary": doc.is_primary,
            }
            for doc in entry.documents
        ],
        "ace": {
            "entry_id": entry.ace_entry_id,
            "status": entry.ace_status,
            "filed_at": entry.filed_at.isoformat() if entry.filed_at else None,
        },
        "liquidation": {
            "date": entry.liquidation_date.isoformat() if entry.liquidation_date else None,
            "type": entry.liquidation_type,
            "amount": float(entry.liquidated_duty or 0) if entry.liquidated_duty else None,
        },
    }


@router.get("/{entry_id}/export/abi")
async def export_abi_message(
    entry_id: str,
    message_type: str = Query("SE", description="Message type: SE (Summary), AD (Add), RM (Replace)"),
    format: str = Query("json", description="Output format: json, raw"),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate ABI (Automated Broker Interface) message for ACE filing.
    
    Generates CBP CATAIR-compliant ABI records for electronic filing.
    
    Message Types:
    - SE: Entry Summary (primary filing)
    - AD: Add Entry (new entry)
    - RM: Replace Entry (amendment)
    
    Output Formats:
    - json: Structured JSON with records and validation
    - raw: Raw ABI message (fixed-width text)
    
    Task 3.2 from ROADMAP_FULL_WORKFLOW.md
    """
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID format")
    
    if message_type not in ["SE", "AD", "RM", "DE"]:
        raise HTTPException(status_code=400, detail="Invalid message type. Use SE, AD, RM, or DE")
    
    try:
        from app.services.abi_generator import generate_abi_message
        message = await generate_abi_message(db, entry_id, message_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ABI generation failed: {str(e)}")
    
    if format == "raw":
        # Return raw ABI text
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            content=message.to_abi_string(),
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename=ABI_{message_type}_{entry_id[:8]}.txt",
            },
        )
    
    # Return JSON with validation info
    response = message.to_dict()
    response["entry_id"] = entry_id
    response["filing_ready"] = message.validate()
    
    return response


@router.post("/{entry_id}/export/abi/download")
async def download_abi_file(
    entry_id: str,
    message_type: str = Query("SE", description="Message type: SE (Summary), AD (Add), RM (Replace)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Download ABI file for ACE submission.
    
    Returns a downloadable .abi file with proper headers.
    Use this for manual import into ACE-certified software.
    """
    from fastapi.responses import Response
    from app.services.abi_file_exporter import ABIFileExporter
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID format")
    
    if message_type not in ["SE", "AD", "RM", "DE"]:
        raise HTTPException(status_code=400, detail="Invalid message type. Use SE, AD, RM, or DE")
    
    try:
        exporter = ABIFileExporter(db)
        content, filename = await exporter.export_entry(entry_id, message_type)
        
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-ABI-Message-Type": message_type,
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ABI export failed: {str(e)}")


class BulkABIExportRequest(BaseModel):
    """Request for bulk ABI export."""
    entry_ids: List[str]
    message_type: str = "SE"


@router.post("/export/abi/bulk")
async def bulk_export_abi(
    request: BulkABIExportRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Export multiple entries as a ZIP archive of ABI files.
    
    Returns a ZIP containing individual .abi files for each entry.
    Includes a manifest file with export status.
    """
    from fastapi.responses import Response
    from app.services.abi_file_exporter import ABIFileExporter
    
    if not request.entry_ids:
        raise HTTPException(status_code=400, detail="No entry IDs provided")
    
    if len(request.entry_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 entries per bulk export")
    
    try:
        exporter = ABIFileExporter(db)
        zip_bytes, filename = await exporter.export_bulk(
            request.entry_ids,
            request.message_type
        )
        
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk export failed: {str(e)}")


@router.post("/{entry_id}/file/abi")
async def file_abi_message(
    entry_id: str,
    message_type: str = Query("SE", description="Message type"),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and store ABI message for filing.
    
    This prepares the entry for ACE submission by:
    1. Generating the ABI message
    2. Validating the message
    3. Storing for audit
    4. Updating entry status to READY_TO_FILE
    
    Note: Actual transmission to ACE requires separate implementation
    of the ACE Direct connection or via a certified software vendor.
    """
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID format")
    
    # Get entry
    result = await db.execute(
        select(Entry)
        .options(selectinload(Entry.lines))
        .where(Entry.id == entry_uuid)
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Check entry has required data
    if not entry.lines:
        raise HTTPException(status_code=400, detail="Entry has no line items")
    
    if not entry.port_of_entry:
        raise HTTPException(status_code=400, detail="Port of entry is required for filing")
    
    # Generate message
    from app.services.abi_generator import generate_abi_message
    message = await generate_abi_message(db, entry_id, message_type)
    
    # Validate
    is_valid = message.validate()
    
    if not is_valid:
        return {
            "success": False,
            "entry_id": entry_id,
            "message_type": message_type,
            "validation": {
                "is_valid": False,
                "errors": message.validation_errors,
                "warnings": message.validation_warnings,
            },
            "action_required": "Fix validation errors before filing",
        }
    
    # Store the ABI message in entry's ace_response for audit
    entry.ace_response = {
        "abi_message": message.to_abi_string(),
        "message_type": message_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(message.records),
    }
    
    # Update status to ready to file
    if entry.status in [EntryStatus.DRAFT.value, EntryStatus.PENDING_REVIEW.value]:
        old_status = entry.status
        entry.status = EntryStatus.READY_TO_FILE.value
        
        # Add status history
        history = EntryStatusHistory(
            entry_id=entry.id,
            from_status=old_status,
            to_status=EntryStatus.READY_TO_FILE.value,
            changed_by="system",
            reason=f"ABI {message_type} message generated and validated",
        )
        db.add(history)
    
    await db.commit()
    
    return {
        "success": True,
        "entry_id": entry_id,
        "message_type": message_type,
        "status": entry.status,
        "validation": {
            "is_valid": True,
            "errors": [],
            "warnings": message.validation_warnings,
        },
        "record_count": len(message.records),
        "message": "ABI message generated and stored. Entry ready for filing.",
        "next_steps": [
            "Review entry details",
            "Submit via ACE Direct or certified vendor",
            "Monitor ACE for acceptance/rejection",
        ],
    }


# ==================== ACE Status Tracking (Task 3.4) ====================

@router.get("/{entry_id}/ace-status")
async def get_ace_status(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get ACE status for an entry.
    
    Returns comprehensive status information including:
    - Current ACE status
    - Filing status
    - Status history
    - Rejection details if applicable
    """
    from app.services.ace_status_service import ACEStatusService
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    service = ACEStatusService(db)
    result = await service.get_entry_status(entry_uuid)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.post("/{entry_id}/file")
async def file_entry_to_ace(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit entry to ACE/CBP.
    
    Marks entry as filed and generates ACE entry ID.
    In production, this would transmit to ACE.
    """
    from app.services.ace_status_service import ACEStatusService
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    # Verify entry is ready to file
    query = select(Entry).where(Entry.id == entry_uuid)
    result = await db.execute(query)
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    if entry.status not in [EntryStatus.READY_TO_FILE.value, EntryStatus.DRAFT.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Entry status is '{entry.status}'. Must be 'ready_to_file' to submit."
        )
    
    service = ACEStatusService(db)
    result = await service.mark_filed(entry_uuid)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return {
        **result,
        "message": "Entry submitted to CBP/ACE",
        "next_steps": [
            "Monitor entry status for CBP response",
            "Entry will be accepted or rejected within 24-48 hours",
        ],
    }


@router.post("/{entry_id}/poll-ace")
async def poll_ace_status(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Poll ACE for status update (simulated).
    
    In production, this would call the ACE API to check status.
    For demo purposes, simulates status progression.
    """
    from app.services.ace_status_service import ACEStatusService
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    service = ACEStatusService(db)
    result = await service.simulate_ace_poll(entry_uuid)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/{entry_id}/resubmit")
async def resubmit_rejected_entry(
    entry_id: str,
    corrections: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Resubmit a rejected entry after corrections.
    
    Resets entry status so it can be filed again.
    """
    from app.services.ace_status_service import ACEStatusService
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    service = ACEStatusService(db)
    result = await service.resubmit_entry(entry_uuid, corrections)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/pending-status/list")
async def get_entries_pending_status(
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """
    Get entries that are pending ACE status updates.
    
    Useful for batch polling/monitoring.
    """
    from app.services.ace_status_service import ACEStatusService
    
    service = ACEStatusService(db)
    entries = await service.get_entries_pending_status(limit)
    
    return {
        "count": len(entries),
        "entries": entries,
    }


class SimulateACEResponseRequest(BaseModel):
    """Request to simulate an ACE response."""
    ace_status: str
    message: str = "Simulated ACE response"
    error_codes: Optional[List[str]] = None


@router.post("/{entry_id}/simulate-ace-response")
async def simulate_ace_response(
    entry_id: str,
    request: SimulateACEResponseRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Simulate an ACE response for testing.
    
    Allows testing different status scenarios:
    - accepted: CBP accepted the entry
    - rejected: CBP rejected with error codes
    - hold: CBP hold for examination
    - released: Cargo released
    - liquidated: Entry liquidated
    """
    from app.services.ace_status_service import (
        ACEStatusService, ACEStatus, ACEStatusMessage, ACEMessageType
    )
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    # Map string to enum
    try:
        ace_status = ACEStatus(request.ace_status)
    except ValueError:
        valid_statuses = [s.value for s in ACEStatus]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ACE status. Valid values: {valid_statuses}"
        )
    
    # Determine message type
    message_type_map = {
        ACEStatus.ACCEPTED: ACEMessageType.ACCEPTANCE,
        ACEStatus.REJECTED: ACEMessageType.REJECTION,
        ACEStatus.RELEASED: ACEMessageType.RELEASE,
        ACEStatus.HOLD: ACEMessageType.HOLD,
        ACEStatus.INTENSIVE_EXAM: ACEMessageType.HOLD,
        ACEStatus.LIQUIDATED: ACEMessageType.LIQUIDATION,
    }
    msg_type = message_type_map.get(ace_status, ACEMessageType.STATUS_UPDATE)
    
    message = ACEStatusMessage(
        message_type=msg_type,
        ace_status=ace_status,
        message=request.message,
        error_codes=request.error_codes or [],
    )
    
    service = ACEStatusService(db)
    result = await service.update_status(entry_uuid, ace_status, message, "Simulation")
    
    return result


# ==================== Entry Amendment (Task 3.5) ====================

class AmendmentChangeRequest(BaseModel):
    """Single field change in an amendment."""
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    change_type: str = "other"
    line_number: Optional[int] = None


class CreateAmendmentRequest(BaseModel):
    """Request to create an amendment."""
    changes: List[AmendmentChangeRequest]
    reason: str = "clerical_error"
    is_prior_disclosure: bool = False
    notes: Optional[str] = None


class PreviewAmendmentRequest(BaseModel):
    """Request to preview an amendment."""
    total_entered_value: Optional[float] = None
    importer_of_record_number: Optional[str] = None
    importer_of_record_name: Optional[str] = None
    lines: Optional[List[dict]] = None


@router.post("/{entry_id}/amend/preview")
async def preview_amendment(
    entry_id: str,
    request: PreviewAmendmentRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Preview what an amendment would look like without applying it.
    
    Compares proposed changes with current entry and returns:
    - List of differences
    - Estimated duty impact
    - Whether prior disclosure is recommended
    """
    from app.services.entry_amendment_service import preview_amendment as preview_amend
    
    try:
        proposed_changes = request.model_dump(exclude_none=True)
        result = await preview_amend(db, entry_id, proposed_changes)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{entry_id}/amend")
async def create_amendment(
    entry_id: str,
    request: CreateAmendmentRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create an amendment for an entry.
    
    Creates amendment record with:
    - Field changes tracked
    - Duty difference calculated
    - Prior disclosure flag
    """
    from app.services.entry_amendment_service import EntryAmendmentService
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    service = EntryAmendmentService(db)
    
    try:
        # Convert changes
        changes = [
            {
                "field_name": c.field_name,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "change_type": c.change_type,
                "line_number": c.line_number,
            }
            for c in request.changes
        ]
        
        amendment = await service.create_amendment(
            entry_id=entry_uuid,
            changes=changes,
            reason=request.reason,
            is_prior_disclosure=request.is_prior_disclosure,
            notes=request.notes or "",
            created_by="user",
        )
        
        return {
            "amendment": amendment.to_dict(),
            "message": "Amendment created successfully",
            "next_steps": [
                "Review amendment details",
                "Apply amendment to update entry",
                "Generate ABI RM message for submission",
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{entry_id}/amend/{amendment_id}/apply")
async def apply_amendment(
    entry_id: str,
    amendment_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Apply a created amendment to update the entry.
    
    Updates entry fields and recalculates totals.
    """
    from app.services.entry_amendment_service import EntryAmendmentService, Amendment, AmendmentReason
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    # For now, create a simple amendment (in production would fetch from DB)
    # This is a simplified flow for demo purposes
    service = EntryAmendmentService(db)
    
    # Get entry
    query = select(Entry).where(Entry.id == entry_uuid)
    result = await db.execute(query)
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Find amendment in ace_response.amendments
    if not entry.ace_response or "amendments" not in entry.ace_response:
        raise HTTPException(status_code=404, detail="Amendment not found")
    
    amendment_dict = next(
        (a for a in entry.ace_response.get("amendments", []) if a.get("id") == amendment_id),
        None
    )
    
    if not amendment_dict:
        # Create a dummy amendment for demo
        from app.services.entry_amendment_service import Amendment, FieldChange
        amendment = Amendment(
            id=amendment_id,
            entry_id=entry_id,
            amendment_number=1,
            reason=AmendmentReason.CLERICAL_ERROR,
            changes=[],
            original_duty=float(entry.total_amount_due or 0),
            amended_duty=float(entry.total_amount_due or 0),
        )
    else:
        from app.services.entry_amendment_service import Amendment, FieldChange, AmendmentReason
        amendment = Amendment(
            id=amendment_dict["id"],
            entry_id=amendment_dict["entry_id"],
            amendment_number=amendment_dict.get("amendment_number", 1),
            reason=AmendmentReason(amendment_dict.get("reason", "clerical_error")),
            is_prior_disclosure=amendment_dict.get("is_prior_disclosure", False),
            changes=[],
            original_duty=amendment_dict.get("original_duty", 0),
            amended_duty=amendment_dict.get("amended_duty", 0),
            duty_difference=amendment_dict.get("duty_difference", 0),
        )
    
    result = await service.apply_amendment(entry_uuid, amendment)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/{entry_id}/amend/generate-abi")
async def generate_amendment_abi(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate ABI RM (Replace/Modify) message for an amendment.
    
    Returns the ABI message in CATAIR format for submission.
    """
    from app.services.entry_amendment_service import EntryAmendmentService, Amendment
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    service = EntryAmendmentService(db)
    
    # Create placeholder amendment for ABI generation
    amendment = Amendment(
        id=str(uuid4()) if 'uuid4' in dir() else "temp-amendment",
        entry_id=entry_id,
    )
    
    try:
        result = await service.generate_amendment_abi(entry_uuid, amendment)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{entry_id}/amendments")
async def get_amendment_history(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all amendments for an entry.
    
    Returns chronological list of amendments with details.
    """
    from app.services.entry_amendment_service import EntryAmendmentService
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    service = EntryAmendmentService(db)
    amendments = await service.get_amendment_history(entry_uuid)
    
    return {
        "entry_id": entry_id,
        "amendment_count": len(amendments),
        "amendments": amendments,
    }


@router.post("/{entry_id}/amend/quick")
async def quick_amendment(
    entry_id: str,
    field: str = Query(..., description="Field to change"),
    old_value: str = Query(..., description="Current value"),
    new_value: str = Query(..., description="New value"),
    line_number: Optional[int] = Query(None, description="Line number if line-level change"),
    reason: str = Query("clerical_error", description="Amendment reason"),
    is_prior_disclosure: bool = Query(False, description="Prior disclosure flag"),
    db: AsyncSession = Depends(get_db),
):
    """
    Quick single-field amendment.
    
    Convenience endpoint for simple corrections.
    Creates amendment, applies it, and generates ABI message.
    """
    from app.services.entry_amendment_service import EntryAmendmentService
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    service = EntryAmendmentService(db)
    
    try:
        # Create amendment
        changes = [{
            "field_name": field,
            "old_value": old_value,
            "new_value": new_value,
            "change_type": "other",
            "line_number": line_number,
        }]
        
        amendment = await service.create_amendment(
            entry_id=entry_uuid,
            changes=changes,
            reason=reason,
            is_prior_disclosure=is_prior_disclosure,
            notes=f"Quick amendment: {field} from {old_value} to {new_value}",
            created_by="user",
        )
        
        # Apply amendment
        apply_result = await service.apply_amendment(entry_uuid, amendment)
        
        # Generate ABI
        abi_result = await service.generate_amendment_abi(entry_uuid, amendment)
        
        return {
            "amendment": amendment.to_dict(),
            "applied": apply_result,
            "abi_message": {
                "message_type": abi_result.get("message_type"),
                "record_count": abi_result.get("abi_message", {}).get("record_count"),
                "is_valid": abi_result.get("validation", {}).get("is_valid"),
            },
            "message": "Amendment created, applied, and ABI generated",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
