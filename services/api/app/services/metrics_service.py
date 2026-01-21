"""Metrics service for storing and querying time-series data."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from decimal import Decimal

from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics_timeseries import MetricsTimeseries
from app.schemas.metrics import (
    MetricsIngestRequest,
    MetricsResponse,
    MetricsQueryRequest,
    MetricsQueryResponse,
)

logger = logging.getLogger(__name__)


class MetricsService:
    """Service for managing metrics time-series data."""

    @staticmethod
    async def ingest_metrics(
        session: AsyncSession,
        metrics: MetricsIngestRequest,
    ) -> MetricsResponse:
        """
        Ingest a metrics data point.

        Args:
            session: Database session
            metrics: MetricsIngestRequest schema

        Returns:
            Created MetricsResponse
        """
        try:
            metrics_record = MetricsTimeseries(
                pipeline_id=metrics.pipeline_id,
                worker_id=metrics.worker_id,
                file_type=metrics.file_type,
                timestamp=metrics.timestamp,
                throughput=metrics.throughput,
                latency_p50=metrics.latency_p50,
                latency_p95=metrics.latency_p95,
                latency_p99=metrics.latency_p99,
                error_rate=metrics.error_rate,
                dlq_count=metrics.dlq_count,
            )

            session.add(metrics_record)
            await session.commit()
            await session.refresh(metrics_record)

            logger.debug(f"Ingested metrics: pipeline={metrics.pipeline_id}, timestamp={metrics.timestamp}")
            return MetricsService._to_response(metrics_record)

        except Exception as e:
            await session.rollback()
            logger.error(f"Error ingesting metrics: {e}")
            raise

    @staticmethod
    async def query_metrics(
        session: AsyncSession,
        query: MetricsQueryRequest,
    ) -> MetricsQueryResponse:
        """
        Query metrics with optional filtering.

        Args:
            session: Database session
            query: MetricsQueryRequest schema

        Returns:
            MetricsQueryResponse
        """
        try:
            sql_query = select(MetricsTimeseries)

            # Parse time range
            end_time = query.end_time or datetime.now(timezone.utc)
            if query.start_time is None:
                if query.time_range == "1h":
                    start_time = end_time - timedelta(hours=1)
                elif query.time_range == "24h":
                    start_time = end_time - timedelta(hours=24)
                elif query.time_range == "7d":
                    start_time = end_time - timedelta(days=7)
                elif query.time_range == "30d":
                    start_time = end_time - timedelta(days=30)
                else:
                    start_time = end_time - timedelta(hours=24)
            else:
                start_time = query.start_time

            # Add filters
            filters = [MetricsTimeseries.timestamp >= start_time, MetricsTimeseries.timestamp <= end_time]

            if query.pipeline_id:
                filters.append(MetricsTimeseries.pipeline_id == query.pipeline_id)
            if query.worker_id:
                filters.append(MetricsTimeseries.worker_id == query.worker_id)
            if query.file_type:
                filters.append(MetricsTimeseries.file_type == query.file_type)

            sql_query = sql_query.where(and_(*filters))

            # Order by timestamp descending
            sql_query = sql_query.order_by(desc(MetricsTimeseries.timestamp))

            result = await session.execute(sql_query)
            metrics_list = result.scalars().all()

            responses = [MetricsService._to_response(m) for m in metrics_list]

            return MetricsQueryResponse(
                metrics=responses,
                count=len(responses),
                time_range=query.time_range,
                query_timestamp=datetime.now(timezone.utc),
            )

        except Exception as e:
            logger.error(f"Error querying metrics: {e}")
            raise

    @staticmethod
    async def get_latest_metrics(
        session: AsyncSession,
        pipeline_id: Optional[UUID] = None,
        worker_id: Optional[UUID] = None,
    ) -> Optional[MetricsResponse]:
        """Get the latest metrics for a pipeline or worker."""
        try:
            query = select(MetricsTimeseries)

            if pipeline_id:
                query = query.where(MetricsTimeseries.pipeline_id == pipeline_id)
            elif worker_id:
                query = query.where(MetricsTimeseries.worker_id == worker_id)
            else:
                return None

            query = query.order_by(desc(MetricsTimeseries.timestamp)).limit(1)

            result = await session.execute(query)
            metrics = result.scalar_one_or_none()

            return MetricsService._to_response(metrics) if metrics else None

        except Exception as e:
            logger.error(f"Error getting latest metrics: {e}")
            raise

    @staticmethod
    async def cleanup_old_metrics(
        session: AsyncSession,
        retention_days: int = 30,
    ) -> int:
        """
        Delete metrics older than retention period.

        Args:
            session: Database session
            retention_days: Number of days to retain

        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

            # Note: In SQLAlchemy 2.0, we need to use delete differently
            from sqlalchemy import delete as sql_delete

            delete_query = sql_delete(MetricsTimeseries).where(
                MetricsTimeseries.timestamp < cutoff_date
            )

            result = await session.execute(delete_query)
            await session.commit()

            deleted_count = result.rowcount
            logger.info(f"Cleaned up {deleted_count} old metrics records")
            return deleted_count

        except Exception as e:
            await session.rollback()
            logger.error(f"Error cleaning up old metrics: {e}")
            raise

    @staticmethod
    def _to_response(metrics: MetricsTimeseries) -> MetricsResponse:
        """Convert MetricsTimeseries to MetricsResponse."""
        return MetricsResponse(
            id=metrics.id,
            pipeline_id=metrics.pipeline_id,
            worker_id=metrics.worker_id,
            file_type=metrics.file_type,
            timestamp=metrics.timestamp,
            throughput=metrics.throughput,
            latency_p50=metrics.latency_p50,
            latency_p95=metrics.latency_p95,
            latency_p99=metrics.latency_p99,
            error_rate=metrics.error_rate,
            dlq_count=metrics.dlq_count,
            created_at=metrics.created_at,
        )
