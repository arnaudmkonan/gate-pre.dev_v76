"""
GATE Platform — Webhook Service.

Manages webhook registration, HMAC signature verification, and async delivery.
"""
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import WebhookEndpoint, WebhookDelivery

logger = logging.getLogger(__name__)

# Supported event types
WEBHOOK_EVENTS = [
    "entry.created",
    "entry.updated",
    "entry.filed",
    "entry.accepted",
    "entry.rejected",
    "entry.liquidated",
    "shipment.created",
    "shipment.updated",
    "document.processed",
    "document.extracted",
    "compliance.alert",
    "isf.filed",
    "isf.accepted",
    "client.created",
    "invoice.created",
]


class WebhookService:
    """Manages webhook lifecycle and delivery."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(
        self,
        url: str,
        events: List[str],
        name: str = "Webhook",
        client_id: Optional[UUID] = None,
    ) -> WebhookEndpoint:
        """Register a new webhook endpoint."""
        # Validate events
        invalid = [e for e in events if e not in WEBHOOK_EVENTS]
        if invalid:
            raise ValueError(f"Invalid event types: {invalid}. Valid: {WEBHOOK_EVENTS}")

        # Generate signing secret
        secret = f"whsec_{secrets.token_hex(24)}"

        endpoint = WebhookEndpoint(
            url=url,
            name=name,
            secret=secret,
            events=events,
            client_id=client_id,
            is_active=True,
        )
        self.db.add(endpoint)
        await self.db.commit()
        await self.db.refresh(endpoint)
        return endpoint

    async def list_endpoints(
        self,
        client_id: Optional[UUID] = None,
        active_only: bool = True,
    ) -> List[WebhookEndpoint]:
        """List webhook endpoints, optionally filtered by client."""
        q = select(WebhookEndpoint)
        if client_id:
            q = q.where(WebhookEndpoint.client_id == client_id)
        if active_only:
            q = q.where(WebhookEndpoint.is_active == True)
        result = await self.db.execute(q.order_by(WebhookEndpoint.created_at.desc()))
        return list(result.scalars().all())

    async def delete_endpoint(self, endpoint_id: UUID) -> bool:
        """Delete a webhook endpoint and all its deliveries."""
        result = await self.db.execute(
            select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id)
        )
        endpoint = result.scalar_one_or_none()
        if not endpoint:
            return False
        await self.db.delete(endpoint)
        await self.db.commit()
        return True

    async def test_endpoint(self, endpoint_id: UUID) -> dict:
        """Send a test webhook to verify the endpoint is reachable."""
        result = await self.db.execute(
            select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id)
        )
        endpoint = result.scalar_one_or_none()
        if not endpoint:
            return {"success": False, "error": "Endpoint not found"}

        test_payload = {
            "event": "webhook.test",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {"message": "This is a test webhook from GATE Platform"},
        }

        return await self._deliver(endpoint, "webhook.test", test_payload)

    async def dispatch_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        client_id: Optional[UUID] = None,
    ) -> int:
        """
        Dispatch an event to all matching webhook endpoints.

        Returns number of deliveries queued.
        """
        # Find matching endpoints
        q = select(WebhookEndpoint).where(
            WebhookEndpoint.is_active == True,
        )
        if client_id:
            q = q.where(WebhookEndpoint.client_id == client_id)

        result = await self.db.execute(q)
        endpoints = result.scalars().all()

        count = 0
        payload = {
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        for endpoint in endpoints:
            # Check if this endpoint subscribes to this event
            if event_type not in (endpoint.events or []):
                continue

            # Create delivery record
            delivery = WebhookDelivery(
                endpoint_id=endpoint.id,
                event_type=event_type,
                payload=payload,
                status="pending",
            )
            self.db.add(delivery)
            count += 1

            # Attempt immediate delivery (in production, queue to Celery)
            try:
                result = await self._deliver(endpoint, event_type, payload)
                delivery.status = "delivered" if result.get("success") else "failed"
                delivery.response_code = result.get("status_code")
                delivery.response_body = result.get("response_body", "")[:1000]
                delivery.error_message = result.get("error")
                delivery.attempt_count = 1
                delivery.delivered_at = datetime.now(timezone.utc) if delivery.status == "delivered" else None
            except Exception as e:
                delivery.status = "failed"
                delivery.error_message = str(e)
                delivery.attempt_count = 1

        if count > 0:
            await self.db.commit()

        return count

    async def get_deliveries(
        self,
        endpoint_id: UUID,
        limit: int = 50,
    ) -> List[WebhookDelivery]:
        """Get recent deliveries for an endpoint."""
        result = await self.db.execute(
            select(WebhookDelivery)
            .where(WebhookDelivery.endpoint_id == endpoint_id)
            .order_by(WebhookDelivery.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # =========================================================================
    # Internal
    # =========================================================================

    @staticmethod
    def _sign_payload(payload: dict, secret: str) -> str:
        """Generate HMAC-SHA256 signature for payload."""
        body = json.dumps(payload, sort_keys=True, default=str)
        signature = hmac.new(
            secret.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={signature}"

    async def _deliver(
        self,
        endpoint: WebhookEndpoint,
        event_type: str,
        payload: dict,
    ) -> dict:
        """Actually deliver a webhook via HTTP POST."""
        signature = self._sign_payload(payload, endpoint.secret)

        headers = {
            "Content-Type": "application/json",
            "X-Gate-Event": event_type,
            "X-Gate-Signature": signature,
            "X-Gate-Delivery": str(endpoint.id),
            "User-Agent": "GATE-Platform-Webhook/1.0",
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    endpoint.url,
                    json=payload,
                    headers=headers,
                )

            success = 200 <= response.status_code < 300

            # Update endpoint status
            endpoint.last_triggered_at = datetime.now(timezone.utc)
            if success:
                endpoint.failure_count = 0
            else:
                endpoint.failure_count = (endpoint.failure_count or 0) + 1
                if endpoint.failure_count >= endpoint.max_failures:
                    endpoint.is_active = False
                    logger.warning(f"Webhook {endpoint.id} disabled after {endpoint.failure_count} consecutive failures")

            return {
                "success": success,
                "status_code": response.status_code,
                "response_body": response.text[:500],
            }

        except Exception as e:
            endpoint.failure_count = (endpoint.failure_count or 0) + 1
            if endpoint.failure_count >= endpoint.max_failures:
                endpoint.is_active = False

            return {
                "success": False,
                "error": str(e),
            }
