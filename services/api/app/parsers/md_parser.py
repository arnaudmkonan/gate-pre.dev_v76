import logging
import re
from typing import Dict

from app.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class MdParser(BaseParser):
    """Parser for Markdown files."""

    SUPPORTED_EXTENSIONS = ["md", "markdown"]

    async def extract_metadata(self, file_bytes: bytes, filename: str) -> Dict:
        """Extract metadata from Markdown file."""
        try:
            text = file_bytes.decode("utf-8", errors="replace")

            # Extract title from first H1 heading
            title_match = re.search(r"^# (.+)$", text, re.MULTILINE)
            title = title_match.group(1) if title_match else filename.replace(".md", "")

            # Count code blocks
            code_blocks = len(re.findall(r"```", text))

            # Extract preview (first 500 chars)
            preview = text[:500]

            # Check for front matter
            has_frontmatter = text.startswith("---")

            return {
                "mime_type": "text/markdown",
                "page_count": None,
                "language": None,
                "title": title,
                "extracted_text_preview": preview,
                "metadata": {
                    "code_blocks": code_blocks,
                    "has_frontmatter": has_frontmatter,
                    "char_count": len(text),
                }
            }
        except Exception as e:
            logger.error(f"Error extracting Markdown metadata: {e}")
            raise

    async def extract_text(self, file_bytes: bytes) -> str:
        """Extract full text from Markdown file."""
        return file_bytes.decode("utf-8", errors="replace")

    async def validate_format(self, file_bytes: bytes) -> bool:
        """Validate that file is valid Markdown."""
        try:
            file_bytes.decode("utf-8")
            return True
        except (UnicodeDecodeError, AttributeError):
            return False
