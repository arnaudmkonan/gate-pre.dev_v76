import logging
from typing import Optional

from celery import Celery
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
    beat_schedule={
        "process-pending-retries": {
            "task": "app.workers.retry_worker.process_pending_retries",
            "schedule": 60.0,  # Every 1 minute
        },
        "schedule-batch-processor": {
            "task": "app.workers.batch_runner.schedule_batch_processor",
            "schedule": 300.0,  # Every 5 minutes
        },
        "process-pending-jobs": {
            "task": "app.workers.job_processor.process_pending_jobs",
            "schedule": 30.0,  # Every 30 seconds
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
