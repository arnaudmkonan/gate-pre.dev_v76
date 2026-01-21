import logging
from uuid import UUID
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def vectorize_batch(
    self,
    batch_id: str,
    file_ids: list[str],
):
    """
    Celery task to vectorize a batch of files.

    Args:
        batch_id: Batch ID (string UUID)
        file_ids: List of file IDs to vectorize (string UUIDs)

    Returns:
        Results dict with successful and failed counts
    """
    try:
        from app.core.database import SessionLocal
        from app.services.scheduler.scheduler import BatchVectorizerScheduler
        from app.services.vector.raw_vector_service import RawVectorService
        from app.services.metadata.metadata_normalizer import MetadataNormalizer
        from app.models import RawVector, SilverMetadata
        from app.schemas.vector_store import RawVectorCreate
        import asyncio

        with SessionLocal() as session:
            scheduler = BatchVectorizerScheduler(session)
            vector_service = RawVectorService(session)

            successful = []
            failed = []
            batch_uuid = UUID(batch_id)

            for file_id_str in file_ids:
                try:
                    file_uuid = UUID(file_id_str)

                    # Generate embedding (placeholder - use actual OpenAI API in production)
                    embedding = _generate_embedding(file_id_str)

                    # Store raw vector
                    payload = RawVectorCreate(
                        file_id=file_uuid,
                        vector=embedding,
                        metadata={"source": "batch_vectorize"},
                        provenance={
                            "processor_agent_id": "batch-vectorizer-v1",
                            "extraction_version": "1.0.0"
                        }
                    )

                    # Use async method in sync context
                    result = asyncio.run(vector_service.store(payload))
                    successful.append(str(result.id))

                    logger.info(f"Vectorized file {file_id_str}")

                except Exception as e:
                    logger.error(f"Failed to vectorize file {file_id_str}: {e}")
                    failed.append({
                        "file_id": file_id_str,
                        "error": str(e)
                    })

                    # Add to DLQ
                    try:
                        asyncio.run(scheduler.add_to_dlq(
                            batch_id=batch_uuid,
                            file_id=file_uuid,
                            error_reason=str(e),
                        ))
                    except Exception as dlq_error:
                        logger.error(f"Failed to add to DLQ: {dlq_error}")

            # Mark batch as processed
            asyncio.run(scheduler.mark_processed(
                batch_uuid,
                len(successful),
                len(failed),
            ))

            logger.info(f"Batch {batch_id} vectorization complete: {len(successful)} successful, {len(failed)} failed")

            return {
                "status": "completed",
                "batch_id": batch_id,
                "successful_count": len(successful),
                "failed_count": len(failed),
                "successful_ids": successful,
                "failed_records": failed,
            }

    except Exception as e:
        logger.error(f"Batch vectorization task failed: {e}")
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


def _generate_embedding(content: str, dimension: int = 1536) -> list[float]:
    """
    Generate placeholder embedding.

    In production, this would call OpenAI API.
    """
    import hashlib
    import random

    # Deterministic pseudo-random based on content
    hash_obj = hashlib.md5(content.encode())
    hash_int = int(hash_obj.hexdigest(), 16)
    random.seed(hash_int % 2**32)

    embedding = [random.random() for _ in range(dimension)]
    return embedding
