import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models import SilverRecord, RetryQueue, RetryQueueStatus
from app.schemas.orchestration import (
    SilverRecordResponse,
    RetryQueueItemResponse,
    RetryQueueListResponse,
    RetryQueueUpdate,
    RetryQueueRetryRequest,
)
from app.schemas.silver import SilverRecordBatch, SilverUpsertResult
from app.services.metadata import MapperService
from app.services.vector import VectorService
from app.services.silver_service import SilverService
from app.services.audit_service import AuditService
from app.services.normalization_validation_service import NormalizationValidationService
from app.services.vectorization_trigger_service import VectorizationTriggerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metadata", tags=["metadata"])


@router.get(
    "/silver/{file_id}",
    response_model=SilverRecordResponse,
    status_code=status.HTTP_200_OK,
)
async def get_silver_record(
    file_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get normalized/silver record for a file.

    Returns the normalized schema record with extracted metadata
    and processing steps. Available within 60 seconds of successful
    extraction and mapping.

    Returns:
        200 OK with silver record
        204 No Content if processing still pending with Retry-After header
        404 Not Found if file doesn't exist
    """
    try:
        stmt = select(SilverRecord).where(SilverRecord.file_id == file_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            # Return 204 if still processing
            raise HTTPException(
                status_code=status.HTTP_204_NO_CONTENT,
                headers={"Retry-After": "5"},
            )

        return SilverRecordResponse.from_orm(record)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get silver record for {file_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve silver record",
        )


@router.get(
    "/retry-queue",
    response_model=RetryQueueListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_retry_queue(
    status_filter: str = Query(None, description="Filter by status"),
    error_type: str = Query(None, description="Filter by error type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """
    List flagged records in retry queue.

    Shows records that failed mapping or embedding generation and
    need manual review or retry.

    Returns:
        200 OK with paginated list of retry queue items
    """
    try:
        stmt = select(RetryQueue)

        if status_filter:
            stmt = stmt.where(RetryQueue.status == status_filter)

        if error_type:
            stmt = stmt.where(RetryQueue.error_type == error_type)

        # Get total count
        count_stmt = select(func.count(RetryQueue.id))
        if status_filter:
            count_stmt = count_stmt.where(RetryQueue.status == status_filter)
        if error_type:
            count_stmt = count_stmt.where(RetryQueue.error_type == error_type)

        count_result = await session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        stmt = stmt.order_by(RetryQueue.created_at.desc()).offset(offset).limit(page_size)

        result = await session.execute(stmt)
        items = result.scalars().all()

        return RetryQueueListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=[RetryQueueItemResponse.from_orm(item) for item in items],
        )

    except Exception as e:
        logger.error(f"Failed to list retry queue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve retry queue",
        )


@router.get(
    "/retry-queue/{item_id}",
    response_model=RetryQueueItemResponse,
    status_code=status.HTTP_200_OK,
)
async def get_retry_queue_item(
    item_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get a specific retry queue item.

    Returns:
        200 OK with retry queue item
        404 Not Found if item doesn't exist
    """
    try:
        stmt = select(RetryQueue).where(RetryQueue.id == item_id)
        result = await session.execute(stmt)
        item = result.scalar_one_or_none()

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Retry queue item {item_id} not found",
            )

        return RetryQueueItemResponse.from_orm(item)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get retry queue item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve retry queue item",
        )


@router.patch(
    "/retry-queue/{item_id}",
    response_model=RetryQueueItemResponse,
    status_code=status.HTTP_200_OK,
)
async def update_retry_queue_item(
    item_id: UUID,
    request: RetryQueueUpdate,
    session: AsyncSession = Depends(get_db),
):
    """
    Update a retry queue item (notes, status).

    Returns:
        200 OK with updated item
        404 Not Found if item doesn't exist
    """
    try:
        stmt = select(RetryQueue).where(RetryQueue.id == item_id)
        result = await session.execute(stmt)
        item = result.scalar_one_or_none()

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Retry queue item {item_id} not found",
            )

        if request.manual_notes is not None:
            item.manual_notes = request.manual_notes

        if request.status is not None:
            item.status = request.status

        await session.commit()

        return RetryQueueItemResponse.from_orm(item)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update retry queue item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update retry queue item",
        )


