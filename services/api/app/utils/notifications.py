"""Notification sender utility for alerts."""

import logging
import asyncio
import smtplib
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationSender:
    """Send notifications via email and webhook."""

    @staticmethod
    async def send_email(
        recipient: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        retry_count: int = 3,
    ) -> bool:
        """
        Send an email notification.

        Args:
            recipient: Email address
            subject: Email subject
            body: Plain text body
            html_body: HTML body (optional)
            retry_count: Number of retries

        Returns:
            True if successful, False otherwise
        """
        try:
            if not settings.smtp_host or not settings.smtp_port:
                logger.warning("SMTP configuration not set, skipping email notification")
                return False

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.smtp_from_email
            msg["To"] = recipient

            # Attach plain text
            msg.attach(MIMEText(body, "plain"))

            # Attach HTML if provided
            if html_body:
                msg.attach(MIMEText(html_body, "html"))

            # Send with retries
            for attempt in range(retry_count):
                try:
                    # Use async executor to avoid blocking
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        lambda: NotificationSender._send_smtp(msg, recipient),
                    )

                    logger.info(f"Email sent to {recipient}")
                    return True

                except Exception as e:
                    if attempt == retry_count - 1:
                        raise
                    logger.warning(f"Retry {attempt + 1} for email to {recipient}: {e}")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        except Exception as e:
            logger.error(f"Error sending email to {recipient}: {e}")
            return False

    @staticmethod
    async def send_webhook(
        webhook_url: str,
        payload: Dict[str, Any],
        retry_count: int = 3,
    ) -> bool:
        """
        Send a webhook notification.

        Args:
            webhook_url: Webhook URL
            payload: JSON payload
            retry_count: Number of retries

        Returns:
            True if successful, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for attempt in range(retry_count):
                    try:
                        response = await client.post(webhook_url, json=payload)
                        response.raise_for_status()

                        logger.info(f"Webhook sent to {webhook_url}")
                        return True

                    except Exception as e:
                        if attempt == retry_count - 1:
                            raise
                        logger.warning(f"Retry {attempt + 1} for webhook to {webhook_url}: {e}")
                        await asyncio.sleep(2 ** attempt)

        except Exception as e:
            logger.error(f"Error sending webhook to {webhook_url}: {e}")
            return False

    @staticmethod
    def _send_smtp(msg: MIMEMultipart, recipient: str) -> None:
        """Send SMTP message (blocking)."""
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_tls:
                server.starttls()

            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)

            server.send_message(msg)

    @staticmethod
    def create_alert_email_body(
        alert_name: str,
        metric_value: float,
        threshold: float,
        severity: str,
        timestamp: datetime,
        context: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, str]:
        """
        Create email body for alert notification.

        Args:
            alert_name: Alert name
            metric_value: Current metric value
            threshold: Threshold value
            severity: Severity level
            timestamp: Alert timestamp
            context: Additional context

        Returns:
            Tuple of (plain_text, html_body)
        """
        plain_text = f"""
Alert: {alert_name}
Severity: {severity}

Current Value: {metric_value}
Threshold: {threshold}
Triggered At: {timestamp.isoformat()}

{f"Context: {context}" if context else ""}
"""

        html_body = f"""
<html>
  <body>
    <h2>Alert: {alert_name}</h2>
    <p><strong>Severity:</strong> <span style="color: {'red' if severity == 'critical' else 'orange'}">{severity.upper()}</span></p>
    <hr />
    <p><strong>Current Value:</strong> {metric_value}</p>
    <p><strong>Threshold:</strong> {threshold}</p>
    <p><strong>Triggered At:</strong> {timestamp.isoformat()}</p>
    {f"<p><strong>Context:</strong> {context}</p>" if context else ""}
  </body>
</html>
"""

        return plain_text, html_body

    @staticmethod
    def create_alert_webhook_payload(
        alert_id: str,
        alert_name: str,
        metric_value: float,
        threshold: float,
        severity: str,
        timestamp: datetime,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create webhook payload for alert notification.

        Args:
            alert_id: Alert ID
            alert_name: Alert name
            metric_value: Current metric value
            threshold: Threshold value
            severity: Severity level
            timestamp: Alert timestamp
            context: Additional context

        Returns:
            Webhook payload dict
        """
        return {
            "alert_id": alert_id,
            "alert_name": alert_name,
            "metric_value": metric_value,
            "threshold": threshold,
            "severity": severity,
            "timestamp": timestamp.isoformat(),
            "context": context,
        }
