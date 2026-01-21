"""Service for admin dashboard metrics collection."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.queue_job import QueueJob
from app.models.errors_raw import ErrorsRaw
from app.schemas.dashboard import (
    PipelineStatusResponse,
    QueueLengthResponse,
    ErrorSummary,
    RecentErrorsResponse,
    ThroughputResponse,
    ThroughputMetric,
    DashboardDataResponse,
)

logger = logging.getLogger(__name__)


class DashboardService:
    """Service for dashboard data collection."""

    @staticmethod
    async def get_pipeline_status(session: AsyncSession) -> PipelineStatusResponse:
        """Get pipeline status."""
        try:
            from app.models.ingest_job import IngestJob
            
            # Count jobs by status from QueueJob table
            queue_query = select(
                func.count(QueueJob.id).filter(QueueJob.status == "running").label("running"),
                func.count(QueueJob.id).filter(QueueJob.status == "completed").label("completed"),
                func.count(QueueJob.id).filter(QueueJob.status == "failed").label("failed"),
            )
            queue_result = await session.execute(queue_query)
            queue_active, queue_completed, queue_failed = queue_result.first() or (0, 0, 0)
            
            # Also count from IngestJob table (which is where our jobs actually are)
            ingest_query = select(
                func.count(IngestJob.id).filter(IngestJob.status == "processing").label("running"),
                func.count(IngestJob.id).filter(IngestJob.status == "completed").label("completed"),
                func.count(IngestJob.id).filter(IngestJob.status == "failed").label("failed"),
            )
            ingest_result = await session.execute(ingest_query)
            ingest_active, ingest_completed, ingest_failed = ingest_result.first() or (0, 0, 0)
            
            # Combine both
            active = (queue_active or 0) + (ingest_active or 0)
            completed = (queue_completed or 0) + (ingest_completed or 0)
            failed = (queue_failed or 0) + (ingest_failed or 0)

            status = "error" if failed > 0 else "running" if active > 0 else "idle"

            return PipelineStatusResponse(
                status=status,
                active_jobs=active,
                completed_jobs=completed,
                failed_jobs=failed,
            )
        except Exception as e:
            logger.error(f"Failed to get pipeline status: {e}")
            return PipelineStatusResponse(
                status="error",
                active_jobs=0,
                completed_jobs=0,
                failed_jobs=0,
            )

    @staticmethod
    async def get_queue_length(session: AsyncSession) -> QueueLengthResponse:
        """Get queue length metrics."""
        try:
            query = select(
                func.count(QueueJob.id).filter(QueueJob.status == "pending").label("pending"),
                func.count(QueueJob.id).filter(QueueJob.status == "running").label("running"),
                func.count(QueueJob.id).filter(QueueJob.status == "failed").label("failed"),
            )
            result = await session.execute(query)
            pending, running, failed = result.first() or (0, 0, 0)
            total = (pending or 0) + (running or 0)

            return QueueLengthResponse(
                pending=pending or 0,
                running=running or 0,
                failed=failed or 0,
                total=total,
            )
        except Exception as e:
            logger.error(f"Failed to get queue length: {e}")
            return QueueLengthResponse(pending=0, running=0, failed=0, total=0)

    @staticmethod
    async def get_recent_errors(session: AsyncSession, limit: int = 5) -> RecentErrorsResponse:
        """Get recent errors."""
        try:
            # Get recent errors
            query = (
                select(ErrorsRaw)
                .order_by(ErrorsRaw.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(query)
            errors = result.scalars().all()

            # Get total errors in last 24 hours
            twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
            count_query = select(func.count(ErrorsRaw.id)).filter(
                ErrorsRaw.created_at >= twenty_four_hours_ago
            )
            count_result = await session.execute(count_query)
            total_24h = count_result.scalar() or 0

            error_summaries = []
            for error in errors:
                error_summaries.append(
                    ErrorSummary(
                        id=str(error.id),
                        error_type=error.error_type or "unknown",
                        message=error.message or "No message",
                        timestamp=error.created_at.isoformat(),
                        file_id=str(error.file_id) if hasattr(error, "file_id") else None,
                    )
                )

            return RecentErrorsResponse(
                errors=error_summaries,
                total_errors_24h=total_24h,
            )
        except Exception as e:
            logger.error(f"Failed to get recent errors: {e}")
            return RecentErrorsResponse(errors=[], total_errors_24h=0)

    @staticmethod
    async def get_throughput(session: AsyncSession, hours: int = 24) -> ThroughputResponse:
        """Get throughput metrics for last N hours."""
        try:
            from app.models.ingest_job import IngestJob
            from sqlalchemy import text
            
            now = datetime.now(timezone.utc)
            start_time = now - timedelta(hours=hours)

            # Create the date_trunc expression
            hour_trunc = func.date_trunc("hour", IngestJob.updated_at)
            
            # Get completed jobs from IngestJob table (more reliable)
            query = select(
                hour_trunc.label("hour"),
                func.count(IngestJob.id).label("count"),
            ).where(
                IngestJob.status == "completed",
                IngestJob.updated_at >= start_time,
            ).group_by(
                hour_trunc
            ).order_by(
                text("hour")
            )

            result = await session.execute(query)
            rows = result.all()

            metrics = []
            total_files = 0
            for hour, count in rows:
                if hour:
                    metrics.append(
                        ThroughputMetric(
                            timestamp=hour.isoformat(),
                            files_processed=count or 0,
                        )
                    )
                    total_files += count or 0

            average = total_files / max(hours, 1) if hours > 0 else 0

            return ThroughputResponse(
                metrics=metrics,
                average_files_per_hour=average,
            )
        except Exception as e:
            logger.error(f"Failed to get throughput: {e}")
            return ThroughputResponse(metrics=[], average_files_per_hour=0.0)

    @staticmethod
    async def get_dashboard_data(session: AsyncSession) -> DashboardDataResponse:
        """Get complete dashboard data."""
        pipeline_status = await DashboardService.get_pipeline_status(session)
        queue_length = await DashboardService.get_queue_length(session)
        recent_errors = await DashboardService.get_recent_errors(session)
        throughput = await DashboardService.get_throughput(session)

        return DashboardDataResponse(
            pipeline_status=pipeline_status,
            queue_length=queue_length,
            recent_errors=recent_errors,
            throughput=throughput,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
