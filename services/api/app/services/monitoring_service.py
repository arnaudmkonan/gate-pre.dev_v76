"""Monitoring service for health checks and status management."""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitoring import MonitoringMetrics
from app.schemas.monitoring import (
    MonitoringStatusResponse,
    HealthCheckResult,
    HealthCheckProbeResponse,
    ConnectivityStatus,
)

logger = logging.getLogger(__name__)


class MonitoringService:
    """Service for managing monitoring and health checks."""

    @staticmethod
    async def record_status(
        session: AsyncSession,
        pipeline_id: Optional[UUID] = None,
        worker_id: Optional[UUID] = None,
        status: str = "unknown",
        connectivity_status: Optional[Dict[str, str]] = None,
        error_message: Optional[str] = None,
        recent_errors: Optional[List[Dict[str, Any]]] = None,
        affected_file_ids: Optional[List[UUID]] = None,
    ) -> MonitoringMetrics:
        """
        Record a monitoring status entry.

        Args:
            session: Database session
            pipeline_id: Pipeline ID (optional)
            worker_id: Worker ID (optional)
            status: Health status (healthy, degraded, failed)
            connectivity_status: Connectivity status for storage, queue, database
            error_message: Error message if status is not healthy
            recent_errors: List of recent error logs
            affected_file_ids: List of affected file IDs

        Returns:
            Created MonitoringMetrics instance
        """
        try:
            metrics = MonitoringMetrics(
                pipeline_id=pipeline_id,
                worker_id=worker_id,
                status=status,
                last_checked_at=datetime.now(timezone.utc),
                connectivity_status=connectivity_status,
                error_message=error_message,
                recent_errors=recent_errors,
                affected_file_ids=affected_file_ids,
            )

            session.add(metrics)
            await session.commit()
            await session.refresh(metrics)

            logger.info(f"Recorded monitoring status: pipeline={pipeline_id}, status={status}")
            return metrics

        except Exception as e:
            await session.rollback()
            logger.error(f"Error recording monitoring status: {e}")
            raise

    @staticmethod
    async def get_status(
        session: AsyncSession,
        pipeline_id: Optional[UUID] = None,
        worker_id: Optional[UUID] = None,
    ) -> Optional[MonitoringStatusResponse]:
        """
        Get the latest status for a pipeline or worker.

        Args:
            session: Database session
            pipeline_id: Pipeline ID (optional)
            worker_id: Worker ID (optional)

        Returns:
            Latest MonitoringStatusResponse or None
        """
        try:
            query = select(MonitoringMetrics)

            if pipeline_id:
                query = query.where(MonitoringMetrics.pipeline_id == pipeline_id)
            elif worker_id:
                query = query.where(MonitoringMetrics.worker_id == worker_id)
            else:
                return None

            # Order by last_checked_at descending and get the most recent
            query = query.order_by(MonitoringMetrics.last_checked_at.desc()).limit(1)

            result = await session.execute(query)
            metrics = result.scalar_one_or_none()

            if not metrics:
                return None

            return MonitoringStatusResponse(
                id=metrics.id,
                pipeline_id=metrics.pipeline_id,
                worker_id=metrics.worker_id,
                status=metrics.status,
                last_checked_at=metrics.last_checked_at,
                connectivity_status=metrics.connectivity_status,
                error_message=metrics.error_message,
                recent_errors=metrics.recent_errors,
                affected_file_ids=metrics.affected_file_ids,
                created_at=metrics.created_at,
                updated_at=metrics.updated_at,
            )

        except Exception as e:
            logger.error(f"Error getting monitoring status: {e}")
            raise

    @staticmethod
    async def list_statuses(
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[MonitoringStatusResponse], int]:
        """
        List all monitoring statuses.

        Returns:
            Tuple of (statuses, total_count)
        """
        try:
            # Get total count
            count_result = await session.execute(select(MonitoringMetrics))
            total = len(count_result.scalars().all())

            # Get paginated results, most recent first
            query = (
                select(MonitoringMetrics)
                .order_by(MonitoringMetrics.last_checked_at.desc())
                .offset(offset)
                .limit(limit)
            )

            result = await session.execute(query)
            metrics_list = result.scalars().all()

            responses = [
                MonitoringStatusResponse(
                    id=m.id,
                    pipeline_id=m.pipeline_id,
                    worker_id=m.worker_id,
                    status=m.status,
                    last_checked_at=m.last_checked_at,
                    connectivity_status=m.connectivity_status,
                    error_message=m.error_message,
                    recent_errors=m.recent_errors,
                    affected_file_ids=m.affected_file_ids,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                )
                for m in metrics_list
            ]

            return responses, total

        except Exception as e:
            logger.error(f"Error listing monitoring statuses: {e}")
            raise

    @staticmethod
    def create_probe_response(
        health_checks: List[HealthCheckResult],
    ) -> HealthCheckProbeResponse:
        """
        Create a probe response from health check results.

        Args:
            health_checks: List of HealthCheckResult

        Returns:
            HealthCheckProbeResponse
        """
        passed_count = sum(1 for check in health_checks if check.passed)
        total_count = len(health_checks)

        if passed_count == total_count:
            overall_health = "healthy"
        elif passed_count > 0:
            overall_health = "degraded"
        else:
            overall_health = "failed"

        return HealthCheckProbeResponse(
            overall_health=overall_health,
            results=health_checks,
            timestamp=datetime.now(timezone.utc),
        )
