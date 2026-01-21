"""Service for managing silver (normalized) records."""

import hashlib
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.silver_record import SilverRecord
from app.schemas.silver import (
    SilverRecordInput,
    SilverRecordBatch,
    SilverUpsertResult,
    FailedRecord,
)

logger = logging.getLogger(__name__)


class SilverService:
    """Service for silver record operations."""

    @staticmethod
    def _hash_content(content: dict) -> str:
        """Generate SHA256 hash of content for deduplication."""
        import json
        content_str = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(content_str.encode()).hexdigest()

    @staticmethod
    async def upsert_batch(
        session: AsyncSession,
        batch: SilverRecordBatch,
    ) -> SilverUpsertResult:
        """
        Upsert a batch of silver records with deduplication.

        Performs idempotent upsert: records with same canonical_id or
        (batch_id, raw_record_hash) update existing rows; new records are inserted.
        All operations within a single transaction for atomicity.

        Args:
            session: Async database session
            batch: Batch of records to upsert

        Returns:
            SilverUpsertResult with counts of inserted/updated/failed records

        Raises:
            SQLAlchemyError: On database errors (returned in failed_records)
        """
        start_time = time.time()
        batch_id = batch.batch_id or uuid.uuid4()
        inserted_count = 0
        updated_count = 0
        failed_records: List[FailedRecord] = []

        try:
            # Process each record
            for idx, record_input in enumerate(batch.records):
                try:
                    # Validate required fields
                    if not record_input.source_file_id:
                        raise ValueError("source_file_id is required")
                    if not record_input.file_type:
                        raise ValueError("file_type is required")

                    # Generate canonical ID if not provided
                    canonical_id = record_input.canonical_id or f"{record_input.document_id}#{record_input.record_id}"

                    # Generate content hash for deduplication
                    raw_record_hash = SilverService._hash_content(
                        record_input.normalized_payload or {}
                    )

                    # Look for existing record by canonical_id or (batch_id, hash)
                    existing_stmt = select(SilverRecord).where(
                        (SilverRecord.canonical_id == canonical_id)
                        | (
                            and_(
                                SilverRecord.batch_id == batch_id,
                                SilverRecord.raw_record_hash == raw_record_hash,
                            )
                        )
                    )
                    result = await session.execute(existing_stmt)
                    existing_record = result.scalar_one_or_none()

                    if existing_record:
                        # Update existing record
                        existing_record.title = record_input.title or existing_record.title
                        existing_record.author = record_input.author or existing_record.author
                        existing_record.language = record_input.language or existing_record.language
                        existing_record.content = record_input.content or existing_record.content
                        existing_record.extraction_date = (
                            record_input.extraction_date or existing_record.extraction_date
                        )
                        existing_record.document_date = (
                            record_input.document_date or existing_record.document_date
                        )
                        existing_record.record_metadata = (
                            record_input.record_metadata or existing_record.record_metadata
                        )
                        existing_record.raw_content = (
                            record_input.normalized_payload or existing_record.raw_content
                        )
                        existing_record.size_bytes = record_input.size_bytes
                        existing_record.file_type = record_input.file_type
                        existing_record.batch_id = batch_id
                        existing_record.updated_at = datetime.utcnow()

                        await session.flush()
                        updated_count += 1
                        logger.debug(f"Updated silver record: {canonical_id}")
                    else:
                        # Insert new record
                        new_record = SilverRecord(
                            file_id=record_input.source_file_id,
                            canonical_id=canonical_id,
                            batch_id=batch_id,
                            raw_record_hash=raw_record_hash,
                            title=record_input.title,
                            author=record_input.author,
                            language=record_input.language,
                            content=record_input.content,
                            extraction_date=record_input.extraction_date,
                            document_date=record_input.document_date,
                            file_type=record_input.file_type,
                            size_bytes=record_input.size_bytes,
                            record_metadata=record_input.record_metadata,
                            raw_content=record_input.normalized_payload,
                            processing_status="pending",
                        )
                        session.add(new_record)
                        await session.flush()
                        inserted_count += 1
                        logger.debug(f"Inserted silver record: {canonical_id}")

                except ValueError as e:
                    # Validation error
                    failed_records.append(
                        FailedRecord(
                            record_index=idx,
                            document_id=record_input.document_id,
                            record_id=record_input.record_id,
                            error_message=str(e),
                            error_type="validation_error",
                            field_errors={"value": str(e)},
                        )
                    )
                    logger.warning(f"Validation failed for record {idx}: {e}")
                    # Raise to trigger batch-level rollback for ALL-OR-NOTHING semantics
                    raise

                except (IntegrityError, SQLAlchemyError) as e:
                    # Database error
                    failed_records.append(
                        FailedRecord(
                            record_index=idx,
                            document_id=record_input.document_id,
                            record_id=record_input.record_id,
                            error_message=str(e),
                            error_type="database_error",
                        )
                    )
                    logger.error(f"Database error for record {idx}: {e}")
                    # Raise to trigger batch-level rollback for ALL-OR-NOTHING semantics
                    raise

            # Commit all changes only if ALL records succeeded
            await session.commit()

        except Exception as e:
            logger.error(f"Fatal error during batch upsert: {e}")
            await session.rollback()
            raise

        processing_time_ms = int((time.time() - start_time) * 1000)

        result = SilverUpsertResult(
            batch_id=batch_id,
            total_records=len(batch.records),
            inserted_count=inserted_count,
            updated_count=updated_count,
            failed_count=len(failed_records),
            processing_time_ms=processing_time_ms,
            failed_records=failed_records,
        )

        logger.info(
            f"Batch upsert complete: batch_id={batch_id}, inserted={inserted_count}, "
            f"updated={updated_count}, failed={len(failed_records)}, time_ms={processing_time_ms}"
        )

        return result

    @staticmethod
    async def get_record(
        session: AsyncSession,
        record_id: uuid.UUID,
    ) -> Optional[SilverRecord]:
        """Get a silver record by ID."""
        stmt = select(SilverRecord).where(SilverRecord.id == record_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_records_by_batch(
        session: AsyncSession,
        batch_id: uuid.UUID,
        limit: int = 1000,
        offset: int = 0,
    ) -> Tuple[List[SilverRecord], int]:
        """Get all silver records in a batch with pagination."""
        # Get total count
        count_stmt = select(SilverRecord).where(SilverRecord.batch_id == batch_id)
        count_result = await session.execute(count_stmt)
        total = len(count_result.scalars().all())

        # Get paginated results
        stmt = (
            select(SilverRecord)
            .where(SilverRecord.batch_id == batch_id)
            .order_by(SilverRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        records = result.scalars().all()

        return records, total
