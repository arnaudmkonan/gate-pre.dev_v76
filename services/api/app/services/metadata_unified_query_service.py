"""Unified metadata query service for Story 5."""
import logging
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, func

from app.models.raw_file import RawFile
from app.models.document_metadata import DocumentMetadata
from app.models.silver_metadata import SilverMetadata
from app.models.vector_embedding import VectorEmbedding

logger = logging.getLogger(__name__)


class MetadataUnifiedQueryService:
    """Service for querying unified metadata across all tables (Story 5)."""

    @staticmethod
    async def query_by_filters(
        session: AsyncSession,
        uploader_id: Optional[str] = None,
        date_range: Optional[Tuple] = None,
        file_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        entity: Optional[str] = None,
        text_search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
    ) -> Tuple[List[dict], int]:
        """
        Query metadata with multiple filters and pagination.

        Args:
            session: Database session
            uploader_id: Filter by uploader
            date_range: Tuple of (start_date, end_date)
            file_type: Filter by file type
            tags: Filter by tags (array)
            entity: Filter by entity
            text_search: Full-text search on title/summary
            page: Page number (1-indexed)
            page_size: Items per page
            sort_by: Sort field (created_at, title, etc.)

        Returns:
            Tuple of (results, total_count)
        """
        try:
            # Build base query joining multiple tables
            query = select(
                RawFile.id,
                RawFile.filename,
                RawFile.file_type,
                RawFile.file_size,
                RawFile.uploader_id,
                RawFile.created_at.label("file_created_at"),
                DocumentMetadata.id.label("dm_id"),
                DocumentMetadata.title,
                DocumentMetadata.author,
                DocumentMetadata.page_count,
                DocumentMetadata.summary,
                DocumentMetadata.extraction_status,
                DocumentMetadata.error_reason,
                SilverMetadata.id.label("sm_id"),
                SilverMetadata.status.label("silver_status"),
                SilverMetadata.normalized_tags,
                VectorEmbedding.id.label("vector_id"),
                VectorEmbedding.vector_status,
            ).outerjoin(
                DocumentMetadata, RawFile.id == DocumentMetadata.file_id
            ).outerjoin(
                SilverMetadata, RawFile.id == SilverMetadata.file_id
            ).outerjoin(
                VectorEmbedding, RawFile.id == VectorEmbedding.file_id
            )

            # Apply filters
            if uploader_id:
                query = query.where(RawFile.uploader_id == uploader_id)

            if date_range and len(date_range) >= 2:
                start_date, end_date = date_range[0], date_range[1]
                query = query.where(
                    and_(
                        RawFile.created_at >= start_date,
                        RawFile.created_at <= end_date,
                    )
                )

            if file_type:
                query = query.where(RawFile.file_type == file_type)

            if text_search:
                search_pattern = f"%{text_search}%"
                query = query.where(
                    or_(
                        DocumentMetadata.title.ilike(search_pattern),
                        DocumentMetadata.summary.ilike(search_pattern),
                    )
                )

            # Get total count before pagination
            count_query = select(func.count(RawFile.id.distinct())).select_from(
                select(RawFile).outerjoin(
                    DocumentMetadata, RawFile.id == DocumentMetadata.file_id
                ).outerjoin(
                    SilverMetadata, RawFile.id == SilverMetadata.file_id
                ).outerjoin(
                    VectorEmbedding, RawFile.id == VectorEmbedding.file_id
                ).subquery()
            )

            count_result = await session.execute(count_query)
            total_count = count_result.scalar() or 0

            # Apply sorting
            if sort_by == "created_at":
                query = query.order_by(RawFile.created_at.desc())
            elif sort_by == "title":
                query = query.order_by(DocumentMetadata.title.asc())
            elif sort_by == "file_type":
                query = query.order_by(RawFile.file_type.asc())
            else:
                query = query.order_by(RawFile.created_at.desc())

            # Apply pagination
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size).distinct()

            result = await session.execute(query)
            rows = result.fetchall()

            # Format results
            results = []
            for row in rows:
                results.append({
                    "file_id": str(row.id),
                    "filename": row.filename,
                    "file_type": row.file_type,
                    "file_size": row.file_size,
                    "uploader_id": row.uploader_id,
                    "title": row.title,
                    "author": row.author,
                    "page_count": row.page_count,
                    "summary": row.summary,
                    "document_status": row.extraction_status,
                    "silver_status": row.silver_status,
                    "vector_status": row.vector_status,
                    "normalized_tags": row.normalized_tags,
                    "error_reason": row.error_reason,
                    "created_at": row.file_created_at.isoformat() if row.file_created_at else None,
                })

            logger.info(f"Query returned {len(results)} results from {total_count} total")
            return results, total_count

        except Exception as e:
            logger.error(f"Error querying unified metadata: {e}")
            raise

    @staticmethod
    async def query_by_uploader_and_status(
        session: AsyncSession,
        uploader_id: str,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        """
        Quick query by uploader and optional status.

        Returns results within 300ms SLA.
        """
        try:
            query = select(RawFile).where(RawFile.uploader_id == uploader_id)

            if status:
                query = query.where(DocumentMetadata.extraction_status == status)

            query = query.limit(limit).order_by(RawFile.created_at.desc())

            result = await session.execute(query)
            files = result.scalars().all()

            return [
                {
                    "file_id": str(f.id),
                    "filename": f.filename,
                    "file_type": f.file_type,
                    "created_at": f.created_at.isoformat(),
                }
                for f in files
            ]

        except Exception as e:
            logger.error(f"Error querying by uploader: {e}")
            return []
