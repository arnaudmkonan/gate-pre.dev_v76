import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.models.raw_file import RawFile, RawFileStatus
from app.models.ingest_job import IngestJob, IngestJobStatus
from app.models.storage_config import StorageConfig
from app.schemas.upload import UploadResponse, RawFileResponse
from app.services.storage_service import StorageService
from app.services.idempotency_service import IdempotencyService
from app.services.ingest_service import IngestService
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/upload", tags=["upload"])

# Supported file types for ingestion
SUPPORTED_FILE_TYPES = {
    "txt", "md", "docx", "xlsx", "pptx", "html", "pdf",
    "json", "csv", "yml", "xml"
}


def get_file_extension(filename: str) -> str:
    """Extract file extension from filename."""
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


@router.post(
    "",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_file(
    file: UploadFile = File(...),
    source: str = None,
    customer_id: str = None,
    tags: str = None,
    idempotency_key: str = Header(None),
    session: AsyncSession = Depends(get_db),
):
    """
    Upload a document for ingestion.

    Supports multipart/form-data with the following fields:
    - file: The document file to upload
    - source: Optional source identifier (e.g., "crm", "email")
    - customer_id: Optional customer ID for multi-tenant systems
    - tags: Optional comma-separated tags
    - Idempotency-Key header: Optional key for idempotent uploads

    Returns:
        202 Accepted with job_id and file_id
        415 Unsupported Media Type for unsupported file types
        413 Payload Too Large for files exceeding max size
    """
    try:
        # Validate file extension
        file_ext = get_file_extension(file.filename)
        if file_ext not in SUPPORTED_FILE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type: .{file_ext}. "
                       f"Supported types: {', '.join(sorted(SUPPORTED_FILE_TYPES))}",
            )

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        # Validate file size
        max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_PAYLOAD_TOO_LARGE,
                detail=f"File size {file_size} bytes exceeds maximum {max_size_bytes} bytes "
                       f"({settings.max_upload_size_mb}MB)",
            )

        # Check for idempotency
        if idempotency_key:
            existing = await IdempotencyService.check_idempotency_key(
                session, idempotency_key
            )
            if existing:
                # Return the same job ID
                logger.info(f"Idempotent request detected: {idempotency_key}")
                raw_file = await session.get(RawFile, existing["file_id"])
                return UploadResponse(
                    job_id=existing["job_id"],
                    file_id=existing["file_id"],
                    filename=raw_file.filename,
                    file_type=raw_file.file_type,
                    size=raw_file.file_size,
                    storage_path=raw_file.storage_path,
                    status=raw_file.status,
                    message="File already processed (idempotent request)",
                )

        # Get active storage config, or use local storage for development
        result = await session.execute(
            select(StorageConfig).where(StorageConfig.is_active == True).limit(1)
        )
        storage_config = result.scalar_one_or_none()

        if storage_config:
            # Use cloud storage (S3/Supabase)
            storage_service = StorageService(storage_config)
            storage_result = storage_service.upload_file(
                file_bytes=file_content,
                filename=file.filename,
                content_type=file.content_type or "application/octet-stream",
            )
        else:
            # Fall back to local storage for development/testing
            from app.services.local_storage_service import LocalStorageService
            logger.info("Using local storage (cloud storage not configured)")
            local_storage = LocalStorageService()
            storage_result = local_storage.upload_file(
                file_bytes=file_content,
                filename=file.filename,
                content_type=file.content_type or "application/octet-stream",
            )

        # Parse tags if provided
        tags_list = None
        if tags:
            tags_list = [t.strip() for t in tags.split(",")]

        # Check if file needs chunking (>50MB)
        chunk_size = 50 * 1024 * 1024  # 50MB
        is_chunked = file_size > chunk_size
        total_chunks = (file_size + chunk_size - 1) // chunk_size if is_chunked else 1

        # Create raw file record(s)
        raw_files = []
        if is_chunked:
            # Create a master record and chunk records
            master_file = RawFile(
                filename=file.filename,
                file_type=file_ext,
                file_size=file_size,
                storage_path=storage_result["storage_path"],
                mime_type=file.content_type or "application/octet-stream",
                status=RawFileStatus.UPLOADED,
                uploader_id=None,
                source=source,
                customer_id=customer_id,
                tags=tags_list,
                checksum=storage_result["checksum"],
                assembly_metadata={
                    "chunk_strategy": "size_based",
                    "chunk_size_bytes": chunk_size,
                    "total_chunks": total_chunks,
                    "reassembly_order": list(range(total_chunks)),
                }
            )
            session.add(master_file)
            await session.flush()
            raw_files.append(master_file)

            # Note: Actual chunk records are created by the queuing task
            logger.info(f"Created chunked file record: {file.filename} ({total_chunks} chunks)")
        else:
            raw_file = RawFile(
                filename=file.filename,
                file_type=file_ext,
                file_size=file_size,
                storage_path=storage_result["storage_path"],
                mime_type=file.content_type or "application/octet-stream",
                status=RawFileStatus.UPLOADED,
                uploader_id=None,  # Can be set from auth context in production
                source=source,
                customer_id=customer_id,
                tags=tags_list,
                checksum=storage_result["checksum"],
            )
            session.add(raw_file)
            await session.flush()
            raw_files.append(raw_file)

        # Create ingest job
        ingest_job = IngestJob(
            filename=file.filename,
            file_type=file_ext,
            size=file_size,
            storage_path=storage_result["storage_path"],
            status=IngestJobStatus.PENDING,
            uploader_id=None,
        )

        session.add(ingest_job)
        await session.flush()

        # Store idempotency key if provided
        if idempotency_key:
            await IdempotencyService.store_idempotency_key(
                session=session,
                idempotency_key=idempotency_key,
                file_id=raw_file.id,
                job_id=ingest_job.id,
                ttl_hours=24,
            )

        # Commit transaction
        await session.commit()

        # Trigger async task to transition to "queued" status
        try:
            from app.workers.ingest_tasks import queue_raw_file
            queue_raw_file.delay(str(raw_files[0].id))
        except Exception as task_error:
            logger.warning(f"Could not trigger async queuing task: {task_error}. File will stay in UPLOADED state.")
            # Set to QUEUED synchronously as fallback
            raw_files[0].status = RawFileStatus.QUEUED
            await session.commit()

        logger.info(
            f"File uploaded successfully: {file.filename} "
            f"(job_id={ingest_job.id}, file_id={raw_files[0].id}, size={file_size} bytes)"
        )

        return UploadResponse(
            job_id=ingest_job.id,
            file_id=raw_files[0].id,
            filename=file.filename,
            file_type=file_ext,
            size=file_size,
            storage_path=storage_result["storage_path"],
            status=raw_files[0].status,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file",
        )


@router.get("/{file_id}", response_model=RawFileResponse)
async def get_file_info(
    file_id: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Get information about an uploaded file.

    Returns:
        200 OK with file information
        404 Not Found if file doesn't exist
    """
    try:
        raw_file = await session.get(RawFile, file_id)

        if not raw_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File {file_id} not found",
            )

        return RawFileResponse.from_orm(raw_file)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving file info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve file information",
        )
