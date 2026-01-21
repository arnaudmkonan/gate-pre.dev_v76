import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.dead_letter_queue import DeadLetterQueue
from app.models.job_log import JobLog, JobStatus
from app.schemas.queue import (
    CeleryConfigCreate,
    CeleryConfigResponse,
    DLQResponse,
    JobLogResponse,
    JobPageResponse,
    JobRetryRequest,
    JobStatusResponse,
)
from app.models.celery_config import CeleryConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/queue", tags=["queue"])


@router.post("/config", response_model=CeleryConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_queue_config(
    config: CeleryConfigCreate,
    session: AsyncSession = Depends(get_db),
):
    """Create new queue configuration."""
    try:
        celery_config = CeleryConfig(
            redis_host=config.redis_host,
            redis_port=config.redis_port,
            redis_password=config.redis_password,
            result_backend=f"redis://:{config.redis_password}@{config.redis_host}:{config.redis_port}/1"
            if config.redis_password
            else f"redis://{config.redis_host}:{config.redis_port}/1",
            worker_concurrency=config.worker_concurrency,
            task_timeout=config.task_timeout,
            max_retries=config.max_retries,
            retry_backoff=config.retry_backoff,
            is_active=True,
        )

        session.add(celery_config)
        await session.commit()
        await session.refresh(celery_config)

        logger.info(f"Queue config created: {celery_config.id}")
        return celery_config

    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating queue config: {e}")
        raise HTTPException(status_code=500, detail="Failed to create queue config")


@router.get("/config", response_model=CeleryConfigResponse)
async def get_queue_config(session: AsyncSession = Depends(get_db)):
    """Get active queue configuration."""
    try:
        result = await session.execute(
            select(CeleryConfig).where(CeleryConfig.is_active == True).limit(1)
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="No active queue config found")

        return config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving queue config: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve queue config")


@router.get("/status", response_model=JobStatusResponse)
async def get_queue_status(session: AsyncSession = Depends(get_db)):
    """Get queue status (pending, running, failed counts)."""
    try:
        # Count jobs by status
        pending_result = await session.execute(
            select(JobLog).where(JobLog.status == JobStatus.PENDING)
        )
        pending_count = len(pending_result.scalars().all())

        running_result = await session.execute(
            select(JobLog).where(JobLog.status == JobStatus.RUNNING)
        )
        running_count = len(running_result.scalars().all())

        failed_result = await session.execute(
            select(JobLog).where(JobLog.status == JobStatus.FAILED)
        )
        failed_count = len(failed_result.scalars().all())

        return JobStatusResponse(
            pending=pending_count,
            running=running_count,
            failed=failed_count,
        )

    except Exception as e:
        logger.error(f"Error retrieving queue status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve queue status")


@router.get("/jobs", response_model=JobPageResponse)
async def get_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """Get paginated list of jobs."""
    try:
        query = select(JobLog)

        if status:
            query = query.where(JobLog.status == status)

        # Get total count
        count_result = await session.execute(
            select(JobLog).where(
                JobLog.status == status if status else True
            )
        )
        total = len(count_result.scalars().all())

        # Get paginated results
        offset = (page - 1) * page_size
        query = query.order_by(desc(JobLog.created_at)).offset(offset).limit(page_size)

        result = await session.execute(query)
        jobs = result.scalars().all()

        return JobPageResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=jobs,
        )

    except Exception as e:
        logger.error(f"Error retrieving jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve jobs")


@router.get("/dlq", response_model=list[DLQResponse])
async def get_dead_letter_queue(
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    """Get dead letter queue jobs."""
    try:
        result = await session.execute(
            select(DeadLetterQueue)
            .order_by(desc(DeadLetterQueue.created_at))
            .limit(limit)
        )
        jobs = result.scalars().all()
        return jobs

    except Exception as e:
        logger.error(f"Error retrieving DLQ: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve DLQ")


@router.post("/jobs/{job_id}/retry", response_model=dict)
async def retry_job(
    job_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Retry a failed job."""
    try:
        result = await session.execute(
            select(JobLog).where(JobLog.job_id == job_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Reset status to pending for retry
        job.status = JobStatus.PENDING
        job.retry_count += 1

        await session.commit()

        logger.info(f"Job retried: {job_id}, attempt: {job.retry_count}")

        return {"status": "retry_queued", "job_id": job_id}

    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error retrying job: {e}")
        raise HTTPException(status_code=500, detail="Failed to retry job")
