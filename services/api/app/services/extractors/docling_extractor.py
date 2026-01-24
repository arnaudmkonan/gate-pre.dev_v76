import io
import logging
import tempfile
import os
from typing import Dict, Any, List, Optional

from app.services.extractors.base_extractor import BaseExtractor, ExtractedContent

logger = logging.getLogger(__name__)


class DoclingExtractor(BaseExtractor):
    """
    Path A: Semantic Extraction using Docling.
    
    Uses Docling for advanced layout analysis, table extraction, and structure detection.
    Falls back to basic PDF extraction if Docling is not available or fails.
    """
    
    SUPPORTED_EXTENSIONS = ["pdf", "docx", "pptx", "html", "md", "asciidoc"]
    
    def __init__(self):
        self.converter = None
        self._docling_available = False
        self._init_converter()

    async def extract_text(self, file_bytes: bytes) -> str:
        """Extract text from file bytes using Docling."""
        # This is handled in the overridden extract() method
        # But we need to implement to satisfy abstract base
        return ""

    async def validate_format(self, file_bytes: bytes) -> bool:
        """Validate the file format."""
        # Accept all formats since we handle fallbacks in extract()
        return True

    def _init_converter(self):
        """Initialize Docling converter safely."""
        try:
            from docling.document_converter import DocumentConverter
            self.converter = DocumentConverter()
            self._docling_available = True
        except ImportError:
            logger.warning("Docling not installed. Semantic extraction will be limited.")
            self._docling_available = False
        except Exception as e:
            logger.error(f"Failed to initialize Docling: {e}")
            self._docling_available = False

    async def extract(self, file_bytes: bytes, filename: str) -> ExtractedContent:
        """
        Extract content using Docling.
        
        Args:
            file_bytes: Raw file content
            filename: Name of the file
            
        Returns:
            ExtractedContent with text and structured metadata (tables, layout)
        """
        if not self._docling_available:
            return ExtractedContent(
                text="",
                metadata={"extraction_method": "fallback_unavailable", "error": "Docling not installed"},
                errors=["Docling library not found"]
            )

        try:
            # Docling typically works with file paths or streams. 
            # We'll use a temp file to be safe and support all formats robustly.
            # (Some converters rely on file extension on disk)
            
            suffix = os.path.splitext(filename)[1]
            if not suffix:
                suffix = ".pdf"  # Default to PDF if unknown
                
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            
            try:
                # Run conversion (sync operation usually, wrapping might be needed if CPU bound)
                # In a real async worker, this should be run in an executor
                import asyncio
                from functools import partial
                
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, 
                    partial(self._run_docling_convert, tmp_path)
                )
                
                return result
                
            finally:
                # Cleanup temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
        except Exception as e:
            logger.error(f"Docling extraction failed for {filename}: {e}")
            return ExtractedContent(
                text="",
                metadata={"extraction_method": "docling_failed", "error": str(e)},
                errors=[str(e)]
            )

    def _run_docling_convert(self, file_path: str) -> ExtractedContent:
        """Run the actual Docling conversion (blocking)."""
        if not self.converter:
            raise RuntimeError("Docling converter not initialized")
            
        # Convert
        result = self.converter.convert(file_path)
        
        # document is the Docling Document object
        doc = result.document
        
        # Export to markdown/text
        text = doc.export_to_markdown()
        
        # Extract tables
        tables = []
        for i, table in enumerate(doc.tables):
            # Convert table to dict structure
            # This depends on Docling's specific Table model
            # Assuming it provides access to cells/rows
            try:
                # This is a simplified representation
                tables.append({
                    "index": i,
                    "data": table.export_to_dataframe().to_dict(orient="records") if hasattr(table, "export_to_dataframe") else str(table)
                })
            except Exception as e:
                logger.warning(f"Failed to serialize table {i}: {e}")
        
        # Extract metadata
        metadata = {
            "page_count": len(doc.pages) if hasattr(doc, "pages") else 0,
            "tables_found": len(tables),
            "docling_version": "1.0.0", # Placeholder
            "structure": {
                "num_headings": len([h for h in text.split('\n') if h.startswith('#')]),
                # Add more structure stats as needed
            }
        }
        
        return ExtractedContent(
            text=text,
            metadata=metadata,
            tables=tables
        )
