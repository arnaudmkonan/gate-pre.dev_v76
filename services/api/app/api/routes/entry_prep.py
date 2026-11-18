"""
Entry Prep API Routes

API endpoints for preparing customs entry data from shipments.
Provides pre-filled CBP 7501 data for ACE submission.

Phase 5 Task 5.2 from trade automation implementation plan.
"""
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.entry_prep_service import EntryPrepService
from app.core.auth import get_current_user

router = APIRouter(prefix="/api/entries/prep", tags=["Entry Prep"], dependencies=[Depends(get_current_user)])



class EntryPrepResponse(BaseModel):
    """Response model for entry prep data"""
    entry_number: Optional[str] = None
    entry_type: str
    entry_date: Optional[str] = None
    filer_code: Optional[str] = None
    port_code: Optional[str] = None
    importer: dict
    consignee: dict
    transport: dict
    bond: dict
    origin: dict
    totals: dict
    line_items: list
    metadata: dict
    
    class Config:
        from_attributes = True


class ValidationResult(BaseModel):
    """Validation result model"""
    is_valid: bool
    completeness_score: float
    errors: list[str]
    warnings: list[str]
    field_issues: dict


class ExportResult(BaseModel):
    """Export result model"""
    format: str
    data: dict
    warnings: list[str]


class EntryUpdateRequest(BaseModel):
    """Request model for updating entry data"""
    field_path: str  # e.g., "importer.name" or "line_items.0.hts_number"
    value: str | int | float


@router.get("/{shipment_id}", response_model=EntryPrepResponse)
async def get_entry_prep_data(
    shipment_id: UUID,
    session: AsyncSession = Depends(get_db)
):
    """
    Get pre-filled entry data for a shipment.
    
    Aggregates data from the shipment and linked documents
    to create a CBP 7501 compatible entry summary.
    """
    try:
        entry_data = await EntryPrepService.prepare_from_shipment(session, shipment_id)
        return entry_data.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to prepare entry data: {str(e)}"
        )


@router.post("/{shipment_id}/validate", response_model=ValidationResult)
async def validate_entry_data(
    shipment_id: UUID,
    session: AsyncSession = Depends(get_db)
):
    """
    Validate entry data for a shipment.
    
    Checks for:
    - Required fields
    - Format compliance
    - Logical consistency
    - ACE submission requirements
    """
    try:
        entry_data = await EntryPrepService.prepare_from_shipment(session, shipment_id)
        
        errors = []
        warnings = entry_data.validation_warnings.copy()
        field_issues = {}
        
        # Check critical required fields
        if not entry_data.importer_name:
            errors.append("Importer name is required")
            field_issues["importer.name"] = "Required"
        
        if not entry_data.master_bill:
            errors.append("Bill of lading is required")
            field_issues["transport.master_bill"] = "Required"
        
        if not (entry_data.port_of_entry or entry_data.port_code):
            errors.append("Port of entry is required")
            field_issues["port_code"] = "Required"
        
        if entry_data.total_entered_value <= 0:
            errors.append("Declared value must be greater than zero")
            field_issues["totals.value"] = "Invalid value"
        
        # Check line items
        if len(entry_data.line_items) == 0:
            warnings.append("No line items found - commercial invoice data may be missing")
        else:
            for idx, item in enumerate(entry_data.line_items):
                if not item.get("hts_number"):
                    field_issues[f"line_items.{idx}.hts_number"] = "HTS code required"
                elif len(item.get("hts_number", "")) < 6:
                    field_issues[f"line_items.{idx}.hts_number"] = "HTS code must be at least 6 digits"
        
        # Validate HTS codes format
        for idx, item in enumerate(entry_data.line_items):
            hts = item.get("hts_number", "")
            if hts and not hts.replace(".", "").isdigit():
                errors.append(f"Line {idx + 1}: Invalid HTS code format")
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            completeness_score=entry_data.completeness_score,
            errors=errors,
            warnings=warnings,
            field_issues=field_issues
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Validation failed: {str(e)}"
        )


