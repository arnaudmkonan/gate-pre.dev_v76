"""Service for building complete document metadata from extraction results."""
import logging
import time
from typing import Dict, Optional

from app.parsers.registry import ParserRegistry
from app.services.entity_extractor import EntityExtractor

logger = logging.getLogger(__name__)


class MetadataBuilder:
    """Service for orchestrating document metadata extraction and enrichment."""

    @staticmethod
    async def build_metadata(
        file_bytes: bytes,
        filename: str,
        file_type: str,
        timeout_seconds: int = 60,
    ) -> Dict:
        """
        Build complete document metadata from file.

        Args:
            file_bytes: Raw file bytes
            filename: Original filename
            file_type: File type/extension
            timeout_seconds: Maximum time for extraction (default 60s)

        Returns:
            Dict with complete metadata including confidence scores and entities
        """
        start_time = time.time()
        processing_time_ms = 0

        try:
            # Get appropriate parser
            parser = ParserRegistry.get_parser(file_type)
            if not parser:
                return {
                    "filename": filename,
                    "file_type": file_type,
                    "extraction_status": "failed",
                    "error_reason": f"No parser available for .{file_type}",
                    "processing_time_ms": max(1, int((time.time() - start_time) * 1000)),
                    "is_retryable": False,
                    "confidence_scores": {},
                    "detected_entities": [],
                }

            # Validate format
            is_valid = await parser.validate_format(file_bytes)
            if not is_valid:
                return {
                    "filename": filename,
                    "file_type": file_type,
                    "extraction_status": "failed",
                    "error_reason": "Invalid file format",
                    "processing_time_ms": max(1, int((time.time() - start_time) * 1000)),
                    "is_retryable": True,
                    "confidence_scores": {},
                    "detected_entities": [],
                }

            # Extract base metadata
            metadata = await parser.extract_metadata(file_bytes, filename)

            # Extract text for entity extraction
            text = await parser.extract_text(file_bytes)

            # Extract entities
            entities_result = await EntityExtractor.extract_entities_with_confidence(text)

            processing_time_ms = max(1, int((time.time() - start_time) * 1000))

            # Check for timeout
            if processing_time_ms > (timeout_seconds * 1000):
                logger.warning(f"Metadata extraction timeout: {processing_time_ms}ms > {timeout_seconds}s")
                return {
                    "filename": filename,
                    "file_type": file_type,
                    "extraction_status": "timeout",
                    "error_reason": f"Extraction exceeded {timeout_seconds}s timeout",
                    "processing_time_ms": processing_time_ms,
                    "is_retryable": True,
                    "confidence_scores": {},
                    "detected_entities": [],
                }

            # Build complete metadata with confidence scores
            complete_metadata = {
                "filename": filename,
                "file_type": file_type,
                **metadata,
                "extraction_status": "success",
                "processing_time_ms": processing_time_ms,
                "is_retryable": False,
                "error_reason": None,
                "detected_entities": entities_result.get("entities", []),
                "confidence_scores": {
                    "title": metadata.get("title_confidence", 0.8),
                    "language": metadata.get("language_confidence", 0.9),
                    "page_count": metadata.get("page_count_confidence", 0.95),
                    "entities": entities_result.get("extraction_confidence", 0.0),
                },
            }

            # Add summary if available
            if "summary" in metadata:
                complete_metadata["summary"] = metadata["summary"]
            else:
                # Generate a 3-sentence summary from text
                complete_metadata["summary"] = MetadataBuilder._generate_summary(text)

            logger.info(f"Metadata built successfully for {filename}: {processing_time_ms}ms")
            return complete_metadata

        except Exception as e:
            processing_time_ms = max(1, int((time.time() - start_time) * 1000))
            logger.error(f"Error building metadata for {filename}: {e}")
            return {
                "filename": filename,
                "file_type": file_type,
                "extraction_status": "failed",
                "error_reason": str(e),
                "processing_time_ms": processing_time_ms,
                "is_retryable": True,
                "confidence_scores": {},
                "detected_entities": [],
            }

    @staticmethod
    def _generate_summary(text: str, max_sentences: int = 3) -> str:
        """
        Generate a simple summary from text.

        Args:
            text: Document text
            max_sentences: Maximum sentences in summary

        Returns:
            Summary string
        """
        if not text:
            return ""

        # Split into sentences (basic approach)
        sentences = text.split(".")
        summary_sentences = [s.strip() + "." for s in sentences[:max_sentences] if s.strip()]
        summary = " ".join(summary_sentences)

        # Limit to 500 characters
        return summary[:500] if len(summary) > 500 else summary
