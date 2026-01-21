"""
Admin queues routes for viewing queued/failed files.
Provides file listing with metadata for admin override operations.
"""

import logging
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.agent_ack import AgentAck, AgentAckStatus
from app.models.ingest_job import IngestJob, IngestJobStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/queues", tags=["admin-queues"])


class QueuedFileResponse(BaseModel):
    """Queued/failed file response."""

    file_id: str
    filename: str
    status: str
    file_type: str
    current_agent_id: str
    upload_timestamp: str
    dispatched_at: str
    file_size: int


class QueuesListResponse(BaseModel):
    """Paginated queued files response."""

    total: int
    page: int
    page_size: int
    items: List[QueuedFileResponse]


@router.get("/", response_model=QueuesListResponse)
async def list_queued_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    agent_filter: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """
    Get list of queued/failed files with metadata.

    Supports pagination and filtering by status and agent.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        status_filter: Filter by status (pending, acknowledged, completed, failed)
        agent_filter: Filter by agent ID
        session: Database session

    Returns:
        QueuesListResponse with paginated queued files
    """
    try:
        # Build query for ACK records (pending and failed)
        query = select(AgentAck, IngestJob).join(
            IngestJob, AgentAck.file_id == IngestJob.id
        )

        # Filter by ACK status (pending or failed)
        if status_filter:
            query = query.where(AgentAck.status == status_filter)
        else:
            # Default to showing pending and failed
            query = query.where(
                AgentAck.status.in_([AgentAckStatus.PENDING, AgentAckStatus.FAILED])
            )

        # Filter by agent if provided
        if agent_filter:
            query = query.where(AgentAck.agent_id == agent_filter)

        # Order by dispatch time (newest first)
        query = query.order_by(AgentAck.dispatched_at.desc())

        # Get total count
        count_result = await session.execute(
            select(AgentAck).select_from(
                AgentAck.__table__.join(IngestJob, AgentAck.file_id == IngestJob.id)
            )
        )
        total = len(count_result.all())

        # Paginate
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await session.execute(query)
        items = []

        for ack, job in result.unique().all():
            items.append(
                QueuedFileResponse(
                    file_id=str(job.id),
                    filename=job.filename,
                    status=ack.status,
                    file_type=job.file_type,
                    current_agent_id=ack.agent_id,
                    upload_timestamp=job.created_at.isoformat(),
                    dispatched_at=ack.dispatched_at.isoformat(),
                    file_size=job.size,
                )
            )

        return QueuesListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )

    except Exception as e:
        logger.error(f"Failed to list queued files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list queued files",
        )


@router.get("/{file_id}", response_model=QueuedFileResponse)
async def get_queued_file(
    file_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get details of a specific queued/failed file.

    Args:
        file_id: File ID
        session: Database session

    Returns:
        QueuedFileResponse with file details
    """
    try:
        # Get latest ACK for file
        query = (
            select(AgentAck, IngestJob)
            .join(IngestJob, AgentAck.file_id == IngestJob.id)
            .where(AgentAck.file_id == file_id)
            .order_by(AgentAck.dispatched_at.desc())
            .limit(1)
        )

        result = await session.execute(query)
        row = result.first()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )

        ack, job = row

        return QueuedFileResponse(
            file_id=str(job.id),
            filename=job.filename,
            status=ack.status,
            file_type=job.file_type,
            current_agent_id=ack.agent_id,
            upload_timestamp=job.created_at.isoformat(),
            dispatched_at=ack.dispatched_at.isoformat(),
            file_size=job.size,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get queued file {file_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get file details",
        )
