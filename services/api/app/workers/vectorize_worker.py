"""Celery worker task for vectorization."""

import logging
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.lib.embeddings import TenantAwareEmbeddingClient
from app.models.vector_embedding import VectorEmbedding
from app.models.silver_record import SilverRecord
from app.models.dead_letter_queue import DeadLetterQueue

logger = logging.getLogger(__name__)


@celery_app.task(
    name="vectorize_record",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    default_retry_delay=5,
)
def vectorize_record(
    self,
    silver_record_id: str,
    text_content: str,
    metadata: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None,
):
    """
    Vectorize a single silver record.

    Generates embedding for text content and stores it linked to the silver record.
    On persistent failure, routes to dead-letter queue.

    Args:
        silver_record_id: UUID of silver record
        text_content: Text to embed
        metadata: Optional metadata
        tenant_id: Tenant ID for multi-tenant support

    Returns:
        Dict with embedding result or error
    """
    try:
        record_uuid = UUID(silver_record_id)

        # Run async function
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _vectorize_record_async(
                    record_uuid, text_content, metadata, tenant_id
                )
            )
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Vectorization task failed for {silver_record_id}: {e}")
        # Retry with exponential backoff
        self.retry(exc=e)


async def _vectorize_record_async(
    silver_record_id: UUID,
    text_content: str,
    metadata: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Async implementation of vectorization."""
    async with AsyncSessionLocal() as session:
        try:
            # Validate record exists
            stmt = select(SilverRecord).where(SilverRecord.id == silver_record_id)
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if not record:
                logger.error(f"Silver record {silver_record_id} not found")
                return {
                    "status": "failed",
                    "error": "Record not found",
                    "silver_record_id": str(silver_record_id),
                }

            # Generate embedding
            client = TenantAwareEmbeddingClient(tenant_id=tenant_id)
            embedding, error = await client.generate_embedding(
                text_content, metadata=metadata
            )

            if error:
                # Determine if error is retriable
                if client._is_retriable_error(error):
                    logger.warning(f"Retriable error for {silver_record_id}: {error}")
                    # Re-raise to trigger retry
                    raise Exception(f"Retriable: {error}")
                else:
                    # Permanent failure - route to dead-letter queue
                    logger.error(f"Permanent error for {silver_record_id}: {error}")
                    await _route_to_dlq(session, silver_record_id, error)
                    return {
                        "status": "failed",
                        "error": error,
                        "silver_record_id": str(silver_record_id),
                        "routed_to_dlq": True,
                    }

            # Store embedding
            vector_embedding = VectorEmbedding(
                file_id=record.file_id,
                embedding=embedding,
                embedding_metadata={
                    "silver_record_id": str(silver_record_id),
                    "source_document": record.title or "unknown",
                    "language": record.language or "unknown",
                    **(metadata or {}),
                },
                content_preview=text_content[:500] if text_content else None,
            )

            session.add(vector_embedding)
            await session.flush()

            # Update silver record with vector_store_id
            record.vector_store_id = str(vector_embedding.id)
            await session.flush()

            await session.commit()

            logger.info(
                f"Successfully vectorized record {silver_record_id}: embedding {vector_embedding.id}"
            )

            return {
                "status": "success",
                "silver_record_id": str(silver_record_id),
                "embedding_id": str(vector_embedding.id),
                "embedding_dimensions": len(embedding) if embedding else 0,
            }

        except Exception as e:
            logger.error(f"Vectorization failed for {silver_record_id}: {e}")
            await session.rollback()
            raise


async def _route_to_dlq(
    session: AsyncSession,
    silver_record_id: UUID,
    error_message: str,
):
    """Route a failed vectorization to dead-letter queue."""
    try:
        dlq_item = DeadLetterQueue(
            job_id=silver_record_id,  # Store as job_id for reference
            original_filename=f"silver_record_{silver_record_id}",
            error_message=error_message,
            final_exception="VectorizationError",
            status="pending_review",
        )
        session.add(dlq_item)
        await session.flush()
        logger.info(f"Routed {silver_record_id} to dead-letter queue")
    except Exception as e:
        logger.error(f"Failed to route to DLQ: {e}")


@celery_app.task(
    name="vectorize_batch",
    bind=True,
)
def vectorize_batch(
    self,
    silver_record_ids: list,
    batch_size: int = 10,
    tenant_id: Optional[str] = None,
):
    """
    Vectorize a batch of silver records.

    Enqueues individual vectorization tasks for each record.

    Args:
        silver_record_ids: List of silver record IDs
        batch_size: Size of sub-batches for parallel processing
        tenant_id: Tenant ID

    Returns:
        List of job IDs
    """
    job_ids = []

    for record_id in silver_record_ids:
        task = celery_app.send_task(
            "vectorize_record",
            args=[record_id, "", {}, tenant_id],
            retry=True,
            retry_policy={
                "max_retries": 3,
                "interval_start": 1,
                "interval_step": 2,
            },
        )
        job_ids.append(task.id)

    return {"job_ids": job_ids, "total": len(silver_record_ids)}
