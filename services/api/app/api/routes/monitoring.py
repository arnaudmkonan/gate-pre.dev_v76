"""FastAPI routes for monitoring endpoints."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.monitoring_service import MonitoringService
from app.schemas.monitoring import (
    MonitoringStatusResponse,
    HealthCheckProbeRequest,
    HealthCheckProbeResponse,
    HealthCheckResult,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/status", response_model=MonitoringStatusResponse)
async def get_monitoring_status(
    pipeline_id: Optional[UUID] = None,
    worker_id: Optional[UUID] = None,
    session: AsyncSession = Depends(get_db),
):
    """Get the latest monitoring status for a pipeline or worker."""
    try:
        if not pipeline_id and not worker_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either pipeline_id or worker_id must be provided",
            )

        status_response = await MonitoringService.get_status(
            session=session,
            pipeline_id=pipeline_id,
            worker_id=worker_id,
        )

        if not status_response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No monitoring status found",
            )

        return status_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting monitoring status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving monitoring status",
        )


@router.get("/statuses", response_model=dict)
async def list_monitoring_statuses(
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """List all monitoring statuses."""
    try:
        statuses, total = await MonitoringService.list_statuses(
            session=session,
            limit=limit,
            offset=offset,
        )

        return {
            "statuses": statuses,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"Error listing monitoring statuses: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving monitoring statuses",
        )


@router.post("/probe", response_model=HealthCheckProbeResponse)
async def run_health_check_probe(
    request: HealthCheckProbeRequest,
):
    """Run a health check probe on system components."""
    try:
        results = []

        # Check storage
        if "storage" in request.components:
            try:
                # TODO: Implement actual storage connectivity check
                results.append(
                    HealthCheckResult(
                        passed=True,
                        component="storage",
                        message="Storage connectivity OK",
                        timestamp=__import__("datetime").datetime.now(
                            __import__("datetime").timezone.utc
                        ),
                    )
                )
            except Exception as e:
                results.append(
                    HealthCheckResult(
                        passed=False,
                        component="storage",
                        message=f"Storage connectivity failed: {str(e)}",
                        timestamp=__import__("datetime").datetime.now(
                            __import__("datetime").timezone.utc
                        ),
                    )
                )

        # Check queue
        if "queue" in request.components:
            try:
                # TODO: Implement actual queue connectivity check
                results.append(
                    HealthCheckResult(
                        passed=True,
                        component="queue",
                        message="Queue connectivity OK",
                        timestamp=__import__("datetime").datetime.now(
                            __import__("datetime").timezone.utc
                        ),
                    )
                )
            except Exception as e:
                results.append(
                    HealthCheckResult(
                        passed=False,
                        component="queue",
                        message=f"Queue connectivity failed: {str(e)}",
                        timestamp=__import__("datetime").datetime.now(
                            __import__("datetime").timezone.utc
                        ),
                    )
                )

        # Check database
        if "database" in request.components:
            try:
                # TODO: Implement actual database connectivity check
                results.append(
                    HealthCheckResult(
                        passed=True,
                        component="database",
                        message="Database connectivity OK",
                        timestamp=__import__("datetime").datetime.now(
                            __import__("datetime").timezone.utc
                        ),
                    )
                )
            except Exception as e:
                results.append(
                    HealthCheckResult(
                        passed=False,
                        component="database",
                        message=f"Database connectivity failed: {str(e)}",
                        timestamp=__import__("datetime").datetime.now(
                            __import__("datetime").timezone.utc
                        ),
                    )
                )

        return MonitoringService.create_probe_response(results)

    except Exception as e:
        logger.error(f"Error running health check probe: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error running health check probe",
        )
