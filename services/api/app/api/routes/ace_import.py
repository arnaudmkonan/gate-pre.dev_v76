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
