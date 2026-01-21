"""
Error repository for database operations on errors.
Async SQLAlchemy methods for error queries and management.
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.errors_raw import ErrorsRaw, ErrorType

logger = logging.getLogger(__name__)


class ErrorRepository:
    """Repository for error records."""

    @staticmethod
    async def create_error(
        session: AsyncSession,
        file_id: UUID,
        agent_id: str,
        error_type: str,
        stack_trace: Optional[str],
        processing_step: str,
        error_classification: str = ErrorType.TRANSIENT,
        max_retries: int = 3,
    ) -> ErrorsRaw:
        """Create error record."""
        try:
            error = ErrorsRaw(
                file_id=file_id,
                agent_id=agent_id,
                error_type=error_type,
                stack_trace=stack_trace,
                processing_step=processing_step,
                error_classification=error_classification,
                retry_count=0,
                max_retries=max_retries,
                error_timestamp=datetime.utcnow(),
            )
            session.add(error)
            await session.commit()
            logger.info(f"Created error record: file {file_id}, type {error_type}")
            return error
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to create error record: {e}")
            raise

    @staticmethod
    async def get_error_by_id(
        session: AsyncSession,
        error_id: UUID,
    ) -> Optional[ErrorsRaw]:
        """Get error by ID."""
        try:
            query = select(ErrorsRaw).where(ErrorsRaw.id == error_id)
            result = await session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get error {error_id}: {e}")
            raise

    @staticmethod
    async def list_errors(
        session: AsyncSession,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[ErrorsRaw], int]:
        """List all errors with pagination."""
        try:
            # Count total
            count_query = select(ErrorsRaw)
            count_result = await session.execute(count_query)
            total = len(count_result.all())

            # Paginate
            offset = (page - 1) * page_size
            query = (
                select(ErrorsRaw)
                .order_by(ErrorsRaw.error_timestamp.desc())
                .offset(offset)
                .limit(page_size)
            )
            result = await session.execute(query)
            return result.scalars().all(), total
        except Exception as e:
            logger.error(f"Failed to list errors: {e}")
            raise

    @staticmethod
    async def search_errors(
        session: AsyncSession,
        file_id: Optional[UUID] = None,
        agent_id: Optional[str] = None,
        error_type: Optional[str] = None,
        error_classification: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[ErrorsRaw], int]:
        """Search errors by multiple filters."""
        try:
            conditions = []

            if file_id:
                conditions.append(ErrorsRaw.file_id == file_id)
            if agent_id:
                conditions.append(ErrorsRaw.agent_id == agent_id)
            if error_type:
                conditions.append(ErrorsRaw.error_type == error_type)
            if error_classification:
                conditions.append(ErrorsRaw.error_classification == error_classification)

            # Count total
            count_query = select(ErrorsRaw)
            if conditions:
                count_query = count_query.where(and_(*conditions))
            count_result = await session.execute(count_query)
            total = len(count_result.all())

            # Paginate
            offset = (page - 1) * page_size
            query = select(ErrorsRaw).order_by(ErrorsRaw.error_timestamp.desc())
            if conditions:
                query = query.where(and_(*conditions))
            query = query.offset(offset).limit(page_size)

            result = await session.execute(query)
            return result.scalars().all(), total
        except Exception as e:
            logger.error(f"Failed to search errors: {e}")
            raise

    @staticmethod
    async def increment_retry_count(
        session: AsyncSession,
        error_id: UUID,
    ) -> Optional[ErrorsRaw]:
        """Increment retry count for error."""
        try:
            error = await ErrorRepository.get_error_by_id(session, error_id)
            if not error:
                return None

            error.retry_count += 1
            error.last_attempt_ts = datetime.utcnow()

            await session.commit()
            return error
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to increment retry count: {e}")
            raise

    @staticmethod
    async def get_retryable_errors(
        session: AsyncSession,
        limit: int = 100,
    ) -> List[ErrorsRaw]:
        """Get errors that can still be retried."""
        try:
            query = select(ErrorsRaw).where(
                and_(
                    ErrorsRaw.retry_count < ErrorsRaw.max_retries,
                    ErrorsRaw.error_classification == ErrorType.TRANSIENT,
                )
            )
            query = query.order_by(ErrorsRaw.error_timestamp.asc()).limit(limit)
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get retryable errors: {e}")
            raise

    @staticmethod
    async def get_permanent_errors(
        session: AsyncSession,
        limit: int = 100,
    ) -> List[ErrorsRaw]:
        """Get permanent errors (no more retries)."""
        try:
            query = select(ErrorsRaw).where(
                ErrorsRaw.error_classification == ErrorType.PERMANENT,
            )
            query = query.order_by(ErrorsRaw.error_timestamp.asc()).limit(limit)
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get permanent errors: {e}")
            raise
