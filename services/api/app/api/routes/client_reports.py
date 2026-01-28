"""
Client Reporting API Routes.

Endpoints for generating client reports.

Task 4.5 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional
from uuid import UUID
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import json
import io

from app.core.database import get_db


router = APIRouter(prefix="/api/clients", tags=["Client Reports"])


# ==================== Request Models ====================

class ReportRequest(BaseModel):
    """Report generation request."""
    report_type: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    year: Optional[int] = None


# ==================== Helper Functions ====================

def parse_date(date_str: str) -> date:
    """Parse date string to date object."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}. Use YYYY-MM-DD")


def generate_csv(data: dict, report_type: str) -> str:
    """Generate CSV from report data."""
    lines = []
    
    if report_type == "entry_summary":
        # Header
        lines.append("Entry Number,Entry Date,Entry Type,Port,Status,Value,Duty,Lines")
        for entry in data.get("entries", []):
            lines.append(f"{entry['entry_number']},{entry['entry_date']},{entry['entry_type']},{entry['port_of_entry']},{entry['status']},{entry['total_value']},{entry['total_duty']},{entry['line_count']}")
    
    elif report_type == "duty_paid":
        lines.append("Entry Number,Entry Date,Value,Duty,MPF,HMF,ADD,CVD,Total")
        for entry in data.get("entries", []):
            lines.append(f"{entry['entry_number']},{entry['entry_date']},{entry['entry_value']},{entry['duty']},{entry['mpf']},{entry['hmf']},{entry['add_duty']},{entry['cvd']},{entry['total']}")
    
    elif report_type == "hts_chapter":
        lines.append("Chapter,Description,Lines,Entries,Value,Duty,Unique HTS Codes")
        for chapter in data.get("chapters", []):
            lines.append(f"{chapter['chapter']},{chapter['chapter_description']},{chapter['line_count']},{chapter['entry_count']},{chapter['total_value']},{chapter['total_duty']},{chapter['unique_hts_codes']}")
    
    elif report_type == "ytd_statistics":
        lines.append("Month,Entries,Value,Duty")
        for month in data.get("monthly", []):
            lines.append(f"{month['month_name']},{month['entry_count']},{month['total_value']},{month['total_duty']}")
    
    elif report_type == "country_of_origin":
        lines.append("Country Code,Country Name,Lines,Entries,Value,Duty")
        for country in data.get("countries", []):
            lines.append(f"{country['country_code']},{country['country_name']},{country['line_count']},{country['entry_count']},{country['total_value']},{country['total_duty']}")
    
    return "\n".join(lines)


# ==================== Endpoints ====================

