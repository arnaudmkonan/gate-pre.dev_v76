"""Billable usage events per client (metering for pilots)."""
from sqlalchemy import Column, String, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import BaseModel


class ClientUsageEvent(BaseModel):
    __tablename__ = "client_usage_events"

    client_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    resource_id = Column(String(255), nullable=True)
    event_metadata = Column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_usage_client_created", "client_id", "created_at"),
        Index("ix_usage_type_created", "event_type", "created_at"),
    )
