from abc import ABC, abstractmethod
from typing import Dict, Optional


class BaseParser(ABC):
    """Base class for document parsers."""

    SUPPORTED_EXTENSIONS: list[str] = []

    @abstractmethod
    async def extract_metadata(self, file_bytes: bytes, filename: str) -> Dict:
        """
        Extract metadata from file.

        Returns:
            Dict with keys: mime_type, page_count, language, title, extracted_text_preview
        """
        pass

    @abstractmethod
    async def extract_text(self, file_bytes: bytes) -> str:
        """Extract full text content from file."""
        pass

    @abstractmethod
    async def validate_format(self, file_bytes: bytes) -> bool:
        """Validate that file is in expected format."""
        pass
