"""Service for extracting named entities from documents using OpenAI."""
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class EntityExtractor:
    """Service for extracting named entities from text using OpenAI API."""

    @staticmethod
    async def extract_entities(text: str) -> list[dict]:
        """
        Extract named entities from text using OpenAI API.

        Args:
            text: Document text to extract entities from

        Returns:
            List of {text, type, confidence} objects
        """
        # Return empty list for very small documents
        if not text or len(text) < 50:
            logger.debug("Text too short for entity extraction")
            return []

        try:
            # For now, return empty list as OpenAI client initialization is environment-dependent
            # In production, this would call OpenAI's NER capabilities
            logger.info(f"Entity extraction would process {len(text)} characters of text")
            return []

        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return []

    @staticmethod
    async def extract_entities_with_confidence(text: str) -> dict:
        """
        Extract entities with confidence scores.

        Args:
            text: Text to extract entities from

        Returns:
            Dict with entities list and overall confidence
        """
        entities = await EntityExtractor.extract_entities(text)
        return {
            "entities": entities,
            "extraction_confidence": 0.9 if entities else 0.0,
            "entity_count": len(entities),
        }
