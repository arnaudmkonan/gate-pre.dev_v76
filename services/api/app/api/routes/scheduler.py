import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.scheduler.scheduler import BatchVectorizerScheduler
from app.models import Batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@router.get("/v1/status/{batch_id}")
async def get_batch_status(
    batch_id: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Get status and progress of a batch vectorization job.

    Returns:
        - batch_id: The batch ID
        - status: Current status (pending, processing, completed, failed)
        - processed_count: Number of successfully processed items
        - failed_count: Number of failed items
        - total_count: Total items in batch
        - eta: Estimated time to completion
    """
    try:
        batch_uuid = UUID(batch_id)
        scheduler = BatchVectorizerScheduler(session)
        progress = await scheduler.get_batch_progress(batch_uuid)

        if "error" in progress:
            raise HTTPException(status_code=404, detail=progress["error"])

        return progress

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid batch_id format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting batch status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get batch status")


@router.get("/v1/batches")
async def list_batches(
    status_filter: str = Query(None, description="Filter by status: pending, processing, completed, failed"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """
    List batches with optional filtering by status.

    Returns:
        List of batches with status and counts
    """
    try:
        from sqlalchemy import select

        stmt = select(Batch)

        if status_filter:
            stmt = stmt.where(Batch.status == status_filter)

        stmt = stmt.offset(offset).limit(limit)

        result = await session.execute(stmt)
        batches = result.scalars().all()

        return [
            {
                "id": str(b.id),
                "status": b.status,
                "processed_count": b.processed_count,
                "failed_count": b.failed_count,
                "total_count": b.total_count,
                "created_at": b.created_at.isoformat(),
                "updated_at": b.updated_at.isoformat(),
            }
            for b in batches
        ]

    except Exception as e:
        logger.error(f"Error listing batches: {e}")
        raise HTTPException(status_code=500, detail="Failed to list batches")


@router.post("/v1/batches", status_code=status.HTTP_201_CREATED)
async def create_batch(
    file_ids: list[str],
    session: AsyncSession = Depends(get_db),
):
    """
    Create a new batch for vectorization.

    Args:
        file_ids: List of file IDs to vectorize

    Returns:
        Created batch with ID
    """
    try:
        batch = Batch(
            status="pending",
            total_count=len(file_ids),
            processed_count=0,
            failed_count=0,
        )

        session.add(batch)
        await session.commit()
        await session.refresh(batch)

        logger.info(f"Created batch {batch.id} with {len(file_ids)} files")

        return {
            "id": str(batch.id),
            "status": batch.status,
            "total_count": batch.total_count,
            "file_ids": file_ids,
            "created_at": batch.created_at.isoformat(),
        }

    except Exception as e:
        logger.error(f"Error creating batch: {e}")
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to create batch")
