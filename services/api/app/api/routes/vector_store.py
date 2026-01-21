import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.embeddings import Embeddings
from app.models.vector_store_config import VectorStoreConfig
from app.schemas.vector_store import (
    EmbeddingResponse,
    SearchResponse,
    VectorStoreConfigCreate,
    VectorStoreConfigResponse,
    VectorStoreConfigUpdate,
    RawVectorCreate,
    RawVectorResponse,
    VectorSearchQuery,
    VectorSearchResult,
)
from app.services.vector_store_service import VectorStoreService
from app.services.vector.raw_vector_service import RawVectorService
from app.services.search.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vector-store", tags=["vector-store"])


@router.post("/config", response_model=VectorStoreConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_vector_store_config(
    config: VectorStoreConfigCreate,
    session: AsyncSession = Depends(get_db),
):
    """Create new vector store configuration."""
    try:
        vector_config = VectorStoreConfig(
            backend=config.backend,
            url=config.url,
            api_key=config.api_key,
            embedding_model=config.embedding_model,
            embedding_dimension=config.embedding_dimension,
            namespace_collection_name=config.namespace_collection_name,
            is_active=True,
        )

        session.add(vector_config)
        await session.commit()
        await session.refresh(vector_config)

        logger.info(f"Vector store config created: {vector_config.id}")
        return vector_config

    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating vector store config: {e}")
        raise HTTPException(status_code=500, detail="Failed to create vector store config")


@router.get("/config", response_model=VectorStoreConfigResponse)
async def get_vector_store_config(session: AsyncSession = Depends(get_db)):
    """Get active vector store configuration."""
    try:
        result = await session.execute(
            select(VectorStoreConfig).where(VectorStoreConfig.is_active == True).limit(1)
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="No active vector store config found")

        return config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving vector store config: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve vector store config")


@router.put("/config/{config_id}", response_model=VectorStoreConfigResponse)
async def update_vector_store_config(
    config_id: str,
    config_update: VectorStoreConfigUpdate,
    session: AsyncSession = Depends(get_db),
):
    """Update vector store configuration."""
    try:
        result = await session.execute(
            select(VectorStoreConfig).where(VectorStoreConfig.id == config_id)
        )
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Vector store config not found")

        # Update fields
        update_data = config_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(config, field, value)

        await session.commit()
        await session.refresh(config)

        logger.info(f"Vector store config updated: {config_id}")
        return config

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating vector store config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update vector store config")


@router.post("/search", response_model=SearchResponse)
async def search_similar(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """Search for similar embeddings."""
    try:
        # Get active vector store config
        result = await session.execute(
            select(VectorStoreConfig).where(VectorStoreConfig.is_active == True).limit(1)
        )
        vector_config = result.scalar_one_or_none()

        if not vector_config:
            raise HTTPException(status_code=400, detail="Vector store not configured")

        # Initialize service
        service = VectorStoreService(vector_config, settings.openai_api_key)

        # Start timing
        start_time = time.time()

        # Perform search
        results = await service.search_similar(
            session=session,
            query_text=query,
            limit=limit,
        )

        query_time_ms = (time.time() - start_time) * 1000

        # Convert results to response format
        embedding_responses = [
            EmbeddingResponse(
                id=r["id"],
                content_chunk=r["content_chunk"],
                metadata_source_file_id=r["metadata_source_file_id"],
                metadata_timestamp=r["metadata_timestamp"],
                metadata_embedding_model=r["metadata_embedding_model"],
                similarity_score=r["similarity_score"],
            )
            for r in results
        ]

        return SearchResponse(
            results=embedding_responses,
            query_time_ms=query_time_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching embeddings: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/embeddings", response_model=list[EmbeddingResponse])
async def get_embeddings(
    upload_id: str = Query(...),
    limit: int = Query(50, ge=1, le=1000),
    session: AsyncSession = Depends(get_db),
):
    """Get embeddings for a document."""
    try:
        result = await session.execute(
            select(Embeddings)
            .where(Embeddings.upload_metadata_id == upload_id)
            .limit(limit)
        )
        embeddings = result.scalars().all()

        return [
            EmbeddingResponse(
                id=e.id,
                content_chunk=e.content_chunk,
                metadata_source_file_id=e.metadata_source_file_id,
                metadata_timestamp=e.metadata_timestamp,
                metadata_embedding_model=e.metadata_embedding_model,
                similarity_score=None,
            )
            for e in embeddings
        ]

    except Exception as e:
        logger.error(f"Error retrieving embeddings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve embeddings")


# --- Raw Vector Storage Endpoints (Story 1) ---


@router.post("/v1/vectors", response_model=RawVectorResponse, status_code=status.HTTP_201_CREATED)
async def store_vector(
    payload: RawVectorCreate,
    session: AsyncSession = Depends(get_db),
):
    """
    Store raw vector with metadata and provenance.

    - Returns 201 on success
    - Returns 400 if provenance is invalid
    - Returns 409 if file_id already exists (use PUT for idempotent update)
    """
    try:
        service = RawVectorService(session)
        result = await service.store(payload)
        return result
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error storing vector: {e}")
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail=f"Vector already exists for file {payload.file_id}. Use PUT endpoint for idempotent updates."
            )
        raise HTTPException(status_code=500, detail="Failed to store vector")


@router.get("/v1/vectors/{file_id}", response_model=RawVectorResponse)
async def get_vector(
    file_id: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve vector by file_id.

    Must return within 200ms for up to 10k records.
    """
    try:
        from uuid import UUID
        file_uuid = UUID(file_id)
        service = RawVectorService(session)
        result = await service.get_by_file_id(file_uuid)
        return result
    except ValueError as e:
        logger.warning(f"Vector not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving vector: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve vector")


@router.put("/v1/vectors/{file_id}", response_model=RawVectorResponse)
async def upsert_vector(
    file_id: str,
    payload: RawVectorCreate,
    session: AsyncSession = Depends(get_db),
):
    """
    Idempotent upsert: update if exists, insert if not.

    Explicit request to overwrite on duplicate.
    """
    try:
        from uuid import UUID
        # Ensure file_id in payload matches URL
        file_uuid = UUID(file_id)
        if payload.file_id != file_uuid:
            raise HTTPException(
                status_code=400,
                detail="file_id in payload must match URL parameter"
            )

        service = RawVectorService(session)
        result = await service.upsert(payload)
        return result
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error upserting vector: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert vector")


@router.post("/v1/vectors/batch", response_model=list[RawVectorResponse], status_code=status.HTTP_201_CREATED)
async def batch_store_vectors(
    payloads: list[RawVectorCreate],
    session: AsyncSession = Depends(get_db),
):
    """
    Batch insert vectors with error handling.

    Returns list of successfully stored vectors. Failed items are logged.
    """
    try:
        service = RawVectorService(session)
        results = []
        failed = []

        for payload in payloads:
            try:
                result = await service.store(payload)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to store vector for file {payload.file_id}: {e}")
                failed.append({
                    "file_id": str(payload.file_id),
                    "error": str(e)
                })

        logger.info(f"Batch store: {len(results)} successful, {len(failed)} failed")
        if failed:
            logger.warning(f"Failed records: {failed}")

        return results

    except Exception as e:
        logger.error(f"Error in batch store: {e}")
        raise HTTPException(status_code=500, detail="Failed to batch store vectors")


# --- Vector Search Endpoints (Story 4) ---


@router.post("/v1/search", response_model=VectorSearchResult)
async def vector_search(
    query: VectorSearchQuery,
    session: AsyncSession = Depends(get_db),
):
    """
    Perform semantic vector search with optional filtering.

    - Accepts either text query (server-side embedding) or pre-computed embedding
    - Supports metadata filters: date_range, document_type
    - Pagination with limit and offset
    - Returns results ranked by similarity score

    Returns:
        - 200 OK with search results
        - 400 Bad Request for invalid input
        - 502 Bad Gateway if embedding generation fails
    """
    try:
        # Validate input
        if not query.query and not query.embedding:
            raise ValueError("Either query or embedding must be provided")

        if query.query and query.embedding:
            raise ValueError("Provide either query OR embedding, not both")

        service = SearchService(session)

        # Perform search
        results = await service.search(
            query=query.query,
            embedding=query.embedding,
            filters=query.filters,
            limit=query.limit,
            offset=query.offset,
        )

        return VectorSearchResult(
            results=[
                {
                    "file_id": r["file_id"],
                    "similarity_score": r["similarity_score"],
                    "snippet": None,  # Could extract text preview if stored
                    "metadata": r["metadata"],
                    "explainability": r["explainability"],
                }
                for r in results["results"]
            ],
            total_count=results["total_count"],
            processing_time_ms=results["processing_time_ms"],
        )

    except ValueError as e:
        logger.warning(f"Search validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Search failed: {e}")
        if "embedding" in str(e).lower():
            raise HTTPException(status_code=502, detail="Failed to generate embedding")
        raise HTTPException(status_code=500, detail="Search failed")
