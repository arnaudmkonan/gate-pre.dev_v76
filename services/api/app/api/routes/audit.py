"""Routes for audit logging and export."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.audit import AuditLogResponse, AuditExportRequest, AuditExportResponse
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=AuditExportResponse)
async def get_audit_logs(
    resource_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """
    Get audit logs with optional filtering.

    Supports filtering by resource_id, action, and resource_type.
    """
    try:
        result = await AuditService.export_audit(
            session,
            resource_id=resource_id,
            action=action,
            resource_type=resource_type,
            limit=limit,
            offset=offset,
        )

        return AuditExportResponse(**result)

    except Exception as e:
        logger.error(f"Error retrieving audit logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit logs")


@router.post("/export")
async def export_audit_logs(
    request: AuditExportRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Export audit logs in JSON format.

    Supports filtering by resource_id, action, resource_type, and date range.
    """
    try:
        result = await AuditService.export_audit(
            session,
            resource_id=request.resource_id,
            action=request.action,
            resource_type=request.resource_type,
            limit=request.limit,
            offset=request.offset,
        )

        # Convert to JSON-exportable format
        export_data = {
            "export_timestamp": str(datetime.utcnow()),
            "filters": {
                "resource_id": request.resource_id,
                "action": request.action,
                "resource_type": request.resource_type,
                "start_date": str(request.start_date) if request.start_date else None,
                "end_date": str(request.end_date) if request.end_date else None,
            },
            "logs": result["logs"],
            "total_count": result["total_count"],
        }

        return export_data

    except Exception as e:
        logger.error(f"Error exporting audit logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to export audit logs")
