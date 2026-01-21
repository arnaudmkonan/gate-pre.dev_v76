"""Service for mapping raw and document metadata to normalized silver schema."""
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.document_metadata import DocumentMetadata
from app.models.quarantine import Quarantine
from app.models.silver_metadata import SilverMetadata
from app.services.validation_service import ValidationService

logger = logging.getLogger(__name__)


class MappingService:
    """Service for mapping raw/document metadata to normalized silver schema."""

    # Configurable field mappings
    FIELD_MAPPINGS = {
        "title": "title",
        "author": "author",
        "language": "language",
        "page_count": "page_count",
        "document_type": "document_type",
        "created_at": "date",
    }

    @staticmethod
    async def map_to_silver(
        session: AsyncSession,
        file_id: UUID,
        document_metadata: DocumentMetadata,
    ) -> Tuple[Optional[SilverMetadata], bool, Optional[str]]:
        """
        Map document metadata to normalized silver schema.

        Args:
            session: Database session
            file_id: File ID to map
            document_metadata: Extracted document metadata

        Returns:
            Tuple of (SilverMetadata, success, error_reason)
        """
        start_time = datetime.utcnow()

        try:
            # Build normalized schema
            normalized_data = {}

            # Apply field mappings with type coercion
            for source_field, target_field in MappingService.FIELD_MAPPINGS.items():
                source_value = getattr(document_metadata, source_field, None)
                if source_value is not None:
                    # Type coercion
                    if target_field == "page_count" and isinstance(source_value, str):
                        try:
                            normalized_data[target_field] = int(source_value)
                        except (ValueError, TypeError):
                            normalized_data[target_field] = None
                    elif target_field == "date" and isinstance(source_value, str):
                        try:
                            normalized_data[target_field] = datetime.fromisoformat(source_value)
                        except (ValueError, TypeError):
                            normalized_data[target_field] = None
                    else:
                        normalized_data[target_field] = source_value

            # Add additional fields
            normalized_data["tags"] = document_metadata.tags or []
            normalized_data["content_hash"] = MappingService._calculate_content_hash(document_metadata)

            # Validate normalized data
            is_valid, validation_errors = await ValidationService.validate_fields(normalized_data)

            if not is_valid:
                # Move to quarantine
                logger.warning(f"Validation failed for file {file_id}: {validation_errors}")
                await MappingService._quarantine_record(
                    session, file_id, normalized_data, validation_errors
                )
                return None, False, f"Validation failed: {json.dumps(validation_errors)}"

            # Create silver metadata
            silver = SilverMetadata(
                file_id=file_id,
                title=normalized_data.get("title"),
                author=normalized_data.get("author"),
                date=normalized_data.get("date"),
                document_type=normalized_data.get("document_type"),
                language=normalized_data.get("language"),
                page_count=normalized_data.get("page_count"),
                normalized_tags=normalized_data.get("tags", []),
                content_hash=normalized_data.get("content_hash"),
                status="success",
                metadata_json=normalized_data,
                mapping_version="1.0",
                mapping_summary=MappingService._generate_mapping_summary(normalized_data),
            )

            session.add(silver)
            await session.commit()

            processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            logger.info(
                f"Mapping complete for {file_id}: {processing_time_ms}ms, "
                f"fields={len(normalized_data)}, status=success"
            )

            return silver, True, None

        except Exception as e:
            await session.rollback()
            logger.error(f"Error mapping metadata for {file_id}: {e}")
            return None, False, str(e)

    @staticmethod
    async def _quarantine_record(
        session: AsyncSession,
        file_id: UUID,
        original_data: Dict,
        validation_errors: list,
    ) -> None:
        """Move failed mapping to quarantine."""
        try:
            quarantine = Quarantine(
                file_id=file_id,
                original_data=original_data,
                validation_errors=[
                    {"field": err.get("field"), "reason": err.get("reason")}
                    for err in validation_errors
                ],
            )
            session.add(quarantine)
            await session.commit()
            logger.info(f"Record quarantined: {file_id}")
        except Exception as e:
            logger.error(f"Error quarantining record: {e}")

    @staticmethod
    def _calculate_content_hash(document_metadata: DocumentMetadata) -> str:
        """Calculate content hash from metadata."""
        import hashlib

        content = f"{document_metadata.title}{document_metadata.author}{document_metadata.file_type}"
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def _generate_mapping_summary(normalized_data: Dict) -> str:
        """Generate summary of mapping transformations."""
        return json.dumps({
            "fields_processed": len(normalized_data),
            "fields": list(normalized_data.keys()),
            "timestamp": datetime.utcnow().isoformat(),
        })

    @staticmethod
    async def check_idempotency(
        session: AsyncSession,
        file_id: UUID,
        content_hash: str,
    ) -> Optional[SilverMetadata]:
        """
        Check if mapping already exists (idempotency).

        Returns:
            Existing SilverMetadata if found, None otherwise
        """
        try:
            query = select(SilverMetadata).where(
                (SilverMetadata.file_id == file_id) &
                (SilverMetadata.content_hash == content_hash)
            )
            result = await session.execute(query)
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error checking idempotency: {e}")
            return None
