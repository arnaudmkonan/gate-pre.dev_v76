import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.ingest import (
    BatchScheduleCreate,
    BatchScheduleResponse,
    BatchScheduleUpdate,
    BatchMetricsResponse,
)
from app.services.batch_service import BatchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/batch/schedules", tags=["batch"])


@router.post("", response_model=BatchScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule_data: BatchScheduleCreate,
    session: AsyncSession = Depends(get_db),
):
    """
    Create a new batch schedule.

    Parameters:
    - schedule_name: Unique name for the schedule
    - cron_expression: Cron expression for scheduling (e.g., "0 * * * *" for hourly)
    - max_concurrency: Maximum concurrent jobs (1-100)
    - batch_size: Jobs per batch (1-500)
    - description: Optional description
    """
    try:
        schedule = await BatchService.create_schedule(
            session,
            schedule_name=schedule_data.schedule_name,
            cron_expression=schedule_data.cron_expression,
            max_concurrency=schedule_data.max_concurrency,
            batch_size=schedule_data.batch_size,
            description=schedule_data.description,
        )

        return BatchScheduleResponse.from_orm(schedule)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error creating schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create schedule",
        )


@router.get("", response_model=list[BatchScheduleResponse])
async def list_schedules(
    is_active: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """
    List batch schedules.

    Parameters:
    - is_active: Filter by active status
    - limit: Number of schedules to return
    - offset: Offset for pagination
    """
    try:
        schedules, total = await BatchService.list_schedules(
            session,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )

        return [BatchScheduleResponse.from_orm(s) for s in schedules]

    except Exception as e:
        logger.error(f"Error listing schedules: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list schedules",
        )


@router.get("/{schedule_id}", response_model=BatchScheduleResponse)
async def get_schedule(
    schedule_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get details of a specific batch schedule."""
    try:
        schedule = await BatchService.get_schedule(session, schedule_id)

        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule {schedule_id} not found",
            )

        return BatchScheduleResponse.from_orm(schedule)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve schedule",
        )


@router.put("/{schedule_id}", response_model=BatchScheduleResponse)
async def update_schedule(
    schedule_id: UUID,
    schedule_data: BatchScheduleUpdate,
    session: AsyncSession = Depends(get_db),
):
    """Update a batch schedule."""
    try:
        schedule = await BatchService.update_schedule(
            session,
            schedule_id,
            schedule_name=schedule_data.schedule_name,
            cron_expression=schedule_data.cron_expression,
            max_concurrency=schedule_data.max_concurrency,
            batch_size=schedule_data.batch_size,
            is_active=schedule_data.is_active,
            description=schedule_data.description,
        )

        return BatchScheduleResponse.from_orm(schedule)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error updating schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update schedule",
        )


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Delete a batch schedule."""
    try:
        await BatchService.delete_schedule(session, schedule_id)
        logger.info(f"Schedule {schedule_id} deleted")

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error deleting schedule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete schedule",
        )


@router.get("/{schedule_id}/metrics", response_model=BatchMetricsResponse)
async def get_schedule_metrics(
    schedule_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get metrics for a batch schedule.

    Returns execution time, job counts, and other metrics for the last run.
    """
    try:
        schedule = await BatchService.get_schedule(session, schedule_id)

        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule {schedule_id} not found",
            )

        # TODO: Calculate metrics from job logs
        # For now, return a placeholder response
        return BatchMetricsResponse(
            schedule_id=schedule.id,
            schedule_name=schedule.schedule_name,
            total_jobs_processed=0,
            execution_time_seconds=0,
            jobs_succeeded=0,
            jobs_failed=0,
            last_run_at=schedule.last_run_at or schedule.created_at,
            average_job_time_seconds=0.0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving schedule metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve schedule metrics",
        )
