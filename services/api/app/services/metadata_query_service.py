import logging
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.models.document_metadata import DocumentMetadata

logger = logging.getLogger(__name__)


class MetadataQueryService:
    """Service for querying document metadata with filtering and pagination."""

    @staticmethod
    async def query_by_job_id(
        session: AsyncSession,
        job_id: UUID,
    ) -> Optional[DocumentMetadata]:
        """
        Query metadata by job ID.

        Args:
            session: Database session
            job_id: Job ID to search for

        Returns:
            DocumentMetadata if found, None otherwise
        """
        try:
            query = select(DocumentMetadata).where(DocumentMetadata.job_id == job_id)
            result = await session.execute(query)
            metadata = result.scalars().first()

            if not metadata:
                logger.info(f"No metadata found for job_id: {job_id}")
                return None

            logger.info(f"Metadata found for job_id: {job_id}")
            return metadata

        except Exception as e:
            logger.error(f"Error querying metadata by job_id: {e}")
            raise

    @staticmethod
    async def query_by_document_id(
        session: AsyncSession,
        document_id: UUID,
    ) -> Optional[DocumentMetadata]:
        """
        Query metadata by document ID.

        Args:
            session: Database session
            document_id: Document ID to search for

        Returns:
            DocumentMetadata if found, None otherwise
        """
        try:
            query = select(DocumentMetadata).where(DocumentMetadata.id == document_id)
            result = await session.execute(query)
            metadata = result.scalars().first()

            if not metadata:
                logger.info(f"No metadata found for document_id: {document_id}")
                return None

            logger.info(f"Metadata found for document_id: {document_id}")
            return metadata

        except Exception as e:
            logger.error(f"Error querying metadata by document_id: {e}")
            raise

    @staticmethod
    async def list_with_filters(
        session: AsyncSession,
        customer_id: Optional[str] = None,
        file_type: Optional[str] = None,
        ingestion_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[list[DocumentMetadata], int]:
        """
        List metadata with filtering and pagination.

        Args:
            session: Database session
            customer_id: Filter by customer ID
            file_type: Filter by file type
            ingestion_status: Filter by ingestion status
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Tuple of (metadata_list, total_count)
        """
        try:
            query = select(DocumentMetadata)

            # Apply filters
            if customer_id:
                query = query.where(DocumentMetadata.customer_id == customer_id)
            if file_type:
                query = query.where(DocumentMetadata.file_type == file_type)
            if ingestion_status:
                query = query.where(DocumentMetadata.ingestion_status == ingestion_status)

            # Get total count
            count_query = select(func.count()).select_from(DocumentMetadata)
            if customer_id:
                count_query = count_query.where(DocumentMetadata.customer_id == customer_id)
            if file_type:
                count_query = count_query.where(DocumentMetadata.file_type == file_type)
            if ingestion_status:
                count_query = count_query.where(DocumentMetadata.ingestion_status == ingestion_status)

            count_result = await session.execute(count_query)
            total_count = count_result.scalar() or 0

            # Apply pagination
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size)
            query = query.order_by(DocumentMetadata.created_at.desc())

            # Execute query
            result = await session.execute(query)
            metadata_list = result.scalars().all()

            logger.info(
                f"Queried metadata: customer_id={customer_id}, file_type={file_type}, "
                f"status={ingestion_status}, page={page}, page_size={page_size}, total={total_count}"
            )

            return metadata_list, total_count

        except Exception as e:
            logger.error(f"Error listing metadata with filters: {e}")
            raise

    @staticmethod
    async def is_metadata_available(
        session: AsyncSession,
        job_id: UUID,
    ) -> bool:
        """
        Check if metadata is available for a job.

        Args:
            session: Database session
            job_id: Job ID to check

        Returns:
            True if metadata exists, False otherwise
        """
        try:
            query = select(DocumentMetadata).where(DocumentMetadata.job_id == job_id)
            result = await session.execute(query)
            metadata = result.scalars().first()

            return metadata is not None

        except Exception as e:
            logger.error(f"Error checking metadata availability: {e}")
            raise
