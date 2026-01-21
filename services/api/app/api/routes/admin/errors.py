"""
Admin errors search and management routes.
Provides endpoints for searching, filtering, and managing processing errors.
"""

import logging
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from uuid import UUID

from app.core.database import get_db
from app.models.errors_raw import ErrorsRaw
from app.repositories.error_repo import ErrorRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/errors", tags=["admin-errors"])


class ErrorResponse(BaseModel):
    """Error response model."""

    id: str
    file_id: str
    agent_id: str
    error_type: str
    error_classification: str
    stack_trace: Optional[str]
    processing_step: str
    retry_count: int
    max_retries: int
    status: str
    error_timestamp: str
    created_at: str


class ErrorSearchRequest(BaseModel):
    """Error search request model."""

    file_id: Optional[UUID] = None
    agent_id: Optional[str] = None
    error_type: Optional[str] = None
    error_classification: Optional[str] = None
    processing_step: Optional[str] = None
    limit: int = 50
    offset: int = 0


class ErrorSearchResponse(BaseModel):
    """Error search response model."""

    total: int
    limit: int
    offset: int
    errors: List[ErrorResponse]


@router.get("/search", response_model=ErrorSearchResponse)
async def search_errors(
    file_id: Optional[UUID] = Query(None, description="Filter by file ID"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    error_type: Optional[str] = Query(None, description="Filter by error type"),
    error_classification: Optional[str] = Query(None, description="Filter by error classification"),
    processing_step: Optional[str] = Query(None, description="Filter by processing step"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    session: AsyncSession = Depends(get_db),
):
    """
    Search for processing errors with optional filters.

    Returns paginated error records matching the specified criteria.

    Args:
        file_id: Optional file UUID to filter by
        agent_id: Optional agent ID to filter by
        error_type: Optional error type to filter by
        error_classification: Optional error classification (transient/permanent)
        processing_step: Optional processing step to filter by
        limit: Max number of results (default 50, max 500)
        offset: Result offset for pagination
        session: Database session

    Returns:
        ErrorSearchResponse with matching errors and pagination info
    """
    try:
        # Build filter conditions
        conditions = []

        if file_id:
            conditions.append(ErrorsRaw.file_id == file_id)
        if agent_id:
            conditions.append(ErrorsRaw.agent_id == agent_id)
        if error_type:
            conditions.append(ErrorsRaw.error_type == error_type)
        if error_classification:
            conditions.append(ErrorsRaw.error_classification == error_classification)
        if processing_step:
            conditions.append(ErrorsRaw.processing_step == processing_step)

        # Count total matching records
        count_query = select(ErrorsRaw)
        if conditions:
            count_query = count_query.where(and_(*conditions))

        result = await session.execute(count_query)
        total = len(result.fetchall())

        # Get paginated results
        query = select(ErrorsRaw)
        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(ErrorsRaw.error_timestamp.desc()).limit(limit).offset(offset)

        result = await session.execute(query)
        errors = result.scalars().all()

        # Convert to response models
        def get_error_status(error):
            """Compute status based on classification and retry count."""
            if error.error_classification == "permanent":
                return "FINAL"
            if error.retry_count >= error.max_retries:
                return "MAX_RETRIES_REACHED"
            return "RETRYABLE"

        error_responses = [
            ErrorResponse(
                id=str(error.id),
                file_id=str(error.file_id),
                agent_id=error.agent_id,
                error_type=error.error_type,
                error_classification=error.error_classification,
                stack_trace=error.stack_trace,
                processing_step=error.processing_step,
                retry_count=error.retry_count,
                max_retries=error.max_retries,
                status=get_error_status(error),
                error_timestamp=error.error_timestamp.isoformat() if error.error_timestamp else None,
                created_at=error.created_at.isoformat() if error.created_at else None,
            )
            for error in errors
        ]

        logger.info(f"Search returned {len(error_responses)} of {total} errors")

        return ErrorSearchResponse(
            total=total,
            limit=limit,
            offset=offset,
            errors=error_responses,
        )

    except Exception as e:
        logger.error(f"Failed to search errors: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search errors",
        )


@router.post("/search", response_model=ErrorSearchResponse)
async def search_errors_post(
    request: ErrorSearchRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Search for processing errors (POST variant).

    Allows searching with more complex filter combinations.

    Args:
        request: ErrorSearchRequest with filter criteria
        session: Database session

    Returns:
        ErrorSearchResponse with matching errors and pagination info
    """
    try:
        # Build filter conditions
        conditions = []

        if request.file_id:
            conditions.append(ErrorsRaw.file_id == request.file_id)
        if request.agent_id:
            conditions.append(ErrorsRaw.agent_id == request.agent_id)
        if request.error_type:
            conditions.append(ErrorsRaw.error_type == request.error_type)
        if request.error_classification:
            conditions.append(ErrorsRaw.error_classification == request.error_classification)
        if request.processing_step:
            conditions.append(ErrorsRaw.processing_step == request.processing_step)

        # Count total matching records
        count_query = select(ErrorsRaw)
        if conditions:
            count_query = count_query.where(and_(*conditions))

        result = await session.execute(count_query)
        total = len(result.fetchall())

        # Get paginated results
        query = select(ErrorsRaw)
        if conditions:
            query = query.where(and_(*conditions))

        query = (
            query.order_by(ErrorsRaw.error_timestamp.desc())
            .limit(request.limit)
            .offset(request.offset)
        )

        result = await session.execute(query)
        errors = result.scalars().all()

        # Convert to response models
        def get_error_status(error):
            """Compute status based on classification and retry count."""
            if error.error_classification == "permanent":
                return "FINAL"
            if error.retry_count >= error.max_retries:
                return "MAX_RETRIES_REACHED"
            return "RETRYABLE"

        error_responses = [
            ErrorResponse(
                id=str(error.id),
                file_id=str(error.file_id),
                agent_id=error.agent_id,
                error_type=error.error_type,
                error_classification=error.error_classification,
                stack_trace=error.stack_trace,
                processing_step=error.processing_step,
                retry_count=error.retry_count,
                max_retries=error.max_retries,
                status=get_error_status(error),
                error_timestamp=error.error_timestamp.isoformat() if error.error_timestamp else None,
                created_at=error.created_at.isoformat() if error.created_at else None,
            )
            for error in errors
        ]

        logger.info(f"Search returned {len(error_responses)} of {total} errors")

        return ErrorSearchResponse(
            total=total,
            limit=request.limit,
            offset=request.offset,
            errors=error_responses,
        )

    except Exception as e:
        logger.error(f"Failed to search errors: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search errors",
        )

class ErrorInsertRequest(BaseModel):
    """Request to insert a test error."""

    file_id: UUID = Field(..., description="File ID")
    agent_id: str = Field(..., description="Agent ID")
    error_type: str = Field(..., description="Error type (e.g., 'timeout', 'invalid')")
    error_classification: str = Field(
        default="transient",
        description="Error classification: 'transient' or 'permanent'"
    )
    processing_step: str = Field(default="unknown", description="Step where error occurred")
    stack_trace: Optional[str] = Field(None, description="Optional stack trace")
    retry_count: int = Field(default=0, ge=0, description="Current retry count")
    max_retries: int = Field(default=3, ge=1, description="Max retry attempts")


class ErrorInsertResponse(BaseModel):
    """Response from error insertion."""

    id: str
    file_id: str
    agent_id: str
    error_type: str
    error_classification: str
    retry_count: int
    max_retries: int
    processing_step: str
    message: str


@router.post("/insert", response_model=ErrorInsertResponse, status_code=status.HTTP_201_CREATED)
async def insert_test_error(
    request: ErrorInsertRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Insert a test error record for testing error handling workflows.

    This endpoint is for testing/demonstration purposes only.
    Allows manual insertion of errors with specified classification.

    Args:
        request: ErrorInsertRequest with error details
        session: Database session

    Returns:
        ErrorInsertResponse with created error details
    """
    try:
        # Create error record
        error = await ErrorRepository.create_error(
            session,
            file_id=request.file_id,
            agent_id=request.agent_id,
            error_type=request.error_type,
            stack_trace=request.stack_trace,
            processing_step=request.processing_step,
            error_classification=request.error_classification,
            max_retries=request.max_retries,
        )

        # Update retry count if provided
        if request.retry_count > 0:
            error.retry_count = request.retry_count
            await session.commit()

        logger.info(
            f"Inserted test error: file {request.file_id}, agent {request.agent_id}, "
            f"type {request.error_type}, classification {request.error_classification}"
        )

        return ErrorInsertResponse(
            id=str(error.id),
            file_id=str(error.file_id),
            agent_id=error.agent_id,
            error_type=error.error_type,
            error_classification=error.error_classification,
            retry_count=error.retry_count,
            max_retries=error.max_retries,
            processing_step=error.processing_step,
            message=f"Error inserted successfully for file {request.file_id}",
        )

    except Exception as e:
        logger.error(f"Failed to insert error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to insert error",
        )


class RequeueRequest(BaseModel):
    """Request to requeue a failed error."""
    operator_id: Optional[str] = Field(None, description="Operator ID")
    reason: Optional[str] = Field(None, description="Reason for requeuing")


class RequeueResponse(BaseModel):
    """Response from requeue operation."""
    id: str
    file_id: str
    status: str
    retry_count: int
    message: str


@router.post("/{error_id}/requeue", response_model=RequeueResponse)
async def requeue_error(
    error_id: UUID,
    request: RequeueRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Manually requeue a failed error for retry.

    Resets retry_count to 0 and sets classification back to transient
    to allow retry processing.

    Args:
        error_id: ID of the error to requeue
        request: RequeueRequest with operator info and reason
        session: Database session

    Returns:
        RequeueResponse with requeue details
    """
    try:
        # Get the error
        error = await ErrorRepository.get_error_by_id(session, error_id)
        if not error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Error {error_id} not found",
            )

        # Reset for retry
        error.retry_count = 0
        error.error_classification = "transient"  # Allow retry
        error.last_attempt_ts = datetime.utcnow()

        await session.commit()
        await session.refresh(error)

        logger.info(
            f"Error {error_id} requeued by operator {request.operator_id}: {request.reason}"
        )

        return RequeueResponse(
            id=str(error.id),
            file_id=str(error.file_id),
            status="requeued",
            retry_count=error.retry_count,
            message=f"Error requeued for retry. File {error.file_id} is ready to be processed again.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to requeue error {error_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to requeue error",
        )


class BatchRequeueRequest(BaseModel):
    """Request to requeue multiple errors."""
    error_ids: List[UUID] = Field(..., description="List of error IDs to requeue")
    operator_id: Optional[str] = Field(None, description="Operator ID")
    reason: Optional[str] = Field(None, description="Reason for requeuing")


class BatchRequeueResponse(BaseModel):
    """Response from batch requeue operation."""
    total: int
    succeeded: int
    failed: int
    message: str


@router.post("/batch-requeue", response_model=BatchRequeueResponse)
async def batch_requeue_errors(
    request: BatchRequeueRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Requeue multiple failed errors for retry.

    Args:
        request: BatchRequeueRequest with error IDs and operator info
        session: Database session

    Returns:
        BatchRequeueResponse with results
    """
    try:
        succeeded = 0
        failed = 0

        for error_id in request.error_ids:
            try:
                error = await ErrorRepository.get_error_by_id(session, error_id)
                if not error:
                    logger.warning(f"Error {error_id} not found")
                    failed += 1
                    continue

                # Reset for retry
                error.retry_count = 0
                error.error_classification = "transient"
                error.last_attempt_ts = datetime.utcnow()

                await session.commit()
                succeeded += 1

            except Exception as e:
                logger.error(f"Failed to requeue error {error_id}: {e}")
                failed += 1

        logger.info(
            f"Batch requeue completed by {request.operator_id}: "
            f"{succeeded} succeeded, {failed} failed"
        )

        return BatchRequeueResponse(
            total=len(request.error_ids),
            succeeded=succeeded,
            failed=failed,
            message=f"Batch requeue completed: {succeeded} errors requeued, {failed} failed",
        )

    except Exception as e:
        logger.error(f"Failed batch requeue operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process batch requeue",
        )
