import logging
from typing import Dict

from app.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class TxtParser(BaseParser):
    """Parser for plain text files."""

    SUPPORTED_EXTENSIONS = ["txt"]

    async def extract_metadata(self, file_bytes: bytes, filename: str) -> Dict:
        """Extract metadata from text file."""
        try:
            # Detect encoding
            encoding = self._detect_encoding(file_bytes)
            text = file_bytes.decode(encoding, errors="replace")

            # Count lines and characters
            lines = text.split("\n")
            char_count = len(text)
            line_count = len(lines)

            # Extract preview (first 500 chars)
            preview = text[:500]

            return {
                "mime_type": "text/plain",
                "page_count": None,
                "language": None,
                "title": filename.replace(".txt", ""),
                "extracted_text_preview": preview,
                "metadata": {
                    "encoding": encoding,
                    "char_count": char_count,
                    "line_count": line_count,
                }
            }
        except Exception as e:
            logger.error(f"Error extracting TXT metadata: {e}")
            raise

    async def extract_text(self, file_bytes: bytes) -> str:
        """Extract full text from file."""
        encoding = self._detect_encoding(file_bytes)
        return file_bytes.decode(encoding, errors="replace")

    async def validate_format(self, file_bytes: bytes) -> bool:
        """Validate that file is text."""
        try:
            # Try to decode as text
            file_bytes.decode("utf-8")
            return True
        except (UnicodeDecodeError, AttributeError):
            return False

    @staticmethod
    def _detect_encoding(file_bytes: bytes) -> str:
        """Detect text encoding."""
        # Try common encodings
        for encoding in ["utf-8", "latin-1", "cp1252", "iso-8859-1"]:
            try:
                file_bytes.decode(encoding)
                return encoding
            except (UnicodeDecodeError, AttributeError):
                continue
        return "utf-8"  # Default fallback
