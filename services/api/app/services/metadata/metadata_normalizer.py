import logging
from datetime import datetime
from dateutil import parser as date_parser

from app.schemas.normalized_metadata import NormalizedMetadata

logger = logging.getLogger(__name__)


class MetadataNormalizer:
    """Transform raw metadata to normalized schema."""

    # Mapping of common field names to normalized fields
    TITLE_ALIASES = ["title", "name", "subject", "heading", "h1"]
    AUTHOR_ALIASES = ["author", "creator", "owner", "contributor", "user"]
    DATE_ALIASES = ["date", "created_at", "modified_at", "updated_at", "publication_date"]
    TYPE_ALIASES = ["document_type", "type", "kind", "category", "doctype"]

    @staticmethod
    def transform(raw: dict) -> NormalizedMetadata:
        """
        Transform raw metadata dict to normalized NormalizedMetadata schema.

        Args:
            raw: Raw metadata dictionary from extraction

        Returns:
            NormalizedMetadata object compatible with SilverMetadata model

        Raises:
            ValueError: If required fields are missing
        """
        try:
            # Extract file_id (required)
            file_id = raw.get("file_id")
            if not file_id:
                raise ValueError("Missing required field: file_id")

            # Extract and normalize title
            title = MetadataNormalizer._extract_field(raw, MetadataNormalizer.TITLE_ALIASES)

            # Extract and normalize author
            author = MetadataNormalizer._extract_field(raw, MetadataNormalizer.AUTHOR_ALIASES)

            # Extract and normalize dates
            dates = MetadataNormalizer._extract_dates(raw)

            # Extract and normalize document type
            document_type = MetadataNormalizer._extract_field(raw, MetadataNormalizer.TYPE_ALIASES)

            # Extract custom metadata (all fields not in the standard set)
            standard_fields = {"file_id", "title", "author", "date", "document_type", "metadata"}
            custom_metadata = {
                k: v for k, v in raw.items()
                if k not in standard_fields and not any(
                    k in aliases for aliases in [
                        MetadataNormalizer.TITLE_ALIASES,
                        MetadataNormalizer.AUTHOR_ALIASES,
                        MetadataNormalizer.DATE_ALIASES,
                        MetadataNormalizer.TYPE_ALIASES,
                    ]
                )
            }

            # Preserve source metadata for traceability
            source_metadata = {
                "original_keys": list(raw.keys()),
                "extraction_timestamp": datetime.utcnow().isoformat(),
            }

            normalized = NormalizedMetadata(
                file_id=file_id,
                title=title,
                author=author,
                dates=dates,
                document_type=document_type,
                custom_metadata=custom_metadata or None,
                source_metadata=source_metadata,
                mapping_version="1.0.0",
            )

            logger.info(f"Normalized metadata for file {file_id}")
            return normalized

        except Exception as e:
            logger.error(f"Failed to normalize metadata: {e}")
            raise

    @staticmethod
    def _extract_field(raw: dict, aliases: list) -> str | None:
        """
        Extract a field from raw metadata using alias list.

        Args:
            raw: Raw metadata dict
            aliases: List of possible field names (case-insensitive)

        Returns:
            Field value or None if not found
        """
        raw_lower = {k.lower(): v for k, v in raw.items()}

        for alias in aliases:
            if alias.lower() in raw_lower:
                value = raw_lower[alias.lower()]
                if value and isinstance(value, str):
                    return value.strip() or None
                elif value:
                    return str(value)

        return None

    @staticmethod
    def _extract_dates(raw: dict) -> list[datetime] | None:
        """
        Extract and normalize dates from raw metadata.

        Args:
            raw: Raw metadata dict

        Returns:
            List of datetime objects normalized to ISO 8601, or None
        """
        dates = []
        raw_lower = {k.lower(): v for k, v in raw.items()}

        # Check all date aliases
        for alias in MetadataNormalizer.DATE_ALIASES:
            if alias.lower() in raw_lower:
                date_value = raw_lower[alias.lower()]
                try:
                    if isinstance(date_value, str):
                        dt = date_parser.isoparse(date_value)
                        if dt not in dates:
                            dates.append(dt)
                    elif isinstance(date_value, datetime):
                        if date_value not in dates:
                            dates.append(date_value)
                except Exception as e:
                    logger.warning(f"Failed to parse date {date_value}: {e}")

        return dates if dates else None

    @staticmethod
    def validate_field_types(normalized: NormalizedMetadata) -> bool:
        """
        Validate that all fields match expected types.

        Args:
            normalized: Normalized metadata

        Returns:
            True if valid, raises ValueError otherwise
        """
        errors = []

        if normalized.title is not None and not isinstance(normalized.title, str):
            errors.append("title must be a string")

        if normalized.author is not None and not isinstance(normalized.author, str):
            errors.append("author must be a string")

        if normalized.document_type is not None and not isinstance(normalized.document_type, str):
            errors.append("document_type must be a string")

        if normalized.dates is not None and not isinstance(normalized.dates, list):
            errors.append("dates must be a list")

        if normalized.custom_metadata is not None and not isinstance(normalized.custom_metadata, dict):
            errors.append("custom_metadata must be a dict")

        if errors:
            raise ValueError(f"Field type validation failed: {'; '.join(errors)}")

        return True

    @staticmethod
    def handle_missing_optional_fields(normalized: NormalizedMetadata) -> NormalizedMetadata:
        """
        Handle missing optional fields by populating defaults.

        Args:
            normalized: Normalized metadata

        Returns:
            Updated NormalizedMetadata with defaults filled in
        """
        # Set empty custom_metadata if not present
        if normalized.custom_metadata is None:
            normalized.custom_metadata = {}

        # Ensure dates list is always a list (empty if no dates)
        if normalized.dates is None:
            normalized.dates = []

        return normalized