@router.post("/{shipment_id}/export")
async def export_entry_data(
    shipment_id: UUID,
    format: str = "ace",  # ace, json, pdf, excel
    session: AsyncSession = Depends(get_db)
):
    """
    Export entry data in specified format.
    
    Formats:
    - ace: ACE-compatible JSON structure
    - json: Full entry data as JSON
    - pdf: CBP Form 7501 Entry Summary PDF
    - excel: CBP Form 7501 Entry Summary Excel (.xlsx)
    """
    from fastapi.responses import Response
    from app.services.cargowise_exporter import CargoWiseExporter

    try:
        entry_data = await EntryPrepService.prepare_from_shipment(session, shipment_id)
        fmt = format.lower()

        if fmt in ("pdf", "excel", "xlsx"):
            raw = entry_data.to_dict()
            summary = {
                "entry_number": raw.get("entry_number") or f"PREP-{str(shipment_id)[:8].upper()}",
                "entry_type": raw.get("entry_type") or "01",
                "status": "prepared",
                "port_of_entry": raw.get("port_code") or raw.get("transport", {}).get("port_of_entry") or "-",
                "port_of_unlading": raw.get("transport", {}).get("port_of_unlading") or "-",
                "entry_date": raw.get("entry_date") or "-",
                "import_date": raw.get("transport", {}).get("import_date") or "-",
                "mode_of_transport": "10 (Vessel)",
                "carrier_code": raw.get("transport", {}).get("carrier_code") or raw.get("transport", {}).get("scac_code") or "-",
                "vessel_name": raw.get("transport", {}).get("vessel_name") or "-",
                "voyage_number": raw.get("transport", {}).get("voyage_number") or "-",
                "bill_of_lading": raw.get("transport", {}).get("master_bill") or "-",
                "house_bill": raw.get("transport", {}).get("house_bill") or "-",
                "bond_type": raw.get("bond", {}).get("type") or "8 (Continuous)",
                "surety_code": raw.get("bond", {}).get("surety_code") or "-",
                "importer_name": raw.get("importer", {}).get("name") or "-",
                "importer_ior": raw.get("importer", {}).get("ior_number") or "-",
                "consignee_name": raw.get("consignee", {}).get("name") or raw.get("importer", {}).get("name") or "-",
                "country_of_origin": raw.get("origin", {}).get("country_of_origin") or "-",
                "totals": {
                    "entered_value": float(raw.get("totals", {}).get("entered_value") or 0),
                    "base_duty": float(raw.get("totals", {}).get("duty") or 0),
                    "section_301": 0.0,
                    "section_232": 0.0,
                    "add_amount": 0.0,
                    "cvd_amount": 0.0,
                    "mpf": float(raw.get("totals", {}).get("mpf") or 0),
                    "hmf": float(raw.get("totals", {}).get("hmf") or 0),
                    "total_due": float(raw.get("totals", {}).get("grand_total") or 0),
                },
                "lines": [
                    {
                        "line_number": item.get("line_number", idx + 1),
                        "hts_code": item.get("hts_number") or "-",
                        "description": item.get("description") or "-",
                        "country_of_origin": item.get("country_of_origin") or "-",
                        "quantity": float(item.get("quantity") or 0),
                        "uom": item.get("unit") or "PCS",
                        "entered_value": float(item.get("entered_value") or 0),
                        "duty_rate": float(item.get("duty_rate") or 0),
                        "duty_amount": float(item.get("duty_amount") or 0),
                    }
                    for idx, item in enumerate(raw.get("line_items", []))
                ],
                "parties": [],
            }
            if fmt == "pdf":
                pdf_bytes = CargoWiseExporter.build_7501_pdf_from_dict(summary)
                return Response(
                    content=pdf_bytes,
                    media_type="application/pdf",
                    headers={
                        "Content-Disposition": f'attachment; filename="CBP_7501_Prep_{str(shipment_id)[:8]}.pdf"',
                    },
                )
            else:
                xlsx_bytes = CargoWiseExporter.build_7501_excel_from_dict(summary)
                return Response(
                    content=xlsx_bytes,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={
                        "Content-Disposition": f'attachment; filename="CBP_7501_Prep_{str(shipment_id)[:8]}.xlsx"',
                    },
                )

        if fmt == "ace":
            export_data = EntryPrepService.export_to_ace_format(entry_data)
        elif fmt == "json":
            export_data = entry_data.to_dict()
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported export format: {format}. Use 'ace', 'json', 'pdf', or 'excel'."
            )
        
        return ExportResult(
            format=format,
            data=export_data,
            warnings=entry_data.validation_warnings
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Export failed: {str(e)}"
        )


@router.get("/line-items/{shipment_id}")
async def get_line_items(
    shipment_id: UUID,
    session: AsyncSession = Depends(get_db)
):
    """Get just the line items for a shipment's entry."""
    try:
        entry_data = await EntryPrepService.prepare_from_shipment(session, shipment_id)
        return {
            "line_items": entry_data.line_items,
            "count": len(entry_data.line_items),
            "total_value": float(entry_data.total_entered_value),
            "total_duty": float(entry_data.total_duty)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get line items: {str(e)}"
        )


@router.get("/summary/{shipment_id}")
async def get_entry_summary(
    shipment_id: UUID,
    session: AsyncSession = Depends(get_db)
):
    """Get a quick summary of entry prep status."""
    try:
        entry_data = await EntryPrepService.prepare_from_shipment(session, shipment_id)
        
        return {
            "shipment_id": str(shipment_id),
            "completeness_score": entry_data.completeness_score,
            "is_ready": entry_data.completeness_score >= 0.8 and len([
                w for w in entry_data.validation_warnings 
                if "missing" in w.lower() or "required" in w.lower()
            ]) == 0,
            "warnings_count": len(entry_data.validation_warnings),
            "line_items_count": len(entry_data.line_items),
            "totals": {
                "value": float(entry_data.total_entered_value),
                "duty": float(entry_data.total_duty),
                "fees": float(entry_data.total_mpf + entry_data.total_hmf),
                "grand_total": float(entry_data.grand_total),
            },
            "key_fields": {
                "importer": entry_data.importer_name or "[Missing]",
                "bill_of_lading": entry_data.master_bill or "[Missing]",
                "port": entry_data.port_of_entry or entry_data.port_code or "[Missing]",
                "origin": entry_data.country_of_origin or entry_data.foreign_port or "[Missing]",
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get summary: {str(e)}"
        )
