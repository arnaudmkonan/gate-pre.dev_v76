"""
Webhook management API routes.

Endpoints for registering, testing, and managing webhook subscriptions.
"""
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.webhook_service import WebhookService, WEBHOOK_EVENTS

router = APIRouter(prefix="/api/settings/webhooks", tags=["Webhooks"])


# ==================== Schemas ====================

class WebhookCreate(BaseModel):
    """Create a new webhook endpoint."""
    url: str
    name: str = "Webhook"
    events: List[str]


class WebhookResponse(BaseModel):
    """Webhook endpoint response."""
    id: str
    url: str
    name: str
    events: List[str]
    secret: Optional[str] = None  # Only shown on create
    is_active: bool
    failure_count: int
    created_at: str
    last_triggered_at: Optional[str] = None


class WebhookDeliveryResponse(BaseModel):
    """Webhook delivery record."""
    id: str
    event_type: str
    status: str
    response_code: Optional[int] = None
    error_message: Optional[str] = None
    attempt_count: int
    created_at: str
    delivered_at: Optional[str] = None


# ==================== Endpoints ====================

@router.get("/events")
async def list_events():
    """List all available webhook event types."""
    return {"events": WEBHOOK_EVENTS}


@router.post("", status_code=201)
async def create_webhook(
    request: WebhookCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new webhook endpoint."""
    service = WebhookService(db)
    try:
        endpoint = await service.register(
            url=request.url,
            events=request.events,
            name=request.name,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return WebhookResponse(
        id=str(endpoint.id),
        url=endpoint.url,
        name=endpoint.name,
        events=endpoint.events,
        secret=endpoint.secret,  # Only shown once on create
        is_active=endpoint.is_active,
        failure_count=endpoint.failure_count or 0,
        created_at=endpoint.created_at.isoformat(),
    )


@router.get("")
async def list_webhooks(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """List all registered webhook endpoints."""
    service = WebhookService(db)
    endpoints = await service.list_endpoints(active_only=active_only)

    return {
        "count": len(endpoints),
        "webhooks": [
            WebhookResponse(
                id=str(ep.id),
                url=ep.url,
                name=ep.name,
                events=ep.events or [],
                is_active=ep.is_active,
                failure_count=ep.failure_count or 0,
                created_at=ep.created_at.isoformat(),
                last_triggered_at=ep.last_triggered_at.isoformat() if ep.last_triggered_at else None,
            ).dict()
            for ep in endpoints
        ],
    }


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Send a test payload to verify the webhook endpoint."""
    service = WebhookService(db)
    result = await service.test_endpoint(UUID(webhook_id))
    return result


@router.get("/{webhook_id}/deliveries")
async def get_deliveries(
    webhook_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get recent delivery history for a webhook endpoint."""
    service = WebhookService(db)
    deliveries = await service.get_deliveries(UUID(webhook_id), limit=limit)

    return {
        "count": len(deliveries),
        "deliveries": [
            WebhookDeliveryResponse(
                id=str(d.id),
                event_type=d.event_type,
                status=d.status,
                response_code=d.response_code,
                error_message=d.error_message,
                attempt_count=d.attempt_count,
                created_at=d.created_at.isoformat(),
                delivered_at=d.delivered_at.isoformat() if d.delivered_at else None,
            ).dict()
            for d in deliveries
        ],
    }


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a webhook endpoint and all its delivery history."""
    service = WebhookService(db)
    deleted = await service.delete_endpoint(UUID(webhook_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"deleted": True}
