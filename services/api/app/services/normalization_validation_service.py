"""Service for validating normalized silver records against normalization rules."""

import logging
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NormalizationValidation, SilverRecord
from app.schemas.silver import SilverRecordInput
from app.services.validation_engine import ValidationEngine, ValidationResult

logger = logging.getLogger(__name__)


class NormalizationValidationService:
    """Service for validating normalized records before silver upsert."""

    @staticmethod
    async def validate_batch(
        session: AsyncSession,
        batch_id: UUID,
        records: List[SilverRecordInput],
    ) -> Dict[str, Any]:
        """
        Validate a batch of records for normalization compliance.

        Validates each record against the normalization schema and rules,
        records validation results to database, and returns summary stats.

        Args:
            session: Async database session
            batch_id: ID of the batch being validated
            records: List of records to validate

        Returns:
            Dict with validation summary:
            {
                "batch_id": UUID,
                "total_records": int,
                "passed_count": int,
                "failed_count": int,
                "warning_count": int,
                "validation_time_ms": int,
                "records": [ValidationResult],
            }
        """
        import time
        start_time = time.time()

        passed_count = 0
        failed_count = 0
        warning_count = 0
        validation_results = []

        try:
            for idx, record in enumerate(records):
                # Convert record to dict for validation
                record_dict = record.model_dump()
                record_dict["record_index"] = idx

                # Validate against schema
                validation_result = ValidationEngine.validate_record(record_dict)

                # Store validation result
                validation_status = "pass" if validation_result.is_valid else "fail"
                if validation_result.warnings:
                    validation_status = "warning" if validation_status == "pass" else "fail"

                # Prepare field errors
                field_errors = {}
                for error in validation_result.errors:
                    if error.field not in field_errors:
                        field_errors[error.field] = []
                    field_errors[error.field].append(error.message)

                # Persist validation record
                validation_record = NormalizationValidation(
                    batch_id=batch_id,
                    record_id=record.record_id,
                    document_id=record.document_id,
                    validation_status=validation_status,
                    field_errors=field_errors if field_errors else None,
                    validation_details=validation_result.to_dict(),
                    error_message=(
                        "; ".join([e.message for e in validation_result.errors])
                        if validation_result.errors
                        else None
                    ),
                )

                session.add(validation_record)

                # Update counters
                if validation_result.is_valid:
                    passed_count += 1
                else:
                    failed_count += 1

                if validation_result.warnings:
                    warning_count += 1

                validation_results.append({
                    "record_index": idx,
                    "document_id": record.document_id,
                    "record_id": record.record_id,
                    "status": validation_status,
                    "errors": [e.to_dict() for e in validation_result.errors],
                    "warnings": [w.to_dict() for w in validation_result.warnings],
                })

            await session.commit()
            logger.info(
                f"Batch validation complete: batch_id={batch_id}, "
                f"passed={passed_count}, failed={failed_count}, warnings={warning_count}"
            )

        except Exception as e:
            logger.error(f"Error during batch validation: {e}")
            await session.rollback()
            raise

        processing_time_ms = int((time.time() - start_time) * 1000)

        return {
            "batch_id": batch_id,
            "total_records": len(records),
            "passed_count": passed_count,
            "failed_count": failed_count,
            "warning_count": warning_count,
            "validation_time_ms": processing_time_ms,
            "records": validation_results,
        }

    @staticmethod
    async def validate_record(
        session: AsyncSession,
        batch_id: UUID,
        record: SilverRecordInput,
    ) -> Dict[str, Any]:
        """
        Validate a single record for normalization compliance.

        Args:
            session: Async database session
            batch_id: ID of the batch
            record: Record to validate

        Returns:
            Dict with validation result for the record
        """
        record_dict = record.model_dump()
        validation_result = ValidationEngine.validate_record(record_dict)

        validation_status = "pass" if validation_result.is_valid else "fail"
        if validation_result.warnings:
            validation_status = "warning" if validation_status == "pass" else "fail"

        # Prepare field errors
        field_errors = {}
        for error in validation_result.errors:
            if error.field not in field_errors:
                field_errors[error.field] = []
            field_errors[error.field].append(error.message)

        # Persist validation record
        validation_record = NormalizationValidation(
            batch_id=batch_id,
            record_id=record.record_id,
            document_id=record.document_id,
            validation_status=validation_status,
            field_errors=field_errors if field_errors else None,
            validation_details=validation_result.to_dict(),
            error_message=(
                "; ".join([e.message for e in validation_result.errors])
                if validation_result.errors
                else None
            ),
        )

        session.add(validation_record)
        await session.commit()

        return {
            "document_id": record.document_id,
            "record_id": record.record_id,
            "status": validation_status,
            "errors": [e.to_dict() for e in validation_result.errors],
            "warnings": [w.to_dict() for w in validation_result.warnings],
            "validation_details": validation_result.to_dict(),
        }

    @staticmethod
    async def get_batch_validation_report(
        session: AsyncSession,
        batch_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get validation report for a batch.

        Args:
            session: Async database session
            batch_id: ID of the batch

        Returns:
            Dict with batch validation summary and per-record results
        """
        stmt = select(NormalizationValidation).where(
            NormalizationValidation.batch_id == batch_id
        )
        result = await session.execute(stmt)
        validation_records = result.scalars().all()

        if not validation_records:
            return {
                "batch_id": batch_id,
                "total_records": 0,
                "passed_count": 0,
                "failed_count": 0,
                "warning_count": 0,
                "records": [],
            }

        passed_count = sum(1 for r in validation_records if r.validation_status == "pass")
        failed_count = sum(1 for r in validation_records if r.validation_status == "fail")
        warning_count = sum(1 for r in validation_records if r.validation_status == "warning")

        return {
            "batch_id": batch_id,
            "total_records": len(validation_records),
            "passed_count": passed_count,
            "failed_count": failed_count,
            "warning_count": warning_count,
            "records": [
                {
                    "record_id": r.record_id,
                    "document_id": r.document_id,
                    "status": r.validation_status,
                    "errors": r.field_errors or {},
                    "validation_details": r.validation_details,
                    "error_message": r.error_message,
                }
                for r in validation_records
            ],
        }

    @staticmethod
    async def get_failed_validations(
        session: AsyncSession,
        batch_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get failed validation records for a batch.

        Args:
            session: Async database session
            batch_id: ID of the batch
            limit: Max records to return
            offset: Offset for pagination

        Returns:
            Tuple of (records, total_count)
        """
        stmt = select(NormalizationValidation).where(
            NormalizationValidation.batch_id == batch_id,
            NormalizationValidation.validation_status.in_(["fail", "warning"]),
        )

        # Get total count
        count_result = await session.execute(select(NormalizationValidation).where(
            NormalizationValidation.batch_id == batch_id,
            NormalizationValidation.validation_status.in_(["fail", "warning"]),
        ))
        total = len(count_result.scalars().all())

        # Get paginated results
        stmt = stmt.order_by(NormalizationValidation.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)

        result = await session.execute(stmt)
        records = result.scalars().all()

        return (
            [
                {
                    "record_id": r.record_id,
                    "document_id": r.document_id,
                    "status": r.validation_status,
                    "errors": r.field_errors or {},
                    "error_message": r.error_message,
                    "created_at": r.created_at,
                }
                for r in records
            ],
            total,
        )
