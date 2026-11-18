"""API routes for ingestion jobs (Story 2 & 4)."""
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.ingest_jobs import (
    IngestJobResponse,
    IngestJobListResponse,
    ModeSelectorRequest,
    MappingPreviewRequest,
    MappingPreviewResponse,
)
from app.services.ingest_service import IngestService
from app.core.auth import get_current_user
from app.startup.ingest_access import assert_can_access_job, uploader_scope_for_list

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingest", tags=["ingest_jobs"], dependencies=[Depends(get_current_user)])


@router.get("/jobs", response_model=IngestJobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: Optional[str] = None,
    created_after: Optional[datetime] = None,
    source: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get paginated list of ingestion jobs with optional filters.

    Non-admin users only see jobs they uploaded.
    """
    del source, created_after  # reserved for future filters
    try:
        uploader_id = uploader_scope_for_list(current_user)
        jobs, total_count = await IngestService.list_jobs(
            session,
            status=status,
            uploader_id=uploader_id,
            page=page,
            page_size=page_size,
        )

        job_responses = [IngestJobResponse.model_validate(job) for job in jobs]
        total_pages = (total_count + page_size - 1) // page_size if total_count else 0

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
    current_user: dict = Depends(get_current_user),
):
    """Get detailed information about a specific ingestion job."""
    try:
        job = await IngestService.get_job_detail(session, job_id)
        if not job:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found",
            )
        assert_can_access_job(job, current_user)
        return IngestJobResponse.model_validate(job)
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
    current_user: dict = Depends(get_current_user),
):
    """Select or update ingestion mode for a job (Story 4)."""
    try:
        existing = await IngestService.get_job_detail(session, job_id)
        if not existing:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found",
            )
        assert_can_access_job(existing, current_user)

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

        return IngestJobResponse.model_validate(job)
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
    current_user: dict = Depends(get_current_user),
):
    """Preview mapping configuration for a sample document (Story 4 - Guided Mapping)."""
    try:
        job = await IngestService.get_job_detail(session, job_id)
        if not job:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found",
            )
        assert_can_access_job(job, current_user)

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
