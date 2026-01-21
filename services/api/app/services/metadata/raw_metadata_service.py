"""Service for managing raw file metadata and deduplication."""
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.raw_metadata import RawMetadata
from app.models.upload_event import UploadEvent, UploadEventType

logger = logging.getLogger(__name__)


class RawMetadataService:
    """Service for saving, retrieving, and managing raw file metadata with deduplication."""

    @staticmethod
    async def save_raw_metadata(
        session: AsyncSession,
        filename: str,
        file_size: int,
        checksum: str,
        storage_location: str,
        uploader_id: Optional[str] = None,
        file_type: Optional[str] = None,
    ) -> tuple[RawMetadata, UploadEvent, bool]:
        """
        Save raw file metadata to the database with idempotency via checksum.

        Args:
            session: Database session
            filename: Name of the file
            file_size: Size in bytes
            checksum: SHA-256 checksum of file
            storage_location: Path in Supabase Storage
            uploader_id: ID of user who uploaded
            file_type: File type/extension

        Returns:
            Tuple of (RawMetadata, UploadEvent, is_duplicate)

        Raises:
            ValueError: If required fields are missing
        """
        # Validate required fields
        if not filename:
            raise ValueError("filename is required")
        if not storage_location:
            raise ValueError("storage_location is required")
        if not checksum:
            raise ValueError("checksum is required")

        try:
            # Check for existing metadata by checksum (deduplication)
            existing = await RawMetadataService.get_by_checksum(session, checksum)

            if existing:
                # Record duplicate upload event
                logger.info(f"Duplicate detected: checksum={checksum}, linking to existing metadata {existing.id}")
                upload_event = UploadEvent(
                    raw_metadata_id=existing.id,
                    upload_timestamp=datetime.utcnow(),
                    event_type=UploadEventType.DUPLICATE,
                    user_id=uploader_id,
                )
                session.add(upload_event)
                await session.commit()
                logger.info(f"Upload event recorded: {upload_event.id}, type=duplicate")
                return existing, upload_event, True

            # Create new metadata record
            raw_metadata = RawMetadata(
                filename=filename,
                file_size=file_size,
                checksum=checksum,
                storage_location=storage_location,
                uploader_id=uploader_id,
                file_type=file_type,
            )
            session.add(raw_metadata)
            await session.flush()  # Get the ID without full commit
            logger.info(f"Raw metadata created: {raw_metadata.id}, checksum={checksum}")

            # Record new upload event
            upload_event = UploadEvent(
                raw_metadata_id=raw_metadata.id,
                upload_timestamp=datetime.utcnow(),
                event_type=UploadEventType.NEW,
                user_id=uploader_id,
            )
            session.add(upload_event)
            await session.commit()
            logger.info(f"Upload event recorded: {upload_event.id}, type=new")

            return raw_metadata, upload_event, False

        except Exception as e:
            await session.rollback()
            logger.error(f"Error saving raw metadata: {e}")
            raise

    @staticmethod
    async def get_by_record_id(
        session: AsyncSession,
        record_id: UUID,
    ) -> Optional[RawMetadata]:
        """
        Get raw metadata by record ID.

        Args:
            session: Database session
            record_id: UUID of the metadata record

        Returns:
            RawMetadata if found, None otherwise
        """
        try:
            query = select(RawMetadata).where(RawMetadata.id == record_id)
            result = await session.execute(query)
            metadata = result.scalars().first()

            if metadata:
                logger.info(f"Raw metadata found: {record_id}")
            else:
                logger.info(f"Raw metadata not found: {record_id}")

            return metadata

        except Exception as e:
            logger.error(f"Error retrieving raw metadata by ID: {e}")
            raise

    @staticmethod
    async def get_by_checksum(
        session: AsyncSession,
        checksum: str,
    ) -> Optional[RawMetadata]:
        """
        Get raw metadata by checksum (for deduplication checks).

        Args:
            session: Database session
            checksum: SHA-256 checksum

        Returns:
            RawMetadata if found, None otherwise
        """
        try:
            query = select(RawMetadata).where(RawMetadata.checksum == checksum)
            result = await session.execute(query)
            metadata = result.scalars().first()

            if metadata:
                logger.info(f"Raw metadata found by checksum: {checksum}")
            else:
                logger.debug(f"Raw metadata not found by checksum: {checksum}")

            return metadata

        except Exception as e:
            logger.error(f"Error retrieving raw metadata by checksum: {e}")
            raise

    @staticmethod
    async def check_duplicate_by_checksum(
        session: AsyncSession,
        checksum: str,
    ) -> Optional[RawMetadata]:
        """
        Check if a file with this checksum already exists (deduplication check).

        Args:
            session: Database session
            checksum: SHA-256 checksum to check

        Returns:
            Existing RawMetadata if found, None if not a duplicate
        """
        return await RawMetadataService.get_by_checksum(session, checksum)

    @staticmethod
    async def get_upload_events(
        session: AsyncSession,
        raw_metadata_id: UUID,
    ) -> list[UploadEvent]:
        """
        Get all upload events for a raw metadata record.

        Args:
            session: Database session
            raw_metadata_id: ID of the raw metadata record

        Returns:
            List of UploadEvent records
        """
        try:
            query = select(UploadEvent).where(
                UploadEvent.raw_metadata_id == raw_metadata_id
            ).order_by(UploadEvent.upload_timestamp.desc())
            result = await session.execute(query)
            events = result.scalars().all()

            logger.info(f"Retrieved {len(events)} upload events for metadata {raw_metadata_id}")
            return events

        except Exception as e:
            logger.error(f"Error retrieving upload events: {e}")
            raise
