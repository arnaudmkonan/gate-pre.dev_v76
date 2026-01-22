"""
Export API Routes.

Endpoints for exporting extracted data to Excel, CSV, and other formats.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.export_service import ExportService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/export", tags=["Export"])


# Request/Response Models

class ExportRequest(BaseModel):
    """Request for exporting documents."""
    document_ids: List[str]
    mapping_template_id: Optional[str] = None
    include_confidence: bool = False
    include_metadata: bool = False


class FieldMappingRequest(BaseModel):
    """Request for creating a field mapping template."""
    name: str
    description: Optional[str] = None
    customer_id: Optional[str] = None
    document_type: Optional[str] = None
    mappings: List[dict]
    is_default: bool = False


class PreviewResponse(BaseModel):
    """Preview of export data."""
    total_documents: int
    sample_rows: List[dict]
    available_fields: List[dict]


# API Endpoints

@router.get("/fields/{document_id}")
async def get_available_fields(
    document_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Get available fields for export from a document.
    
    Returns list of all extractable fields with their types and sample values.
    """
    try:
        fields = await ExportService.get_extractable_fields(session, document_id)
        return {
            "document_id": document_id,
            "fields": fields,
            "field_count": len(fields),
        }
    except Exception as e:
        logger.error(f"Error getting extractable fields: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview")
async def preview_export(
    request: ExportRequest,
    max_rows: int = Query(default=5, le=20),
    session: AsyncSession = Depends(get_db)
):
    """
    Preview export data before generating file.
    
    Returns sample rows and available fields.
    """
    try:
        # Get sample data for first few documents
        sample_docs = request.document_ids[:max_rows]
        rows = []
        all_fields = set()
        
        for doc_id in sample_docs:
            row_data = await ExportService._get_document_export_data(
                session,
                doc_id,
                None,  # No mapping for preview
                request.include_confidence,
                request.include_metadata
            )
            if row_data:
                rows.append(row_data)
                all_fields.update(row_data.keys())
        
        return {
            "total_documents": len(request.document_ids),
            "sample_rows": rows,
            "available_fields": sorted(list(all_fields)),
            "preview_count": len(rows),
        }
    except Exception as e:
        logger.error(f"Error previewing export: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/excel")
async def export_to_excel(
    request: ExportRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Export extracted data to Excel format.
    
    Returns downloadable .xlsx file.
    """
    try:
        excel_bytes = await ExportService.export_to_excel(
            session,
            request.document_ids,
            request.mapping_template_id,
            request.include_confidence,
            request.include_metadata
        )
        
        filename = f"export_{len(request.document_ids)}_documents.xlsx"
        
        return StreamingResponse(
            iter([excel_bytes]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(excel_bytes)),
            }
        )
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="Excel export requires openpyxl library"
        )
    except Exception as e:
        logger.error(f"Error exporting to Excel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/csv")
async def export_to_csv(
    request: ExportRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Export extracted data to CSV format.
    
    Returns downloadable .csv file.
    """
    try:
        csv_bytes = await ExportService.export_to_csv(
            session,
            request.document_ids,
            request.mapping_template_id,
            request.include_confidence,
            request.include_metadata
        )
        
        filename = f"export_{len(request.document_ids)}_documents.csv"
        
        return StreamingResponse(
            iter([csv_bytes]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(csv_bytes)),
            }
        )
    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Mapping Template Endpoints

@router.get("/mappings")
async def list_mapping_templates(
    customer_id: Optional[str] = None,
    document_type: Optional[str] = None,
    session: AsyncSession = Depends(get_db)
):
    """List available field mapping templates."""
    try:
        templates = await ExportService.get_mapping_templates(
            session, customer_id, document_type
        )
        return {
            "templates": [t.to_dict() for t in templates],
            "count": len(templates),
        }
    except Exception as e:
        logger.error(f"Error listing mapping templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mappings")
async def create_mapping_template(
    request: FieldMappingRequest,
    session: AsyncSession = Depends(get_db)
):
    """Create a new field mapping template."""
    try:
        template = await ExportService.create_mapping_template(
            session,
            name=request.name,
            mappings=request.mappings,
            customer_id=request.customer_id,
            document_type=request.document_type,
            description=request.description,
            is_default=request.is_default
        )
        
        return {
            "message": "Mapping template created successfully",
            "template": template.to_dict(),
        }
    except Exception as e:
        logger.error(f"Error creating mapping template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mappings/{template_id}")
async def get_mapping_template(
    template_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get a specific mapping template by ID."""
    from sqlalchemy import select
    from app.models.extraction_result import FieldMappingTemplate
    
    try:
        result = await session.execute(
            select(FieldMappingTemplate).where(
                FieldMappingTemplate.id == UUID(template_id)
            )
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        return template.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting mapping template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/mappings/{template_id}")
async def delete_mapping_template(
    template_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Delete a mapping template."""
    from sqlalchemy import select
    from app.models.extraction_result import FieldMappingTemplate
    
    try:
        result = await session.execute(
            select(FieldMappingTemplate).where(
                FieldMappingTemplate.id == UUID(template_id)
            )
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        await session.delete(template)
        await session.commit()
        
        return {"message": "Template deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting mapping template: {e}")
        raise HTTPException(status_code=500, detail=str(e))
