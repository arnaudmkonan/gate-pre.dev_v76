"""
Email Ingestion API Routes.

Endpoints for managing email document ingestion.
"""

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.services.email_ingest_service import (
    EmailIngestService,
    check_email_configured,
    get_email_status,
)
from app.workers.email_monitor_worker import sync_email_now


router = APIRouter(prefix="/api/email", tags=["Email Ingestion"])


# ==================== Response Models ====================

class EmailStatusResponse(BaseModel):
    """Email connection status response."""
    configured: bool
    connected: bool
    host: Optional[str] = None
    username: Optional[str] = None
    folder: Optional[str] = None
    message_count: Optional[int] = None
    last_check: Optional[str] = None
    error: Optional[str] = None


class EmailSyncResponse(BaseModel):
    """Email sync result response."""
    status: str
    emails_found: int = 0
    emails_processed: int = 0
    documents_created: int = 0
    errors: list = []
    task_id: Optional[str] = None
    timestamp: str


class EmailConfigResponse(BaseModel):
    """Email configuration status."""
    configured: bool
    host: Optional[str] = None
    port: int = 993
    folder: str = "INBOX"
    poll_interval_minutes: int = 5
    message: Optional[str] = None


# ==================== Endpoints ====================

@router.get("/status", response_model=EmailStatusResponse)
async def get_status():
    """
    Get email connection status.
    
    Returns current connection state, message count, and any errors.
    """
    try:
        status = get_email_status()
        return EmailStatusResponse(**status)
    except Exception as e:
        return EmailStatusResponse(
            configured=check_email_configured(),
            connected=False,
            error=str(e)
        )


@router.get("/config", response_model=EmailConfigResponse)
async def get_config():
    """
    Get email ingestion configuration.
    
    Shows current email settings (without sensitive data).
    """
    from app.core.config import settings
    
    if not check_email_configured():
        return EmailConfigResponse(
            configured=False,
            message="Email not configured. Set EMAIL_IMAP_HOST, EMAIL_IMAP_USER, EMAIL_IMAP_PASSWORD"
        )
    
    return EmailConfigResponse(
        configured=True,
        host=settings.email_imap_host,
        port=settings.email_imap_port,
        folder=settings.email_folder,
        poll_interval_minutes=settings.email_poll_interval_minutes
    )


@router.post("/sync", response_model=EmailSyncResponse)
async def trigger_sync(background_tasks: BackgroundTasks):
    """
    Manually trigger email sync.
    
    Checks inbox for new emails with attachments and processes them.
    This runs asynchronously in the background.
    """
    if not check_email_configured():
        raise HTTPException(
            status_code=400,
            detail="Email not configured. Set EMAIL_IMAP_* environment variables."
        )
    
    # Trigger async task
    task = sync_email_now.delay()
    
    return EmailSyncResponse(
        status="started",
        task_id=task.id,
        timestamp=datetime.utcnow().isoformat()
    )


@router.post("/sync/blocking", response_model=EmailSyncResponse)
async def trigger_sync_blocking():
    """
    Trigger email sync and wait for completion.
    
    Synchronous version that waits for processing to complete.
    Use for testing or when you need immediate results.
    """
    if not check_email_configured():
        raise HTTPException(
            status_code=400,
            detail="Email not configured. Set EMAIL_IMAP_* environment variables."
        )
    
    # Run synchronously
    result = sync_email_now()
    
    return EmailSyncResponse(
        status=result.get("status", "unknown"),
        emails_found=result.get("emails_found", 0),
        emails_processed=result.get("emails_processed", 0),
        documents_created=result.get("documents_created", 0),
        errors=result.get("errors", []),
        timestamp=result.get("timestamp", datetime.utcnow().isoformat())
    )


@router.get("/test-connection")
async def test_connection():
    """
    Test email connection.
    
    Attempts to connect to the configured email server
    and returns connection details or error.
    """
    if not check_email_configured():
        return {
            "success": False,
            "error": "Email not configured",
            "help": "Set EMAIL_IMAP_HOST, EMAIL_IMAP_USER, EMAIL_IMAP_PASSWORD environment variables"
        }
    
    try:
        service = EmailIngestService()
        with service:
            status = service.get_status()
            
            return {
                "success": True,
                "host": status.get("host"),
                "username": status.get("username"),
                "folder": status.get("folder"),
                "message_count": status.get("message_count"),
                "message": f"Successfully connected to {status.get('host')}"
            }
    
    except ConnectionError as e:
        return {
            "success": False,
            "error": str(e),
            "help": "Check your email credentials and server settings"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
