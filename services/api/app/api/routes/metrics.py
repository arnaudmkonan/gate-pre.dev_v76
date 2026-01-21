"""FastAPI routes for metrics endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.metrics_service import MetricsService
from app.schemas.metrics import (
    MetricsIngestRequest,
    MetricsQueryRequest,
    MetricsQueryResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.post("/ingest")
async def ingest_metrics(
    metrics: MetricsIngestRequest,
    session: AsyncSession = Depends(get_db),
):
    """Ingest metrics data."""
    try:
        result = await MetricsService.ingest_metrics(session=session, metrics=metrics)
        return {"id": result.id, "timestamp": result.timestamp}

    except Exception as e:
        logger.error(f"Error ingesting metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error ingesting metrics",
        )


@router.post("/query", response_model=MetricsQueryResponse)
async def query_metrics(
    query: MetricsQueryRequest,
    session: AsyncSession = Depends(get_db),
):
    """Query metrics with filters."""
    try:
        return await MetricsService.query_metrics(session=session, query=query)

    except Exception as e:
        logger.error(f"Error querying metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error querying metrics",
        )


@router.get("/export")
async def export_metrics_csv(
    pipeline_id: str = None,
    worker_id: str = None,
    time_range: str = "24h",
    session: AsyncSession = Depends(get_db),
):
    """Export metrics as CSV."""
    try:
        query = MetricsQueryRequest(
            pipeline_id=UUID(pipeline_id) if pipeline_id else None,
            worker_id=UUID(worker_id) if worker_id else None,
            time_range=time_range,
        )

        result = await MetricsService.query_metrics(session=session, query=query)

        # Generate CSV
        csv_content = "timestamp,pipeline_id,worker_id,file_type,throughput,latency_p50,latency_p95,latency_p99,error_rate,dlq_count\n"

        for metric in result.metrics:
            csv_content += f"{metric.timestamp},{metric.pipeline_id},{metric.worker_id},{metric.file_type},{metric.throughput},{metric.latency_p50},{metric.latency_p95},{metric.latency_p99},{metric.error_rate},{metric.dlq_count}\n"

        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=metrics-{time_range}.csv"},
        )

    except Exception as e:
        logger.error(f"Error exporting metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error exporting metrics",
        )
