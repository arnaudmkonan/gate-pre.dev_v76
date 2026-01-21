"""Service for normalizing raw extractions to silver schema."""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update

from app.models import RawExtraction, SilverRecord, ExtractionStatus
from app.utils.content_sniffer import sniff_file_type

logger = logging.getLogger(__name__)


class NormalizerService:
    """Service for normalizing extracted content to silver schema."""

    # Mapping configuration (can be loaded from YAML in production)
    DEFAULT_MAPPING_RULES = {
        "title": {
            "sources": ["metadata.title", "text_preview_first_line"],
            "default": "Untitled Document",
        },
        "author": {
            "sources": ["metadata.author", "metadata.creator"],
            "default": None,
        },
        "language": {
            "sources": ["metadata.language", "detected_language"],
            "default": "en",
        },
        "content": {
            "sources": ["text"],
            "default": "",
        },
        "document_date": {
            "sources": ["metadata.modified", "metadata.created"],
            "default": None,
        },
    }

    @staticmethod
    async def normalize_extraction(
        session: AsyncSession,
        raw_extraction: RawExtraction,
        file_id: UUID,
        filename: str,
        file_type: str,
        file_size: int,
    ) -> Optional[SilverRecord]:
        """
        Normalize a raw extraction to silver schema.

        Args:
            session: Database session
            raw_extraction: RawExtraction object
            file_id: ID of the raw file
            filename: Original filename
            file_type: File type
            file_size: File size in bytes

        Returns:
            SilverRecord object or None if normalization fails
        """
        try:
            if raw_extraction.status not in [ExtractionStatus.SUCCESS, ExtractionStatus.PARTIAL]:
                logger.warning(f"Cannot normalize extraction with status: {raw_extraction.status}")
                return None

            # Extract mapping data from raw extraction
            mapping_data = {
                "metadata": raw_extraction.extracted_metadata or {},
                "text": raw_extraction.extracted_text or "",
                "text_preview_first_line": (raw_extraction.extracted_text or "").split("\n")[0] if raw_extraction.extracted_text else "",
            }

            # Apply mapping rules
            normalized = await NormalizerService._apply_mapping_rules(mapping_data)

            # Detect language if not present
            if not normalized.get("language") or normalized["language"] == "en":
                lang = await NormalizerService._detect_language(mapping_data.get("text", ""))
                if lang:
                    normalized["language"] = lang

            # Create silver record
            silver_record = SilverRecord(
                file_id=file_id,
                raw_content=raw_extraction.raw_content,
                title=normalized.get("title"),
                author=normalized.get("author"),
                document_date=NormalizerService._parse_iso_date(normalized.get("document_date")),
                extraction_date=datetime.utcnow(),
                file_type=file_type,
                size_bytes=file_size,
                language=normalized.get("language"),
                content=normalized.get("content"),
                record_metadata={
                    "filename": filename,
                    "mapping_version": "1.0",
                    "normalization_timestamp": datetime.utcnow().isoformat(),
                    "raw_extraction_id": str(raw_extraction.id),
                },
                processing_status="completed",
            )

            # Persist to database
            stmt = insert(SilverRecord).values(
                file_id=silver_record.file_id,
                raw_content=silver_record.raw_content,
                title=silver_record.title,
                author=silver_record.author,
                document_date=silver_record.document_date,
                extraction_date=silver_record.extraction_date,
                file_type=silver_record.file_type,
                size_bytes=silver_record.size_bytes,
                language=silver_record.language,
                content=silver_record.content,
                record_metadata=silver_record.record_metadata,
                processing_status=silver_record.processing_status,
            ).returning(SilverRecord)

            result = await session.execute(stmt)
            silver_record = result.scalar_one()
            await session.commit()

            logger.info(f"Normalized extraction {raw_extraction.id} to silver record {silver_record.id}")
            return silver_record

        except Exception as e:
            logger.error(f"Error normalizing extraction: {e}")
            return None

    @staticmethod
    async def _apply_mapping_rules(mapping_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply mapping rules to extract normalized fields.

        Args:
            mapping_data: Dict with extracted metadata and text

        Returns:
            Dict with normalized fields
        """
        normalized = {}

        for field, rules in NormalizerService.DEFAULT_MAPPING_RULES.items():
            value = None

            # Try each source in order
            for source in rules.get("sources", []):
                if "." in source:
                    # Nested access
                    parts = source.split(".")
                    current = mapping_data
                    for part in parts:
                        if isinstance(current, dict):
                            current = current.get(part)
                        else:
                            break
                    value = current if isinstance(current, (str, type(None))) else None
                else:
                    # Direct access
                    value = mapping_data.get(source)

                if value:
                    break

            # Use default if no value found
            if not value:
                value = rules.get("default")

            normalized[field] = value

        return normalized

    @staticmethod
    async def _detect_language(text: str) -> Optional[str]:
        """
        Detect language from text.

        Args:
            text: Text to analyze

        Returns:
            ISO 639-1 language code or None
        """
        if not text or len(text) < 10:
            return "en"  # Default to English

        try:
            # Try using textblob or langdetect if available
            try:
                from textblob import TextBlob
                blob = TextBlob(text[:500])
                lang_code = str(blob.detect_language())
                return lang_code if lang_code else "en"
            except Exception:
                pass

            try:
                from langdetect import detect
                lang_code = detect(text[:500])
                return lang_code if lang_code else "en"
            except Exception:
                pass

            return "en"  # Fallback to English

        except Exception as e:
            logger.warning(f"Error detecting language: {e}")
            return "en"

    @staticmethod
    def _parse_iso_date(date_value: Any) -> Optional[datetime]:
        """
        Parse ISO 8601 date string.

        Args:
            date_value: String or datetime object

        Returns:
            datetime object or None
        """
        if isinstance(date_value, datetime):
            return date_value

        if isinstance(date_value, str):
            try:
                return datetime.fromisoformat(date_value.replace("Z", "+00:00"))
            except Exception:
                try:
                    return datetime.strptime(date_value, "%Y-%m-%d")
                except Exception:
                    logger.warning(f"Could not parse date: {date_value}")
                    return None

        return None

    @staticmethod
    async def get_normalization_status(
        session: AsyncSession,
        file_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get normalization status for a file.

        Args:
            session: Database session
            file_id: ID of the file

        Returns:
            Status dict
        """
        # Check for raw extraction
        stmt = select(RawExtraction).where(RawExtraction.file_id == file_id)
        result = await session.execute(stmt)
        raw_extraction = result.scalar_one_or_none()

        # Check for silver record
        stmt = select(SilverRecord).where(SilverRecord.file_id == file_id)
        result = await session.execute(stmt)
        silver_record = result.scalar_one_or_none()

        return {
            "file_id": str(file_id),
            "raw_extraction_status": raw_extraction.status if raw_extraction else None,
            "silver_record_status": silver_record.processing_status if silver_record else None,
            "raw_extraction_id": str(raw_extraction.id) if raw_extraction else None,
            "silver_record_id": str(silver_record.id) if silver_record else None,
        }
