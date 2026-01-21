import logging
import hashlib
import json
from uuid import UUID
from datetime import datetime
from typing import Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import SilverRecord, RawFile, RetryQueue

logger = logging.getLogger(__name__)


class MapperService:
    """Maps raw extracted data to the silver/normalized schema."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def map_to_silver(
        self,
        file_id: UUID,
        raw_content: dict,
        file_type: str,
        file_size: int,
    ) -> SilverRecord:
        """
        Map raw extracted content to silver schema.

        Args:
            file_id: ID of the raw file
            raw_content: Raw extracted content from the ingestion agent
            file_type: File type/extension
            file_size: File size in bytes

        Returns:
            Created SilverRecord
        """
        processing_steps = ["extraction"]

        try:
            # Extract standard fields with null handling
            title = self._extract_field(raw_content, ["title", "name"])
            author = self._extract_field(raw_content, ["author", "creator", "author_name"])
            extraction_date = self._extract_datetime(
                raw_content, ["extraction_date", "processed_at"]
            )
            document_date = self._extract_datetime(
                raw_content, ["document_date", "date", "created_at"]
            )
            language = self._extract_field(raw_content, ["language", "lang"])
            content = self._extract_field(raw_content, ["content", "text", "body"])

            processing_steps.append("field_extraction")

            # Generate checksum of content
            checksum = self._compute_checksum(str(content))
            processing_steps.append("checksum_generation")

            # Enrich metadata with facets and processing steps
            metadata = {
                "source_id": str(file_id),
                "checksum": checksum,
                "processing_steps": processing_steps,
                "file_type_detected": file_type,
                "facets": self._extract_facets(raw_content),
                "mapped_at": datetime.utcnow().isoformat(),
            }

            # Create silver record
            silver_record = SilverRecord(
                file_id=file_id,
                raw_content=raw_content,
                title=title,
                author=author,
                extraction_date=extraction_date,
                document_date=document_date,
                file_type=file_type,
                size_bytes=file_size,
                language=language if isinstance(language, str) else None,
                content=content if isinstance(content, str) else None,
                record_metadata=metadata,
                processing_status="completed",
            )

            self.session.add(silver_record)
            await self.session.commit()

            logger.info(f"Successfully mapped file {file_id} to silver schema")
            return silver_record

        except Exception as e:
            logger.error(f"Failed to map file {file_id} to silver: {e}")
            await self.session.rollback()
            # Add to retry queue
            await self._add_to_retry_queue(
                file_id,
                "mapping_error",
                str(e),
            )
            raise

    async def batch_map_to_silver(
        self,
        mapping_data: list[dict],
    ) -> tuple[list[SilverRecord], list[dict]]:
        """
        Batch map multiple files to silver schema.

        Args:
            mapping_data: List of dicts with file_id, raw_content, file_type, file_size

        Returns:
            Tuple of (successful_records, failed_records)
        """
        successful = []
        failed = []

        for data in mapping_data:
            try:
                record = await self.map_to_silver(
                    file_id=data["file_id"],
                    raw_content=data["raw_content"],
                    file_type=data["file_type"],
                    file_size=data["file_size"],
                )
                successful.append(record)
            except Exception as e:
                logger.error(f"Batch mapping failed for {data['file_id']}: {e}")
                failed.append({
                    "file_id": data["file_id"],
                    "error": str(e),
                })

        logger.info(
            f"Batch mapping complete: {len(successful)} successful, {len(failed)} failed"
        )
        return successful, failed

    def _extract_field(self, data: dict, keys: list[str]) -> Optional[Any]:
        """Extract field from data, trying multiple keys."""
        if not isinstance(data, dict):
            return None

        for key in keys:
            if key in data:
                value = data[key]
                # Handle nested dicts/lists
                if isinstance(value, (dict, list)):
                    # Try to get a string representation or first item
                    if isinstance(value, list) and len(value) > 0:
                        return value[0] if isinstance(value[0], (str, int)) else None
                    elif isinstance(value, dict):
                        return None
                return value

        return None

    def _extract_datetime(self, data: dict, keys: list[str]) -> Optional[datetime]:
        """Extract datetime field from data."""
        for key in keys:
            if key in data:
                value = data[key]
                if isinstance(value, datetime):
                    return value
                elif isinstance(value, str):
                    try:
                        # Try common ISO formats
                        return datetime.fromisoformat(value.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        continue

        return None

    def _extract_facets(self, data: dict) -> dict:
        """Extract key-value facets from raw content for indexing."""
        facets = {}

        # Common facet keys to extract
        facet_keys = [
            "category",
            "type",
            "tags",
            "keywords",
            "department",
            "status",
        ]

        for key in facet_keys:
            if key in data:
                facets[key] = data[key]

        return facets

    def _compute_checksum(self, content: str) -> str:
        """Compute SHA-256 checksum of content."""
        return hashlib.sha256(content.encode()).hexdigest()

    async def _add_to_retry_queue(
        self,
        file_id: UUID,
        error_type: str,
        error_message: str,
    ) -> None:
        """Add failed record to retry queue."""
        try:
            retry_item = RetryQueue(
                file_id=file_id,
                error_type=error_type,
                error_message=error_message,
            )
            self.session.add(retry_item)
            await self.session.commit()
            logger.info(f"Added file {file_id} to retry queue")
        except Exception as e:
            logger.error(f"Failed to add to retry queue: {e}")
            await self.session.rollback()
