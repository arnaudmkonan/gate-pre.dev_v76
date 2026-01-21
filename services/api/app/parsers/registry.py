import logging
from typing import Dict, Optional

from app.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class ParserRegistry:
    """Registry for document parsers."""

    _parsers: Dict[str, BaseParser] = {}

    @classmethod
    def register(cls, file_extension: str, parser: BaseParser) -> None:
        """
        Register a parser for a file extension.

        Args:
            file_extension: File extension (e.g., "pdf", "txt", "md")
            parser: Parser instance
        """
        cls._parsers[file_extension.lower()] = parser
        logger.info(f"Parser registered for .{file_extension}")

    @classmethod
    def get_parser(cls, file_extension: str) -> Optional[BaseParser]:
        """Get parser for file extension."""
        return cls._parsers.get(file_extension.lower())

    @classmethod
    def supports(cls, file_extension: str) -> bool:
        """Check if parser exists for file extension."""
        return file_extension.lower() in cls._parsers

    @classmethod
    def get_supported_extensions(cls) -> list[str]:
        """Get list of supported file extensions."""
        return list(cls._parsers.keys())

    @classmethod
    def get_all_parsers(cls) -> Dict[str, BaseParser]:
        """Get all registered parsers."""
        return cls._parsers.copy()
