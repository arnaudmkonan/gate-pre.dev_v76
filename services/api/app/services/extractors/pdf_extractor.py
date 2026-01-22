"""
PDF Document Extractor.

Handles extraction from both native PDFs and scanned (image-based) PDFs.
Uses PyMuPDF (fitz) for native PDF text extraction and Tesseract OCR
for scanned documents.
"""

import io
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from app.services.extractors.base_extractor import BaseExtractor, ExtractedContent

logger = logging.getLogger(__name__)


@dataclass
class PDFPageInfo:
    """Information about a single PDF page."""
    page_number: int
    text: str
    is_scanned: bool
    has_images: bool
    word_count: int


class PDFExtractor(BaseExtractor):
    """
    Extractor for PDF documents.
    
    Handles:
    - Native PDFs with selectable text
    - Scanned PDFs (image-based) using OCR
    - Mixed documents (some pages native, some scanned)
    - Table extraction from PDFs
    - Metadata extraction (title, author, dates)
    """
    
    SUPPORTED_EXTENSIONS = ["pdf"]
    
    # Threshold for determining if a page is scanned
    MIN_TEXT_CHARS_FOR_NATIVE = 50
    
    def __init__(self, enable_ocr: bool = True, ocr_language: str = "eng"):
        """
        Initialize PDF extractor.
        
        Args:
            enable_ocr: Whether to use OCR for scanned pages
            ocr_language: Tesseract language code(s)
        """
        self.enable_ocr = enable_ocr
        self.ocr_language = ocr_language
    
    async def extract_text(self, file_bytes: bytes) -> str:
        """Extract text from PDF, using OCR for scanned pages."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF not installed. Run: pip install pymupdf")
            return ""
        
        all_text = []
        
        try:
            # Open PDF from bytes
            pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                page_text = page.get_text("text")
                
                # Check if page is scanned (little to no text)
                if len(page_text.strip()) < self.MIN_TEXT_CHARS_FOR_NATIVE:
                    if self.enable_ocr:
                        # Try OCR
                        ocr_text = await self._ocr_page(page)
                        if ocr_text:
                            all_text.append(f"[Page {page_num + 1}]\n{ocr_text}")
                            continue
                
                if page_text.strip():
                    all_text.append(f"[Page {page_num + 1}]\n{page_text}")
            
            pdf_document.close()
            
            return "\n\n".join(all_text)
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return ""
    
    async def _ocr_page(self, page) -> str:
        """Perform OCR on a PDF page."""
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            logger.warning("pytesseract or Pillow not installed for OCR")
            return ""
        
        try:
            # Render page to image
            pix = page.get_pixmap(matrix=page.get_matrix() * 2)  # 2x scale for better OCR
            img_bytes = pix.tobytes("png")
            
            # Convert to PIL Image
            image = Image.open(io.BytesIO(img_bytes))
            
            # Perform OCR
            text = pytesseract.image_to_string(image, lang=self.ocr_language)
            
            return text.strip()
            
        except Exception as e:
            logger.warning(f"OCR failed for page: {e}")
            return ""
    
    async def validate_format(self, file_bytes: bytes) -> bool:
        """Validate that file is a valid PDF."""
        # Check PDF magic bytes
        return file_bytes[:4] == b'%PDF'
    
    async def extract_tables(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Extract tables from PDF.
        
        Uses PyMuPDF's table detection capabilities.
        """
        try:
            import fitz
        except ImportError:
            return []
        
        tables = []
        
        try:
            pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                
                # Try to find tables using text blocks analysis
                page_tables = self._detect_tables_from_blocks(page)
                
                for idx, table_data in enumerate(page_tables):
                    tables.append({
                        "page": page_num + 1,
                        "table_index": idx,
                        "headers": table_data.get("headers", []),
                        "rows": table_data.get("rows", []),
                        "row_count": len(table_data.get("rows", [])),
                    })
            
            pdf_document.close()
            
        except Exception as e:
            logger.error(f"Error extracting tables from PDF: {e}")
        
        return tables
    
    def _detect_tables_from_blocks(self, page) -> List[Dict[str, Any]]:
        """
        Detect tables from text blocks on a page.
        
        Simple heuristic: Look for aligned text blocks that form grid patterns.
        """
        tables = []
        
        try:
            # Get text blocks
            blocks = page.get_text("blocks")
            
            # Group blocks by similar y-coordinates (rows)
            rows = {}
            for block in blocks:
                if len(block) >= 5 and block[4]:  # Text blocks have content at index 4
                    y_coord = round(block[1], 0)  # Round y to group rows
                    if y_coord not in rows:
                        rows[y_coord] = []
                    rows[y_coord].append({
                        "x": block[0],
                        "text": block[4].strip(),
                    })
            
            # Sort rows by y-coordinate
            sorted_rows = sorted(rows.items(), key=lambda x: x[0])
            
            # Look for table-like structures (multiple items per row, similar x positions)
            potential_table_rows = []
            for y, items in sorted_rows:
                if len(items) >= 2:  # At least 2 columns
                    sorted_items = sorted(items, key=lambda x: x["x"])
                    potential_table_rows.append([item["text"] for item in sorted_items])
            
            # If we have multiple rows with similar column counts, it's likely a table
            if len(potential_table_rows) >= 2:
                # Use first row as headers
                tables.append({
                    "headers": potential_table_rows[0] if potential_table_rows else [],
                    "rows": potential_table_rows[1:] if len(potential_table_rows) > 1 else [],
                })
        
        except Exception as e:
            logger.warning(f"Table detection failed: {e}")
        
        return tables
    
    async def extract_metadata(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Extract metadata from PDF."""
        try:
            import fitz
        except ImportError:
            return {"filename": filename, "file_size": len(file_bytes)}
        
        metadata = {
            "filename": filename,
            "file_size": len(file_bytes),
            "format": "pdf",
        }
        
        try:
            pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
            
            # Basic metadata
            metadata["page_count"] = len(pdf_document)
            
            # PDF metadata dict
            pdf_meta = pdf_document.metadata
            if pdf_meta:
                if pdf_meta.get("title"):
                    metadata["title"] = pdf_meta["title"]
                if pdf_meta.get("author"):
                    metadata["author"] = pdf_meta["author"]
                if pdf_meta.get("subject"):
                    metadata["subject"] = pdf_meta["subject"]
                if pdf_meta.get("keywords"):
                    metadata["keywords"] = pdf_meta["keywords"]
                if pdf_meta.get("creationDate"):
                    metadata["creation_date"] = self._parse_pdf_date(pdf_meta["creationDate"])
                if pdf_meta.get("modDate"):
                    metadata["modification_date"] = self._parse_pdf_date(pdf_meta["modDate"])
                if pdf_meta.get("creator"):
                    metadata["creator_tool"] = pdf_meta["creator"]
            
            # Analyze pages for scanned vs native
            scanned_pages = 0
            native_pages = 0
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                page_text = page.get_text("text")
                
                if len(page_text.strip()) < self.MIN_TEXT_CHARS_FOR_NATIVE:
                    scanned_pages += 1
                else:
                    native_pages += 1
            
            metadata["scanned_pages"] = scanned_pages
            metadata["native_pages"] = native_pages
            metadata["is_fully_scanned"] = native_pages == 0 and scanned_pages > 0
            metadata["is_mixed"] = scanned_pages > 0 and native_pages > 0
            
            pdf_document.close()
            
        except Exception as e:
            logger.error(f"Error extracting PDF metadata: {e}")
        
        return metadata
    
    def _parse_pdf_date(self, date_str: str) -> Optional[str]:
        """Parse PDF date format (D:YYYYMMDDHHmmSS) to ISO format."""
        if not date_str:
            return None
        
        try:
            # Remove 'D:' prefix if present
            if date_str.startswith("D:"):
                date_str = date_str[2:]
            
            # Parse basic date
            if len(date_str) >= 8:
                year = date_str[0:4]
                month = date_str[4:6]
                day = date_str[6:8]
                return f"{year}-{month}-{day}"
        except:
            pass
        
        return None
    
    async def extract_embedded_objects(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        """Extract embedded images and other objects from PDF."""
        try:
            import fitz
        except ImportError:
            return []
        
        objects = []
        
        try:
            pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                
                # Get images on page
                image_list = page.get_images()
                
                for img_idx, img in enumerate(image_list):
                    xref = img[0]
                    
                    try:
                        base_image = pdf_document.extract_image(xref)
                        if base_image:
                            objects.append({
                                "type": "image",
                                "page": page_num + 1,
                                "index": img_idx,
                                "format": base_image.get("ext", "unknown"),
                                "width": base_image.get("width", 0),
                                "height": base_image.get("height", 0),
                                "size_bytes": len(base_image.get("image", b"")),
                            })
                    except Exception as e:
                        logger.debug(f"Could not extract image {xref}: {e}")
            
            pdf_document.close()
            
        except Exception as e:
            logger.error(f"Error extracting embedded objects: {e}")
        
        return objects
    
    async def analyze_document(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Comprehensive document analysis.
        
        Returns detailed information about the PDF for processing decisions.
        """
        metadata = await self.extract_metadata(file_bytes, filename)
        
        analysis = {
            "metadata": metadata,
            "extraction_method": "native" if not metadata.get("is_fully_scanned") else "ocr",
            "requires_ocr": metadata.get("is_fully_scanned", False) or metadata.get("is_mixed", False),
            "estimated_processing_time": self._estimate_processing_time(metadata),
            "confidence_estimate": self._estimate_confidence(metadata),
        }
        
        return analysis
    
    def _estimate_processing_time(self, metadata: Dict) -> str:
        """Estimate processing time based on document characteristics."""
        page_count = metadata.get("page_count", 1)
        is_scanned = metadata.get("is_fully_scanned", False)
        
        if is_scanned:
            # OCR is slower: ~5 seconds per page
            seconds = page_count * 5
        else:
            # Native extraction: ~0.5 seconds per page
            seconds = page_count * 0.5
        
        if seconds < 60:
            return f"{int(seconds)} seconds"
        else:
            return f"{int(seconds / 60)} minutes"
    
    def _estimate_confidence(self, metadata: Dict) -> float:
        """Estimate extraction confidence based on document characteristics."""
        base_confidence = 0.95
        
        if metadata.get("is_fully_scanned"):
            base_confidence -= 0.15  # OCR is less reliable
        
        if metadata.get("is_mixed"):
            base_confidence -= 0.05  # Mixed docs are slightly harder
        
        if metadata.get("page_count", 1) > 50:
            base_confidence -= 0.05  # Long documents may have more errors
        
        return max(0.5, base_confidence)
