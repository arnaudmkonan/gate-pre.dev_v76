import logging
from typing import Dict

logger = logging.getLogger(__name__)


class PdfParser:
    """Parser for PDF files."""

    SUPPORTED_EXTENSIONS = ["pdf"]

    async def extract_metadata(self, file_bytes: bytes, filename: str) -> Dict:
        """Extract metadata from PDF file."""
        try:
            try:
                from PyPDF2 import PdfReader
            except ImportError:
                logger.warning("PyPDF2 not installed, returning basic metadata")
                return {
                    "mime_type": "application/pdf",
                    "page_count": None,
                    "language": None,
                    "title": filename.replace(".pdf", ""),
                    "extracted_text_preview": None,
                    "metadata": {"note": "PyPDF2 not installed"}
                }

            from io import BytesIO
            pdf_file = BytesIO(file_bytes)
            reader = PdfReader(pdf_file)

            # Get page count
            page_count = len(reader.pages)

            # Try to get title from metadata
            title = filename.replace(".pdf", "")
            if reader.metadata and reader.metadata.get("/Title"):
                title = reader.metadata.get("/Title", title)

            # Extract text preview from first page
            text_preview = None
            if page_count > 0:
                first_page = reader.pages[0]
                text_preview = first_page.extract_text()[:500]

            return {
                "mime_type": "application/pdf",
                "page_count": page_count,
                "language": None,
                "title": title,
                "extracted_text_preview": text_preview,
                "metadata": {
                    "author": reader.metadata.get("/Author") if reader.metadata else None,
                    "creator": reader.metadata.get("/Creator") if reader.metadata else None,
                }
            }
        except Exception as e:
            logger.error(f"Error extracting PDF metadata: {e}")
            raise

    async def extract_text(self, file_bytes: bytes) -> str:
        """Extract full text from PDF file."""
        try:
            from PyPDF2 import PdfReader
            from io import BytesIO

            pdf_file = BytesIO(file_bytes)
            reader = PdfReader(pdf_file)

            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"

            return text
        except ImportError:
            logger.warning("PyPDF2 not installed, cannot extract text")
            return ""
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            raise

    async def validate_format(self, file_bytes: bytes) -> bool:
        """Validate that file is valid PDF."""
        try:
            # Check for PDF header
            return file_bytes.startswith(b"%PDF")
        except (TypeError, AttributeError):
            return False
