"""
Celery tasks for embedding generation.

Handles batch embedding generation for documents that are missing embeddings.
"""
import logging
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import get_sync_db, AsyncSessionLocal
from app.core.config import settings
from app.models.document_metadata import DocumentMetadata
from app.models.document_embedding import DocumentEmbedding

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2)
def generate_document_embeddings(self, document_ids: List[str]) -> Dict[str, Any]:
    """
    Generate embeddings for a list of documents.
    
    Args:
        document_ids: List of document IDs to generate embeddings for
        
    Returns:
        Dict with results for each document
    """
    import asyncio
    
    logger.info(f"Starting embedding generation for {len(document_ids)} documents")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(
            _generate_embeddings_batch(document_ids)
        )
        return results
    finally:
        loop.close()


async def _generate_embeddings_batch(document_ids: List[str]) -> Dict[str, Any]:
    """Async implementation of batch embedding generation."""
    from app.lib.embeddings import TenantAwareEmbeddingClient
    
    results = {
        "success": [],
        "failed": [],
        "skipped": [],
        "total_chunks": 0,
    }
    
    client = TenantAwareEmbeddingClient()
    
    async with AsyncSessionLocal() as session:
        for doc_id in document_ids:
            try:
                doc_uuid = UUID(doc_id)
                
                # Get document
                doc_result = await session.execute(
                    select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
                )
                document = doc_result.scalar_one_or_none()
                
                if not document:
                    logger.warning(f"Document {doc_id} not found")
                    results["skipped"].append({
                        "document_id": doc_id,
                        "reason": "not_found"
                    })
                    continue
                
                # Check if already has embeddings
                existing_result = await session.execute(
                    select(DocumentEmbedding).where(
                        DocumentEmbedding.document_id == doc_uuid
                    ).limit(1)
                )
                if existing_result.scalar_one_or_none():
                    logger.info(f"Document {doc_id} already has embeddings, skipping")
                    results["skipped"].append({
                        "document_id": doc_id,
                        "filename": document.filename,
                        "reason": "already_has_embeddings"
                    })
                    continue
                
                # Get text to embed
                text = document.extracted_text_snippet
                if not text or len(text.strip()) < 10:
                    logger.warning(f"Document {doc_id} has insufficient text")
                    results["skipped"].append({
                        "document_id": doc_id,
                        "filename": document.filename,
                        "reason": "insufficient_text"
                    })
                    continue
                
                # Generate embeddings
                chunks_created = await _generate_embeddings_for_document(
                    session, document, text, client
                )
                
                results["success"].append({
                    "document_id": doc_id,
                    "filename": document.filename,
                    "chunks_created": chunks_created,
                })
                results["total_chunks"] += chunks_created
                
                logger.info(f"Generated {chunks_created} embeddings for {document.filename}")
                
            except Exception as e:
                logger.error(f"Failed to generate embeddings for {doc_id}: {e}")
                results["failed"].append({
                    "document_id": doc_id,
                    "error": str(e)
                })
        
        await session.commit()
    
    return results


async def _generate_embeddings_for_document(
    session,
    document: DocumentMetadata,
    text: str,
    client,
) -> int:
    """Generate embeddings for a single document."""
    # Chunk text
    max_chunk_size = 1000
    chunks = _chunk_text(text, max_chunk_size)
    
    chunks_created = 0
    
    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        
        # Generate embedding
        embedding, error = await client.generate_embedding(
            chunk,
            metadata={
                "filename": document.filename,
                "file_type": document.file_type,
                "document_id": str(document.id),
            }
        )
        
        if error:
            logger.warning(f"Failed to embed chunk {i} for {document.filename}: {error}")
            continue
        
        if embedding:
            # Store embedding
            doc_embedding = DocumentEmbedding(
                document_id=document.id,
                chunk_index=i,
                embedding=embedding,
                content_preview=chunk[:500] if chunk else None,
                embedding_metadata={
                    "filename": document.filename,
                    "file_type": document.file_type,
                    "chunk_size": len(chunk),
                },
            )
            session.add(doc_embedding)
            chunks_created += 1
    
    # Update document vector_store_id to indicate it has embeddings
    if chunks_created > 0:
        document.vector_store_id = str(document.id)
        session.add(document)
    
    return chunks_created


def _chunk_text(text: str, max_size: int) -> List[str]:
    """Split text into chunks for embedding."""
    if len(text) <= max_size:
        return [text]
    
    chunks = []
    paragraphs = text.split('\n\n')
    current_chunk = ""
    
    for para in paragraphs:
        if len(current_chunk) + len(para) <= max_size:
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks
