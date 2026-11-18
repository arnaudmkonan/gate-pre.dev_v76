"""Aggregate health for workers, queues, and ingest DLQ (admin observability)."""
import asyncio
import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.dead_letter_queue import DeadLetterQueue
from app.models.ingest_job import IngestJob

logger = logging.getLogger(__name__)


def _celery_worker_probe() -> dict[str, Any]:
    try:
        from app.core.celery_app import celery_app

        inspect = celery_app.control.inspect(timeout=2.0)
        if not inspect:
            return {"status": "unknown", "worker_count": 0, "workers": []}

        ping = inspect.ping() or {}
        active = inspect.active() or {}
        return {
            "status": "ok" if ping else "degraded",
            "worker_count": len(ping),
            "workers": sorted(ping.keys()),
            "active_tasks": sum(len(tasks) for tasks in active.values()),
        }
    except Exception as e:
        logger.warning("Celery worker probe failed: %s", e)
        return {"status": "error", "error": str(e), "worker_count": 0, "workers": []}


def _redis_broker_probe() -> dict[str, Any]:
    try:
        import redis

        client = redis.from_url(settings.celery_broker_url, decode_responses=True)
        queue_depth = client.llen("celery")
        client.close()
        return {"status": "ok", "celery_queue_depth": queue_depth}
    except Exception as e:
        logger.warning("Redis broker probe failed: %s", e)
        return {"status": "error", "error": str(e)}


class PlatformHealthService:
    @staticmethod
    async def get_snapshot(session: AsyncSession) -> dict[str, Any]:
        celery_workers, redis_broker = await asyncio.gather(
            asyncio.to_thread(_celery_worker_probe),
            asyncio.to_thread(_redis_broker_probe),
        )

        ingest_counts: dict[str, int] = {}
        try:
            rows = await session.execute(
                select(IngestJob.status, func.count(IngestJob.id)).group_by(IngestJob.status)
            )
            for status, count in rows.all():
                ingest_counts[str(status)] = int(count)
        except Exception as e:
            logger.warning("Ingest job counts failed: %s", e)

        dlq_pending = 0
        try:
            result = await session.execute(
                select(func.count(DeadLetterQueue.id)).where(
                    DeadLetterQueue.status == "pending_review"
                )
            )
            dlq_pending = int(result.scalar() or 0)
        except Exception as e:
            logger.warning("DLQ count failed: %s", e)

        overall = "healthy"
        if celery_workers.get("status") == "error" or redis_broker.get("status") == "error":
            overall = "degraded"
        if celery_workers.get("worker_count", 0) == 0:
            overall = "degraded"

        return {
            "status": overall,
            "environment": settings.environment,
            "celery": celery_workers,
            "broker": redis_broker,
            "ingest_jobs_by_status": ingest_counts,
            "ingest_dlq_pending_review": dlq_pending,
        }
