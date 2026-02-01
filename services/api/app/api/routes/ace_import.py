"""
ACE Import API Routes
Endpoints for uploading and querying CBP ACE entry data.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel

from app.core.database import get_db
from app.services.ace_importer_service import (
    ACEImporterService,
    ACEToEntryImporter,
    load_sample_ace_data,
    SAMPLE_ACE_DATA,
)

router = APIRouter(prefix="/api/ace", tags=["ACE Import"])


# ==================== Request/Response Models ====================

class ImportCSVRequest(BaseModel):
    """Request to import CSV content directly."""
    csv_content: str
    batch_id: Optional[str] = None


class ImportResult(BaseModel):
    """Result from import operation."""
    success: bool
    batch_id: str
    entries_parsed: int
    entries_saved: int
    total_value: float
    total_duty: float
    errors: list
    warnings: list


# ==================== Endpoints ====================

@router.post("/import/csv", response_model=ImportResult)
async def import_csv_content(
    request: ImportCSVRequest,
    db=Depends(get_db)
):
    """
    Import ACE entry data from CSV content.
    
    Accepts CSV with headers matching ACE/7501 fields:
    - entry_number, entry_date, entry_type
    - importer_name, importer_number
    - port_code, port_name
    - hts_code, description, country_of_origin
    - quantity, unit, entered_value, duty_rate, duty_amount
    
    Field names are normalized (e.g., 'HTS' → 'hts_code', 'Entry #' → 'entry_number')
    """
    service = ACEImporterService(db)
    result = await service.import_csv(request.csv_content, request.batch_id)
    return result


@router.post("/import/file")
async def import_csv_file(
    file: UploadFile = File(...),
    batch_id: Optional[str] = None,
    db=Depends(get_db)
):
    """
    Import ACE entry data from uploaded CSV file.
    
    Supports CSV and TSV files. Excel support requires pandas.
    """
    if not file.filename.lower().endswith(('.csv', '.tsv', '.txt')):
        raise HTTPException(400, "Only CSV/TSV files are supported")
    
    content = await file.read()
    csv_content = content.decode('utf-8-sig')  # Handle BOM
    
    service = ACEImporterService(db)
    result = await service.import_csv(csv_content, batch_id)
    result["filename"] = file.filename
    
    return result


@router.post("/import/sample")
async def import_sample_data(db=Depends(get_db)):
    """
    Load sample ACE data for demonstration.
    
    Creates 13 sample entry records across 6 unique entries with realistic data.
    """
    result = await load_sample_ace_data(db)
    return result


@router.get("/entries")
async def list_entries(
    batch_id: Optional[str] = Query(None, description="Filter by import batch"),
    importer: Optional[str] = Query(None, description="Filter by importer name"),
    hts_code: Optional[str] = Query(None, description="Filter by HTS code prefix"),
    country: Optional[str] = Query(None, description="Filter by country of origin"),
    date_from: Optional[str] = Query(None, description="Filter by entry date (from)"),
    date_to: Optional[str] = Query(None, description="Filter by entry date (to)"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db=Depends(get_db)
):
    """
    Query ACE entries with optional filters.
    
    Returns paginated list of entries with total count.
    """
    service = ACEImporterService(db)
    result = await service.get_entries(
        batch_id=batch_id,
        importer=importer,
        hts_code=hts_code,
        country=country,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset
    )
    return result


@router.get("/statistics")
async def get_statistics(
    batch_id: Optional[str] = Query(None, description="Filter by import batch"),
    db=Depends(get_db)
):
    """
    Get statistics for ACE entries.
    
    Returns:
    - Total entries and unique entry numbers
    - Total value and duty amounts
    - Lists of importers, ports, HTS codes, countries
    - Date range
    """
    service = ACEImporterService(db)
    result = await service.get_statistics(batch_id)
    return result


@router.get("/sample-data")
async def get_sample_data():
    """
    Get the sample ACE data CSV for reference.
    
    Returns the raw CSV content that would be imported by /import/sample.
    """
    return {
        "format": "csv",
        "rows": 13,
        "columns": ["entry_number", "entry_date", "entry_type", "importer_name", 
                    "port_name", "hts_code", "description", "country_of_origin",
                    "quantity", "unit", "entered_value", "duty_rate", "duty_amount"],
        "content": SAMPLE_ACE_DATA
    }


@router.get("/field-mappings")
async def get_field_mappings():
    """
    Get the field name mappings used for CSV normalization.

    Shows which column names are recognized for each standard field.
    """
    from app.services.ace_importer_service import FIELD_MAPPINGS

    return {
        "mappings": FIELD_MAPPINGS,
        "description": "Column names are case-insensitive and normalized (spaces/dashes become underscores)"
    }


# ==================== New Entry-Based Import Endpoints ====================

class EntryImportResult(BaseModel):
    """Result from Entry-based import."""
    success: bool
    batch_id: str
    entries_created: int
    lines_created: int
    total_value: float
    total_duty: float
    linked_shipments: int
    errors: list
    warnings: list
    entry_ids: list


@router.post("/import/to-entry", response_model=EntryImportResult)
async def import_csv_to_entry(
    request: ImportCSVRequest,
    link_to_shipment: bool = True,
    db=Depends(get_db)
):
    """
    Import ACE entry data into the unified Entry model.

    This is the preferred import method that creates proper Entry records:
    - Groups line items by entry_number (one Entry per unique number)
    - Sets source_type="ace_import" for tracking
    - Creates EntryLine records for each CSV row
    - Optionally links to existing Shipments

    Use this instead of /import/csv for new imports.
    """
    service = ACEToEntryImporter(db)
    result = await service.import_csv_to_entries(
        request.csv_content,
        request.batch_id,
        link_to_shipment=link_to_shipment
    )
    return result


@router.post("/import/file-to-entry")
async def import_file_to_entry(
    file: UploadFile = File(...),
    batch_id: Optional[str] = None,
    link_to_shipment: bool = True,
    db=Depends(get_db)
):
    """
    Import ACE entry data from uploaded file into Entry model.

    Creates proper Entry and EntryLine records.
    """
    if not file.filename.lower().endswith(('.csv', '.tsv', '.txt')):
        raise HTTPException(400, "Only CSV/TSV files are supported")

    content = await file.read()
    csv_content = content.decode('utf-8-sig')

    service = ACEToEntryImporter(db)
    result = await service.import_csv_to_entries(
        csv_content,
        batch_id,
        link_to_shipment=link_to_shipment
    )
    result["filename"] = file.filename

    return result


@router.get("/entries-unified")
async def list_unified_entries(
    source_type: Optional[str] = Query("ace_import", description="Filter by source type"),
    importer: Optional[str] = Query(None, description="Filter by importer name"),
    entry_number: Optional[str] = Query(None, description="Filter by entry number"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db=Depends(get_db)
):
    """
    Query entries from the unified Entry model.

    Returns entries with their line items.
    """
    from sqlalchemy import select, func, and_
    from sqlalchemy.orm import selectinload
    from app.models.entry import Entry

    query = select(Entry).options(selectinload(Entry.lines))

    filters = []
    if source_type:
        filters.append(Entry.source_type == source_type)
    if importer:
        filters.append(Entry.importer_of_record_name.ilike(f"%{importer}%"))
    if entry_number:
        filters.append(Entry.entry_number.like(f"%{entry_number}%"))
    if status:
        filters.append(Entry.status == status)

    if filters:
        query = query.where(and_(*filters))

    # Get total count
    count_query = select(func.count()).select_from(Entry)
    if filters:
        count_query = count_query.where(and_(*filters))
    total = await db.scalar(count_query)

    # Apply pagination
    query = query.order_by(Entry.entry_date.desc().nullslast()).offset(offset).limit(limit)

    result = await db.execute(query)
    entries = result.scalars().unique().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": [
            {
                "id": str(e.id),
                "entry_number": e.entry_number,
                "entry_type": e.entry_type,
                "entry_date": e.entry_date.isoformat() if e.entry_date else None,
                "source_type": e.source_type,
                "status": e.status,
                "importer_of_record_name": e.importer_of_record_name,
                "total_entered_value": float(e.total_entered_value) if e.total_entered_value else 0,
                "total_duty": float(e.total_duty) if e.total_duty else 0,
                "line_count": e.line_count,
                "shipment_id": str(e.shipment_id) if e.shipment_id else None,
                "lines": [
                    {
                        "line_number": l.line_number,
                        "hts_code": l.hts_code,
                        "description": l.product_description,
                        "country_of_origin": l.country_of_origin,
                        "quantity": float(l.quantity_1) if l.quantity_1 else None,
                        "entered_value": float(l.entered_value) if l.entered_value else None,
                        "duty_amount": float(l.duty_amount) if l.duty_amount else None,
                    }
                    for l in e.lines
                ]
            }
            for e in entries
        ]
    }
