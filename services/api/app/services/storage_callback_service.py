import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.models.raw_file import RawFile, RawFileStatus
from app.models.document_metadata import DocumentMetadata
from app.models.ingest_job import IngestJobStatus

logger = logging.getLogger(__name__)


class StorageCallbackService:
    """Service for handling storage callbacks and enqueuing extraction tasks."""

    @staticmethod
    def validate_signature(payload: str, signature: str, secret: str) -> bool:
        """
        Validate HMAC signature of callback payload.

        Args:
            payload: Raw request body as string
            signature: Signature header value
            secret: Secret key for validation

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            expected_signature = hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256,
            ).hexdigest()

            # Constant-time comparison to prevent timing attacks
            return hmac.compare_digest(expected_signature, signature)

        except Exception as e:
            logger.error(f"Error validating signature: {e}")
            return False

    @staticmethod
    async def process_callback(
        session: AsyncSession,
        payload: dict,
        file_id: Optional[str] = None,
    ) -> dict:
        """
        Process storage callback and update raw file status.

        Args:
            session: Database session
            payload: Callback payload with file info
            file_id: Optional file ID for idempotency

        Returns:
            Dictionary with processing result
        """
        try:
            # Extract file info from payload
            storage_path = payload.get("path") or payload.get("storage_path")
            status = payload.get("status", "stored")  # stored or failed
            error_message = payload.get("error_message")

            if not storage_path:
                raise ValueError("Missing storage_path in callback payload")

            # Find raw file by storage path or file_id
            query = select(RawFile)
            if file_id:
                query = query.where(RawFile.id == file_id)
            else:
                query = query.where(RawFile.storage_path == storage_path)

            result = await session.execute(query)
            raw_file = result.scalars().first()

            if not raw_file:
                logger.warning(f"Raw file not found for storage_path: {storage_path}")
                return {
                    "success": False,
                    "error": "Raw file not found",
                    "storage_path": storage_path,
                }

            # Check idempotency - if already processed, return success
            if raw_file.status == RawFileStatus.STORED:
                logger.info(f"Raw file already stored (idempotent): {raw_file.id}")
                return {
                    "success": True,
                    "message": "File already processed (idempotent)",
                    "file_id": str(raw_file.id),
                    "storage_path": storage_path,
                }

            # Update raw file status
            if status == "stored":
                raw_file.status = RawFileStatus.STORED
                raw_file.stored_at = datetime.now(timezone.utc)
                raw_file.error_message = None
                raw_file.retry_count = 0

                logger.info(f"Raw file marked as stored: {raw_file.id}")
            elif status == "failed":
                raw_file.status = RawFileStatus.FAILED
                raw_file.error_message = error_message or "Storage callback indicated failure"
                raw_file.retry_count += 1

                logger.warning(f"Raw file marked as failed: {raw_file.id}, error: {error_message}")

                # Implement retry logic
                if raw_file.retry_count >= raw_file.max_retries:
                    logger.error(f"Max retries exceeded for file: {raw_file.id}")
                    # TODO: Send admin notification
                    return {
                        "success": False,
                        "error": "Max retries exceeded",
                        "file_id": str(raw_file.id),
                    }

            # Commit raw file status update
            await session.commit()

            # Create or update document metadata if status is stored
            if status == "stored":
                metadata_result = await StorageCallbackService._create_metadata(
                    session, raw_file
                )
                logger.info(f"Metadata created/updated for file: {raw_file.id}")
            else:
                metadata_result = None

            return {
                "success": True,
                "file_id": str(raw_file.id),
                "storage_path": storage_path,
                "status": raw_file.status,
                "metadata_id": str(metadata_result.id) if metadata_result else None,
            }

        except ValueError as e:
            logger.error(f"Validation error in callback: {e}")
            return {
                "success": False,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Error processing storage callback: {e}")
            raise

    @staticmethod
    async def _create_metadata(
        session: AsyncSession,
        raw_file: RawFile,
    ) -> Optional[DocumentMetadata]:
        """
        Create document metadata record for stored file.

        Args:
            session: Database session
            raw_file: The raw file record

        Returns:
            Created DocumentMetadata record
        """
        try:
            # Check if metadata already exists
            query = select(DocumentMetadata).where(
                DocumentMetadata.raw_storage_path == raw_file.storage_path
            )
            result = await session.execute(query)
            existing_metadata = result.scalars().first()

            if existing_metadata:
                return existing_metadata

            # Create new metadata record
            metadata = DocumentMetadata(
                job_id=raw_file.id,  # Using raw_file.id as job_id for now
                filename=raw_file.filename,
                file_type=raw_file.file_type,
                size=raw_file.file_size,
                uploader=raw_file.uploader_id,
                ingestion_status="pending",  # Will be updated as extraction progresses
                raw_storage_path=raw_file.storage_path,
                customer_id=raw_file.customer_id,
                source=raw_file.source,
                tags=raw_file.tags,
                mime_type=f"application/{raw_file.file_type}",
            )

            session.add(metadata)
            await session.flush()

            return metadata

        except Exception as e:
            logger.error(f"Error creating metadata: {e}")
            raise
