"""Service for generating and managing document metadata."""

import logging
import hashlib
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update

from app.models import RawExtraction, DocumentMetadataVersion, MetadataStatus, RawFile

logger = logging.getLogger(__name__)


class MetadataGeneratorService:
    """Service for generating and versioning metadata."""

    MIN_CONFIDENCE_THRESHOLD = 0.5

    @staticmethod
    async def generate_metadata(
        session: AsyncSession,
        raw_extraction: RawExtraction,
        raw_file: RawFile,
    ) -> Optional[DocumentMetadataVersion]:
        """
        Generate metadata from a raw extraction.

        Args:
            session: Database session
            raw_extraction: RawExtraction object
            raw_file: RawFile object

        Returns:
            DocumentMetadataVersion object or None
        """
        try:
            # Get version number
            version = await MetadataGeneratorService._get_next_version(session, raw_file.id)

            # Extract metadata fields
            extracted_metadata = raw_extraction.extracted_metadata or {}
            extracted_text = raw_extraction.extracted_text or ""

            # Parse dates
            created_date = MetadataGeneratorService._parse_date(
                extracted_metadata.get("created") or extracted_metadata.get("created_at_doc")
            )
            modified_date = MetadataGeneratorService._parse_date(
                extracted_metadata.get("modified") or extracted_metadata.get("modified_at_doc")
            )

            # Detect language
            language = extracted_metadata.get("language") or "en"

            # Extract entities
            entities, low_confidence_entities = await MetadataGeneratorService._extract_entities(
                extracted_text
            )

            # Compute checksum
            checksum = hashlib.sha256(extracted_text.encode()).hexdigest()

            # Create metadata record
            metadata_version = DocumentMetadataVersion(
                file_id=raw_file.id,
                version=version,
                status=MetadataStatus.ACTIVE,
                title=extracted_metadata.get("title") or raw_file.filename,
                author=extracted_metadata.get("author"),
                created_at_doc=created_date,
                modified_at_doc=modified_date,
                language=language,
                file_type=raw_file.file_type,
                entities=entities,
                low_confidence_entities=low_confidence_entities,
                checksum=checksum,
                file_size_bytes=raw_file.file_size,
                extraction_timestamp=datetime.utcnow(),
                metadata_generated_at=datetime.utcnow(),
                lineage={
                    "file_id": str(raw_file.id),
                    "extraction_id": str(raw_extraction.id),
                },
            )

            # Supersede previous active version
            await MetadataGeneratorService._supersede_previous_versions(session, raw_file.id)

            # Persist to database
            stmt = insert(DocumentMetadataVersion).values(
                file_id=metadata_version.file_id,
                version=metadata_version.version,
                status=metadata_version.status.value,
                title=metadata_version.title,
                author=metadata_version.author,
                created_at_doc=metadata_version.created_at_doc,
                modified_at_doc=metadata_version.modified_at_doc,
                language=metadata_version.language,
                file_type=metadata_version.file_type,
                entities=metadata_version.entities,
                low_confidence_entities=metadata_version.low_confidence_entities,
                checksum=metadata_version.checksum,
                file_size_bytes=metadata_version.file_size_bytes,
                extraction_timestamp=metadata_version.extraction_timestamp,
                metadata_generated_at=metadata_version.metadata_generated_at,
                lineage=metadata_version.lineage,
            ).returning(DocumentMetadataVersion)

            result = await session.execute(stmt)
            metadata_version = result.scalar_one()
            await session.commit()

            logger.info(
                f"Generated metadata version {version} for file {raw_file.id}"
            )
            return metadata_version

        except Exception as e:
            logger.error(f"Error generating metadata: {e}")
            return None

    @staticmethod
    async def _get_next_version(session: AsyncSession, file_id: UUID) -> int:
        """Get next version number for metadata."""
        stmt = select(DocumentMetadataVersion).where(
            DocumentMetadataVersion.file_id == file_id
        ).order_by(DocumentMetadataVersion.version.desc()).limit(1)

        result = await session.execute(stmt)
        latest = result.scalar_one_or_none()

        return (latest.version + 1) if latest else 1

    @staticmethod
    async def _supersede_previous_versions(session: AsyncSession, file_id: UUID) -> None:
        """Mark all previous versions as superseded."""
        stmt = (
            update(DocumentMetadataVersion)
            .where(
                (DocumentMetadataVersion.file_id == file_id) &
                (DocumentMetadataVersion.status == MetadataStatus.ACTIVE)
            )
            .values(status=MetadataStatus.SUPERSEDED)
        )
        await session.execute(stmt)
        await session.commit()

    @staticmethod
    def _parse_date(date_value: Any) -> Optional[datetime]:
        """
        Parse various date formats to ISO 8601.

        Args:
            date_value: String or datetime object

        Returns:
            datetime object in UTC or None
        """
        if date_value is None:
            return None

        if isinstance(date_value, datetime):
            return date_value

        if isinstance(date_value, str):
            try:
                # Try ISO 8601 format
                return datetime.fromisoformat(date_value.replace("Z", "+00:00"))
            except Exception:
                try:
                    # Try common date formats
                    for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y"]:
                        try:
                            return datetime.strptime(date_value, fmt)
                        except Exception:
                            continue
                except Exception:
                    pass

            logger.warning(f"Could not parse date: {date_value}")
            return None

        return None

    @staticmethod
    async def _extract_entities(text: str) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract named entities from text.

        Args:
            text: Text to analyze

        Returns:
            Tuple of (high_confidence_entities, low_confidence_entities)
        """
        high_confidence = []
        low_confidence = []

        try:
            # Try using spaCy if available
            try:
                import spacy

                nlp = spacy.load("en_core_web_sm")
                doc = nlp(text[:5000])  # Limit to first 5000 chars for performance

                entity_counts = {}
                for ent in doc.ents:
                    key = (ent.text.lower(), ent.label_)
                    entity_counts[key] = entity_counts.get(key, 0) + 1

                # Score entities by frequency (simple confidence metric)
                for (text, label), count in entity_counts.items():
                    confidence = min(count / 5.0, 1.0)  # Normalize to 0-1
                    entity = {
                        "name": text,
                        "type": label,
                        "confidence": confidence,
                    }

                    if confidence >= MetadataGeneratorService.MIN_CONFIDENCE_THRESHOLD:
                        high_confidence.append(entity)
                    else:
                        low_confidence.append(entity)

                # Return top 5 for high confidence
                high_confidence.sort(key=lambda x: x["confidence"], reverse=True)
                return high_confidence[:5], low_confidence

            except ImportError:
                logger.warning("spaCy not available, skipping entity extraction")
                return [], []

        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return [], []

    @staticmethod
    async def get_current_metadata(
        session: AsyncSession,
        file_id: UUID,
    ) -> Optional[DocumentMetadataVersion]:
        """
        Get the current active metadata version for a file.

        Args:
            session: Database session
            file_id: File ID

        Returns:
            DocumentMetadataVersion or None
        """
        stmt = (
            select(DocumentMetadataVersion)
            .where(
                (DocumentMetadataVersion.file_id == file_id) &
                (DocumentMetadataVersion.status == MetadataStatus.ACTIVE)
            )
            .order_by(DocumentMetadataVersion.version.desc())
            .limit(1)
        )

        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_metadata_history(
        session: AsyncSession,
        file_id: UUID,
    ) -> List[DocumentMetadataVersion]:
        """
        Get all metadata versions for a file.

        Args:
            session: Database session
            file_id: File ID

        Returns:
            List of DocumentMetadataVersion objects
        """
        stmt = (
            select(DocumentMetadataVersion)
            .where(DocumentMetadataVersion.file_id == file_id)
            .order_by(DocumentMetadataVersion.version.desc())
        )

        result = await session.execute(stmt)
        return result.scalars().all()
