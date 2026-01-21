import logging
from uuid import UUID
from celery import shared_task

from app.schemas.vector_store import RawVectorCreate

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def store_vector(
    self,
    file_id: str,
    vector: list,
    metadata: dict = None,
    provenance: dict = None,
):
    """
    Celery task to store a vector in background.

    Args:
        file_id: File ID (string UUID)
        vector: Embedding vector
        metadata: Optional file metadata
        provenance: Provenance metadata (processor_agent_id, extraction_version)

    Returns:
        Success status
    """
    try:
        from app.core.database import SessionLocal
        from app.services.vector.raw_vector_service import RawVectorService

        # Convert string UUID back to UUID
        file_uuid = UUID(file_id)

        # Create payload
        payload = RawVectorCreate(
            file_id=file_uuid,
            vector=vector,
            metadata=metadata or {},
            provenance=provenance or {},
        )

        # Get session and store vector
        with SessionLocal() as session:
            service = RawVectorService(session)
            # Note: store() is async, need to handle in sync context
            import asyncio
            result = asyncio.run(service.store(payload))
            logger.info(f"Stored vector for file {file_id}")
            return {"status": "success", "file_id": file_id, "id": str(result.id)}

    except Exception as e:
        logger.error(f"Failed to store vector: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


@shared_task(bind=True, max_retries=3)
def batch_store_vectors(
    self,
    vectors_data: list[dict],
):
    """
    Celery task to batch store vectors.

    Args:
        vectors_data: List of vector data dicts with file_id, vector, metadata, provenance

    Returns:
        Results dict with successful and failed counts
    """
    try:
        from app.core.database import SessionLocal
        from app.services.vector.raw_vector_service import RawVectorService
        from uuid import UUID

        with SessionLocal() as session:
            service = RawVectorService(session)
            successful = []
            failed = []

            for data in vectors_data:
                try:
                    payload = RawVectorCreate(
                        file_id=UUID(data["file_id"]),
                        vector=data["vector"],
                        metadata=data.get("metadata"),
                        provenance=data.get("provenance"),
                    )
                    # Note: need async handling
                    import asyncio
                    result = asyncio.run(service.store(payload))
                    successful.append(str(result.id))
                except Exception as e:
                    logger.error(f"Failed to store vector for {data['file_id']}: {e}")
                    failed.append({
                        "file_id": data["file_id"],
                        "error": str(e)
                    })

            logger.info(f"Batch store: {len(successful)} successful, {len(failed)} failed")
            return {
                "status": "completed",
                "successful_count": len(successful),
                "failed_count": len(failed),
                "successful_ids": successful,
                "failed_records": failed,
            }

    except Exception as e:
        logger.error(f"Batch store task failed: {e}")
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
