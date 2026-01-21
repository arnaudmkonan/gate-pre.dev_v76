"""Admin dashboard API endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.dashboard import DashboardDataResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/admin/dashboard", tags=["Admin - Dashboard"])


@router.get("/", response_model=DashboardDataResponse, status_code=status.HTTP_200_OK)
async def get_dashboard(session: AsyncSession = Depends(get_db)):
    """Get admin dashboard data with pipeline status, queue metrics, errors, and throughput."""
    dashboard_data = await DashboardService.get_dashboard_data(session)
    return dashboard_data