@router.get("/{client_id}/reports")
async def list_available_reports(
    client_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all available report types."""
    from app.services.client_reporting_service import ClientReportService
    
    service = ClientReportService(db)
    reports = await service.list_available_reports()
    
    return {
        "client_id": client_id,
        "available_reports": reports,
    }


@router.get("/{client_id}/reports/entry-summary")
async def get_entry_summary_report(
    client_id: str,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate entry summary report.
    
    Shows all entries with totals and breakdowns.
    """
    from app.services.client_reporting_service import ClientReportService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientReportService(db)
    report = await service.get_entry_summary(
        client_uuid,
        parse_date(start_date),
        parse_date(end_date),
    )
    
    return report


@router.get("/{client_id}/reports/duty-paid")
async def get_duty_paid_report(
    client_id: str,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate duty paid report.
    
    Detailed breakdown of all duties, fees, and taxes.
    """
    from app.services.client_reporting_service import ClientReportService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientReportService(db)
    report = await service.get_duty_paid_report(
        client_uuid,
        parse_date(start_date),
        parse_date(end_date),
    )
    
    return report


@router.get("/{client_id}/reports/hts-chapter")
async def get_hts_chapter_report(
    client_id: str,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate HTS chapter report.
    
    Import history grouped by HTS chapter (first 2 digits).
    """
    from app.services.client_reporting_service import ClientReportService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientReportService(db)
    report = await service.get_hts_chapter_report(
        client_uuid,
        parse_date(start_date),
        parse_date(end_date),
    )
    
    return report


@router.get("/{client_id}/reports/ytd")
async def get_ytd_statistics(
    client_id: str,
    year: Optional[int] = Query(None, description="Year (defaults to current year)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate year-to-date statistics.
    
    Monthly breakdown of entries, values, and duties.
    """
    from app.services.client_reporting_service import ClientReportService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientReportService(db)
    report = await service.get_ytd_statistics(client_uuid, year)
    
    return report


@router.get("/{client_id}/reports/country-of-origin")
async def get_country_of_origin_report(
    client_id: str,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate country of origin report.
    
    Import breakdown by country of origin.
    """
    from app.services.client_reporting_service import ClientReportService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientReportService(db)
    report = await service.get_country_of_origin_report(
        client_uuid,
        parse_date(start_date),
        parse_date(end_date),
    )
    
    return report


@router.post("/{client_id}/reports/generate")
async def generate_report(
    client_id: str,
    request: ReportRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate any report by type.
    
    Unified endpoint for all report types.
    """
    from app.services.client_reporting_service import ClientReportService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientReportService(db)
    
    try:
        report = await service.generate_report(
            client_uuid,
            request.report_type,
            parse_date(request.start_date),
            parse_date(request.end_date),
            year=request.year,
        )
        return report
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Export Endpoints ====================

@router.get("/{client_id}/reports/export/csv")
async def export_report_csv(
    client_id: str,
    report_type: str = Query(..., description="Report type"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Export report as CSV file.
    
    Downloads a CSV file of the report data.
    """
    from app.services.client_reporting_service import ClientReportService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientReportService(db)
    
    try:
        report = await service.generate_report(
            client_uuid,
            report_type,
            parse_date(start_date),
            parse_date(end_date),
            year=year,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Generate CSV
    csv_content = generate_csv(report, report_type)
    
    # Create response
    filename = f"{report_type}_{start_date}_{end_date}.csv"
    
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{client_id}/reports/export/json")
async def export_report_json(
    client_id: str,
    report_type: str = Query(..., description="Report type"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Export report as JSON file.
    
    Downloads a JSON file of the report data.
    """
    from app.services.client_reporting_service import ClientReportService
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientReportService(db)
    
    try:
        report = await service.generate_report(
            client_uuid,
            report_type,
            parse_date(start_date),
            parse_date(end_date),
            year=year,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Create response
    filename = f"{report_type}_{start_date}_{end_date}.json"
    json_content = json.dumps(report, indent=2)
    
    return StreamingResponse(
        io.StringIO(json_content),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ==================== Quick Statistics ====================

@router.get("/{client_id}/stats/quick")
async def get_quick_stats(
    client_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get quick statistics for a client.
    
    Shows high-level metrics without requiring date range.
    """
    from app.services.client_reporting_service import ClientReportService
    from datetime import date
    
    try:
        client_uuid = UUID(client_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid client ID")
    
    service = ClientReportService(db)
    
    # Current year YTD
    current_year = date.today().year
    ytd = await service.get_ytd_statistics(client_uuid, current_year)
    
    # Last 30 days
    end_date = date.today()
    start_date = end_date.replace(day=1)  # Start of month
    monthly = await service.get_entry_summary(client_uuid, start_date, end_date)
    
    return {
        "client_id": client_id,
        "ytd": {
            "year": current_year,
            "entries": ytd["ytd_totals"]["entries"],
            "value": ytd["ytd_totals"]["value"],
            "duty": ytd["ytd_totals"]["duty"],
        },
        "current_month": {
            "month": date.today().strftime("%B %Y"),
            "entries": monthly["summary"]["total_entries"],
            "value": monthly["financials"]["total_value"],
            "duty": monthly["financials"]["total_duty"],
        },
        "averages": ytd["averages"],
    }
