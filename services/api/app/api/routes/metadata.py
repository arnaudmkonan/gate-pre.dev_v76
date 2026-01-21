import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.document_metadata import DocumentMetadata
from app.schemas.metadata import MetadataResponse, MetadataListResponse
from app.schemas.normalized_metadata import NormalizedMetadataResponse, MetadataReprocessRequest
from app.services.metadata_query_service import MetadataQueryService
from app.workers.process_metadata import process_metadata as process_metadata_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metadata", tags=["metadata"])


@router.get(
    "",
    response_model=MetadataListResponse,
    status_code=status.HTTP_200_OK,
)
async def query_metadata(
    job_id: Optional[UUID] = Query(None, description="Filter by job ID"),
    document_id: Optional[UUID] = Query(None, description="Filter by document ID"),
    customer_id: Optional[str] = Query(None, description="Filter by customer ID"),
    file_type: Optional[str] = Query(None, description="Filter by file type"),
    ingestion_status: Optional[str] = Query(None, description="Filter by ingestion status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_db),
):
    """
    Query metadata for documents with filtering and pagination.

    Query parameters:
    - job_id: Filter by specific job ID
    - document_id: Filter by specific document ID
    - customer_id: Filter by customer ID
    - file_type: Filter by file type (txt, pdf, docx, etc.)
    - ingestion_status: Filter by status (pending, extracting, completed, failed)
    - page: Page number (default 1)
    - page_size: Items per page (default 20, max 100)

    Returns:
        200 OK with paginated metadata
        204 No Content if no metadata available yet for a specific job_id
        401 Unauthorized if authentication is required
    """
    try:
        # If querying by specific job_id
        if job_id:
            metadata = await MetadataQueryService.query_by_job_id(session, job_id)

            if not metadata:
                # Return 204 No Content with Retry-After header
                return HTTPException(
                    status_code=status.HTTP_204_NO_CONTENT,
                    headers={"Retry-After": "5"},
                )

            return MetadataListResponse(
                total=1,
                page=1,
                page_size=1,
                items=[MetadataResponse.from_orm(metadata)],
            )

        # If querying by specific document_id
        if document_id:
            metadata = await MetadataQueryService.query_by_document_id(session, document_id)

            if not metadata:
                return HTTPException(
                    status_code=status.HTTP_204_NO_CONTENT,
                    headers={"Retry-After": "5"},
                )

            return MetadataListResponse(
                total=1,
                page=1,
                page_size=1,
                items=[MetadataResponse.from_orm(metadata)],
            )

        # Query with filters and pagination
        metadata_list, total_count = await MetadataQueryService.list_with_filters(
            session=session,
            customer_id=customer_id,
            file_type=file_type,
            ingestion_status=ingestion_status,
            page=page,
            page_size=page_size,
        )

        # If no results found
        if total_count == 0:
            return MetadataListResponse(
                total=0,
                page=page,
                page_size=page_size,
                items=[],
            )

        return MetadataListResponse(
            total=total_count,
            page=page,
            page_size=page_size,
            items=[MetadataResponse.from_orm(m) for m in metadata_list],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metadata",
        )


@router.get(
    "/{metadata_id}",
    response_model=MetadataResponse,
    status_code=status.HTTP_200_OK,
)
async def get_metadata(
    metadata_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get metadata for a specific document by ID.

    Returns:
        200 OK with metadata
        204 No Content if metadata not yet available with Retry-After header
        404 Not Found if document doesn't exist
    """
    try:
        metadata = await session.get(DocumentMetadata, metadata_id)

        if not metadata:
            # Return 204 No Content if extraction is still pending
            return HTTPException(
                status_code=status.HTTP_204_NO_CONTENT,
                headers={"Retry-After": "5"},
            )

        return MetadataResponse.from_orm(metadata)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metadata",
        )


# --- Metadata Normalization Endpoints (Story 2) ---


@router.post("/v1/reprocess", status_code=status.HTTP_202_ACCEPTED)
async def reprocess_metadata(
    request: MetadataReprocessRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Reprocess metadata for given files or batches.

    Enqueues Celery job for background processing.
    Returns job ID for status tracking.

    Returns:
        202 Accepted with job_id for tracking
    """
    try:
        from sqlalchemy import select
        from app.models import RawExtraction

        file_ids = request.file_ids or []

        if not file_ids and request.date_range:
            # Query files by date range if no specific IDs provided
            start_date = request.date_range.get("start") if request.date_range else None
            end_date = request.date_range.get("end") if request.date_range else None

            # For now, just return files with limit
            stmt = select(RawExtraction).limit(request.limit)
            result = await session.execute(stmt)
            extractions = result.scalars().all()

            batch_data = [
                {
                    "file_id": str(e.file_id),
                    "title": e.data.get("title"),
                    "author": e.data.get("author"),
                    "date": e.data.get("date"),
                    "document_type": e.data.get("document_type"),
                }
                for e in extractions
            ]
        else:
            # Use specific file IDs or get from DB
            batch_data = [
                {"file_id": str(file_id)}
                for file_id in file_ids
            ]

        # Enqueue Celery task
        task = process_metadata_task.delay(batch_data)

        logger.info(f"Enqueued metadata reprocessing: {task.id}")

        return {
            "status": "accepted",
            "job_id": task.id,
            "message": f"Enqueued {len(batch_data)} items for reprocessing"
        }

    except Exception as e:
        logger.error(f"Error enqueueing metadata reprocessing: {e}")
        raise HTTPException(status_code=500, detail="Failed to enqueue metadata reprocessing")
