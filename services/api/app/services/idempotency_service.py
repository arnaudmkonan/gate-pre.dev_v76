import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.upload_idempotency import UploadIdempotencyKey
from app.models.raw_file import RawFile

logger = logging.getLogger(__name__)


class IdempotencyService:
    """Service for managing idempotency keys to prevent duplicate uploads."""

    @staticmethod
    async def check_idempotency_key(
        session: AsyncSession,
        idempotency_key: str,
    ) -> Optional[dict]:
        """
        Check if idempotency key exists and is not expired.

        Args:
            session: Database session
            idempotency_key: The idempotency key to check

        Returns:
            Dictionary with file_id, job_id if found and valid, None otherwise
        """
        try:
            query = select(UploadIdempotencyKey).where(
                UploadIdempotencyKey.idempotency_key == idempotency_key,
                UploadIdempotencyKey.expires_at > datetime.now(timezone.utc),
            )

            result = await session.execute(query)
            key_record = result.scalars().first()

            if key_record:
                logger.info(f"Idempotency key found: {idempotency_key}")
                return {
                    "file_id": key_record.file_id,
                    "job_id": key_record.job_id,
                }

            return None

        except Exception as e:
            logger.error(f"Error checking idempotency key: {e}")
            raise

    @staticmethod
    async def store_idempotency_key(
        session: AsyncSession,
        idempotency_key: str,
        file_id: UUID,
        job_id: UUID,
        ttl_hours: int = 24,
    ) -> UploadIdempotencyKey:
        """
        Store idempotency key for future reference.

        Args:
            session: Database session
            idempotency_key: The idempotency key
            file_id: ID of the uploaded raw file
            job_id: ID of the ingestion job
            ttl_hours: Time-to-live in hours (default 24)

        Returns:
            Created UploadIdempotencyKey record
        """
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

            key_record = UploadIdempotencyKey(
                idempotency_key=idempotency_key,
                file_id=file_id,
                job_id=job_id,
                expires_at=expires_at,
            )

            session.add(key_record)
            await session.flush()

            logger.info(f"Idempotency key stored: {idempotency_key}, expires at {expires_at}")

            return key_record

        except Exception as e:
            logger.error(f"Error storing idempotency key: {e}")
            raise

    @staticmethod
    async def cleanup_expired_keys(session: AsyncSession) -> int:
        """
        Clean up expired idempotency keys.

        Args:
            session: Database session

        Returns:
            Number of keys deleted
        """
        try:
            from sqlalchemy import delete

            query = delete(UploadIdempotencyKey).where(
                UploadIdempotencyKey.expires_at <= datetime.now(timezone.utc)
            )

            result = await session.execute(query)
            await session.commit()

            logger.info(f"Deleted {result.rowcount} expired idempotency keys")

            return result.rowcount

        except Exception as e:
            logger.error(f"Error cleaning up expired keys: {e}")
            raise
