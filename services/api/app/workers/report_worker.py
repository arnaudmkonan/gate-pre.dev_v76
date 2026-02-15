"""
Celery worker for scheduled report execution.
"""
import logging
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.workers.report_worker.run_due_reports")
def run_due_reports(self):
    """
    Check for and execute any scheduled reports that are due.

    Called periodically by Celery beat (every 5 minutes).
    """
    import asyncio
    asyncio.run(_run_due_reports())


async def _run_due_reports():
    """Async implementation of report runner."""
    from app.core.database import AsyncSessionLocal
    from app.services.scheduled_report_service import ScheduledReportService

    async with AsyncSessionLocal() as db:
        service = ScheduledReportService(db)
        due = await service.get_due_schedules()

        if not due:
            return

        logger.info(f"Found {len(due)} due report(s) to generate")

        for schedule in due:
            try:
                result = await service.run_schedule(schedule.id)
                logger.info(f"Report generated: {schedule.name} (id={schedule.id}, status={result.status})")
            except Exception as e:
                logger.error(f"Failed to generate report {schedule.name}: {e}")
