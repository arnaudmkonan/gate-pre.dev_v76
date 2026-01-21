"""Extractor for TXT and DOCX files."""

import logging
from typing import Dict, Any, List

from app.services.extractors.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class TextExtractor(BaseExtractor):
    """Extractor for plain text files."""

    SUPPORTED_EXTENSIONS = ["txt"]

    async def extract_text(self, file_bytes: bytes) -> str:
        """Extract text from plain text file."""
        try:
            # Try UTF-8 first
            return file_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            logger.error(f"Error decoding text file: {e}")
            # Try with latin-1 fallback
            try:
                return file_bytes.decode("latin-1", errors="replace")
            except Exception:
                return ""

    async def validate_format(self, file_bytes: bytes) -> bool:
        """Validate that file is text."""
        try:
            file_bytes.decode("utf-8")
            return True
        except UnicodeDecodeError:
            try:
                file_bytes.decode("latin-1")
                return True
            except Exception:
                return False


class DocxExtractor(BaseExtractor):
    """Extractor for DOCX files."""

    SUPPORTED_EXTENSIONS = ["docx", "doc"]

    async def extract_text(self, file_bytes: bytes) -> str:
        """Extract text from DOCX file."""
        try:
            from docx import Document
            from io import BytesIO

            doc = Document(BytesIO(file_bytes))
            text_parts = []

            # Extract from paragraphs
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text)

            # Extract from tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        cell_text = cell.text.strip()
                        if cell_text:
                            row_text.append(cell_text)
                    if row_text:
                        text_parts.append(" | ".join(row_text))

            return "\n".join(text_parts)

        except Exception as e:
            logger.error(f"Error extracting DOCX: {e}")
            return ""

    async def validate_format(self, file_bytes: bytes) -> bool:
        """Validate that file is DOCX."""
        try:
            from docx import Document
            from io import BytesIO

            Document(BytesIO(file_bytes))
            return True
        except Exception:
            return False

    async def extract_tables(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        """Extract tables from DOCX."""
        try:
            from docx import Document
            from io import BytesIO

            doc = Document(BytesIO(file_bytes))
            tables = []

            for table_idx, table in enumerate(doc.tables):
                table_data = {
                    "index": table_idx,
                    "rows": [],
                }

                for row_idx, row in enumerate(table.rows):
                    row_data = []
                    for cell in row.cells:
                        row_data.append(cell.text.strip())
                    table_data["rows"].append(row_data)

                if table_data["rows"]:
                    tables.append(table_data)

            return tables

        except Exception as e:
            logger.error(f"Error extracting DOCX tables: {e}")
            return []

    async def extract_metadata(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Extract metadata from DOCX."""
        try:
            from docx import Document
            from io import BytesIO

            doc = Document(BytesIO(file_bytes))
            props = doc.core_properties

            return {
                "filename": filename,
                "file_size": len(file_bytes),
                "title": props.title or None,
                "author": props.author or None,
                "subject": props.subject or None,
                "created": props.created.isoformat() if props.created else None,
                "modified": props.modified.isoformat() if props.modified else None,
                "paragraph_count": len(doc.paragraphs),
                "table_count": len(doc.tables),
            }

        except Exception as e:
            logger.error(f"Error extracting DOCX metadata: {e}")
            return {
                "filename": filename,
                "file_size": len(file_bytes),
            }
