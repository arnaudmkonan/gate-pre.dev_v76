"""API routes for ingestion jobs (Story 2 & 4)."""
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.ingest_job import IngestJob
from app.schemas.ingest_jobs import (
    IngestJobResponse,
    IngestJobListResponse,
    ModeSelectorRequest,
    MappingPreviewRequest,
    MappingPreviewResponse,
)
from app.services.ingest_service import IngestService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingest", tags=["ingest_jobs"])


@router.get("/jobs", response_model=IngestJobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: Optional[str] = None,
    created_after: Optional[datetime] = None,
    source: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    """
    Get paginated list of ingestion jobs with optional filters.

    Query Parameters:
    - page: Page number (1-indexed), default 1
    - page_size: Items per page (1-100), default 50
    - status: Filter by job status (pending, queued, processing, completed, failed)
    - created_after: Filter by creation date (ISO format)
    - source: Filter by source (optional)

    Returns:
        IngestJobListResponse with paginated jobs and metadata
    """
    try:
        from sqlalchemy import text

        # Build filters for SQL
        where_clause_parts = []
        if status:
            where_clause_parts.append(f"status = '{status}'")
        if created_after:
            where_clause_parts.append(f"created_at >= '{created_after.isoformat()}'")

        where_clause = " AND ".join(where_clause_parts)
        where_sql = f" WHERE {where_clause}" if where_clause else ""

        # Get total count
        count_sql = f"SELECT COUNT(*) as total FROM ingest_jobs{where_sql}"
        count_result = await session.execute(text(count_sql))
        total_count = count_result.scalar() or 0

        # Get paginated results
        offset = (page - 1) * page_size
        jobs_sql = f"""
            SELECT * FROM ingest_jobs{where_sql}
            ORDER BY created_at DESC
            LIMIT {page_size} OFFSET {offset}
        """

        result = await session.execute(text(jobs_sql))
        rows = result.fetchall()

        # Convert rows to job objects
        job_responses = []
        for row in rows:
            job_dict = dict(row._mapping)
            # Convert UUID to string
            if 'id' in job_dict and hasattr(job_dict['id'], '__str__'):
                job_dict['id'] = str(job_dict['id'])
            job_responses.append(IngestJobResponse(**job_dict))

        total_pages = (total_count + page_size - 1) // page_size

        return IngestJobListResponse(
            jobs=job_responses,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list jobs",
        )


@router.get("/jobs/{job_id}", response_model=IngestJobResponse)
async def get_job_detail(
    job_id: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Get detailed information about a specific ingestion job.

    Args:
        job_id: The job ID

    Returns:
        IngestJobResponse with full job details
    """
    try:
        job = await IngestService.get_job_detail(session, job_id)
        if not job:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found",
            )
        return IngestJobResponse.from_orm(job)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job detail: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get job details",
        )


@router.post("/jobs/{job_id}/mode", response_model=IngestJobResponse)
async def select_mode(
    job_id: str,
    request: ModeSelectorRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Select or update ingestion mode for a job (Story 4).

    Args:
        job_id: The job ID
        request: Mode selection request with mode, batch_size, schedule_time, mapping_config

    Returns:
        Updated IngestJobResponse
    """
    try:
        job = await IngestService.update_job_mode(
            session=session,
            job_id=job_id,
            mode=request.mode,
            batch_size=request.batch_size,
            schedule_time=request.schedule_time,
            mapping_config=request.mapping_config.dict() if request.mapping_config else None,
        )

        if not job:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found",
            )

        return IngestJobResponse.from_orm(job)
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error selecting mode: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to select ingestion mode",
        )


@router.post("/jobs/{job_id}/mapping-preview", response_model=MappingPreviewResponse)
async def preview_mapping(
    job_id: str,
    request: MappingPreviewRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Preview mapping configuration for a sample document (Story 4 - Guided Mapping).

    Args:
        job_id: The job ID
        request: Mapping preview request with mapping_config and optional sample_content

    Returns:
        MappingPreviewResponse with validation results and extracted fields
    """
    try:
        # Verify job exists
        job = await IngestService.get_job_detail(session, job_id)
        if not job:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found",
            )

        # Validate mapping configuration
        preview_response = await IngestService.validate_mapping_for_sample(
            mapping_config=request.mapping_config,
            sample_content=request.sample_content,
        )

        return preview_response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing mapping: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to preview mapping",
        )
