import logging
from typing import Optional

from celery import Celery
from celery.schedules import crontab
try:
    from celery.signals import after_return, task_failure
except ImportError:
    # In newer Celery versions, use task_postrun instead of after_return
    from celery.signals import task_postrun as after_return, task_failure

from app.core.config import settings

# Initialize Sentry for Celery
def init_sentry_celery():
    """Initialize Sentry in Celery context."""
    try:
        from app.sentry_init import init_sentry
        init_sentry()
    except Exception as e:
        logging.warning(f"Failed to initialize Sentry in Celery: {e}")

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery(
    "doc_ingestion",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Configure Celery
# Ingest work uses a dedicated queue so beat/maintenance tasks cannot starve uploads.
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_compression="gzip",
    result_expires=3600,
    task_default_queue="celery",
    task_routes={
        "app.workers.job_processor.process_ingest_job": {"queue": "ingest"},
        "app.workers.ingest_tasks.queue_raw_file": {"queue": "ingest"},
    },
    beat_schedule={
        "process-pending-retries": {
            "task": "app.workers.retry_worker.process_pending_retries",
            "schedule": 120.0,  # Every 2 minutes
            "options": {"expires": 110},
        },
        "schedule-batch-processor": {
            "task": "app.workers.batch_runner.schedule_batch_processor",
            "schedule": 300.0,  # Every 5 minutes
            "options": {"expires": 290},
        },
        "process-pending-jobs": {
            "task": "app.workers.job_processor.process_pending_jobs",
            # Safety net only — upload path enqueues directly onto `ingest`.
            "schedule": 60.0,
            "options": {"expires": 55, "queue": "ingest"},
        },
        "process-pending-agent-analysis": {
            "task": "app.workers.agent_processor.process_pending_documents",
            "schedule": 180.0,  # Every 3 minutes
            "options": {"expires": 170},
        },
        "process-pending-compliance": {
            "task": "app.workers.compliance_worker.process_pending_compliance",
            "schedule": 300.0,  # Every 5 minutes
            "options": {"expires": 290},
        },
        "run-scheduled-reports": {
            "task": "app.workers.report_worker.run_due_reports",
            "schedule": 300.0,  # Every 5 minutes — checks for due reports
            "options": {"expires": 290},
        },
        "cleanup-audit-logs": {
            "task": "app.workers.audit_worker.cleanup_old_audit_logs",
            "schedule": 86400.0,  # Once per day
            "options": {"expires": 86000},
        },
        # ---- Gap Closure: Deadline & Alert Tasks (added 2026-02-22) -------
        "check-isf-deadlines": {
            "task": "app.workers.deadline_worker.check_isf_deadlines",
            "schedule": 1800.0,   # Every 30 minutes — ISF 24h filing cut-off
            "options": {"expires": 1700},
        },
        "poll-ace-responses": {
            "task": "app.workers.deadline_worker.poll_ace_responses",
            "schedule": 900.0,    # Every 15 minutes — fetch ACE response files
            "options": {"expires": 850},
        },
        "check-bond-sufficiency": {
            "task": "app.workers.deadline_worker.check_bond_sufficiency",
            "schedule": crontab(hour=8, minute=0),  # Daily at 08:00 UTC
        },
        "check-review-sla": {
            "task": "app.workers.deadline_worker.check_review_sla",
            "schedule": 900.0,   # Every 15 minutes
            "options": {"expires": 850},
        },
        "check-overdue-invoices": {
            "task": "app.workers.deadline_worker.check_overdue_invoices",
            "schedule": crontab(hour=9, minute=0),  # Daily at 09:00 UTC
        },
        "monitor-email-inbox": {
            "task": "email.monitor_inbox",
            "schedule": float(max(1, settings.email_poll_interval_minutes) * 60),
            "options": {"expires": max(30, int(settings.email_poll_interval_minutes) * 60 - 10)},
        },
    },
)

# Task registration
celery_app.autodiscover_tasks(["app.workers"])

# Initialize Sentry when Celery starts
init_sentry_celery()


@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing."""
    logger.info(f"Debug task called: {self.request}")
