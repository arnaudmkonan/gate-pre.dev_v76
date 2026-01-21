"""Pydantic schemas for alert endpoints."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, Field


class EscalationPolicy(BaseModel):
    """Escalation policy for alerts."""

    enabled: bool = False
    escalate_after_count: int = 3
    escalate_to: List[str] = Field(default_factory=list)


class AlertRuleCreate(BaseModel):
    """Create an alert rule."""

    name: str
    metric_type: str  # error_rate, dlq_size, pipeline_latency, sla_breach
    threshold: Decimal
    severity: str = "warning"  # critical, warning, info
    evaluation_window_minutes: int = 5
    cooldown_period_minutes: int = 15
    escalation_policy: Optional[EscalationPolicy] = None
    notification_channels: List[str] = Field(default=["email"])  # email, webhook, slack
    enabled: bool = True


class AlertRuleResponse(BaseModel):
    """Response for an alert rule."""

    id: UUID
    name: str
    metric_type: str
    threshold: Decimal
    severity: str
    evaluation_window_minutes: int
    cooldown_period_minutes: int
    escalation_policy: Optional[EscalationPolicy] = None
    notification_channels: List[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class AlertRuleUpdate(BaseModel):
    """Update an alert rule."""

    name: Optional[str] = None
    metric_type: Optional[str] = None
    threshold: Optional[Decimal] = None
    severity: Optional[str] = None
    evaluation_window_minutes: Optional[int] = None
    cooldown_period_minutes: Optional[int] = None
    escalation_policy: Optional[EscalationPolicy] = None
    notification_channels: Optional[List[str]] = None
    enabled: Optional[bool] = None


class AlertResponse(BaseModel):
    """Response for an alert instance."""

    id: UUID
    alert_rule_id: UUID
    severity: str
    metric_value: Decimal
    threshold: Decimal
    status: str  # active, acknowledged, resolved
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[UUID] = None
    notification_sent_at: Optional[datetime] = None
    context_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class TestNotificationRequest(BaseModel):
    """Request to send a test notification."""

    channel: str  # email, webhook, slack
    recipient: str  # email address or webhook URL
    alert_rule_id: Optional[UUID] = None


class TestNotificationResponse(BaseModel):
    """Response from test notification."""

    success: bool
    message: str
    timestamp: datetime
