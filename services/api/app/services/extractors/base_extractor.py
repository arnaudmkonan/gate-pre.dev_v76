"""Base extractor interface for standardized extraction across file formats."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class ExtractedContent:
    """Standardized extracted content from a file."""

    text: str = ""  # Main text content
    tables: List[Dict[str, Any]] = field(default_factory=list)  # Extracted tables
    metadata: Dict[str, Any] = field(default_factory=dict)  # File metadata
    embedded_objects: List[Dict[str, Any]] = field(default_factory=list)  # Images, embedded files, etc.
    sections: List[Dict[str, Any]] = field(default_factory=list)  # Hierarchical sections
    errors: List[str] = field(default_factory=list)  # Errors during extraction


class BaseExtractor(ABC):
    """Abstract base class for document extractors."""

    SUPPORTED_EXTENSIONS: List[str] = []

    async def extract(self, file_bytes: bytes, filename: str) -> ExtractedContent:
        """
        Extract content from file.

        Args:
            file_bytes: Raw file bytes
            filename: Original filename

        Returns:
            ExtractedContent object
        """
        try:
            # Validate format
            if not await self.validate_format(file_bytes):
                return ExtractedContent(
                    errors=[f"Invalid file format: {filename}"]
                )

            # Extract text
            text = await self.extract_text(file_bytes)

            # Extract tables
            tables = await self.extract_tables(file_bytes)

            # Extract metadata
            metadata = await self.extract_metadata(file_bytes, filename)

            # Extract embedded objects
            embedded_objects = await self.extract_embedded_objects(file_bytes)

            return ExtractedContent(
                text=text,
                tables=tables,
                metadata=metadata,
                embedded_objects=embedded_objects,
            )

        except Exception as e:
            logger.error(f"Error extracting from {filename}: {e}")
            return ExtractedContent(errors=[str(e)])

    @abstractmethod
    async def extract_text(self, file_bytes: bytes) -> str:
        """Extract main text content from file."""
        pass

    @abstractmethod
    async def validate_format(self, file_bytes: bytes) -> bool:
        """Validate that file is in expected format."""
        pass

    async def extract_tables(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Extract table data from file.
        Override in subclasses that support tables.
        """
        return []

    async def extract_metadata(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Extract metadata from file.
        Override in subclasses that support metadata extraction.
        """
        return {
            "filename": filename,
            "file_size": len(file_bytes),
        }

    async def extract_embedded_objects(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Extract embedded objects (images, files, etc.).
        Override in subclasses that support embedded objects.
        """
        return []
