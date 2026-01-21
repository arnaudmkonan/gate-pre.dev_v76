import logging
from uuid import UUID
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.celery_app import celery_app
from app.core.config import settings
from app.models import (
    SilverRecord,
    RawFile,
    VectorEmbedding,
)
from app.services.metadata import MapperService
from app.services.vector import VectorService

logger = logging.getLogger(__name__)

# Create async engine for Celery worker
# Ensure we're using asyncpg, not psycopg2
db_url = settings.database_url or "postgresql+asyncpg://postgres:postgres@localhost:5432/doc_ingestion"
if "+asyncpg://" not in db_url:
    db_url = db_url.replace("+psycopg://", "+asyncpg://").replace("+psycopg2://", "+asyncpg://").replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(db_url, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
async def process_metadata(self, file_id: str):
    """
    Process metadata mapping and embedding generation for a file.

    Args:
        file_id: ID of the file to process
    """
    file_uuid = UUID(file_id)

    try:
        async with AsyncSessionLocal() as session:
            # Fetch raw file
            stmt = select(RawFile).where(RawFile.id == file_uuid)
            result = await session.execute(stmt)
            raw_file = result.scalar_one_or_none()

            if not raw_file:
                logger.error(f"RawFile {file_id} not found")
                return {"status": "failed", "error": "RawFile not found"}

            # Initialize services
            mapper = MapperService(session)
            vector_service = VectorService(session)

            logger.info(f"Processing metadata for file {file_id}")

            # TODO: Get extracted raw content from ingestion task result
            # For now, use placeholder
            raw_content = {
                "content": f"Extracted content from {raw_file.filename}",
                "title": raw_file.filename,
                "file_type": raw_file.file_type,
            }

            # Map to silver schema
            silver_record = await mapper.map_to_silver(
                file_id=file_uuid,
                raw_content=raw_content,
                file_type=raw_file.file_type,
                file_size=raw_file.file_size,
            )

            logger.info(f"Mapped file {file_id} to silver schema")

            # Generate embeddings
            if silver_record.content:
                embedding = await vector_service.generate_embedding(
                    file_id=file_uuid,
                    content=silver_record.content,
                    metadata={
                        "source_id": str(file_uuid),
                        "file_type": raw_file.file_type,
                        "language": silver_record.language,
                    },
                )

                logger.info(f"Generated embedding for file {file_id}")

                # Attach metadata to embedding
                embedding_metadata = {
                    "processed_at": datetime.utcnow().isoformat(),
                    "language": silver_record.language,
                    "file_type": raw_file.file_type,
                }
                await vector_service.attach_metadata(embedding.id, embedding_metadata)

            return {
                "status": "success",
                "file_id": file_id,
                "silver_record_id": str(silver_record.id),
            }

    except Exception as exc:
        logger.error(f"Failed to process metadata for file {file_id}: {exc}")

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        else:
            return {"status": "failed", "file_id": file_id, "error": str(exc)}
