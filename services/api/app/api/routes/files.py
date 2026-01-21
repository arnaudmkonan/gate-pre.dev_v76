"""Routes for file versioning and snapshot management."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.file_versions import FileVersionResponse, VersionListResponse
from app.services.snapshot_service import SnapshotService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/{file_id}/versions", response_model=VersionListResponse)
async def list_file_versions(
    file_id: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Get all versions of a file.

    Returns list of versions within 2 seconds.
    """
    try:
        versions = await SnapshotService.list_versions(session, file_id)

        return VersionListResponse(
            versions=versions,
            total_count=len(versions),
        )

    except Exception as e:
        logger.error(f"Error listing versions for file {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list versions")


@router.get("/{file_id}/versions/{version_id}")
async def get_version_metadata(
    file_id: str,
    version_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get metadata for a specific file version."""
    try:
        from sqlalchemy import select
        from app.models.file_version import FileVersion

        result = await session.execute(
            select(FileVersion).where(FileVersion.id == version_id)
        )
        version = result.scalar_one_or_none()

        if not version or str(version.upload_metadata_id) != file_id:
            raise HTTPException(status_code=404, detail="Version not found")

        return {
            "version_id": str(version.id),
            "version_number": version.version_number,
            "file_hash": version.file_hash,
            "is_deduplicated": version.is_deduplicated,
            "storage_path": version.storage_path,
            "created_at": version.created_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving version {version_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve version")


@router.get("/{file_id}/versions/{version_id}/download")
async def download_version(
    file_id: str,
    version_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Download a specific file version."""
    try:
        from sqlalchemy import select
        from app.models.file_version import FileVersion

        result = await session.execute(
            select(FileVersion).where(FileVersion.id == version_id)
        )
        version = result.scalar_one_or_none()

        if not version or str(version.upload_metadata_id) != file_id:
            raise HTTPException(status_code=404, detail="Version not found")

        # In a real implementation, you would:
        # 1. Fetch file from Supabase Storage using version.storage_path
        # 2. Return as StreamingResponse
        # For now, return metadata with signed URL instructions

        return {
            "version_id": str(version.id),
            "storage_path": version.storage_path,
            "file_hash": version.file_hash,
            "is_deduplicated": version.is_deduplicated,
            "message": "Use storage service to download file from storage_path",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading version {version_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to download version")
