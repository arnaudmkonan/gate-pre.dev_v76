"""
Client Portal Dashboard API Routes.

Endpoints for client portal dashboard and entry views.

Task 5.2 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.routes.client_portal import get_current_portal_user


router = APIRouter(prefix="/api/portal/dashboard", tags=["Client Portal Dashboard"])


# ==================== Request Models ====================

class ApproveEntryRequest(BaseModel):
    """Approve entry request."""
    notes: Optional[str] = None


class RequestChangesRequest(BaseModel):
    """Request changes request."""
    change_notes: str


# ==================== Dashboard Endpoints ====================

@router.get("")
async def get_dashboard(
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get complete dashboard for logged-in client user.
    
    Includes:
    - Summary cards (pending, in progress, released, issues)
    - Recent entries
    - Shipments in transit
    - Pending actions
    - Alerts
    - Quick stats
    """
    from app.services.client_dashboard_service import ClientDashboardService
    
    service = ClientDashboardService(db, user)
    dashboard = await service.get_dashboard()
    
    return {
        "user": {
            "name": user.full_name,
            "role": user.role,
        },
        **dashboard,
    }


@router.get("/summary")
async def get_summary_cards(
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Get summary cards only."""
    from app.services.client_dashboard_service import ClientDashboardService
    
    service = ClientDashboardService(db, user)
    return await service.get_summary_cards()


@router.get("/recent-entries")
async def get_recent_entries(
    limit: int = Query(10, ge=1, le=50),
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent entries."""
    from app.services.client_dashboard_service import ClientDashboardService
    
    service = ClientDashboardService(db, user)
    entries = await service.get_recent_entries(limit)
    
    return {
        "entries": entries,
        "count": len(entries),
    }


@router.get("/shipments")
async def get_shipments_in_transit(
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Get shipments in transit."""
    from app.services.client_dashboard_service import ClientDashboardService
    
    service = ClientDashboardService(db, user)
    shipments = await service.get_shipments_in_transit()
    
    return {
        "shipments": shipments,
        "count": len(shipments),
    }


@router.get("/pending-actions")
async def get_pending_actions(
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Get pending actions requiring attention."""
    from app.services.client_dashboard_service import ClientDashboardService
    
    service = ClientDashboardService(db, user)
    actions = await service.get_pending_actions()
    
    return {
        "actions": actions,
        "count": len(actions),
    }


@router.get("/alerts")
async def get_alerts(
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Get alerts and notifications."""
    from app.services.client_dashboard_service import ClientDashboardService
    
    service = ClientDashboardService(db, user)
    alerts = await service.get_alerts()
    
    return {
        "alerts": alerts,
        "count": len(alerts),
    }


@router.get("/stats")
async def get_quick_stats(
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Get quick statistics."""
    from app.services.client_dashboard_service import ClientDashboardService
    
    service = ClientDashboardService(db, user)
    return await service.get_quick_stats()


# ==================== Entry Endpoints (Read-Only for Clients) ====================

@router.get("/entries")
async def list_entries(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """List entries for the client (filtered)."""
    from sqlalchemy import select, func
    from app.models.entry import Entry
    
    # Base query - always filter by client
    base_query = select(Entry).where(Entry.client_id == user.client_id)
    
    if status:
        base_query = base_query.where(Entry.status == status)
    
    # Count
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # Paginated results
    query = base_query.order_by(Entry.entry_date.desc().nullslast()).offset(offset).limit(limit)
    result = await db.execute(query)
    entries = result.scalars().all()
    
    return {
        "entries": [
            {
                "id": str(e.id),
                "entry_number": e.entry_number,
                "entry_date": e.entry_date.isoformat() if e.entry_date else None,
                "entry_type": e.entry_type,
                "port_of_entry": e.port_of_entry,
                "status": e.status,
                "total_value": float(e.total_value or 0),
                "total_duty": float(e.total_duty or 0),
            }
            for e in entries
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/entries/{entry_id}")
async def get_entry_detail(
    entry_id: str,
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Get entry detail (read-only for client)."""
    from app.services.client_dashboard_service import ClientDashboardService
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    service = ClientDashboardService(db, user)
    entry = await service.get_entry_detail(entry_uuid)
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    return entry


# ==================== Entry Approval Endpoints ====================

@router.post("/entries/{entry_id}/approve")
async def approve_entry(
    entry_id: str,
    request: ApproveEntryRequest,
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve an entry (client approval before filing)."""
    from app.services.client_dashboard_service import ClientDashboardService
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    service = ClientDashboardService(db, user)
    
    try:
        entry = await service.approve_entry(entry_uuid, request.notes)
        return {
            "entry_id": str(entry.id),
            "status": entry.status,
            "message": "Entry approved successfully",
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/entries/{entry_id}/request-changes")
async def request_entry_changes(
    entry_id: str,
    request: RequestChangesRequest,
    user = Depends(get_current_portal_user),
    db: AsyncSession = Depends(get_db),
):
    """Request changes to an entry before approval."""
    from app.services.client_dashboard_service import ClientDashboardService
    
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")
    
    service = ClientDashboardService(db, user)
    
    try:
        entry = await service.request_entry_changes(entry_uuid, request.change_notes)
        return {
            "entry_id": str(entry.id),
            "status": entry.status,
            "message": "Change request submitted",
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
