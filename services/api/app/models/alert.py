"""Alert and alert rule models."""

from sqlalchemy import Column, String, Integer, Boolean, Numeric, ForeignKey, Index, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSON

from app.models.base import BaseModel


class AlertRule(BaseModel):
    """Configuration for alert thresholds and evaluation policies."""

    __tablename__ = "alert_rules"

    name = Column(String(255), nullable=False)
    metric_type = Column(String(100), nullable=False)  # error_rate, dlq_size, pipeline_latency, sla_breach
    threshold = Column(Numeric(10, 2), nullable=False)
    severity = Column(String(50), nullable=False, default="warning")  # critical, warning, info
    evaluation_window_minutes = Column(Integer, nullable=False, default=5)
    cooldown_period_minutes = Column(Integer, nullable=False, default=15)
    escalation_policy = Column(JSON, nullable=True)  # {enabled: bool, escalate_after_count: int, escalate_to: [emails]}
    notification_channels = Column(JSON, nullable=False, default='["email"]')  # email, webhook, slack
    enabled = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("idx_alert_rules_metric_type", "metric_type"),
        Index("idx_alert_rules_enabled", "enabled"),
        Index("idx_alert_rules_created_at", "created_at"),
    )


class Alert(BaseModel):
    """Individual alert instance triggered by rule breaches."""

    __tablename__ = "alerts"

    alert_rule_id = Column(UUID(as_uuid=True), ForeignKey("alert_rules.id"), nullable=False)
    severity = Column(String(50), nullable=False)
    metric_value = Column(Numeric(10, 2), nullable=False)
    threshold = Column(Numeric(10, 2), nullable=False)
    status = Column(String(50), nullable=False, default="active")  # active, acknowledged, resolved
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(UUID(as_uuid=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(UUID(as_uuid=True), nullable=True)
    notification_sent_at = Column(DateTime(timezone=True), nullable=True)
    context_data = Column(JSON, nullable=True)  # Pipeline details, affected file IDs, error logs

    __table_args__ = (
        Index("idx_alerts_alert_rule_id", "alert_rule_id"),
        Index("idx_alerts_severity", "severity"),
        Index("idx_alerts_status", "status"),
        Index("idx_alerts_created_at", "created_at"),
    )
