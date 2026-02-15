"""
Landing Page Analytics API Routes.

Tracks page views, conversions, and other metrics from the commercial landing page.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel as PydanticBaseModel, Field
from sqlalchemy import Column, String, DateTime, Integer, Text, select, func, and_
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.base import BaseModel

router = APIRouter(prefix="/api/analytics/landing", tags=["landing-analytics"])


# ============================================================================
# DATABASE MODEL
# ============================================================================

class LandingPageEvent(BaseModel):
    """Landing page analytics events."""
    
    __tablename__ = "landing_page_events"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(String(100), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # page_view, click, scroll, form_start, form_submit
    page_path = Column(String(255), nullable=True)
    element_id = Column(String(100), nullable=True)
    referrer = Column(String(500), nullable=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    utm_source = Column(String(100), nullable=True)
    utm_medium = Column(String(100), nullable=True)
    utm_campaign = Column(String(100), nullable=True)
    event_data = Column(Text, nullable=True)  # JSON string for extra data
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ============================================================================
# SCHEMAS
# ============================================================================

class EventCreate(PydanticBaseModel):
    """Schema for tracking an event."""
    session_id: str = Field(..., max_length=100)
    event_type: str = Field(..., max_length=50)
    page_path: Optional[str] = Field(None, max_length=255)
    element_id: Optional[str] = Field(None, max_length=100)
    referrer: Optional[str] = Field(None, max_length=500)
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    event_data: Optional[str] = None


class EventResponse(PydanticBaseModel):
    """Schema for event response."""
    id: UUID
    session_id: str
    event_type: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class AnalyticsSummary(PydanticBaseModel):
    """Landing page analytics summary."""
    total_page_views: int
    unique_sessions: int
    total_registrations: int
    conversion_rate: float
    views_by_page: dict
    views_by_day: list
    top_referrers: list
    top_utm_sources: list


# ============================================================================
# API ROUTES
# ============================================================================

@router.post("/track", response_model=EventResponse, status_code=201)
async def track_event(
    event_data: EventCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Track a landing page event.
    
    Called from the landing page JavaScript to record user interactions.
    """
    # Get user agent and IP from request
    user_agent = request.headers.get("user-agent", "")
    ip_address = request.client.host if request.client else None
    
    event = LandingPageEvent(
        id=uuid4(),
        session_id=event_data.session_id,
        event_type=event_data.event_type,
        page_path=event_data.page_path,
        element_id=event_data.element_id,
        referrer=event_data.referrer,
        user_agent=user_agent,
        ip_address=ip_address,
        utm_source=event_data.utm_source,
        utm_medium=event_data.utm_medium,
        utm_campaign=event_data.utm_campaign,
        event_data=event_data.event_data,
    )
    
    db.add(event)
    await db.commit()
    await db.refresh(event)
    
    return event


@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """
    Get landing page analytics summary.
    
    Returns aggregated metrics for the specified time period.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get all events in time period
    result = await db.execute(
        select(LandingPageEvent).where(LandingPageEvent.created_at >= since)
    )
    events = result.scalars().all()
    
    # Calculate metrics
    page_views = [e for e in events if e.event_type == "page_view"]
    registrations = [e for e in events if e.event_type == "form_submit"]
    unique_sessions = set(e.session_id for e in page_views)
    
    total_views = len(page_views)
    total_regs = len(registrations)
    conversion_rate = (total_regs / len(unique_sessions) * 100) if unique_sessions else 0
    
    # Views by page
    views_by_page = {}
    for e in page_views:
        path = e.page_path or "/"
        views_by_page[path] = views_by_page.get(path, 0) + 1
    
    # Views by day
    views_by_day = {}
    for e in page_views:
        day = e.created_at.strftime("%Y-%m-%d")
        views_by_day[day] = views_by_day.get(day, 0) + 1
    
    views_by_day_list = [
        {"date": k, "views": v}
        for k, v in sorted(views_by_day.items())
    ]
    
    # Top referrers
    referrer_counts = {}
    for e in page_views:
        if e.referrer:
            referrer_counts[e.referrer] = referrer_counts.get(e.referrer, 0) + 1
    
    top_referrers = [
        {"referrer": k, "count": v}
        for k, v in sorted(referrer_counts.items(), key=lambda x: -x[1])[:10]
    ]
    
    # Top UTM sources
    utm_counts = {}
    for e in page_views:
        if e.utm_source:
            utm_counts[e.utm_source] = utm_counts.get(e.utm_source, 0) + 1
    
    top_utm_sources = [
        {"source": k, "count": v}
        for k, v in sorted(utm_counts.items(), key=lambda x: -x[1])[:10]
    ]
    
    return AnalyticsSummary(
        total_page_views=total_views,
        unique_sessions=len(unique_sessions),
        total_registrations=total_regs,
        conversion_rate=round(conversion_rate, 2),
        views_by_page=views_by_page,
        views_by_day=views_by_day_list,
        top_referrers=top_referrers,
        top_utm_sources=top_utm_sources,
    )


@router.get("/conversion-funnel")
async def get_conversion_funnel(
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """
    Get conversion funnel data.
    
    Shows progression from landing → registration page → form start → completed.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    result = await db.execute(
        select(LandingPageEvent).where(LandingPageEvent.created_at >= since)
    )
    events = result.scalars().all()
    
    # Group by session
    sessions = {}
    for e in events:
        if e.session_id not in sessions:
            sessions[e.session_id] = []
        sessions[e.session_id].append(e.event_type)
    
    # Calculate funnel steps
    landing_views = sum(1 for evts in sessions.values() if "page_view" in evts)
    reg_page_views = sum(1 for evts in sessions.values() if any(e == "page_view" for e in evts) and "form_start" in evts or "form_submit" in evts)
    form_starts = sum(1 for evts in sessions.values() if "form_start" in evts)
    form_submits = sum(1 for evts in sessions.values() if "form_submit" in evts)
    
    return {
        "period_days": days,
        "funnel": [
            {"step": "Landing Page Views", "count": landing_views, "percentage": 100},
            {"step": "Registration Page", "count": reg_page_views, "percentage": round(reg_page_views / landing_views * 100, 1) if landing_views else 0},
            {"step": "Started Form", "count": form_starts, "percentage": round(form_starts / landing_views * 100, 1) if landing_views else 0},
            {"step": "Completed Registration", "count": form_submits, "percentage": round(form_submits / landing_views * 100, 1) if landing_views else 0},
        ],
        "overall_conversion_rate": round(form_submits / landing_views * 100, 2) if landing_views else 0
    }


@router.get("/realtime")
async def get_realtime_stats(db: AsyncSession = Depends(get_db)):
    """
    Get real-time stats (last 30 minutes).
    """
    since = datetime.now(timezone.utc) - timedelta(minutes=30)
    
    result = await db.execute(
        select(LandingPageEvent).where(LandingPageEvent.created_at >= since)
    )
    events = result.scalars().all()
    
    page_views = [e for e in events if e.event_type == "page_view"]
    unique_sessions = set(e.session_id for e in events)
    
    return {
        "period_minutes": 30,
        "active_visitors": len(unique_sessions),
        "page_views": len(page_views),
        "events_by_type": {
            etype: len([e for e in events if e.event_type == etype])
            for etype in set(e.event_type for e in events)
        }
    }
