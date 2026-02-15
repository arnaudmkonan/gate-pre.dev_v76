"""
API routes for embedding management.

Provides endpoints for:
- Checking documents missing embeddings
- Triggering embedding generation for documents
- Viewing embedding statistics
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.models.document_metadata import DocumentMetadata
from app.models.document_embedding import DocumentEmbedding

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/embeddings", tags=["embeddings"])


# ============================================================================
# Pydantic Models
# ============================================================================

class EmbeddingStats(BaseModel):
    """Statistics about embedding coverage."""
    total_documents: int
    documents_with_embeddings: int
    documents_missing_embeddings: int
    total_embedding_chunks: int
    coverage_percentage: float


class DocumentMissingEmbedding(BaseModel):
    """Document that is missing embeddings."""
    id: str
    filename: str
    file_type: str
    size: int
    ingestion_status: str
    extracted_text_length: int
    created_at: str


class MissingEmbeddingsResponse(BaseModel):
    """Response for listing documents missing embeddings."""
    documents: List[DocumentMissingEmbedding]
    total_count: int
    can_generate: bool
    api_key_configured: bool


class GenerateEmbeddingsRequest(BaseModel):
    """Request to generate embeddings for specific documents."""
    document_ids: Optional[List[str]] = None  # If None, generate for all missing
    batch_size: int = 10


class GenerateEmbeddingsResponse(BaseModel):
    """Response after triggering embedding generation."""
    task_id: str
    status: str
    documents_queued: int
    message: str


class EmbeddingGenerationResult(BaseModel):
    """Result of embedding generation for a single document."""
    document_id: str
    filename: str
    status: str
    chunks_generated: int
    error: Optional[str] = None


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/stats", response_model=EmbeddingStats)
async def get_embedding_stats(
    session: AsyncSession = Depends(get_db),
):
    """
    Get statistics about embedding coverage across all documents.
    
    Returns counts of documents with/without embeddings and coverage percentage.
    """
    # Count total documents
    total_result = await session.execute(
        select(func.count(DocumentMetadata.id))
    )
    total_documents = total_result.scalar() or 0
    
    # Count documents with embeddings (have at least one embedding)
    docs_with_embeddings_result = await session.execute(
        select(func.count(func.distinct(DocumentEmbedding.document_id)))
    )
    documents_with_embeddings = docs_with_embeddings_result.scalar() or 0
    
    # Count total embedding chunks
    total_chunks_result = await session.execute(
        select(func.count(DocumentEmbedding.id))
    )
    total_embedding_chunks = total_chunks_result.scalar() or 0
    
    documents_missing = total_documents - documents_with_embeddings
    coverage = (documents_with_embeddings / total_documents * 100) if total_documents > 0 else 0
    
    return EmbeddingStats(
        total_documents=total_documents,
        documents_with_embeddings=documents_with_embeddings,
        documents_missing_embeddings=documents_missing,
        total_embedding_chunks=total_embedding_chunks,
        coverage_percentage=round(coverage, 2),
    )


@router.get("/missing", response_model=MissingEmbeddingsResponse)
async def get_documents_missing_embeddings(
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """
    Get list of documents that are missing embeddings.
    
    Only returns documents that:
    - Have completed ingestion
    - Have extracted text content
    - Don't have any embeddings yet
    """
    # Subquery to get document IDs that have embeddings
    docs_with_embeddings = (
        select(DocumentEmbedding.document_id)
        .distinct()
        .subquery()
    )
    
    # Query documents without embeddings
    query = (
        select(DocumentMetadata)
        .where(
            and_(
                DocumentMetadata.ingestion_status == "completed",
                DocumentMetadata.extracted_text_snippet.isnot(None),
                DocumentMetadata.id.notin_(select(docs_with_embeddings.c.document_id)),
            )
        )
        .order_by(DocumentMetadata.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    
    result = await session.execute(query)
    documents = result.scalars().all()
    
    # Count total missing
    count_query = (
        select(func.count(DocumentMetadata.id))
        .where(
            and_(
                DocumentMetadata.ingestion_status == "completed",
                DocumentMetadata.extracted_text_snippet.isnot(None),
                DocumentMetadata.id.notin_(select(docs_with_embeddings.c.document_id)),
            )
        )
    )
    count_result = await session.execute(count_query)
    total_count = count_result.scalar() or 0
    
    # Check if API key is configured
    api_key_configured = bool(settings.openai_api_key)
    
    return MissingEmbeddingsResponse(
        documents=[
            DocumentMissingEmbedding(
                id=str(doc.id),
                filename=doc.filename,
                file_type=doc.file_type or "unknown",
                size=doc.size or 0,
                ingestion_status=doc.ingestion_status or "unknown",
                extracted_text_length=len(doc.extracted_text_snippet) if doc.extracted_text_snippet else 0,
                created_at=doc.created_at.isoformat() if doc.created_at else "",
            )
            for doc in documents
        ],
        total_count=total_count,
        can_generate=api_key_configured and total_count > 0,
        api_key_configured=api_key_configured,
    )


@router.post("/generate", response_model=GenerateEmbeddingsResponse)
async def generate_embeddings(
    request: GenerateEmbeddingsRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    """
    Trigger embedding generation for documents missing embeddings.
    
    If document_ids is provided, generates for those specific documents.
    Otherwise, generates for all documents missing embeddings.
    """
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI API key not configured. Cannot generate embeddings.",
        )
    
    # Subquery for documents with embeddings
    docs_with_embeddings = (
        select(DocumentEmbedding.document_id)
        .distinct()
        .subquery()
    )
    
    # Build query for target documents
    if request.document_ids:
        # Specific documents requested
        target_uuids = [UUID(doc_id) for doc_id in request.document_ids]
        query = (
            select(DocumentMetadata)
            .where(
                and_(
                    DocumentMetadata.id.in_(target_uuids),
                    DocumentMetadata.ingestion_status == "completed",
                    DocumentMetadata.extracted_text_snippet.isnot(None),
                    DocumentMetadata.id.notin_(select(docs_with_embeddings.c.document_id)),
                )
            )
        )
    else:
        # All documents missing embeddings
        query = (
            select(DocumentMetadata)
            .where(
                and_(
                    DocumentMetadata.ingestion_status == "completed",
                    DocumentMetadata.extracted_text_snippet.isnot(None),
                    DocumentMetadata.id.notin_(select(docs_with_embeddings.c.document_id)),
                )
            )
            .limit(request.batch_size)
        )
    
    result = await session.execute(query)
    documents = result.scalars().all()
    
    if not documents:
        return GenerateEmbeddingsResponse(
            task_id="none",
            status="no_documents",
            documents_queued=0,
            message="No documents found that need embeddings.",
        )
    
    # Queue embedding generation tasks
    from app.workers.embedding_tasks import generate_document_embeddings
    
    task = generate_document_embeddings.delay(
        [str(doc.id) for doc in documents]
    )
    
    return GenerateEmbeddingsResponse(
        task_id=task.id,
        status="queued",
        documents_queued=len(documents),
        message=f"Embedding generation queued for {len(documents)} documents.",
    )


@router.get("/{document_id}")
async def get_document_embeddings(
    document_id: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Get all embeddings for a specific document.
    """
    doc_uuid = UUID(document_id)
    
    # Check document exists
    doc_result = await session.execute(
        select(DocumentMetadata).where(DocumentMetadata.id == doc_uuid)
    )
    document = doc_result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    
    # Get embeddings
    embeddings_result = await session.execute(
        select(DocumentEmbedding)
        .where(DocumentEmbedding.document_id == doc_uuid)
        .order_by(DocumentEmbedding.chunk_index)
    )
    embeddings = embeddings_result.scalars().all()
    
    return {
        "document_id": document_id,
        "filename": document.filename,
        "embedding_count": len(embeddings),
        "embeddings": [
            {
                "id": str(emb.id),
                "chunk_index": emb.chunk_index,
                "content_preview": emb.content_preview[:200] if emb.content_preview else None,
                "embedding_dimensions": len(emb.embedding) if emb.embedding else 0,
                "created_at": emb.created_at.isoformat() if emb.created_at else None,
            }
            for emb in embeddings
        ],
    }
