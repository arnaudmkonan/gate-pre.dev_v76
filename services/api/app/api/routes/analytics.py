"""
Analytics and Reporting API Routes.

Endpoints for:
- Entry analytics dashboard (Task 7.1)
- Compliance score dashboard (Task 7.2)
- CBP report generation (Task 7.3)
- Automated scheduled reports (Task 7.4)
- Export to CSV/Excel (Task 7.5)

Phase 7 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db


router = APIRouter(prefix="/api/analytics", tags=["Analytics & Reporting"])


# ==================== Request Models ====================

class CreateScheduleRequest(BaseModel):
    name: str
    report_type: str
    frequency: str
    recipients: List[str]
    client_id: Optional[str] = None
    day_of_week: Optional[int] = None
    day_of_month: Optional[int] = None
    time_of_day: str = "08:00"
    timezone: str = "America/New_York"
    filters: Optional[dict] = None
    description: Optional[str] = None


class UpdateScheduleRequest(BaseModel):
    name: Optional[str] = None
    frequency: Optional[str] = None
    recipients: Optional[List[str]] = None
    day_of_week: Optional[int] = None
    day_of_month: Optional[int] = None
    time_of_day: Optional[str] = None
    is_active: Optional[bool] = None


# ==================== Dashboard Analytics (Task 7.1) ====================

@router.get("/dashboard")
async def get_dashboard_summary(
    client_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get overall dashboard summary."""
    from app.services.analytics_service import AnalyticsService
    
    service = AnalyticsService(db)
    
    summary = await service.get_dashboard_summary(
        client_id=UUID(client_id) if client_id else None,
        start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
        end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
    )
    
    return summary


@router.get("/entries-by-month")
async def get_entries_by_month(
    client_id: Optional[str] = Query(None),
    months: int = Query(12, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
):
    """Get entries grouped by month for charting."""
    from app.services.analytics_service import AnalyticsService
    
    service = AnalyticsService(db)
    
    data = await service.get_entries_by_month(
        client_id=UUID(client_id) if client_id else None,
        months=months,
    )
    
    return {
        "data": data,
        "chart_type": "bar",
        "x_axis": "month",
        "y_axis": ["count", "total_duty"],
    }


@router.get("/top-hts-codes")
async def get_top_hts_codes(
    client_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get top HTS codes by value."""
    from app.services.analytics_service import AnalyticsService
    
    service = AnalyticsService(db)
    
    data = await service.get_top_hts_codes(
        client_id=UUID(client_id) if client_id else None,
        limit=limit,
        start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
        end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
    )
    
    return {
        "data": data,
        "count": len(data),
    }


@router.get("/top-clients")
async def get_top_clients(
    limit: int = Query(10, ge=1, le=50),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get top clients by entry count."""
    from app.services.analytics_service import AnalyticsService
    
    service = AnalyticsService(db)
    
    data = await service.get_top_clients(
        limit=limit,
        start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
        end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
    )
    
    return {
        "data": data,
        "count": len(data),
    }


@router.get("/port-distribution")
async def get_port_distribution(
    client_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get entry distribution by port."""
    from app.services.analytics_service import AnalyticsService
    
    service = AnalyticsService(db)
    
    data = await service.get_port_distribution(
        client_id=UUID(client_id) if client_id else None,
        start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
        end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
    )
    
    return {
        "data": data,
        "chart_type": "pie",
        "count": len(data),
    }


@router.get("/processing-time")
async def get_processing_time_metrics(
    client_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get entry processing time metrics."""
    from app.services.analytics_service import AnalyticsService
    
    service = AnalyticsService(db)
    
    metrics = await service.get_processing_time_metrics(
        client_id=UUID(client_id) if client_id else None,
        start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
        end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
    )
    
    return metrics


# ==================== Compliance Score (Task 7.2) ====================

@router.get("/compliance/{client_id}")
async def get_client_compliance_score(
    client_id: str,
    months: int = Query(12, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
):
    """Get compliance score for a client."""
    from app.services.analytics_service import ComplianceScoreService
    
    service = ComplianceScoreService(db)
    
    score = await service.calculate_client_score(
        UUID(client_id),
        months=months,
    )
    
    return score


@router.get("/compliance/{client_id}/trend")
async def get_compliance_trend(
    client_id: str,
    months: int = Query(12, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
):
    """Get compliance score trend over time."""
    from app.services.analytics_service import ComplianceScoreService
    
    service = ComplianceScoreService(db)
    
    trend = await service.get_score_trend(
        UUID(client_id),
        months=months,
    )
    
    return {
        "client_id": client_id,
        "trend": trend,
        "chart_type": "line",
    }


# ==================== CBP Reports (Task 7.3) ====================

@router.get("/reports/annual-summary/{client_id}")
async def generate_annual_summary(
    client_id: str,
    year: int = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Generate annual importer activity summary."""
    from app.services.analytics_service import CBPReportService
    
    service = CBPReportService(db)
    
    if not year:
        year = datetime.now().year
    
    try:
        report = await service.generate_annual_summary(UUID(client_id), year)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/reports/record-keeping/{client_id}")
async def generate_record_keeping_report(
    client_id: str,
    start_date: str = Query(...),
    end_date: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Generate CBP record-keeping compliance report."""
    from app.services.analytics_service import CBPReportService
    
    service = CBPReportService(db)
    
    report = await service.generate_record_keeping_report(
        UUID(client_id),
        datetime.strptime(start_date, "%Y-%m-%d").date(),
        datetime.strptime(end_date, "%Y-%m-%d").date(),
    )
    
    return report


@router.get("/reports/isf-compliance/{client_id}")
async def generate_isf_compliance_report(
    client_id: str,
    start_date: str = Query(...),
    end_date: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Generate ISF compliance summary report."""
    from app.services.analytics_service import CBPReportService
    
    service = CBPReportService(db)
    
    report = await service.generate_isf_compliance_summary(
        UUID(client_id),
        datetime.strptime(start_date, "%Y-%m-%d").date(),
        datetime.strptime(end_date, "%Y-%m-%d").date(),
    )
    
    return report


# ==================== Scheduled Reports (Task 7.4) ====================

@router.post("/schedules")
async def create_schedule(
    request: CreateScheduleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a scheduled report."""
    from app.services.scheduled_report_service import ScheduledReportService
    
    service = ScheduledReportService(db)
    
    schedule = await service.create_schedule(
        name=request.name,
        report_type=request.report_type,
        frequency=request.frequency,
        recipients=request.recipients,
        client_id=UUID(request.client_id) if request.client_id else None,
        day_of_week=request.day_of_week,
        day_of_month=request.day_of_month,
        time_of_day=request.time_of_day,
        timezone=request.timezone,
        filters=request.filters,
        description=request.description,
    )
    
    return {
        "schedule": schedule.to_dict(),
        "message": "Schedule created",
    }


@router.get("/schedules")
async def list_schedules(
    client_id: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    report_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List scheduled reports."""
    from app.services.scheduled_report_service import ScheduledReportService
    
    service = ScheduledReportService(db)
    
    schedules = await service.list_schedules(
        client_id=UUID(client_id) if client_id else None,
        is_active=is_active,
        report_type=report_type,
    )
    
    return {
        "schedules": [s.to_dict() for s in schedules],
        "count": len(schedules),
    }


@router.get("/schedules/{schedule_id}")
async def get_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get schedule details."""
    from app.services.scheduled_report_service import ScheduledReportService
    
    service = ScheduledReportService(db)
    schedule = await service.get_schedule(UUID(schedule_id))
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    return schedule.to_dict()


@router.patch("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    request: UpdateScheduleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update a schedule."""
    from app.services.scheduled_report_service import ScheduledReportService
    
    service = ScheduledReportService(db)
    
    try:
        schedule = await service.update_schedule(
            UUID(schedule_id),
            request.model_dump(exclude_none=True),
        )
        return {
            "schedule": schedule.to_dict(),
            "message": "Schedule updated",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/schedules/{schedule_id}/pause")
async def pause_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Pause a schedule."""
    from app.services.scheduled_report_service import ScheduledReportService
    
    service = ScheduledReportService(db)
    
    try:
        schedule = await service.pause_schedule(UUID(schedule_id))
        return {
            "schedule": schedule.to_dict(),
            "message": "Schedule paused",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/schedules/{schedule_id}/resume")
async def resume_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused schedule."""
    from app.services.scheduled_report_service import ScheduledReportService
    
    service = ScheduledReportService(db)
    
    try:
        schedule = await service.resume_schedule(UUID(schedule_id))
        return {
            "schedule": schedule.to_dict(),
            "message": "Schedule resumed",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a schedule."""
    from app.services.scheduled_report_service import ScheduledReportService
    
    service = ScheduledReportService(db)
    await service.delete_schedule(UUID(schedule_id))
    
    return {"message": "Schedule deleted"}


@router.post("/schedules/{schedule_id}/run")
async def run_schedule_now(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Run a scheduled report immediately."""
    from app.services.scheduled_report_service import ScheduledReportService
    
    service = ScheduledReportService(db)
    
    try:
        report = await service.run_schedule(UUID(schedule_id))
        return {
            "report": report.to_dict(),
            "message": "Report generated",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/report-history")
async def get_report_history(
    schedule_id: Optional[str] = Query(None),
    report_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get generated report history."""
    from app.services.scheduled_report_service import ScheduledReportService
    
    service = ScheduledReportService(db)
    
    reports = await service.get_report_history(
        schedule_id=UUID(schedule_id) if schedule_id else None,
        report_type=report_type,
        status=status,
        limit=limit,
    )
    
    return {
        "reports": [r.to_dict() for r in reports],
        "count": len(reports),
    }


# ==================== Export (Task 7.5) ====================

@router.get("/export/entries")
async def export_entries_csv(
    client_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Export entries to CSV."""
    from app.services.analytics_service import ExportService
    
    service = ExportService(db)
    
    csv_data = await service.export_entries_csv(
        client_id=UUID(client_id) if client_id else None,
        start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
        end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
        status=status,
    )
    
    filename = f"entries_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/clients")
async def export_clients_csv(
    db: AsyncSession = Depends(get_db),
):
    """Export clients to CSV."""
    from app.services.analytics_service import ExportService
    
    service = ExportService(db)
    
    csv_data = await service.export_clients_csv()
    
    filename = f"clients_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/preview")
async def preview_export(
    export_type: str = Query(...),
    client_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Preview export data before downloading."""
    from app.services.analytics_service import ExportService
    
    service = ExportService(db)
    
    filters = {}
    if client_id:
        filters["client_id"] = UUID(client_id)
    if start_date:
        filters["start_date"] = datetime.strptime(start_date, "%Y-%m-%d").date()
    if end_date:
        filters["end_date"] = datetime.strptime(end_date, "%Y-%m-%d").date()
    
    preview = await service.get_export_preview(export_type, filters, limit)
    
    return preview


# ==================== Reference Data ====================

@router.get("/reference/report-types")
async def get_report_types():
    """Get available report types."""
    from app.models.scheduled_report import ReportType
    return {
        "types": [{"value": t.value, "name": t.name} for t in ReportType],
    }


@router.get("/reference/frequencies")
async def get_frequencies():
    """Get available report frequencies."""
    from app.models.scheduled_report import ReportFrequency
    return {
        "frequencies": [{"value": f.value, "name": f.name} for f in ReportFrequency],
    }
