"""
GATE Platform — Webhook Models.

Stores webhook endpoint registrations and delivery history.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class WebhookEndpoint(Base):
    """Customer-registered webhook endpoint."""
    __tablename__ = "webhook_endpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True)

    # Endpoint configuration
    url = Column(String, nullable=False)
    name = Column(String, nullable=False, default="Webhook")
    secret = Column(String, nullable=False)  # HMAC secret for signature verification
    events = Column(JSON, nullable=False, default=list)  # List of event types to subscribe to

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    failure_count = Column(Integer, default=0)  # Consecutive failures
    max_failures = Column(Integer, default=10)  # Disable after N consecutive failures

    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    deliveries = relationship("WebhookDelivery", back_populates="endpoint", cascade="all, delete-orphan")


class WebhookDelivery(Base):
    """Individual webhook delivery attempt."""
    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    endpoint_id = Column(UUID(as_uuid=True), ForeignKey("webhook_endpoints.id"), nullable=False)

    # Event
    event_type = Column(String, nullable=False)  # e.g., "entry.created"
    payload = Column(JSON, nullable=False)

    # Delivery status
    status = Column(String, default="pending")  # pending, delivered, failed
    response_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    # Retry tracking
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)

    # Timing
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    endpoint = relationship("WebhookEndpoint", back_populates="deliveries")