@router.post(
    "/retry-queue/{item_id}/retry",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_queue_item(
    item_id: UUID,
    request: RetryQueueRetryRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Manually retry a failed mapping or embedding.

    Marks the item for reprocessing and queues it back into the
    metadata processing pipeline.

    Returns:
        202 Accepted with retry status
        404 Not Found if item doesn't exist
    """
    try:
        stmt = select(RetryQueue).where(RetryQueue.id == item_id)
        result = await session.execute(stmt)
        item = result.scalar_one_or_none()

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Retry queue item {item_id} not found",
            )

        # Update retry item
        item.status = RetryQueueStatus.PROCESSING
        item.processing_attempt += 1
        item.manual_notes = request.notes or item.manual_notes
        await session.commit()

        # TODO: Enqueue to Celery for reprocessing
        logger.info(f"Queued retry for item {item_id}")

        return {
            "status": "accepted",
            "message": f"Item {item_id} queued for retry",
            "attempt": item.processing_attempt,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry queue item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry queue item",
        )


@router.post(
    "/silver/upsert",
    response_model=SilverUpsertResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upsert_silver_records(
    batch: SilverRecordBatch,
    session: AsyncSession = Depends(get_db),
):
    """
    Upsert a batch of normalized (silver) records.

    Accepts a batch of normalized records and upserts them into the silver table
    with create-or-update semantics. Records with same canonical_id or
    (batch_id, raw_record_hash) update existing rows; new records are inserted.

    Args:
        batch: Batch of silver records to upsert
        session: Database session

    Returns:
        202 Accepted with upsert result (inserted/updated/failed counts)

    Raises:
        400 Bad Request if batch validation fails
        500 Internal Server Error on database errors
    """
    try:
        # Validate batch size
        if len(batch.records) > 10000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch size exceeds maximum (10000 records)",
            )

        # Perform upsert
        result = await SilverService.upsert_batch(session, batch)

        # Log audit event with summary
        audit_changes = {
            "batch_id": str(result.batch_id),
            "total_records": result.total_records,
            "inserted_count": result.inserted_count,
            "updated_count": result.updated_count,
            "failed_count": result.failed_count,
            "processing_time_ms": result.processing_time_ms,
        }

        await AuditService.log_action(
            session,
            resource_type="silver_records",
            resource_id=str(result.batch_id or "batch_unknown"),
            action="batch_upsert",
            changes=audit_changes,
        )

        await session.commit()

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upsert silver records: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upsert silver records",
        )


@router.post(
    "/silver/validate-batch",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def validate_batch(
    batch: SilverRecordBatch,
    session: AsyncSession = Depends(get_db),
):
    """
    Validate a batch of normalized records for normalization compliance.

    Validates records against the normalization schema and rules, storing
    validation results and returning summary statistics.

    Args:
        batch: Batch of silver records to validate
        session: Database session

    Returns:
        200 OK with validation summary (total, passed, failed, warnings)

    Raises:
        500 Internal Server Error on validation errors
    """
    try:
        batch_id = batch.batch_id or __import__('uuid').uuid4()

        # Validate batch
        result = await NormalizationValidationService.validate_batch(
            session, batch_id, batch.records
        )

        # Log audit event
        audit_changes = {
            "batch_id": str(batch_id),
            "total_records": result["total_records"],
            "passed_count": result["passed_count"],
            "failed_count": result["failed_count"],
            "warning_count": result["warning_count"],
        }

        await AuditService.log_action(
            session,
            resource_type="normalization_validation",
            resource_id=str(batch_id),
            action="batch_validate",
            changes=audit_changes,
        )

        await session.commit()

        return result

    except Exception as e:
        logger.error(f"Failed to validate batch: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate batch",
        )


@router.get(
    "/silver/{batch_id}/validation-report",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def get_validation_report(
    batch_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get validation report for a batch.

    Returns validation summary and per-record validation details.

    Args:
        batch_id: ID of the batch to get report for
        session: Database session

    Returns:
        200 OK with batch validation report
        404 Not Found if batch has no validation records
    """
    try:
        report = await NormalizationValidationService.get_batch_validation_report(
            session, batch_id
        )

        if not report["records"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No validation records found for batch {batch_id}",
            )

        return report

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get validation report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve validation report",
        )


@router.get(
    "/silver/{batch_id}/failed-validations",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def get_failed_validations(
    batch_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """
    Get failed validation records for a batch.

    Lists records that failed or have warnings during normalization validation.

    Args:
        batch_id: ID of the batch
        page: Page number for pagination
        page_size: Number of records per page
        session: Database session

    Returns:
        200 OK with paginated list of failed validations
    """
    try:
        offset = (page - 1) * page_size
        records, total = await NormalizationValidationService.get_failed_validations(
            session, batch_id, limit=page_size, offset=offset
        )

        return {
            "batch_id": batch_id,
            "total": total,
            "page": page,
            "page_size": page_size,
            "records": records,
        }

    except Exception as e:
        logger.error(f"Failed to get failed validations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve failed validations",
        )


@router.post(
    "/silver/{record_id}/trigger-vectorization",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_vectorization(
    record_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Trigger vectorization for a silver record.

    Queues the record for embedding generation if not already vectorized.

    Args:
        record_id: ID of the silver record
        session: Database session

    Returns:
        202 Accepted with vectorization status
        404 Not Found if record doesn't exist
    """
    try:
        result = await VectorizationTriggerService.trigger_vectorization(
            session, record_id
        )

        if result["status"] == "failed":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["message"],
            )

        # Log audit event
        await AuditService.log_action(
            session,
            resource_type="silver_records",
            resource_id=str(record_id),
            action="trigger_vectorization",
            changes={"status": result["status"]},
        )

        await session.commit()

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger vectorization: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger vectorization",
        )


@router.post(
    "/silver/batch/{batch_id}/trigger-vectorization",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_batch_vectorization(
    batch_id: UUID,
    limit: int = Query(None, description="Optional limit on records to process"),
    session: AsyncSession = Depends(get_db),
):
    """
    Trigger vectorization for all records in a batch.

    Queues all non-vectorized records in the batch for embedding generation.

    Args:
        batch_id: ID of the batch
        limit: Optional limit on records to process
        session: Database session

    Returns:
        202 Accepted with batch vectorization summary
    """
    try:
        result = await VectorizationTriggerService.trigger_batch_vectorization(
            session, batch_id, limit=limit
        )

        # Log audit event
        await AuditService.log_action(
            session,
            resource_type="silver_records",
            resource_id=str(batch_id),
            action="trigger_batch_vectorization",
            changes={
                "queued_count": result.get("queued_count", 0),
                "already_embedded_count": result.get("already_embedded_count", 0),
                "failed_count": result.get("failed_count", 0),
            },
        )

        await session.commit()

        return result

    except Exception as e:
        logger.error(f"Failed to trigger batch vectorization: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger batch vectorization",
        )


@router.get(
    "/silver/{file_id}/vectorization-status",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def get_vectorization_status(
    file_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get vectorization status for a file.

    Returns the current vectorization status and any existing embeddings.

    Args:
        file_id: ID of the file
        session: Database session

    Returns:
        200 OK with vectorization status
        404 Not Found if file has no silver record
    """
    try:
        stmt = select(SilverRecord).where(SilverRecord.file_id == file_id)
        result = await session.execute(stmt)
        silver_record = result.scalar_one_or_none()

        if not silver_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No silver record found for file {file_id}",
            )

        status_result = await VectorizationTriggerService.get_vectorization_status(
            session, silver_record.id
        )

        return status_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get vectorization status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve vectorization status",
        )
