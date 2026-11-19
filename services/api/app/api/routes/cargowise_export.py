"""
CargoWise Export API Routes.

Endpoints for exporting entry data to CargoWise format.
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user


router = APIRouter(prefix="/api/export", tags=["Export"], dependencies=[Depends(get_current_user)])


# ==================== Response Models ====================

class CargoWiseExportResponse(BaseModel):
    """CargoWise export response with XML content."""
    entry_id: str
    format: str = "cargowise_xml"
    filename: str
    xml_preview: str  # First 1000 chars
    size_bytes: int


# ==================== Endpoints ====================

@router.post("/cargowise/{entry_id}")
async def export_to_cargowise(
    entry_id: str,
    download: bool = Query(False, description="Return as downloadable file"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export entry to CargoWise XML format (audited under 19 CFR Part 163).
    """
    from app.services.audit_service import audit
    from app.services.cargowise_exporter import CargoWiseExporter
    
    try:
        UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID format")
    
    try:
        exporter = CargoWiseExporter(db)
        xml_content, filename = await exporter.export_entry(entry_id)
        await audit(
            db,
            action="export_cargowise_xml",
            resource_type="entry",
            resource_id=entry_id,
            actor_id=str(current_user.get("id") or current_user.get("email") or "broker"),
            after={"filename": filename, "format": "cargowise_xml"},
        )
        await db.commit()
        
        if download:
            return Response(
                content=xml_content,
                media_type="application/xml",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                }
            )
        
        return CargoWiseExportResponse(
            entry_id=entry_id,
            format="cargowise_xml",
            filename=filename,
            xml_preview=xml_content[:1000] + "..." if len(xml_content) > 1000 else xml_content,
            size_bytes=len(xml_content.encode('utf-8')),
        )
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/cargowise/{entry_id}/download")
async def download_cargowise_xml(
    entry_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Download CargoWise XML file (audited under 19 CFR Part 163).
    """
    from app.services.audit_service import audit
    from app.services.cargowise_exporter import CargoWiseExporter
    
    try:
        UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID format")
    
    try:
        exporter = CargoWiseExporter(db)
        xml_content, filename = await exporter.export_entry(entry_id)
        await audit(
            db,
            action="export_cargowise_xml",
            resource_type="entry",
            resource_id=entry_id,
            actor_id=str(current_user.get("id") or current_user.get("email") or "broker"),
            after={"filename": filename, "format": "cargowise_xml"},
        )
        await db.commit()
        
        return Response(
            content=xml_content,
            media_type="application/xml",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Export-Format": "cargowise_xml",
            }
        )
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/pdf/{entry_id}")
@router.post("/pdf/{entry_id}")
async def export_entry_to_pdf(
    entry_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export entry as a CBP Form 7501 Entry Summary PDF (audited under 19 CFR Part 163).
    """
    from app.services.audit_service import audit
    from app.services.cargowise_exporter import CargoWiseExporter

    try:
        UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID format")

    try:
        exporter = CargoWiseExporter(db)
        pdf_bytes, filename = await exporter.export_entry_pdf(entry_id)
        await audit(
            db,
            action="export_7501_pdf",
            resource_type="entry",
            resource_id=entry_id,
            actor_id=str(current_user.get("id") or current_user.get("email") or "broker"),
            after={"filename": filename, "format": "cbp_7501_pdf"},
        )
        await db.commit()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Export-Format": "cbp_7501_pdf",
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF export failed: {str(e)}")


@router.get("/excel/{entry_id}")
@router.post("/excel/{entry_id}")
async def export_entry_to_excel(
    entry_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export entry as a multi-sheet CBP Form 7501 Entry Summary Excel (.xlsx) workbook (audited under 19 CFR Part 163).
    """
    from app.services.audit_service import audit
    from app.services.cargowise_exporter import CargoWiseExporter

    try:
        UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID format")

    try:
        exporter = CargoWiseExporter(db)
        xlsx_bytes, filename = await exporter.export_entry_excel(entry_id)
        await audit(
            db,
            action="export_7501_excel",
            resource_type="entry",
            resource_id=entry_id,
            actor_id=str(current_user.get("id") or current_user.get("email") or "broker"),
            after={"filename": filename, "format": "cbp_7501_xlsx"},
        )
        await db.commit()
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Export-Format": "cbp_7501_xlsx",
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Excel export failed: {str(e)}")


@router.get("/formats")
async def list_export_formats():
    """
    List available export formats.
    
    Returns supported export formats with descriptions.
    """
    return {
        "formats": [
            {
                "id": "abi",
                "name": "ABI (Automated Broker Interface)",
                "description": "CBP CATAIR-compliant fixed-width format for ACE filing",
                "extensions": [".abi", ".txt"],
                "endpoint": "/api/entries/{id}/export/abi",
                "status": "available",
            },
            {
                "id": "cargowise_xml",
                "name": "CargoWise XML",
                "description": "UniversalShipment XML format for CargoWise One World",
                "extensions": [".xml"],
                "endpoint": "/api/export/cargowise/{id}",
                "status": "available",
            },
            {
                "id": "excel",
                "name": "Excel Spreadsheet",
                "description": "CBP Form 7501 Entry Summary in multi-sheet Excel format",
                "extensions": [".xlsx"],
                "endpoint": "/api/export/excel/{id}",
                "status": "available",
            },
            {
                "id": "pdf",
                "name": "PDF Report (CBP Form 7501)",
                "description": "CBP Form 7501 Entry Summary as a formatted PDF document",
                "extensions": [".pdf"],
                "endpoint": "/api/export/pdf/{id}",
                "status": "available",
            },
        ]
    }
