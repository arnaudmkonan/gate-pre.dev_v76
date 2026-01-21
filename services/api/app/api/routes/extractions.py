"""API routes for raw extractions and extraction management."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.core.database import get_db
from app.models import RawExtraction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/extractions", tags=["extractions"])


class ExtractionResponse(BaseModel):
    """Response model for extraction result."""

    id: str
    file_id: str
    status: str
    extracted_text: Optional[str] = None
    extracted_tables: Optional[list] = None
    extracted_metadata: Optional[dict] = None
    error_message: Optional[str] = None
    error_details: Optional[dict] = None
    extraction_timestamp: Optional[str] = None
    extractor_version: Optional[str] = None
    created_at: str
    updated_at: str
    filename: Optional[str] = None

    class Config:
        from_attributes = True


class ExtractionListResponse(BaseModel):
    """Response model for extraction list."""

    total: int
    page: int
    page_size: int
    items: list[ExtractionResponse]


@router.get(
    "",
    response_model=ExtractionListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_extractions(
    file_id: Optional[str] = Query(None, description="Filter by file ID"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_db),
):
    """
    List raw extraction results with filtering and pagination.

    Query parameters:
    - file_id: Filter by file ID
    - status: Filter by status (pending, in_progress, success, partial, failed)
    - page: Page number (default 1)
    - page_size: Items per page (default 20, max 100)

    Returns:
        200 OK with paginated extraction results
    """
    try:
        query = select(RawExtraction)

        if file_id:
            query = query.where(RawExtraction.file_id == UUID(file_id))

        if status_filter:
            query = query.where(RawExtraction.status == status_filter)

        # Get total count
        count_query = select(func.count(RawExtraction.id))
        if file_id:
            count_query = count_query.where(RawExtraction.file_id == UUID(file_id))
        if status_filter:
            count_query = count_query.where(RawExtraction.status == status_filter)

        count_result = await session.execute(count_query)
        total_count = count_result.scalar() or 0

        # Get paginated results
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size).order_by(
            RawExtraction.created_at.desc()
        )

        result = await session.execute(query)
        extractions = result.scalars().all()

        return ExtractionListResponse(
            total=total_count,
            page=page,
            page_size=page_size,
            items=[
                ExtractionResponse(
                    id=str(e.id),
                    file_id=str(e.file_id),
                    status=e.status,
                    extracted_text=e.extracted_text,
                    extracted_tables=e.extracted_tables,
                    extracted_metadata=e.extracted_metadata,
                    error_message=e.error_message,
                    error_details=e.error_details,
                    extraction_timestamp=e.extraction_timestamp.isoformat()
                    if e.extraction_timestamp
                    else None,
                    extractor_version=e.extractor_version,
                    created_at=e.created_at.isoformat(),
                    updated_at=e.updated_at.isoformat(),
                    filename=None,  # Would need to join with raw_files table
                )
                for e in extractions
            ],
        )

    except Exception as e:
        logger.error(f"Error listing extractions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve extractions",
        )


@router.get(
    "/{extraction_id}",
    response_model=ExtractionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_extraction(
    extraction_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get a specific extraction result."""
    try:
        extraction = await session.get(RawExtraction, extraction_id)

        if not extraction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Extraction not found",
            )

        return ExtractionResponse(
            id=str(extraction.id),
            file_id=str(extraction.file_id),
            status=extraction.status,
            extracted_text=extraction.extracted_text,
            extracted_tables=extraction.extracted_tables,
            extracted_metadata=extraction.extracted_metadata,
            error_message=extraction.error_message,
            error_details=extraction.error_details,
            extraction_timestamp=extraction.extraction_timestamp.isoformat()
            if extraction.extraction_timestamp
            else None,
            extractor_version=extraction.extractor_version,
            created_at=extraction.created_at.isoformat(),
            updated_at=extraction.updated_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting extraction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve extraction",
        )


@router.post(
    "/retry",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def retry_extraction(
    session: AsyncSession = Depends(get_db),
):
    """Retry extraction for failed items."""
    try:
        logger.info("Retrying failed extractions")
        # In production, this would re-process failed extractions
        # For now, just return success
        return {
            "status": "success",
            "message": "Extraction retry initiated",
            "processed_count": 0,
        }
    except Exception as e:
        logger.error(f"Error retrying extraction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
