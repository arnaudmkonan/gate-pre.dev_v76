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
from app.core.auth import get_current_user


router = APIRouter(prefix="/api/email", tags=["Email Ingestion"], dependencies=[Depends(get_current_user)])


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


class InboundEmailAttachment(BaseModel):
    filename: str
    content_base64: str
    content_type: Optional[str] = "application/octet-stream"


class InboundEmailWebhookRequest(BaseModel):
    sender: str
    subject: Optional[str] = ""
    recipient: Optional[str] = "imports@gate.local"
    attachments: list[InboundEmailAttachment] = []


@router.post("/inbound-webhook")
async def process_inbound_email_webhook(
    payload: InboundEmailWebhookRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Zero-Click Inbound Email Webhook ("Forward to GATES").
    Accepts forwarded email payloads with base64 attachments (compatible with
    SendGrid/Postmark/Mailgun inbound webhooks), saves each attachment to storage,
    creates RawFile & IngestJob records, and immediately dispatches pipeline extraction.
    """
    import base64
    from app.core.database import AsyncSessionLocal
    from app.models.raw_file import RawFile, RawFileStatus
    from app.models.ingest_job import IngestJob, IngestJobStatus
    from app.services.local_storage_service import LocalStorageService

    storage = LocalStorageService()
    created_jobs = []
    uploader_id = current_user.get("id")

    async with AsyncSessionLocal() as session:
        for att in payload.attachments:
            try:
                file_bytes = base64.b64decode(att.content_base64)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Invalid base64 attachment {att.filename}: {exc}")

            ext = att.filename.rsplit(".", 1)[-1].lower() if "." in att.filename else "txt"
            storage_res = storage.upload_file(
                file_bytes=file_bytes,
                filename=att.filename,
                content_type=att.content_type or "application/octet-stream",
            )

            raw_file = RawFile(
                filename=att.filename,
                file_type=ext,
                file_size=len(file_bytes),
                storage_path=storage_res["storage_path"],
                mime_type=att.content_type or "application/octet-stream",
                status=RawFileStatus.QUEUED,
                uploader_id=uploader_id,
                source=f"email:{payload.sender}",
                tags=["inbound_email", payload.subject[:50]] if payload.subject else ["inbound_email"],
                checksum=storage_res["checksum"],
            )
            session.add(raw_file)
            await session.flush()

            job = IngestJob(
                filename=att.filename,
                file_type=ext,
                size=len(file_bytes),
                storage_path=storage_res["storage_path"],
                status=IngestJobStatus.PENDING,
                uploader_id=uploader_id,
            )
            session.add(job)
            await session.flush()

            created_jobs.append({
                "filename": att.filename,
                "file_id": str(raw_file.id),
                "job_id": str(job.id),
                "size": len(file_bytes),
            })

        await session.commit()

    # Dispatch async extraction jobs
    for cj in created_jobs:
        try:
            from app.workers.job_processor import process_ingest_job
            process_ingest_job.delay(cj["job_id"])
        except Exception:
            pass

    return {
        "status": "accepted",
        "sender": payload.sender,
        "subject": payload.subject,
        "attachments_received": len(payload.attachments),
        "jobs_created": created_jobs,
        "timestamp": datetime.utcnow().isoformat(),
    }
