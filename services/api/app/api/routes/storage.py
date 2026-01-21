import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.storage_config import StorageConfig
from app.models.upload_metadata import UploadMetadata, UploadStatus
from app.models.file_version import FileVersion
from app.schemas.storage import (
    StorageConfigCreate,
    StorageConfigResponse,
    StorageConfigUpdate,
    UploadResponse,
    UploadMetadataResponse,
)
from app.services.storage_service import StorageService
from app.services.upload_validator import UploadValidator
from app.services.snapshot_service import SnapshotService
from app.services.audit_service import AuditService
from app.services.queue_service import QueueService
from app.workers.ingest_worker import enqueue_for_processing
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/storage", tags=["storage"])


@router.post("/config", response_model=StorageConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_storage_config(
    config: StorageConfigCreate,
    session: AsyncSession = Depends(get_db),
):
    """Create new storage configuration."""
    try:
        storage_config = StorageConfig(
            provider=config.provider,
            endpoint=config.endpoint,
            bucket_name=config.bucket_name,
            region=config.region,
            access_key=config.access_key,
            secret_key=config.secret_key,
            max_file_size_mb=config.max_file_size_mb,
            is_active=True,
        )

        session.add(storage_config)
        await session.commit()
        await session.refresh(storage_config)

        logger.info(f"Storage config created: {storage_config.id}")
        return storage_config

    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating storage config: {e}")
        raise HTTPException(status_code=500, detail="Failed to create storage config")


@router.get("/config", response_model=StorageConfigResponse)
async def get_storage_config(session: AsyncSession = Depends(get_db)):
    """Get active storage configuration."""
    try:
        result = await session.execute(
            select(StorageConfig).where(StorageConfig.is_active == True).limit(1)
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="No active storage config found")

        return config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving storage config: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve storage config")


@router.put("/config/{config_id}", response_model=StorageConfigResponse)
async def update_storage_config(
    config_id: str,
    config_update: StorageConfigUpdate,
    session: AsyncSession = Depends(get_db),
):
    """Update storage configuration."""
    try:
        result = await session.execute(
            select(StorageConfig).where(StorageConfig.id == config_id)
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Storage config not found")

        # Update fields
        update_data = config_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(config, field, value)

        await session.commit()
        await session.refresh(config)

        logger.info(f"Storage config updated: {config_id}")
        return config

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating storage config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update storage config")


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    request: Request = None,
    session: AsyncSession = Depends(get_db),
):
    """
    Upload file to storage with validation, snapshot, and queueing.

    Performs:
    1. File type and size validation
    2. Integrity check
    3. Snapshot creation with deduplication
    4. File version tracking
    5. Queue job creation
    6. Audit logging
    """
    try:
        # Get active storage config
        result = await session.execute(
            select(StorageConfig).where(StorageConfig.is_active == True).limit(1)
        )
        storage_config = result.scalar_one_or_none()

        if not storage_config:
            raise HTTPException(status_code=400, detail="Storage not configured")

        # Read file
        contents = await file.read()

        # Step 1: Validate file (type, size, integrity)
        validator = UploadValidator(max_file_size_mb=storage_config.max_file_size_mb)
        is_valid, error_msg = validator.validate(contents, file.filename, file.content_type)

        if not is_valid:
            logger.warning(f"File validation failed for {file.filename}: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        # Step 2: Upload to storage
        storage_service = StorageService(storage_config)
        upload_result = storage_service.upload_file(
            file_bytes=contents,
            filename=file.filename,
            content_type=file.content_type,
        )

        # Step 3: Create upload metadata record
        ttl = settings.signed_url_ttl_seconds
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)

        upload_metadata = UploadMetadata(
            filename=file.filename,
            file_size=len(contents),
            mime_type=file.content_type,
            checksum=upload_result["checksum"],
            storage_path=upload_result["storage_path"],
            storage_config_id=str(storage_config.id),
            upload_status=UploadStatus.COMPLETED,
            expires_at=expires_at,
        )

        session.add(upload_metadata)
        await session.flush()

        # Step 4: Create snapshot with deduplication
        snapshot_result = await SnapshotService.create_snapshot(
            session,
            file_id=str(upload_metadata.id),
            file_bytes=contents,
            filename=file.filename,
            created_by=request.client.host if request else None,
        )

        # Step 5: Create file version
        file_version = FileVersion(
            upload_metadata_id=upload_metadata.id,
            version_number=snapshot_result["version_number"],
            snapshot_id=snapshot_result["snapshot_id"],
            file_hash=snapshot_result["content_hash"],
            is_deduplicated=snapshot_result["is_deduplicated"],
            storage_path=snapshot_result["storage_path"],
            content_hash_id=snapshot_result["content_hash"],
        )

        session.add(file_version)
        await session.flush()

        # Step 6: Enqueue for processing
        file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else "unknown"
        queue_result = await QueueService.enqueue(
            session,
            file_id=str(upload_metadata.id),
            file_type=file_ext,
            file_size=len(contents),
            uploader_id=request.client.host if request else None,
            priority="normal",
        )

        # Step 7: Log audit event
        await AuditService.log_action(
            session,
            resource_type="file",
            resource_id=str(upload_metadata.id),
            action="create",
            actor_id=request.client.host if request else None,
            changes={"filename": file.filename, "size": len(contents)},
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
        )

        # Generate signed URL
        signed_url, expires_at = storage_service.generate_signed_url(
            upload_result["storage_path"],
            ttl_seconds=ttl,
        )

        await session.commit()

        logger.info(f"File uploaded successfully: {file.filename}, ID: {upload_metadata.id}")

        return UploadResponse(
            file_id=upload_metadata.id,
            signed_url=signed_url,
            expires_at=expires_at,
            size=len(contents),
            mime_type=file.content_type,
            job_id=queue_result["job_id"],
        )

    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/upload/{file_id}", response_model=UploadMetadataResponse)
async def get_upload_metadata(
    file_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get upload metadata."""
    try:
        result = await session.execute(
            select(UploadMetadata).where(UploadMetadata.id == file_id)
        )
        metadata = result.scalar_one_or_none()

        if not metadata:
            raise HTTPException(status_code=404, detail="Upload not found")

        return metadata

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving upload metadata: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve upload metadata")


@router.get("/test")
async def test_storage_connection(session: AsyncSession = Depends(get_db)):
    """Test storage connection by attempting a non-destructive operation."""
    try:
        result = await session.execute(
            select(StorageConfig).where(StorageConfig.is_active == True).limit(1)
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(
                status_code=424,
                detail="No active storage config found. Please configure storage first."
            )

        # Test the storage connection
        try:
            storage_service = StorageService(config)
            # Attempt a simple test operation (list bucket contents with limit)
            storage_service.test_connection()

            return {
                "success": True,
                "message": "Storage connection is working",
                "provider": config.provider,
                "endpoint": config.endpoint,
                "bucket_name": config.bucket_name,
            }
        except Exception as conn_error:
            logger.error(f"Storage connection test failed: {conn_error}")
            raise HTTPException(
                status_code=503,
                detail=f"Storage connection failed: {str(conn_error)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing storage connection: {e}")
        raise HTTPException(status_code=500, detail="Failed to test storage connection")
