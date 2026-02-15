"""Internal API endpoint for raw metadata ingestion and management."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.raw_metadata import (
    RawMetadataCreate,
    RawMetadataResponse,
    RawMetadataQueryResponse,
)
from app.services.metadata.raw_metadata_service import RawMetadataService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal/metadata", tags=["internal-metadata"])


@router.post(
    "/raw",
    response_model=RawMetadataQueryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_raw_metadata(
    request: RawMetadataCreate,
    session: AsyncSession = Depends(get_db),
):
    """
    Save raw file metadata with deduplication by checksum.

    Returns:
        201 Created with metadata and upload event
        409 Conflict if duplicate found
        400 Bad Request if required fields missing
    """
    try:
        # Validate required fields
        if not request.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="filename is required",
            )
        if not request.storage_location:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="storage_location is required",
            )
        if not request.checksum:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="checksum is required",
            )

        # Save metadata with deduplication
        metadata, upload_event, is_duplicate = await RawMetadataService.save_raw_metadata(
            session=session,
            filename=request.filename,
            file_size=request.file_size,
            checksum=request.checksum,
            storage_location=request.storage_location,
            uploader_id=request.uploader_id,
            file_type=request.file_type,
        )

        # Return 409 if duplicate
        if is_duplicate:
            logger.info(f"Duplicate upload detected: checksum={request.checksum}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="File with this checksum already exists",
            )

        logger.info(f"Raw metadata saved: {metadata.id}")

        return RawMetadataQueryResponse(
            metadata=RawMetadataResponse.from_orm(metadata),
            is_duplicate=False,
            upload_event=upload_event.__dict__,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error saving raw metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save raw metadata",
        )


@router.get(
    "/raw/{metadata_id}",
    response_model=RawMetadataResponse,
    status_code=status.HTTP_200_OK,
)
async def get_raw_metadata(
    metadata_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get raw metadata by record ID.

    Returns:
        200 OK with metadata
        404 Not Found if metadata doesn't exist
    """
    try:
        metadata = await RawMetadataService.get_by_record_id(session, metadata_id)

        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Raw metadata {metadata_id} not found",
            )

        return RawMetadataResponse.from_orm(metadata)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving raw metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve raw metadata",
        )


@router.get(
    "/raw/checksum/{checksum}",
    response_model=RawMetadataResponse,
    status_code=status.HTTP_200_OK,
)
async def get_raw_metadata_by_checksum(
    checksum: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Get raw metadata by checksum (for deduplication checks).

    Returns:
        200 OK with metadata
        404 Not Found if not found
    """
    try:
        metadata = await RawMetadataService.get_by_checksum(session, checksum)

        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Raw metadata with checksum {checksum} not found",
            )

        return RawMetadataResponse.from_orm(metadata)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving raw metadata by checksum: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve raw metadata",
        )
