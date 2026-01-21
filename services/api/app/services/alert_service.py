"""Alert service for rule management and alert triggering."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from decimal import Decimal

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertRule, Alert
from app.schemas.alerts import (
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
    AlertResponse,
)

logger = logging.getLogger(__name__)


class AlertService:
    """Service for managing alert rules and alerts."""

    @staticmethod
    async def create_rule(
        session: AsyncSession,
        rule: AlertRuleCreate,
    ) -> AlertRuleResponse:
        """
        Create a new alert rule.

        Args:
            session: Database session
            rule: AlertRuleCreate schema

        Returns:
            Created AlertRuleResponse
        """
        try:
            alert_rule = AlertRule(
                name=rule.name,
                metric_type=rule.metric_type,
                threshold=rule.threshold,
                severity=rule.severity,
                evaluation_window_minutes=rule.evaluation_window_minutes,
                cooldown_period_minutes=rule.cooldown_period_minutes,
                escalation_policy=rule.escalation_policy.dict() if rule.escalation_policy else None,
                notification_channels=rule.notification_channels,
                enabled=rule.enabled,
            )

            session.add(alert_rule)
            await session.commit()
            await session.refresh(alert_rule)

            logger.info(f"Created alert rule: {alert_rule.id} ({rule.name})")
            return AlertService._to_rule_response(alert_rule)

        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating alert rule: {e}")
            raise

    @staticmethod
    async def get_rule(
        session: AsyncSession,
        rule_id: UUID,
    ) -> Optional[AlertRuleResponse]:
        """Get an alert rule by ID."""
        try:
            result = await session.execute(
                select(AlertRule).where(AlertRule.id == rule_id)
            )
            rule = result.scalar_one_or_none()
            return AlertService._to_rule_response(rule) if rule else None

        except Exception as e:
            logger.error(f"Error getting alert rule: {e}")
            raise

    @staticmethod
    async def list_rules(
        session: AsyncSession,
        enabled_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[AlertRuleResponse], int]:
        """
        List alert rules.

        Returns:
            Tuple of (rules, total_count)
        """
        try:
            query = select(AlertRule)

            if enabled_only:
                query = query.where(AlertRule.enabled == True)

            # Get total count
            count_result = await session.execute(query)
            total = len(count_result.scalars().all())

            # Get paginated results
            query = query.order_by(desc(AlertRule.created_at)).offset(offset).limit(limit)
            result = await session.execute(query)
            rules = result.scalars().all()

            return [AlertService._to_rule_response(r) for r in rules], total

        except Exception as e:
            logger.error(f"Error listing alert rules: {e}")
            raise

    @staticmethod
    async def update_rule(
        session: AsyncSession,
        rule_id: UUID,
        update: AlertRuleUpdate,
    ) -> AlertRuleResponse:
        """Update an alert rule."""
        try:
            result = await session.execute(
                select(AlertRule).where(AlertRule.id == rule_id)
            )
            rule = result.scalar_one_or_none()

            if not rule:
                raise ValueError(f"Alert rule {rule_id} not found")

            # Update fields
            if update.name is not None:
                rule.name = update.name
            if update.metric_type is not None:
                rule.metric_type = update.metric_type
            if update.threshold is not None:
                rule.threshold = update.threshold
            if update.severity is not None:
                rule.severity = update.severity
            if update.evaluation_window_minutes is not None:
                rule.evaluation_window_minutes = update.evaluation_window_minutes
            if update.cooldown_period_minutes is not None:
                rule.cooldown_period_minutes = update.cooldown_period_minutes
            if update.escalation_policy is not None:
                rule.escalation_policy = update.escalation_policy.dict()
            if update.notification_channels is not None:
                rule.notification_channels = update.notification_channels
            if update.enabled is not None:
                rule.enabled = update.enabled

            rule.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(rule)

            logger.info(f"Updated alert rule: {rule_id}")
            return AlertService._to_rule_response(rule)

        except Exception as e:
            await session.rollback()
            logger.error(f"Error updating alert rule: {e}")
            raise

    @staticmethod
    async def delete_rule(
        session: AsyncSession,
        rule_id: UUID,
    ) -> None:
        """Delete an alert rule."""
        try:
            result = await session.execute(
                select(AlertRule).where(AlertRule.id == rule_id)
            )
            rule = result.scalar_one_or_none()

            if not rule:
                raise ValueError(f"Alert rule {rule_id} not found")

            await session.delete(rule)
            await session.commit()

            logger.info(f"Deleted alert rule: {rule_id}")

        except Exception as e:
            await session.rollback()
            logger.error(f"Error deleting alert rule: {e}")
            raise

    @staticmethod
    async def trigger_alert(
        session: AsyncSession,
        rule_id: UUID,
        metric_value: Decimal,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> AlertResponse:
        """
        Trigger an alert for a rule breach.

        Args:
            session: Database session
            rule_id: Alert rule ID
            metric_value: Current metric value
            context_data: Additional context information

        Returns:
            Created AlertResponse
        """
        try:
            # Get the rule
            result = await session.execute(
                select(AlertRule).where(AlertRule.id == rule_id)
            )
            rule = result.scalar_one_or_none()

            if not rule:
                raise ValueError(f"Alert rule {rule_id} not found")

            # Create the alert
            alert = Alert(
                alert_rule_id=rule_id,
                severity=rule.severity,
                metric_value=metric_value,
                threshold=rule.threshold,
                status="active",
                context_data=context_data,
            )

            session.add(alert)
            await session.commit()
            await session.refresh(alert)

            logger.info(f"Triggered alert: {alert.id} for rule {rule_id}")
            return AlertService._to_alert_response(alert)

        except Exception as e:
            await session.rollback()
            logger.error(f"Error triggering alert: {e}")
            raise

    @staticmethod
    async def get_alert(
        session: AsyncSession,
        alert_id: UUID,
    ) -> Optional[AlertResponse]:
        """Get an alert by ID."""
        try:
            result = await session.execute(
                select(Alert).where(Alert.id == alert_id)
            )
            alert = result.scalar_one_or_none()
            return AlertService._to_alert_response(alert) if alert else None

        except Exception as e:
            logger.error(f"Error getting alert: {e}")
            raise

    @staticmethod
    async def list_active_alerts(
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[AlertResponse], int]:
        """List active alerts."""
        try:
            query = select(Alert).where(Alert.status == "active")

            # Get total count
            count_result = await session.execute(query)
            total = len(count_result.scalars().all())

            # Get paginated results
            query = query.order_by(desc(Alert.created_at)).offset(offset).limit(limit)
            result = await session.execute(query)
            alerts = result.scalars().all()

            return [AlertService._to_alert_response(a) for a in alerts], total

        except Exception as e:
            logger.error(f"Error listing active alerts: {e}")
            raise

    @staticmethod
    async def acknowledge_alert(
        session: AsyncSession,
        alert_id: UUID,
        acknowledged_by: UUID,
    ) -> AlertResponse:
        """Acknowledge an alert."""
        try:
            result = await session.execute(
                select(Alert).where(Alert.id == alert_id)
            )
            alert = result.scalar_one_or_none()

            if not alert:
                raise ValueError(f"Alert {alert_id} not found")

            alert.status = "acknowledged"
            alert.acknowledged_at = datetime.now(timezone.utc)
            alert.acknowledged_by = acknowledged_by
            alert.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(alert)

            logger.info(f"Acknowledged alert: {alert_id}")
            return AlertService._to_alert_response(alert)

        except Exception as e:
            await session.rollback()
            logger.error(f"Error acknowledging alert: {e}")
            raise

    @staticmethod
    async def resolve_alert(
        session: AsyncSession,
        alert_id: UUID,
        resolved_by: UUID,
    ) -> AlertResponse:
        """Resolve an alert."""
        try:
            result = await session.execute(
                select(Alert).where(Alert.id == alert_id)
            )
            alert = result.scalar_one_or_none()

            if not alert:
                raise ValueError(f"Alert {alert_id} not found")

            alert.status = "resolved"
            alert.resolved_at = datetime.now(timezone.utc)
            alert.resolved_by = resolved_by
            alert.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(alert)

            logger.info(f"Resolved alert: {alert_id}")
            return AlertService._to_alert_response(alert)

        except Exception as e:
            await session.rollback()
            logger.error(f"Error resolving alert: {e}")
            raise

    @staticmethod
    def _to_rule_response(rule: AlertRule) -> AlertRuleResponse:
        """Convert AlertRule to AlertRuleResponse."""
        return AlertRuleResponse(
            id=rule.id,
            name=rule.name,
            metric_type=rule.metric_type,
            threshold=rule.threshold,
            severity=rule.severity,
            evaluation_window_minutes=rule.evaluation_window_minutes,
            cooldown_period_minutes=rule.cooldown_period_minutes,
            escalation_policy=rule.escalation_policy,
            notification_channels=rule.notification_channels,
            enabled=rule.enabled,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )

    @staticmethod
    def _to_alert_response(alert: Alert) -> AlertResponse:
        """Convert Alert to AlertResponse."""
        return AlertResponse(
            id=alert.id,
            alert_rule_id=alert.alert_rule_id,
            severity=alert.severity,
            metric_value=alert.metric_value,
            threshold=alert.threshold,
            status=alert.status,
            acknowledged_at=alert.acknowledged_at,
            acknowledged_by=alert.acknowledged_by,
            resolved_at=alert.resolved_at,
            resolved_by=alert.resolved_by,
            notification_sent_at=alert.notification_sent_at,
            context_data=alert.context_data,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
        )
