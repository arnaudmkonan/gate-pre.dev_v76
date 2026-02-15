"""FastAPI routes for alert management endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.alert_service import AlertService
from app.utils.notifications import NotificationSender
from app.schemas.alerts import (
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertRuleResponse,
    AlertResponse,
    TestNotificationRequest,
    TestNotificationResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.post("/rules", response_model=AlertRuleResponse)
async def create_alert_rule(
    rule: AlertRuleCreate,
    session: AsyncSession = Depends(get_db),
):
    """Create a new alert rule."""
    try:
        return await AlertService.create_rule(session=session, rule=rule)
    except Exception as e:
        logger.error(f"Error creating alert rule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating alert rule",
        )


@router.get("/rules", response_model=dict)
async def list_alert_rules(
    enabled_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """List all alert rules."""
    try:
        rules, total = await AlertService.list_rules(
            session=session,
            enabled_only=enabled_only,
            limit=limit,
            offset=offset,
        )

        return {
            "rules": rules,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"Error listing alert rules: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving alert rules",
        )


@router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(
    rule_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get an alert rule by ID."""
    try:
        rule = await AlertService.get_rule(session=session, rule_id=rule_id)

        if not rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert rule not found",
            )

        return rule

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting alert rule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving alert rule",
        )


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: UUID,
    update: AlertRuleUpdate,
    session: AsyncSession = Depends(get_db),
):
    """Update an alert rule."""
    try:
        return await AlertService.update_rule(
            session=session,
            rule_id=rule_id,
            update=update,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error updating alert rule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating alert rule",
        )


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Delete an alert rule."""
    try:
        await AlertService.delete_rule(session=session, rule_id=rule_id)
        return {"message": "Alert rule deleted successfully"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error deleting alert rule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting alert rule",
        )


@router.post("/test-notification", response_model=TestNotificationResponse)
async def test_notification(
    request: TestNotificationRequest,
):
    """Send a test notification."""
    try:
        success = False
        message = "Test notification sending not implemented"

        if request.channel == "email":
            success = await NotificationSender.send_email(
                recipient=request.recipient,
                subject="Test Alert Notification",
                body="This is a test notification from the documentation ingestion platform.",
                html_body="<html><body><h2>Test Alert Notification</h2><p>This is a test notification from the documentation ingestion platform.</p></body></html>",
            )
            message = "Test email sent successfully" if success else "Failed to send test email"

        elif request.channel == "webhook":
            success = await NotificationSender.send_webhook(
                webhook_url=request.recipient,
                payload={
                    "alert_name": "Test Alert",
                    "severity": "info",
                    "message": "This is a test notification",
                },
            )
            message = "Test webhook sent successfully" if success else "Failed to send test webhook"

        return TestNotificationResponse(
            success=success,
            message=message,
            timestamp=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        )

    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error sending test notification",
        )
