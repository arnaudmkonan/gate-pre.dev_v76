import logging
import time
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingest_job import IngestJob
from app.parsers.registry import ParserRegistry
from app.services.ingest_service import IngestService

logger = logging.getLogger(__name__)


class MetadataService:
    """Service for extracting and managing document metadata."""

    @staticmethod
    async def extract_metadata(
        file_bytes: bytes,
        filename: str,
        file_type: str,
    ) -> Dict:
        """
        Extract metadata from a file.

        Args:
            file_bytes: Raw file bytes
            filename: Original filename
            file_type: File type/extension

        Returns:
            Dict with extracted metadata
        """
        try:
            start_time = time.time()

            # Get appropriate parser
            parser = ParserRegistry.get_parser(file_type)
            if not parser:
                logger.warning(f"No parser found for file type: {file_type}")
                return {
                    "filename": filename,
                    "mime_type": "application/octet-stream",
                    "page_count": None,
                    "language": None,
                    "title": filename,
                    "extracted_text_preview": None,
                    "file_size_bytes": len(file_bytes),
                    "extraction_time_seconds": time.time() - start_time,
                    "error": f"No parser available for .{file_type}",
                }

            # Validate format
            is_valid = await parser.validate_format(file_bytes)
            if not is_valid:
                logger.warning(f"File validation failed for {filename}")
                return {
                    "filename": filename,
                    "mime_type": "application/octet-stream",
                    "error": "Invalid file format",
                    "file_size_bytes": len(file_bytes),
                    "extraction_time_seconds": time.time() - start_time,
                }

            # Extract metadata
            metadata = await parser.extract_metadata(file_bytes, filename)
            metadata["file_size_bytes"] = len(file_bytes)
            metadata["extraction_time_seconds"] = time.time() - start_time

            logger.info(f"Metadata extracted from {filename}: {metadata.get('title')}")
            return metadata

        except Exception as e:
            logger.error(f"Error extracting metadata from {filename}: {e}")
            return {
                "filename": filename,
                "error": str(e),
                "file_size_bytes": len(file_bytes),
                "extraction_time_seconds": time.time() - start_time,
            }

    @staticmethod
    async def update_job_metadata(
        session: AsyncSession,
        job_id: UUID,
        file_bytes: bytes,
    ) -> Optional[IngestJob]:
        """
        Extract and update metadata for a job.

        Args:
            session: Database session
            job_id: Job ID to update
            file_bytes: Raw file bytes

        Returns:
            Updated IngestJob instance
        """
        try:
            # Get job
            job = await IngestService.get_job(session, job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            # Extract metadata
            metadata = await MetadataService.extract_metadata(
                file_bytes,
                job.filename,
                job.file_type,
            )

            # Update job with metadata
            job = await IngestService.update_job_status(
                session,
                job_id,
                job.status,
                metadata=metadata,
            )

            logger.info(f"Job {job_id} metadata updated")
            return job

        except Exception as e:
            logger.error(f"Error updating job metadata: {e}")
            raise

    @staticmethod
    def get_supported_file_types() -> list[str]:
        """Get list of supported file types."""
        return ParserRegistry.get_supported_extensions()

    @staticmethod
    def is_supported(file_type: str) -> bool:
        """Check if file type is supported."""
        return ParserRegistry.supports(file_type)
