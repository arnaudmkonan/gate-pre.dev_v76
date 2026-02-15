"""
Celery worker for audit log maintenance.
"""
import logging
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.workers.audit_worker.cleanup_old_audit_logs")
def cleanup_old_audit_logs(self):
    """
    Clean up audit logs older than the retention period (180 days).

    Called once per day by Celery beat.
    """
    import asyncio
    asyncio.run(_cleanup())


async def _cleanup():
    """Async implementation of audit log cleanup."""
    from app.core.database import AsyncSessionLocal
    from app.services.audit_service import AuditService

    async with AsyncSessionLocal() as db:
        result = await AuditService.cleanup_old_logs(db)
        logger.info(f"Audit cleanup: deleted {result['deleted_count']} logs older than {result['cutoff_date']}")
