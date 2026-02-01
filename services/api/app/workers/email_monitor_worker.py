"""
Email Monitor Celery Worker.

Periodically checks email inbox for new documents to process.

Scheduled via Celery Beat to run every EMAIL_POLL_INTERVAL_MINUTES.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_sync_db
from app.services.email_ingest_service import (
    EmailIngestService,
    EmailMessage,
    IngestionResult,
    check_email_configured,
)

logger = logging.getLogger(__name__)


@shared_task(
    name="email.monitor_inbox",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def monitor_email_inbox(self) -> Dict[str, Any]:
    """
    Celery task to monitor email inbox for new documents.
    
    Returns:
        Dict with processing results
    """
    if not check_email_configured():
        logger.info("Email ingestion not configured, skipping")
        return {
            "status": "skipped",
            "reason": "Email not configured",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    logger.info("Starting email inbox monitor task")
    
    try:
        service = EmailIngestService()
        
        with service:
            # Fetch unread emails with attachments
            emails = service.fetch_unread_emails(limit=20)
            
            if not emails:
                logger.info("No new emails with attachments found")
                return {
                    "status": "success",
                    "emails_found": 0,
                    "documents_created": 0,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            logger.info(f"Found {len(emails)} emails with attachments")
            
            # Process each email
            results = []
            total_docs = 0
            
            for email_msg in emails:
                result = process_email_attachments(email_msg, service)
                results.append(result)
                total_docs += result.documents_created
                
                # Mark as processed if successful
                if result.success:
                    try:
                        service.mark_as_processed(email_msg.message_id)
                    except Exception as e:
                        logger.warning(f"Failed to mark email as processed: {e}")
            
            return {
                "status": "success",
                "emails_found": len(emails),
                "emails_processed": len([r for r in results if r.success]),
                "documents_created": total_docs,
                "errors": [r.error for r in results if r.error],
                "timestamp": datetime.utcnow().isoformat()
            }
    
    except ConnectionError as e:
        logger.error(f"Email connection error: {e}")
        # Retry on connection errors
        raise self.retry(exc=e)
    
    except Exception as e:
        logger.exception(f"Email monitor task failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


def process_email_attachments(
    email_msg: EmailMessage,
    service: EmailIngestService
) -> IngestionResult:
    """
    Process attachments from a single email.
    
    Saves attachments and triggers document processing pipeline.
    """
    from app.services.local_storage_service import LocalStorageService
    
    logger.info(
        f"Processing email from {email_msg.sender_email}: "
        f"{email_msg.subject} ({len(email_msg.attachments)} attachments)"
    )
    
    document_ids = []
    errors = []
    
    with get_sync_db() as session:
        storage = LocalStorageService()
        
        for attachment in email_msg.attachments:
            try:
                # Save to temp file
                temp_path = service.save_attachment_temp(attachment)
                
                # Upload to storage using LocalStorageService
                with open(temp_path, 'rb') as f:
                    file_bytes = f.read()
                    upload_result = storage.upload_file(
                        file_bytes=file_bytes,
                        filename=attachment.filename,
                        content_type=attachment.content_type
                    )
                
                storage_path = upload_result.get("storage_path", f"uploads/{attachment.filename}")
                
                # Determine file type from extension
                file_ext = attachment.filename.rsplit('.', 1)[-1].lower() if '.' in attachment.filename else ''
                
                # Create IngestJob record for the processing pipeline
                from app.models.ingest_job import IngestJob, IngestJobStatus
                
                ingest_job = IngestJob(
                    filename=attachment.filename,
                    file_type=file_ext,
                    size=attachment.size,
                    storage_path=storage_path,
                    status=IngestJobStatus.PENDING,
                    uploader_id="email-ingestion",
                    extracted_metadata={
                        "source": "email",
                        "email_sender": email_msg.sender_email,
                        "email_subject": email_msg.subject,
                        "email_date": email_msg.date.isoformat(),
                        "message_id": email_msg.message_id,
                        "mime_type": attachment.content_type
                    }
                )
                
                session.add(ingest_job)
                session.commit()
                session.refresh(ingest_job)
                
                document_ids.append(str(ingest_job.id))
                
                logger.info(f"Created ingest job {ingest_job.id} from email attachment: {attachment.filename}")
                
                # Cleanup temp file
                import os
                os.unlink(temp_path)
                
            except Exception as e:
                logger.error(f"Failed to process attachment {attachment.filename}: {e}")
                errors.append(f"{attachment.filename}: {str(e)}")
    
    return IngestionResult(
        email_id=email_msg.message_id,
        success=len(errors) == 0,
        documents_created=len(document_ids),
        document_ids=document_ids,
        error="; ".join(errors) if errors else None
    )


@shared_task(name="email.trigger_processing")
def trigger_document_processing(document_id: str):
    """
    Trigger the document processing pipeline for an uploaded document.
    
    This is a lightweight task that delegates to the main processing pipeline.
    """
    from app.workers.extraction_worker import process_document_task
    
    logger.info(f"Triggering processing for document: {document_id}")
    process_document_task.delay(document_id)


@shared_task(name="email.sync_now")
def sync_email_now() -> Dict[str, Any]:
    """
    Manually triggered email sync.
    
    Same as monitor_email_inbox but can be called on demand.
    """
    return monitor_email_inbox()


# Celery Beat schedule entry
# Add this to your celery beat schedule config:
#
# CELERY_BEAT_SCHEDULE = {
#     'monitor-email-inbox': {
#         'task': 'email.monitor_inbox',
#         'schedule': crontab(minute=f'*/{settings.email_poll_interval_minutes}'),
#     },
# }
