"""Optional Stripe checkout + webhooks for paid pilots."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.client import Client
from app.startup.client_access import require_client_scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing/stripe", tags=["Stripe Billing"])


class CheckoutSessionRequest(BaseModel):
    success_url: str = Field(..., description="Redirect after successful payment")
    cancel_url: str = Field(..., description="Redirect if user cancels")


def _stripe():
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    try:
        import stripe
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Stripe SDK not installed") from exc
    stripe.api_key = settings.stripe_secret_key
    return stripe


@router.post("/clients/{client_id}/checkout-session")
async def create_checkout_session(
    body: CheckoutSessionRequest,
    client_uuid: UUID = Depends(require_client_scope),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not settings.stripe_price_id_pilot:
        raise HTTPException(status_code=503, detail="STRIPE_PRICE_ID_PILOT is not set")

    stripe = _stripe()
    result = await db.execute(select(Client).where(Client.id == client_uuid))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    customer_id = client.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(
            name=client.name,
            email=user.get("email"),
            metadata={"client_id": str(client_uuid)},
        )
        customer_id = customer.id
        client.stripe_customer_id = customer_id
        await db.commit()

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": settings.stripe_price_id_pilot, "quantity": 1}],
        success_url=body.success_url,
        cancel_url=body.cancel_url,
        metadata={"client_id": str(client_uuid)},
    )
    return {"checkout_url": session.url, "session_id": session.id}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook secret not configured")

    stripe = _stripe()
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )
    except Exception as exc:
        logger.warning("Stripe webhook verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid webhook signature") from exc

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        client_id = session.get("metadata", {}).get("client_id")
        subscription_id = session.get("subscription")
        if client_id and subscription_id:
            try:
                client_uuid = UUID(client_id)
            except ValueError:
                return {"received": True}
            result = await db.execute(select(Client).where(Client.id == client_uuid))
            client = result.scalar_one_or_none()
            if client:
                client.stripe_subscription_id = subscription_id
                await db.commit()

    return {"received": True}
