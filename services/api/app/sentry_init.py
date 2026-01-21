"""Sentry error tracking initialization and configuration."""
import logging
from typing import Optional

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration

# Try importing FastAPI/Starlette integrations (newer SDK versions)
try:
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration
    HAS_FASTAPI_INTEGRATION = True
except ImportError:
    HAS_FASTAPI_INTEGRATION = False
    # Fallback for older SDK versions
    try:
        from sentry_sdk.integrations.asgi import AsgiIntegration
        HAS_ASGI_INTEGRATION = True
    except ImportError:
        HAS_ASGI_INTEGRATION = False

from app.core.config import settings

logger = logging.getLogger(__name__)


def init_sentry() -> None:
    """Initialize Sentry SDK with FastAPI integration and PII redaction."""
    if not settings.sentry_enabled:
        logger.info("Sentry is disabled, skipping initialization")
        return
    
    if not settings.sentry_dsn:
        logger.info("Sentry DSN not configured, skipping initialization")
        return

    # Configure logging integration
    logging_integration = LoggingIntegration(
        level=logging.INFO,  # Capture info and above as breadcrumbs
        event_level=logging.ERROR,  # Send errors as events
    )

    # Build integrations list
    integrations = [
        CeleryIntegration(),
        SqlalchemyIntegration(),
        logging_integration,
        RedisIntegration(),
    ]
    
    # Add FastAPI/Starlette integrations (newer SDK) or ASGI (older SDK)
    if HAS_FASTAPI_INTEGRATION:
        integrations.extend([FastApiIntegration(), StarletteIntegration()])
    elif HAS_ASGI_INTEGRATION:
        integrations.append(AsgiIntegration())

    # Initialize Sentry with integrations
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=getattr(settings, "sentry_traces_sample_rate", 0.1),
        integrations=integrations,
        before_send=before_send_hook,
        enable_tracing=True,
    )

    logger.info(
        f"Sentry initialized for environment: {settings.environment}",
        extra={"sentry_dsn": settings.sentry_dsn[:20] + "***"},
    )


def before_send_hook(event: dict, hint: dict) -> Optional[dict]:
    """
    Redact PII and sensitive data before sending to Sentry.

    Filters out:
    - Email addresses
    - Phone numbers
    - Credit card numbers
    - API keys and tokens
    - Passwords
    - Social security numbers
    """
    import re

    # Extract the exception value if present
    exc_info = hint.get("exc_info")

    # List of PII patterns to redact
    pii_patterns = {
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b": "[EMAIL]",
        r"\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b": "[PHONE]",
        r"\b(?:\d{4}[-\s]?){3}\d{4}\b": "[CARD]",
        r"(?i)(password|passwd|secret|api[_-]?key|token|auth)[:\s=]+[^\s,}\"]+": r"\1=[REDACTED]",
        r"\b\d{3}-\d{2}-\d{4}\b": "[SSN]",
    }

    def redact_value(text: str) -> str:
        """Redact sensitive patterns in text."""
        if not isinstance(text, str):
            return text
        for pattern, replacement in pii_patterns.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    # Redact exception values
    if "exception" in event:
        for exception in event.get("exception", {}).get("values", []):
            if "value" in exception:
                exception["value"] = redact_value(exception["value"])
            if "module" in exception:
                exception["module"] = redact_value(exception["module"])

    # Redact breadcrumb messages
    for breadcrumb in event.get("breadcrumbs", []):
        if "message" in breadcrumb:
            breadcrumb["message"] = redact_value(breadcrumb["message"])
        if "data" in breadcrumb and isinstance(breadcrumb["data"], dict):
            for key, value in breadcrumb["data"].items():
                if isinstance(value, str):
                    breadcrumb["data"][key] = redact_value(value)

    # Redact request data
    if "request" in event:
        request = event["request"]
        if "url" in request:
            request["url"] = redact_value(request["url"])
        if "cookies" in request:
            request["cookies"] = "[REDACTED]"
        if "headers" in request and isinstance(request["headers"], dict):
            for key in list(request["headers"].keys()):
                if any(
                    sensitive in key.lower()
                    for sensitive in ["auth", "token", "password", "cookie"]
                ):
                    request["headers"][key] = "[REDACTED]"

    # Redact extra context
    if "extra" in event and isinstance(event["extra"], dict):
        for key, value in event["extra"].items():
            if isinstance(value, str):
                event["extra"][key] = redact_value(value)

    # Redact tags
    if "tags" in event and isinstance(event["tags"], dict):
        for key, value in event["tags"].items():
            if isinstance(value, str):
                event["tags"][key] = redact_value(value)

    return event


def capture_exception(exception: Exception, **kwargs) -> None:
    """
    Capture an exception with Sentry.

    Args:
        exception: The exception to capture
        **kwargs: Additional context to include
    """
    if settings.sentry_dsn:
        sentry_sdk.capture_exception(exception, extra=kwargs)


def capture_message(message: str, level: str = "info", **kwargs) -> None:
    """
    Capture a message with Sentry.

    Args:
        message: The message to capture
        level: Log level (info, warning, error, debug)
        **kwargs: Additional context to include
    """
    if settings.sentry_dsn:
        sentry_sdk.capture_message(message, level=level, extra=kwargs)
