"""Celery task for extracting content from files using specialized extractors."""

import logging
import json
import time
from uuid import UUID
from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.celery_app import celery_app
from app.core.config import settings
from app.models import (
    RawFile,
    RawExtraction,
    ExtractionStatus,
    RoutingDecision,
)
from app.services.file_routing_service import FileRoutingService
from app.services.extractors.text_docx_extractor import TextExtractor, DocxExtractor
from app.services.extractors.spreadsheet_presentation_extractor import (
    SpreadsheetExtractor,
    PresentationExtractor,
)
from app.services.extractors.markup_json_extractor import (
    MarkupJsonExtractor,
    XmlExtractor,
    YamlExtractor,
)

logger = logging.getLogger(__name__)

# Create async engine for Celery worker
db_url = settings.database_url or "postgresql+asyncpg://postgres:postgres@localhost:5432/doc_ingestion"
if "+asyncpg://" not in db_url:
    db_url = db_url.replace("+psycopg://", "+asyncpg://").replace("+psycopg2://", "+asyncpg://").replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(db_url, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Extractor mapping
EXTRACTOR_MAPPING = {
    "txt": TextExtractor(),
    "docx": DocxExtractor(),
    "doc": DocxExtractor(),
    "xlsx": SpreadsheetExtractor(),
    "xls": SpreadsheetExtractor(),
    "csv": SpreadsheetExtractor(),
    "pptx": PresentationExtractor(),
    "ppt": PresentationExtractor(),
    "html": MarkupJsonExtractor(),
    "md": MarkupJsonExtractor(),
    "json": MarkupJsonExtractor(),
    "xml": XmlExtractor(),
    "yml": YamlExtractor(),
    "yaml": YamlExtractor(),
}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
async def extract_file(self, file_id: str, mime_type: str = None):
    """
    Extract content from a raw file.

    Args:
        file_id: ID of the RawFile to extract from
        mime_type: Optional MIME type for routing decision
    """
    file_uuid = UUID(file_id)
    start_time = time.time()

    try:
        async with AsyncSessionLocal() as session:
            # Fetch raw file
            stmt = select(RawFile).where(RawFile.id == file_uuid)
            result = await session.execute(stmt)
            raw_file = result.scalar_one_or_none()

            if not raw_file:
                logger.error(f"Raw file {file_id} not found")
                return {"status": "failed", "error": "File not found"}

            # Route the file
            routing_decision = await FileRoutingService.route_file(
                session,
                file_uuid,
                raw_file.filename,
                b"",  # We'll load the actual content if needed
                mime_type,
            )

            if not routing_decision:
                logger.error(f"Failed to route file {file_id}")
                return {"status": "failed", "error": "Routing failed"}

            # Get extractor based on detected type
            extractor = EXTRACTOR_MAPPING.get(routing_decision.detected_type.lower())
            if not extractor:
                logger.warning(f"No extractor for type {routing_decision.detected_type}")
                extractor = EXTRACTOR_MAPPING.get("txt")  # Fallback to text extractor

            # Load file content from storage (placeholder - integrate with storage service)
            file_content = await _load_file_content(file_uuid)
            if not file_content:
                logger.error(f"Could not load file content for {file_id}")
                return {"status": "failed", "error": "Could not load file"}

            # Extract content
            extracted = await extractor.extract(file_content, raw_file.filename)

            # Save extraction to database
            extraction_data = {
                "text": extracted.text,
                "tables": extracted.tables,
                "metadata": extracted.metadata,
                "embedded_objects": extracted.embedded_objects,
                "sections": extracted.sections,
            }

            status = ExtractionStatus.PARTIAL if extracted.errors else ExtractionStatus.SUCCESS

            stmt = insert(RawExtraction).values(
                file_id=file_uuid,
                extractor_version="1.0.0",
                status=status.value,
                raw_content=extraction_data,
                extracted_text=extracted.text,
                extracted_tables=extracted.tables,
                extracted_metadata=extracted.metadata,
                embedded_objects=extracted.embedded_objects,
                error_message="; ".join(extracted.errors) if extracted.errors else None,
                lineage={
                    "raw_id": str(file_uuid),
                    "routing_decision_id": str(routing_decision.id),
                },
            ).returning(RawExtraction)

            result = await session.execute(stmt)
            raw_extraction = result.scalar_one()
            await session.commit()

            elapsed = time.time() - start_time
            logger.info(
                f"Extracted file {file_id} in {elapsed:.2f}s "
                f"(status: {status}, extractor: {routing_decision.chosen_agent})"
            )

            return {
                "status": "success",
                "file_id": str(file_uuid),
                "extraction_id": str(raw_extraction.id),
                "extractor": routing_decision.chosen_agent,
                "extracted_status": status.value,
                "elapsed_seconds": elapsed,
                "text_length": len(extracted.text),
                "table_count": len(extracted.tables),
                "errors": extracted.errors,
            }

    except Exception as e:
        logger.error(f"Error extracting file {file_id}: {e}")
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        else:
            return {"status": "failed", "error": str(e), "retries": self.request.retries}


async def _load_file_content(file_id: UUID) -> bytes:
    """
    Load file content from storage.

    Placeholder - integrate with actual storage service.
    """
    # TODO: Integrate with Supabase Storage or S3
    # For now, return empty bytes
    logger.warning(f"File content loading not implemented for {file_id}")
    return b""
