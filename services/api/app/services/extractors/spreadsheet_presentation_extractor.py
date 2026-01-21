"""Extractor for XLSX, XLS, PPTX, and CSV files."""

import logging
import csv
from io import BytesIO, StringIO
from typing import Dict, Any, List

from app.services.extractors.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class SpreadsheetExtractor(BaseExtractor):
    """Extractor for XLSX and XLS files."""

    SUPPORTED_EXTENSIONS = ["xlsx", "xls", "csv"]

    async def extract_text(self, file_bytes: bytes) -> str:
        """Extract text from spreadsheet."""
        try:
            if file_bytes[:4] == b'PK\x03\x04':  # XLSX (ZIP-based)
                return await self._extract_xlsx_text(file_bytes)
            elif file_bytes[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':  # XLS (OLE)
                return await self._extract_xls_text(file_bytes)
            else:
                # Try CSV
                return await self._extract_csv_text(file_bytes)
        except Exception as e:
            logger.error(f"Error extracting spreadsheet: {e}")
            return ""

    async def _extract_xlsx_text(self, file_bytes: bytes) -> str:
        """Extract text from XLSX file."""
        try:
            from openpyxl import load_workbook

            wb = load_workbook(BytesIO(file_bytes))
            text_parts = []

            for sheet in wb.sheetnames:
                ws = wb[sheet]
                text_parts.append(f"[Sheet: {sheet}]")

                for row in ws.iter_rows():
                    row_text = []
                    for cell in row:
                        if cell.value:
                            row_text.append(str(cell.value))
                    if row_text:
                        text_parts.append(" | ".join(row_text))

            return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"Error extracting XLSX: {e}")
            return ""

    async def _extract_xls_text(self, file_bytes: bytes) -> str:
        """Extract text from XLS file."""
        try:
            import xlrd

            workbook = xlrd.open_workbook(file_contents=file_bytes)
            text_parts = []

            for sheet_idx, sheet in enumerate(workbook.sheets()):
                text_parts.append(f"[Sheet: {sheet.name}]")

                for row_idx in range(sheet.nrows):
                    row_text = []
                    for col_idx in range(sheet.ncols):
                        cell = sheet.cell(row_idx, col_idx)
                        if cell.value:
                            row_text.append(str(cell.value))
                    if row_text:
                        text_parts.append(" | ".join(row_text))

            return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"Error extracting XLS: {e}")
            return ""

    async def _extract_csv_text(self, file_bytes: bytes) -> str:
        """Extract text from CSV file."""
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            return text
        except Exception as e:
            logger.error(f"Error extracting CSV: {e}")
            return ""

    async def validate_format(self, file_bytes: bytes) -> bool:
        """Validate that file is a valid spreadsheet."""
        try:
            # Check for XLSX (ZIP magic)
            if file_bytes[:4] == b'PK\x03\x04':
                from openpyxl import load_workbook
                load_workbook(BytesIO(file_bytes))
                return True
            # Check for XLS (OLE magic)
            elif file_bytes[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
                import xlrd
                xlrd.open_workbook(file_contents=file_bytes)
                return True
            # Try CSV
            else:
                text = file_bytes.decode("utf-8", errors="replace")
                reader = csv.reader(StringIO(text))
                next(reader)  # Try to read first row
                return True
        except Exception:
            return False

    async def extract_tables(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        """Extract table data from spreadsheet."""
        try:
            if file_bytes[:4] == b'PK\x03\x04':
                return await self._extract_xlsx_tables(file_bytes)
            elif file_bytes[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
                return await self._extract_xls_tables(file_bytes)
            else:
                return await self._extract_csv_tables(file_bytes)
        except Exception as e:
            logger.error(f"Error extracting spreadsheet tables: {e}")
            return []

    async def _extract_xlsx_tables(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        """Extract tables from XLSX."""
        try:
            from openpyxl import load_workbook

            wb = load_workbook(BytesIO(file_bytes))
            tables = []

            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                table = {
                    "sheet": sheet_name,
                    "rows": [],
                }

                for row in ws.iter_rows():
                    row_data = []
                    for cell in row:
                        row_data.append(str(cell.value) if cell.value is not None else "")
                    table["rows"].append(row_data)

                tables.append(table)

            return tables
        except Exception as e:
            logger.error(f"Error extracting XLSX tables: {e}")
            return []

    async def _extract_xls_tables(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        """Extract tables from XLS."""
        try:
            import xlrd

            workbook = xlrd.open_workbook(file_contents=file_bytes)
            tables = []

            for sheet_idx, sheet in enumerate(workbook.sheets()):
                table = {
                    "sheet": sheet.name,
                    "rows": [],
                }

                for row_idx in range(sheet.nrows):
                    row_data = []
                    for col_idx in range(sheet.ncols):
                        cell = sheet.cell(row_idx, col_idx)
                        row_data.append(str(cell.value) if cell.value else "")
                    table["rows"].append(row_data)

                tables.append(table)

            return tables
        except Exception as e:
            logger.error(f"Error extracting XLS tables: {e}")
            return []

    async def _extract_csv_tables(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        """Extract tables from CSV."""
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            reader = csv.reader(StringIO(text))

            table = {
                "sheet": "data",
                "rows": [row for row in reader],
            }

            return [table] if table["rows"] else []
        except Exception as e:
            logger.error(f"Error extracting CSV tables: {e}")
            return []


class PresentationExtractor(BaseExtractor):
    """Extractor for PPTX files."""

    SUPPORTED_EXTENSIONS = ["pptx", "ppt"]

    async def extract_text(self, file_bytes: bytes) -> str:
        """Extract text from presentation."""
        try:
            from pptx import Presentation

            prs = Presentation(BytesIO(file_bytes))
            text_parts = []

            for slide_idx, slide in enumerate(prs.slides):
                text_parts.append(f"[Slide {slide_idx + 1}]")

                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        text_parts.append(shape.text)

            return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"Error extracting PPTX: {e}")
            return ""

    async def validate_format(self, file_bytes: bytes) -> bool:
        """Validate that file is PPTX."""
        try:
            from pptx import Presentation

            Presentation(BytesIO(file_bytes))
            return True
        except Exception:
            return False

    async def extract_metadata(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Extract metadata from PPTX."""
        try:
            from pptx import Presentation

            prs = Presentation(BytesIO(file_bytes))
            props = prs.core_properties

            return {
                "filename": filename,
                "file_size": len(file_bytes),
                "title": props.title or None,
                "author": props.author or None,
                "subject": props.subject or None,
                "created": props.created.isoformat() if props.created else None,
                "modified": props.modified.isoformat() if props.modified else None,
                "slide_count": len(prs.slides),
            }
        except Exception as e:
            logger.error(f"Error extracting PPTX metadata: {e}")
            return {
                "filename": filename,
                "file_size": len(file_bytes),
            }
