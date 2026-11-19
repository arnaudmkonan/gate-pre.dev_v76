"""Tenant / client scoping for portal users."""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.client_portal import ClientUserRole


def is_broker_admin(user: dict) -> bool:
    return user.get("role") in (ClientUserRole.ADMIN.value, "broker_admin")


def is_broker_staff(user: dict) -> bool:
    """True for brokerage admins and entry writers (cross-importer access)."""
    return is_broker_admin(user) or user.get("role") == ClientUserRole.BROKER_STAFF.value


def portal_user_client_id(user: dict) -> Optional[UUID]:
    """Client UUID for importer-scoped portal users, or None for brokerage staff."""
    if is_broker_staff(user):
        return None
    raw = user.get("client_id")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not linked to a client organization",
        )
    try:
        return UUID(str(raw))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid client on user profile") from exc


async def assert_user_can_access_client(
    user: dict,
    client_id: UUID,
) -> None:
    """Brokerage staff may access any client; importer portal users only their own client_id."""
    if is_broker_staff(user):
        return
    user_client = user.get("client_id")
    if not user_client or str(client_id) != str(user_client):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this client's data",
        )


async def require_client_scope(
    client_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """FastAPI dependency: validates path `client_id` against the current user."""
    del db
    try:
        client_uuid = UUID(client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid client ID") from exc
    await assert_user_can_access_client(user, client_uuid)
    return client_uuid


async def require_invoice_scope(
    invoice_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    from app.models.client_billing import ClientInvoice

    try:
        invoice_uuid = UUID(invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid invoice ID") from exc

    result = await db.execute(select(ClientInvoice).where(ClientInvoice.id == invoice_uuid))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    await assert_user_can_access_client(user, invoice.client_id)
    return invoice_uuid


async def require_fee_config_scope(
    config_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    from app.models.client_billing import ClientFeeConfig

    try:
        config_uuid = UUID(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid config ID") from exc

    result = await db.execute(select(ClientFeeConfig).where(ClientFeeConfig.id == config_uuid))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Fee configuration not found")
    await assert_user_can_access_client(user, config.client_id)
    return config_uuid


async def assert_template_belongs_to_client(
    db: AsyncSession,
    template_id: UUID,
    client_id: UUID,
    *,
    user: dict,
) -> None:
    """Ensure a client-scoped template route cannot access another tenant's template."""
    from app.models.extraction_template import ExtractionTemplate

    result = await db.execute(
        select(ExtractionTemplate).where(ExtractionTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    owner = template.customer_id
    if owner is None:
        if not is_broker_admin(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only broker admins may access global templates via client routes",
            )
        return

    if str(owner) != str(client_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Template does not belong to this client",
        )
