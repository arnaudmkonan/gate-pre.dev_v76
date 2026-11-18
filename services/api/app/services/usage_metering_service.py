"""Record and summarize per-client usage for billing pilots."""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client_usage_event import ClientUsageEvent

logger = logging.getLogger(__name__)

EVENT_DOCUMENT_UPLOADED = "document_uploaded"
EVENT_EXTRACTION_COMPLETED = "extraction_completed"
EVENT_ACE_TRANSMIT = "ace_transmit"


class UsageMeteringService:
    @staticmethod
    def add_event(
        session: AsyncSession,
        event_type: str,
        *,
        client_id: Optional[UUID] = None,
        quantity: int = 1,
        resource_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        session.add(
            ClientUsageEvent(
                client_id=client_id,
                event_type=event_type,
                quantity=quantity,
                resource_id=resource_id,
                event_metadata=metadata,
            )
        )

    @staticmethod
    async def record(
        session: AsyncSession,
        event_type: str,
        *,
        client_id: Optional[UUID] = None,
        quantity: int = 1,
        resource_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        try:
            session.add(
                ClientUsageEvent(
                    client_id=client_id,
                    event_type=event_type,
                    quantity=quantity,
                    resource_id=resource_id,
                    event_metadata=metadata,
                )
            )
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.warning("Failed to record usage event %s: %s", event_type, e)

    @staticmethod
    async def summary(
        session: AsyncSession,
        client_id: UUID,
        days: int = 30,
    ) -> dict[str, Any]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = await session.execute(
            select(
                ClientUsageEvent.event_type,
                func.coalesce(func.sum(ClientUsageEvent.quantity), 0),
            )
            .where(
                ClientUsageEvent.client_id == client_id,
                ClientUsageEvent.created_at >= since,
            )
            .group_by(ClientUsageEvent.event_type)
        )
        by_type = {event_type: int(total) for event_type, total in rows.all()}
        return {
            "client_id": str(client_id),
            "period_days": days,
            "since": since.isoformat(),
            "totals": by_type,
            "documents_processed": by_type.get(EVENT_DOCUMENT_UPLOADED, 0),
            "extractions_completed": by_type.get(EVENT_EXTRACTION_COMPLETED, 0),
            "ace_transmissions": by_type.get(EVENT_ACE_TRANSMIT, 0),
        }
